"""POST /chat — streaming RAG response via Datastar SSE."""

import html
import json
import uuid

import asyncpg
import datastar_py.consts as ds_consts
from datastar_py.fastapi import DatastarResponse, ServerSentEventGenerator as SSE
from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import get_chat_model, get_db_pool, get_graph, get_session_id

router = APIRouter()


class ChatRequest(BaseModel):
    # Datastar @post sends ALL signals as JSON body — ignore extras like `loading`.
    model_config = ConfigDict(extra="ignore")

    message: str
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


@router.post("/chat")
async def chat(
    request: ChatRequest,
    graph=Depends(get_graph),
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    session_id: uuid.UUID = Depends(get_session_id),
    model: str = Depends(get_chat_model),
):
    logger.info("Chat request thread_id={} message={!r}", request.thread_id, request.message[:100])

    await db_pool.execute(
        "INSERT INTO chat_messages (session_id, sender_type, content) VALUES ($1, $2, $3::jsonb)",
        session_id,
        "student",
        json.dumps({"message": request.message}),
    )

    msg_id = uuid.uuid4().hex[:12]
    safe_msg = html.escape(request.message)

    async def generate():
        # 1. Clear message input
        yield SSE.patch_signals({"message": ""})

        # 2. Append user msg + empty assistant placeholder to #chat.
        #    selector="#chat" + APPEND mode targets the div by CSS selector and
        #    appends the fragment as children (mode is a protocol field, not HTML attr).
        yield SSE.patch_elements(
            f"<div class='msg user'>{safe_msg}</div>"
            f"<div id='msg-{msg_id}' class='msg assistant'></div>",
            selector="#chat",
            mode=ds_consts.ElementPatchMode.APPEND,
        )

        # 3. Stream LLM chunks — morph the assistant div as content grows
        chunks = []
        full = ""
        config = {"configurable": {"thread_id": request.thread_id}}
        try:
            async for event in graph.astream(
                {"messages": [{"role": "user", "content": request.message}]},
                config,
                stream_mode="messages",
            ):
                msg, metadata = event
                if msg.content and metadata.get("langgraph_node") == "chatbot":
                    chunks.append(msg.content)
                    full += msg.content
                    yield SSE.patch_elements(
                        f"<div id='msg-{msg_id}' class='msg assistant'>{html.escape(full)}</div>"
                    )
        except Exception:
            logger.exception("Error streaming response for thread_id={}", request.thread_id)
            raise

        logger.debug("Stream completed for thread_id={}", request.thread_id)

        # 4. Reset loading signal (hides typing indicator)
        yield SSE.patch_signals({"loading": False})

        # 5. Persist assembled assistant reply
        full_text = "".join(chunks)
        await db_pool.execute(
            "INSERT INTO chat_messages (session_id, sender_type, content, metadata)"
            " VALUES ($1, $2, $3::jsonb, $4::jsonb)",
            session_id,
            "assistant",
            json.dumps({"message": full_text}),
            json.dumps({"model": model, "thread_id": request.thread_id}),
        )

    return DatastarResponse(generate())
