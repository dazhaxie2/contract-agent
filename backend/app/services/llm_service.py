"""LLM service abstraction with DashScope and local fallback."""

from __future__ import annotations

import asyncio
import hashlib
import random
import time
from difflib import SequenceMatcher
from typing import AsyncGenerator

from loguru import logger
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

try:
    import dashscope
    from dashscope import Generation, TextEmbedding

    HAS_DASHSCOPE = True
except Exception:
    HAS_DASHSCOPE = False

try:
    from app.middleware.metrics import (
        HAS_PROMETHEUS,
        LLM_LATENCY,
        LLM_REQUEST_COUNT,
        LLM_TOKEN_COUNT,
    )
except Exception:
    HAS_PROMETHEUS = False


def _record_llm(model: str, status: str, latency_s: float, tokens_in: int = 0, tokens_out: int = 0) -> None:
    """埋点到 prometheus_client；HAS_PROMETHEUS=False 时静默 no-op。"""
    if not HAS_PROMETHEUS:
        return
    try:
        LLM_REQUEST_COUNT.labels(model=model, status=status).inc()
        LLM_LATENCY.labels(model=model).observe(max(latency_s, 0.0))
        if tokens_in:
            LLM_TOKEN_COUNT.labels(model=model, type="input").inc(tokens_in)
        if tokens_out:
            LLM_TOKEN_COUNT.labels(model=model, type="output").inc(tokens_out)
    except Exception as exc:  # pragma: no cover - 监控不应阻塞业务
        logger.debug(f"LLM metrics record failed: {exc}")


class LLMCallError(Exception):
    pass


class LLMConfigurationError(LLMCallError):
    pass


def _external_model_available() -> bool:
    return bool(HAS_DASHSCOPE and settings.llm.api_key)


def _ensure_model_available() -> None:
    if settings.llm.require_external and not _external_model_available():
        raise LLMConfigurationError("LLM provider is not configured")


def _seeded_random_vector(text: str, dim: int) -> list[float]:
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    return [rng.random() for _ in range(dim)]


def _local_fallback_content(messages: list[dict]) -> str:
    latest_user = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_user = str(msg.get("content", ""))
            break
    preview = latest_user.strip().replace("\n", " ")[:600]
    return (
        "Local fallback response (LLM_REQUIRE_EXTERNAL=false).\n"
        "This output is generated only when local fallback is explicitly enabled.\n"
        f"User input preview: {preview}"
    )


