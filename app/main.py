import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.lifespan import lifespan
from app.middleware import log_requests
from app.routers import chat, ingest, ui

# Configure loguru
logger.remove()
logger.add(sys.stderr, level=settings.log_level)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(log_requests)

app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(ui.router)
