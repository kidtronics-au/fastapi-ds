import uuid

import asyncpg
from fastapi import Request

from app.config import settings


def get_graph(req: Request):
    return req.app.state.graph


def get_db_pool(req: Request) -> asyncpg.Pool:
    return req.app.state.db_pool


def get_session_id(req: Request) -> uuid.UUID:
    return req.app.state.session_id


def get_chat_model() -> str:
    return settings.chat_model


def get_embedder(req: Request):
    return req.app.state.embedder
