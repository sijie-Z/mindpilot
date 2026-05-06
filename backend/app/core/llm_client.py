"""
Async LLM client wrapper for ZhipuAI API.
All calls run in thread pool to avoid blocking the event loop.
Uses tenacity retry + circuit breaker for resilience.
"""
import asyncio
import json
import threading
from collections.abc import AsyncGenerator
from typing import Any

from zhipuai import ZhipuAI

from app.config import settings
from app.core.logger import get_logger
from app.core.retry import llm_breaker, llm_retry

logger = get_logger(__name__)


class AsyncLLMClient:
    """Thread-safe async wrapper around synchronous ZhipuAI client."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.ZHIPU_API_KEY
        self._model = settings.LLM_MODEL
        self._clients: dict[int, ZhipuAI] = {}
        self._lock = threading.Lock()

    def _get_client(self) -> ZhipuAI:
        """Get or create a thread-local ZhipuAI client instance."""
        thread_id = threading.get_ident()
        if thread_id not in self._clients:
            with self._lock:
                if thread_id not in self._clients:
                    self._clients[thread_id] = ZhipuAI(api_key=self._api_key)
        return self._clients[thread_id]

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Non-streaming chat completion with retry and circuit breaker."""
        if not llm_breaker.is_open:
            return await self._chat_with_retry(messages, model, temperature, max_tokens)
        raise RuntimeError("LLM circuit breaker is open, service unavailable")

    async def _chat_with_retry(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Non-streaming chat with tenacity retry."""
        client = self._get_client()
        model = model or self._model

        @llm_retry(max_attempts=3)
        def _call():
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(None, _call)
            llm_breaker._on_success()
            return response.choices[0].message.content
        except Exception as e:
            llm_breaker._on_failure()
            logger.error("LLM chat failed", model=model, error=str(e))
            raise

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion."""
        if not llm_breaker.is_open:
            client = self._get_client()
            model = model or self._model

            loop = asyncio.get_running_loop()
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        model=model, messages=messages, temperature=temperature, stream=True,
                    ),
                )
                llm_breaker._on_success()
                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                        await asyncio.sleep(0)
            except Exception as e:
                llm_breaker._on_failure()
                logger.error("LLM stream failed", model=model, error=str(e))
                raise
        else:
            raise RuntimeError("LLM circuit breaker is open")

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Chat completion that returns parsed JSON."""
        text = await self.chat(messages=messages, model=model, temperature=temperature)
        return self._parse_json(text)

    async def embed(self, texts: list[str], model: str = "embedding-3") -> list[list[float]]:
        """Generate embeddings with retry."""
        client = self._get_client()

        @llm_retry(max_attempts=3)
        def _call():
            return client.embeddings.create(model=model, input=texts)

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(None, _call)
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error("Embedding failed", model=model, count=len(texts), error=str(e))
            raise

    async def embed_single(self, text: str, model: str = "embedding-3") -> list[float]:
        """Embed a single text."""
        results = await self.embed([text], model=model)
        return results[0]

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Extract JSON from LLM response text."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start:end + 1])
            raise

    async def close(self):
        """Cleanup client instances."""
        self._clients.clear()


# Global async client instance
llm_client = AsyncLLMClient()
