import functools
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app import retriever
from app.config import settings
from app.database import create_pool, create_session
from app.embedder import Embedder
from app.graph import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # --- Startup ---
    logger.info("Starting up...")

    app.state.embedder = Embedder(settings)
    logger.info("Embedder initialized model={}", settings.embedding_model)

    # create_pool registers pgvector codec via init= on every connection
    app.state.db_pool = await create_pool()
    logger.info("Database connection pool created (pgvector codec registered)")

    retrieve_fn = functools.partial(retriever.retrieve, pool=app.state.db_pool)
    app.state.graph = build_graph(
        embedder=app.state.embedder, retrieve_fn=retrieve_fn
    )
    logger.info("LangGraph RAG graph initialized model={}", settings.chat_model)

    app.state.session_id = await create_session(app.state.db_pool)
    logger.info("Chat session created session_id={}", app.state.session_id)

    yield

    # --- Shutdown ---
    await app.state.embedder.close()
    logger.info("Embedder closed")
    await app.state.db_pool.close()
    logger.info("Database connection pool closed")
    logger.info("Shutting down...")
