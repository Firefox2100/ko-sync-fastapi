import time
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from models import User, UserCreate, Document, DocumentProgress, MetadataBook, MetadataBookAuthor, Book, get_db, \
    get_metadata_db, get_user


ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"


router = APIRouter(
    dependencies=[Depends(get_db), Depends(get_metadata_db)],
    responses={404: {"description": "Not found"}},
)


async def authorize_request(request: Request, db: AsyncSession):
    username = request.headers.get("x-auth-user")
    password = request.headers.get("x-auth-key")

    if not username or not password:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = await get_user(db, username)
    if not user or user.password != password:
        raise HTTPException(status_code=403, detail="Forbidden")

    return user


@router.post("/users/create", status_code=201)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    if not ALLOW_REGISTRATION:
        raise HTTPException(status_code=403, detail="Registration is disabled")

    existing = await get_user(db, user.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username is already registered")

    new_user = User(username=user.username, password=user.password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {"username": new_user.username}


@router.get("/users/auth", status_code=200)
async def authorize(request: Request, db: AsyncSession = Depends(get_db)):
    await authorize_request(request, db)
    return {"authorized": "OK"}


@router.get("/syncs/progress/{document}", status_code=200)
async def get_progress(document: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await authorize_request(request, db)

    result = await db.execute(
        select(Document)
        .filter_by(user_id=user.id, document_name=document)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document progress not found")

    return {
        "document": doc.document_name,
        "progress": doc.progress,
        "percentage": doc.percentage,
        "device": doc.device,
        "device_id": doc.device_id,
        "timestamp": doc.timestamp,
    }


@router.put("/syncs/progress", status_code=200)
async def update_progress(position: DocumentProgress,
                          request: Request,
                          db: AsyncSession = Depends(get_db),
                          metadata_db: AsyncSession = Depends(get_metadata_db)
                          ):
    user = await authorize_request(request, db)

    result = await db.execute(
        select(Document)
        .filter_by(user_id=user.id, document_name=position.document)
    )
    doc = result.scalar_one_or_none()
    timestamp = int(time.time())

    if not doc:
        book_result = await db.execute(
            select(Book).filter_by(document_name=position.document)
        )
        book = book_result.scalar_one_or_none()

        doc = Document(
            document_name=position.document,
            progress=position.progress,
            percentage=position.percentage,
            device=position.device,
            device_id=position.device_id,
            timestamp=timestamp,
            user_id=user.id,
            book_id=book.id if book else None,
        )
        db.add(doc)
    else:
        doc.progress = position.progress
        doc.percentage = position.percentage
        doc.device = position.device
        doc.device_id = position.device_id
        doc.timestamp = timestamp

    await db.commit()
    await db.refresh(doc)

    return {"document": doc.document_name, "timestamp": doc.timestamp}



@router.get("/admin/books", status_code=200)
async def get_books(request: Request,
                    db: AsyncSession = Depends(get_db),
                    metadata_db: AsyncSession = Depends(get_metadata_db)
                    ):
    user = await authorize_request(request, db)

    # Load documents eagerly
    await db.refresh(user, ["documents"])
    books = []

    for document in user.documents:
        if document.book_id:
            metadata_result = await metadata_db.execute(
                select(MetadataBook)
                .options(joinedload(MetadataBook.authors_link).joinedload(MetadataBookAuthor.author_relation))
                .filter(MetadataBook.id == document.book_id)
            )
            metadata_book = metadata_result.unique().scalar_one_or_none()

            if metadata_book:
                books.append({
                    "id": document.book_id,
                    "document_name": document.document_name,
                    "progress": document.progress,
                    "percentage": document.percentage,
                    "device": document.device,
                    "device_id": document.device_id,
                    "timestamp": document.timestamp,
                    "metadata": {
                        "title": metadata_book.title,
                        "sort": metadata_book.sort,
                        "authors": [link.author_relation.name for link in metadata_book.authors_link]
                    }
                })

    return books


@router.delete("/admin/books/{document_id}", status_code=200)
async def delete_book(document_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await authorize_request(request, db)

    result = await db.execute(
        select(Document).filter_by(id=document_id, user_id=user.id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.delete(doc)
    await db.commit()

    return {"document": doc.document_name}


@router.get("/healthcheck", status_code=200)
async def healthcheck():
    return {"state": "OK"}
