import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from routes import router
from models import sync_books, init_async_models, AsyncSessionLocal, MetadataAsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_async_models()

    async with AsyncSessionLocal() as db, MetadataAsyncSessionLocal() as metadata_db:
        await sync_books(db, metadata_db)

    yield


def create_app():
    app = FastAPI(title="KOReader Sync Server", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    # Custom Exception Handling
    @app.exception_handler(Exception)
    async def custom_exception_handler(request: Request, exc: Exception):
        logging.error(f"Exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error"},
        )

    return app


app = create_app()
