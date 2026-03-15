# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start PostgreSQL (pgvector) + Ollama
docker compose up -d

# Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the server (development)
uvicorn main:app --reload

# Run the server (production)
uvicorn main:app --host 0.0.0.0 --port 8000
```

Set `LOG_LEVEL=DEBUG` in `.env` for verbose logging.

## Environment

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | API key (also works with any OpenAI-compatible provider) |
| `OPENAI_API_BASE` | Base URL for the LLM provider (e.g. Ollama, OpenRouter) |
| `CHAT_MODEL` | Model name to use (e.g. `gpt-4o`, `llama3`) |
| `EMBEDDING_MODEL` | Embedding model name (default: `nomic-embed-text`) |
| `DATABASE_URL` | PostgreSQL DSN (`postgresql://user:pass@host:5432/db`) |

## Architecture

This is a RAG (Retrieval-Augmented Generation) chat application backed by pgvector and LangGraph.

```
app/
├── config.py        # pydantic-settings Settings (reads .env)
├── database.py      # asyncpg pool creation + pgvector codec registration + session bootstrap
├── embedder.py      # Async OpenAI embedding service (wraps AsyncOpenAI)
├── retriever.py     # pgvector cosine similarity search against document chunks
├── graph.py         # LangGraph RAG StateGraph: START → retrieve → chatbot → END
├── dependencies.py  # FastAPI Depends() providers (graph, db_pool, session_id, model)
├── lifespan.py      # asynccontextmanager startup/shutdown
├── middleware.py    # log_requests HTTP middleware
├── main.py          # FastAPI app wiring (middleware, routers)
└── routers/
    ├── chat.py      # POST /chat  — streaming LLM with RAG
    ├── ingest.py    # POST /ingest — document upload, Docling parse, embed, store
    └── ui.py        # GET /       — serves static/index.html
static/
└── index.html       # Chat UI (read at import time by ui.py)
main.py              # Two-line shim: from app.main import app
```

**Startup order (lifespan):**
1. `Embedder` initialized (async OpenAI client for embeddings).
2. `asyncpg` pool created; pgvector codec registered via `init=` on every connection.
3. `build_graph(embedder, retrieve_fn)` — constructs the LangGraph `StateGraph` with `MemorySaver` (in-process conversation history keyed by `thread_id`).
4. `create_session()` inserts a `chat_sessions` row (hardcoded `student_id` `00000000-0000-0000-0000-000000000001`, subject `"General"`) and stores the UUID in `app.state.session_id`.

**RAG graph (`graph.py`):**
- `RAGState` extends `MessagesState` with `context: list[str]` and `sources: list[str]`.
- `retrieve` node: embeds the last user message, calls `retriever.retrieve()` for top-k pgvector results, populates `context` and `sources`.
- `chatbot` node: prepends a `SystemMessage` containing retrieved context (if any), then calls `llm.ainvoke()`.

**Endpoints:**
- `POST /chat` — accepts `{ message, thread_id }`. Streams the LLM response as `text/plain` via `StreamingResponse`. Persists user message and assembled assistant reply to `chat_messages` as JSONB.
- `POST /ingest` — accepts a file upload; parses with Docling `HybridChunker`, embeds each chunk via `Embedder`, stores vectors in pgvector.
- `GET /` — serves `static/index.html`.

**Dependency injection:** Routes receive `graph`, `db_pool`, `session_id`, and `model` via `Depends()` — no direct `req.app.state.*` access in route handlers.

**Database setup** (run once, in order — app does not auto-migrate):
```bash
psql $DATABASE_URL -f scripts/ddl.sql      # chat_sessions, chat_messages tables
psql $DATABASE_URL -f scripts/rag_ddl.sql  # documents, chunks tables + match_chunks() function
```
- `retriever.py` calls `match_chunks($1, $2)` — a plpgsql stored procedure defined in `rag_ddl.sql`.
- The `chunks.embedding` column is `vector(768)`. Changing `EMBEDDING_MODEL` to one with a different output dimension requires dropping and recreating the `chunks` table.

**Ingest pipeline** (`routers/ingest.py`):
Docling parse and HybridChunker (max_tokens=512) are CPU-bound and run via `asyncio.to_thread()`. The entire doc + all chunks are inserted in a single transaction: `documents` row first, then one `chunks` row per embedding.

**LLM provider flexibility:** `OPENAI_API_BASE` lets you point at any OpenAI-compatible endpoint (Ollama, vLLM, OpenRouter, etc.). The `docker-compose.yml` spins up dual Ollama instances (GPU + ROCM) with model storage at `/home/guru/Projects/ollama/.models`.

**`ds-ref/`**: Contains `ds_snippet.py`, a standalone Datastar SSE streaming reference — not part of the app, kept for reference only.
