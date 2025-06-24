import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from routes import router
from models import get_db, get_metadata_db, sync_books


def create_app():
    # Sync books before starting the app
    db = next(get_db())
    metadata_db = next(get_metadata_db())
    sync_books(db, metadata_db)

    app = FastAPI(title="KOReader Sync Server")

    app.add_middleware(
        CORSMiddleware,             # noqa
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
