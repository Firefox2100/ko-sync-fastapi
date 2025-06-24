import time
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from models import User, UserCreate, Document, DocumentProgress, MetadataBook, Book, get_db, get_metadata_db,\
    get_user


ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"


router = APIRouter(
    dependencies=[Depends(get_db), Depends(get_metadata_db)],
    responses={404: {"description": "Not found"}},
)


def authorize_request(request: Request, db: Session):
    username = request.headers.get("x-auth-user")
    password = request.headers.get("x-auth-key")

    if not username or not password:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = get_user(db, username)
    if not user or user.password != password:  # Fix user key reference
        raise HTTPException(status_code=403, detail="Forbidden")

    return user


@router.post("/users/create", status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if not ALLOW_REGISTRATION:
        raise HTTPException(status_code=403, detail="Registration is disabled")

    if get_user(db, user.username):
        raise HTTPException(status_code=409, detail="Username is already registered")

    new_user = User(
        username=user.username,
        password=user.password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # Refresh to get generated `id` and other fields

    return {"username": new_user.username}


@router.get("/users/auth", status_code=200)
def authorize(request: Request, db: Session = Depends(get_db)):
    authorize_request(request, db)
    return {"authorized": "OK"}


@router.get("/syncs/progress/{document}", status_code=200)
def get_progress(document: str, request: Request, db: Session = Depends(get_db)):
    user = authorize_request(request, db)

    doc = (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.document_name == document)
        .first()
    )

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
def update_progress(position: DocumentProgress,
                    request: Request,
                    db: Session = Depends(get_db),
                    metadata_db: Session = Depends(get_metadata_db)
                    ):
    user = authorize_request(request, db)

    doc = (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.document_name == position.document)
        .first()
    )

    timestamp = int(time.time())

    if not doc:
        # Attempt to find the matching Book by hash
        book = (
            db.query(Book)
            .filter(Book.document_name == position.document)
            .first()
        )

        # Create a new document entry
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
        # Update existing document fields
        doc.progress = position.progress
        doc.percentage = position.percentage
        doc.device = position.device
        doc.device_id = position.device_id
        doc.timestamp = timestamp

    db.commit()
    db.refresh(doc)

    return {"document": doc.document_name, "timestamp": doc.timestamp}



@router.get("/admin/books", status_code=200)
def get_books(request: Request,
              db: Session = Depends(get_db),
              metadata_db: Session = Depends(get_metadata_db)
              ):
    user = authorize_request(request, db)

    documents = user.documents

    books = []

    for document in documents:
        if document.book_id:
            # Query the metadata database for book details
            metadata_book = (
                metadata_db.query(MetadataBook)
                .filter(MetadataBook.id == document.book_id)
                .first()
            )

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
def delete_book(document_id: str, request: Request, db: Session = Depends(get_db)):
    user = authorize_request(request, db)

    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(doc)
    db.commit()

    return {"document": doc.document_name}


@router.get("/healthcheck", status_code=200)
def healthcheck():
    return {"state": "OK"}
