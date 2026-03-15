"""POST /ingest — document upload + embedding pipeline."""

import asyncio
import json
import tempfile
import uuid
from pathlib import Path

import asyncpg
from docling.document_converter import DocumentConverter
from fastapi import APIRouter, Depends, UploadFile
from loguru import logger

from app.dependencies import get_db_pool, get_embedder
from app.embedder import Embedder

router = APIRouter()


def _parse_with_docling(tmp_path: str):
    """CPU-bound: parse document to markdown + DoclingDocument."""
    converter = DocumentConverter()
    result = converter.convert(tmp_path)
    return result.document.export_to_markdown(), result.document


def _chunk_document(parsed_doc, title: str, source: str):
    """CPU-bound: chunk DoclingDocument with HybridChunker."""
    from docling.chunking import HybridChunker

    chunker = HybridChunker(max_tokens=512, merge_peers=True)
    raw_chunks = list(chunker.chunk(dl_doc=parsed_doc))
    chunks = []
    for i, chunk in enumerate(raw_chunks):
        text = chunker.contextualize(chunk=chunk)
        if text.strip():
            chunks.append(
                {
                    "content": text.strip(),
                    "index": i,
                    "token_count": len(text.split()),
                    "metadata": {"title": title, "source": source},
                }
            )
    return chunks


@router.post("/ingest")
async def ingest(
    file: UploadFile,
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    embedder: Embedder = Depends(get_embedder),
):
    filename = file.filename or "upload"
    suffix = Path(filename).suffix or ".pdf"
    logger.info("Ingest request filename={}", filename)

    # 1. Save upload to tempfile
    data = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    # 2 & 3. CPU-bound: parse + chunk in thread pool
    markdown_content, parsed_doc = await asyncio.to_thread(
        _parse_with_docling, tmp_path
    )
    title = Path(filename).stem
    chunks = await asyncio.to_thread(_chunk_document, parsed_doc, title, filename)

    logger.info("Parsed {} chunks from {}", len(chunks), filename)

    # 4. Embed all chunk texts (pure async I/O)
    texts = [c["content"] for c in chunks]
    embeddings = await embedder.embed_chunks(texts)

    # 5. Persist in a single transaction
    doc_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO documents (id, title, source, content, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                doc_id,
                title,
                filename,
                markdown_content,
                json.dumps({"filename": filename}),
            )
            for chunk, embedding in zip(chunks, embeddings):
                await conn.execute(
                    """
                    INSERT INTO chunks
                        (document_id, content, embedding, chunk_index, token_count, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                    """,
                    doc_id,
                    chunk["content"],
                    embedding,
                    chunk["index"],
                    chunk["token_count"],
                    json.dumps(chunk["metadata"]),
                )

    logger.info("Ingested document_id={} chunks={}", doc_id, len(chunks))
    return {"document_id": str(doc_id), "chunks_created": len(chunks)}