class AliyunLLMService:
    def __init__(self):
        if HAS_DASHSCOPE and settings.llm.api_key:
            dashscope.api_key = settings.llm.api_key
        self._semaphore = asyncio.Semaphore(settings.llm.max_concurrent_requests)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_not_exception_type(LLMConfigurationError),
    )
    async def generate(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        async with self._semaphore:
            _ensure_model_available()
            model = model or settings.llm.generation_model
            temperature = settings.llm.generation_temperature if temperature is None else temperature
            max_tokens = max_tokens or settings.llm.generation_max_tokens
            top_p = settings.llm.generation_top_p if top_p is None else top_p
            started = time.perf_counter()

            try:
                if _external_model_available():
                    params = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": top_p,
                        "result_format": "message",
                    }
                    if stop:
                        params["stop"] = stop
                    if tools:
                        params["tools"] = tools

                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(None, lambda: Generation.call(**params))
                    if response.status_code != 200:
                        raise LLMCallError(f"DashScope error: {response.code} {response.message}")

                    choice = response.output.choices[0]
                    latency_ms = (time.perf_counter() - started) * 1000
                    _record_llm(
                        model=model,
                        status="success",
                        latency_s=latency_ms / 1000,
                        tokens_in=int(response.usage.input_tokens or 0),
                        tokens_out=int(response.usage.output_tokens or 0),
                    )
                    payload = {
                        "content": choice.message.content,
                        "role": "assistant",
                        "model": model,
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                            "total_tokens": response.usage.total_tokens,
                        },
                        "latency_ms": round(latency_ms, 2),
                        "finish_reason": getattr(choice, "finish_reason", "stop"),
                    }
                    if hasattr(choice.message, "tool_calls"):
                        payload["tool_calls"] = choice.message.tool_calls
                    return payload

                latency_ms = (time.perf_counter() - started) * 1000
                content = _local_fallback_content(messages)
                fallback_in = sum(max(1, len(str(m.get("content", ""))) // 4) for m in messages)
                fallback_out = max(1, len(content) // 4)
                _record_llm(
                    model="local-fallback",
                    status="fallback",
                    latency_s=latency_ms / 1000,
                    tokens_in=fallback_in,
                    tokens_out=fallback_out,
                )
                return {
                    "content": content,
                    "role": "assistant",
                    "model": model or "local-fallback",
                    "usage": {
                        "input_tokens": fallback_in,
                        "output_tokens": fallback_out,
                        "total_tokens": fallback_in + fallback_out,
                    },
                    "latency_ms": round(latency_ms, 2),
                    "finish_reason": "stop",
                }
            except Exception as exc:
                latency_ms = (time.perf_counter() - started) * 1000
                _record_llm(model=model, status="error", latency_s=latency_ms / 1000)
                logger.error(f"LLM generate failed: {exc} model={model} latency_ms={latency_ms:.2f}")
                raise

    async def generate_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        model = model or settings.llm.generation_model
        temperature = settings.llm.generation_temperature if temperature is None else temperature
        max_tokens = max_tokens or settings.llm.generation_max_tokens

        async with self._semaphore:
            started = time.perf_counter()
            status = "error"
            final_usage = None
            out_chars = 0
            in_chars = sum(len(str(m.get("content", ""))) for m in messages)
            record_model = model
            try:
                _ensure_model_available()
                if _external_model_available():
                    loop = asyncio.get_event_loop()
                    responses = await loop.run_in_executor(
                        None,
                        lambda: Generation.call(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            result_format="message",
                            stream=True,
                            incremental_output=True,
                        ),
                    )
                    for response in responses:
                        if response.status_code != 200:
                            continue
                        # DashScope 在 incremental_output=True 时通常会在最后一帧带 usage
                        usage = getattr(response, "usage", None)
                        if usage is not None and getattr(usage, "total_tokens", None):
                            final_usage = usage
                        text = response.output.choices[0].message.content
                        if text:
                            out_chars += len(text)
                            yield text
                    status = "success"
                    return

                record_model = "local-fallback"
                content = _local_fallback_content(messages)
                words = content.split()
                for word in words:
                    token = word + " "
                    out_chars += len(token)
                    yield token
                    await asyncio.sleep(0.01)
                status = "fallback"
            except GeneratorExit:
                # 下游（HTTP client / SSE 连接）提前断开
                status = "canceled"
                raise
            except Exception:
                status = "error"
                raise
            finally:
                latency_s = time.perf_counter() - started
                if final_usage is not None:
                    tokens_in = int(getattr(final_usage, "input_tokens", 0) or 0)
                    tokens_out = int(getattr(final_usage, "output_tokens", 0) or 0)
                else:
                    tokens_in = max(1, in_chars // 4)
                    tokens_out = max(0, out_chars // 4)
                _record_llm(
                    model=record_model,
                    status=status,
                    latency_s=latency_s,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_not_exception_type(LLMConfigurationError),
    )
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model = model or settings.llm.embedding_model
        approx_tokens_in = sum(max(1, len(t) // 4) for t in texts)
        async with self._semaphore:
            _ensure_model_available()
            started = time.perf_counter()
            try:
                if _external_model_available():
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: TextEmbedding.call(
                            model=model,
                            input=texts,
                            dimension=settings.llm.embedding_dimension,
                        ),
                    )
                    if response.status_code != 200:
                        raise LLMCallError(f"Embedding error: {response.code} {response.message}")
                    latency_s = time.perf_counter() - started
                    usage = getattr(response, "usage", None)
                    tokens_in = int(getattr(usage, "total_tokens", 0) or approx_tokens_in)
                    _record_llm(model=model, status="success", latency_s=latency_s, tokens_in=tokens_in)
                    return [item["embedding"] for item in response.output["embeddings"]]

                latency_s = time.perf_counter() - started
                _record_llm(
                    model="local-fallback",
                    status="fallback",
                    latency_s=latency_s,
                    tokens_in=approx_tokens_in,
                )
                return [_seeded_random_vector(text, settings.llm.embedding_dimension) for text in texts]
            except Exception:
                latency_s = time.perf_counter() - started
                _record_llm(model=model, status="error", latency_s=latency_s)
                raise

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        model = model or settings.llm.reranker_model
        approx_tokens_in = max(1, len(query) // 4) + sum(max(1, len(d or "") // 4) for d in documents)
        async with self._semaphore:
            _ensure_model_available()
            started = time.perf_counter()
            try:
                if _external_model_available():
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: dashscope.TextReRank.call(
                            model=model,
                            query=query,
                            documents=documents,
                            top_n=top_k,
                            return_documents=True,
                        ),
                    )
                    if response.status_code != 200:
                        raise LLMCallError(f"Rerank error: {response.code}")
                    latency_s = time.perf_counter() - started
                    _record_llm(
                        model=model,
                        status="success",
                        latency_s=latency_s,
                        tokens_in=approx_tokens_in,
                    )
                    return [
                        {
                            "index": item["index"],
                            "score": item["relevance_score"],
                            "text": item.get("document", {}).get("text", ""),
                        }
                        for item in response.output["results"]
                    ]

                scored = []
                q = query.lower()
                for i, doc in enumerate(documents):
                    score = SequenceMatcher(None, q[:400], (doc or "").lower()[:400]).ratio()
                    scored.append({"index": i, "score": score, "text": doc})
                scored.sort(key=lambda x: x["score"], reverse=True)
                latency_s = time.perf_counter() - started
                _record_llm(
                    model="local-fallback",
                    status="fallback",
                    latency_s=latency_s,
                    tokens_in=approx_tokens_in,
                )
                return scored[:top_k]
            except Exception:
                latency_s = time.perf_counter() - started
                _record_llm(model=model, status="error", latency_s=latency_s)
                raise

    async def light_generate(self, messages: list[dict], max_tokens: int | None = None) -> dict:
        return await self.generate(
            messages=messages,
            model=settings.llm.light_model,
            temperature=settings.llm.light_temperature,
            max_tokens=max_tokens or settings.llm.light_max_tokens,
        )


llm_service = AliyunLLMService()
