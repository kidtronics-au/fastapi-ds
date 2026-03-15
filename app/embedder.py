"""Async embedding service wrapping openai.AsyncOpenAI."""

import asyncio

import openai
from openai import AsyncOpenAI

from app.config import Settings


class Embedder:
    def __init__(self, settings: Settings) -> None:
        self.model = settings.embedding_model
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
        )

    async def embed_query(self, text: str) -> list[float]:
        """Single embedding for retrieval."""
        response = await self.client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding

    async def embed_chunks(self, texts: list[str]) -> list[list[float]]:
        """Batched embeddings with exponential backoff on rate limits."""
        max_retries = 3
        delay = 1.0
        for attempt in range(max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model, input=texts
                )
                return [d.embedding for d in response.data]
            except openai.RateLimitError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(delay * (2**attempt))

    async def close(self) -> None:
        await self.client.close()
