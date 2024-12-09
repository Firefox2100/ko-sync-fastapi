import os
from sqlalchemy import Column, Integer, Float, String, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker
from pydantic import BaseModel
from typing import Optional


__all__ = [
    'User',
    'Document',
    'UserCreate',
    'DocumentProgress',
    'get_db',
    'get_user',
]


Base = declarative_base()
DATA_PATH = os.getenv("DATA_PATH", "./data")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    documents = relationship("Document", back_populates="owner")


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

    owner = relationship("User", back_populates="documents")


class UserCreate(BaseModel):
    username: str
    password: str

class DocumentProgress(BaseModel):
    document: str
    percentage: Optional[float] = None
    progress: Optional[str] = None
    device: Optional[str] = None
    device_id: Optional[str] = None


def init_models():
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH, exist_ok=True)

    db_url = f'sqlite:///{DATA_PATH}/app.db'

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    local_session_class = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    return local_session_class


LocalSession = init_models()


def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()


def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

