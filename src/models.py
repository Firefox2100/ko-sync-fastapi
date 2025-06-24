import os
import hashlib
from sqlalchemy import Column, Integer, Float, String, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, selectinload
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from sqlalchemy.future import select
from contextlib import asynccontextmanager


__all__ = [
    'Book',
    'MetadataBook',
    'MetadataData',
    'User',
    'Document',
    'UserCreate',
    'DocumentProgress',
    'init_async_models',
    'get_db',
    'get_metadata_db',
    'get_user',
    'sync_books',
    'DATA_PATH'
]


Base = declarative_base()
MetadataBase = declarative_base()
DATA_PATH = os.getenv("DATA_PATH", "./data")


class MetadataBook(MetadataBase):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False, default="Unknown")
    sort = Column(String)
    timestamp = Column(TIMESTAMP)
    pubdate = Column(TIMESTAMP)
    series_index = Column(Float, nullable=False, default=1.0)
    author_sort = Column(String)
    isbn = Column(String, default='')
    lccn = Column(String, default='')
    path = Column(String, nullable=False, default='')
    flags = Column(Integer, nullable=False, default=1)
    uuid = Column(String)
    has_cover = Column(Boolean, default=False)
    last_modified = Column(TIMESTAMP, nullable=False)

    data = relationship("MetadataData", back_populates="book_relation", cascade="all, delete-orphan")
    authors_link = relationship("MetadataBookAuthor", back_populates="book_relation", cascade="all, delete-orphan")


class MetadataData(MetadataBase):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True)
    book = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    format = Column(String, nullable=False)
    uncompressed_size = Column(Integer, nullable=False)
    name = Column(String, nullable=False)

    book_relation = relationship("MetadataBook", back_populates="data")


class MetadataAuthor(MetadataBase):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sort = Column(String, nullable=False)
    link = Column(String, nullable=True)

    books_link = relationship("MetadataBookAuthor", back_populates="author_relation", cascade="all, delete-orphan")


class MetadataBookAuthor(MetadataBase):
    __tablename__ = "books_authors_link"

    id = Column(Integer, primary_key=True)
    book = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    author = Column(Integer, ForeignKey("authors.id"), nullable=False, index=True)

    book_relation = relationship("MetadataBook", back_populates="authors_link")
    author_relation = relationship("MetadataAuthor", back_populates="books_link")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    documents = relationship("Document", back_populates="owner")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String, nullable=False, index=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String, nullable=False, index=True)
    progress = Column(String, nullable=True)
    percentage = Column(Float, nullable=True)
    device = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    timestamp = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True, index=True)
    owner = relationship("User", back_populates="documents")
    book = relationship("Book")


class UserCreate(BaseModel):
    username: str
    password: str


class DocumentProgress(BaseModel):
    document: str
    percentage: Optional[float] = None
    progress: Optional[str] = None
    device: Optional[str] = None
    device_id: Optional[str] = None


def get_async_engine(path: str, readonly: bool = False):
    if readonly:
        return create_async_engine(
            f"sqlite+aiosqlite:///{path}?mode=ro",
            connect_args={"uri": True}  # ✅ Enable SQLite URI interpretation
        )
    else:
        return create_async_engine(
            f"sqlite+aiosqlite:///{path}",
            connect_args={"check_same_thread": False}
        )


engine = get_async_engine(f"{DATA_PATH}/app.db")
metadata_engine = get_async_engine(f"{DATA_PATH}/metadata.db", readonly=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
MetadataAsyncSessionLocal = async_sessionmaker(bind=metadata_engine, class_=AsyncSession, expire_on_commit=False)


async def init_async_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_metadata_db() -> AsyncGenerator[AsyncSession, None]:
    async with MetadataAsyncSessionLocal() as session:
        yield session


async def get_user(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).filter_by(username=username))
    return result.scalar_one_or_none()


async def sync_books(db: AsyncSession, metadata_db: AsyncSession):
    result = await metadata_db.execute(
        select(MetadataBook)
        .options(
            selectinload(MetadataBook.data),
            selectinload(MetadataBook.authors_link).selectinload(MetadataBookAuthor.author_relation)
        )
        .join(MetadataBook.data)
    )
    metadata_books = result.scalars().all()

    for metadata_book in metadata_books:
        if not metadata_book.data:
            continue

        data_name = metadata_book.title
        data_format = metadata_book.data[0].format.lower()

        author_name = metadata_book.authors_link[0].author_relation.name if metadata_book.authors_link else "Unknown"
        document_name = hashlib.md5(f'{author_name} - {data_name}.{data_format}'.encode('utf-8')).hexdigest()

        stmt = sqlite_insert(Book).values(
            id=metadata_book.id,
            document_name=document_name,
        ).on_conflict_do_update(
            index_elements=['id'],
            set_=dict(document_name=document_name),
        )

        await db.execute(stmt)

    await db.commit()
