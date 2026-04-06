"""
阿里云大模型服务 - 集成DashScope SDK
支持通义千问系列模型调用：生成、嵌入、重排
"""

import asyncio
import time
from typing import AsyncGenerator

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

try:
    import dashscope
    from dashscope import Generation, TextEmbedding
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False


class AliyunLLMService:
    """阿里云通义千问大模型服务"""

    def __init__(self):
        if HAS_DASHSCOPE:
            dashscope.api_key = settings.llm.api_key
        self._semaphore = asyncio.Semaphore(settings.llm.max_concurrent_requests)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
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
        """调用阿里云大模型生成"""
        async with self._semaphore:
            model = model or settings.llm.generation_model
            temperature = temperature if temperature is not None else settings.llm.generation_temperature
            max_tokens = max_tokens or settings.llm.generation_max_tokens
            top_p = top_p if top_p is not None else settings.llm.generation_top_p

            start_time = time.perf_counter()

            try:
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

                # 同步调用包装为异步
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: Generation.call(**params) if HAS_DASHSCOPE else self._mock_generate(params),
                )

                latency_ms = (time.perf_counter() - start_time) * 1000

                if HAS_DASHSCOPE:
                    if response.status_code != 200:
                        raise LLMCallError(f"DashScope API error: {response.code} - {response.message}")

                    result = {
                        "content": response.output.choices[0].message.content,
                        "role": "assistant",
                        "model": model,
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                            "total_tokens": response.usage.total_tokens,
                        },
                        "latency_ms": round(latency_ms, 2),
                        "finish_reason": response.output.choices[0].finish_reason,
                    }

                    # 函数调用结果
                    if hasattr(response.output.choices[0].message, "tool_calls"):
                        result["tool_calls"] = response.output.choices[0].message.tool_calls

                    return result
                else:
                    return self._mock_generate_result(params, latency_ms)

            except Exception as exc:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"LLM generation failed: {exc} | model={model} | latency={latency_ms:.0f}ms")
                raise

    async def generate_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成"""
        model = model or settings.llm.generation_model
        temperature = temperature if temperature is not None else settings.llm.generation_temperature
        max_tokens = max_tokens or settings.llm.generation_max_tokens

        async with self._semaphore:
            if HAS_DASHSCOPE:
                responses = Generation.call(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    result_format="message",
                    stream=True,
                    incremental_output=True,
                )
                for response in responses:
                    if response.status_code == 200:
                        content = response.output.choices[0].message.content
                        if content:
                            yield content
            else:
                # Mock stream
                for word in "这是一个模拟的流式输出，用于开发测试。".split():
                    yield word
                    await asyncio.sleep(0.1)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=5))
    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """文本向量化"""
        model = model or settings.llm.embedding_model

        async with self._semaphore:
            try:
                if HAS_DASHSCOPE:
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
                        raise LLMCallError(f"Embedding API error: {response.code} - {response.message}")
                    return [item["embedding"] for item in response.output["embeddings"]]
                else:
                    import random
                    return [[random.random() for _ in range(settings.llm.embedding_dimension)] for _ in texts]
            except Exception as exc:
                logger.error(f"Embedding failed: {exc} | model={model} | batch_size={len(texts)}")
                raise

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """文档重排"""
        model = model or settings.llm.reranker_model

        async with self._semaphore:
            try:
                if HAS_DASHSCOPE:
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
                        raise LLMCallError(f"Rerank API error: {response.code}")
                    return [
                        {"index": r["index"], "score": r["relevance_score"], "text": r.get("document", {}).get("text", "")}
                        for r in response.output["results"]
                    ]
                else:
                    # Mock rerank
                    import random
                    results = [{"index": i, "score": random.uniform(0.5, 1.0), "text": doc} for i, doc in enumerate(documents)]
                    results.sort(key=lambda x: x["score"], reverse=True)
                    return results[:top_k]
            except Exception as exc:
                logger.error(f"Rerank failed: {exc} | model={model}")
                raise

    async def light_generate(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
    ) -> dict:
        """轻量小模型调用 (预处理/校验/改写)"""
        return await self.generate(
            messages=messages,
            model=settings.llm.light_model,
            temperature=settings.llm.light_temperature,
            max_tokens=max_tokens or settings.llm.light_max_tokens,
        )

    @staticmethod
    def _mock_generate(params: dict) -> None:
        return None

    @staticmethod
    def _mock_generate_result(params: dict, latency_ms: float) -> dict:
        return {
            "content": "[开发模式] 这是模拟的大模型输出。请配置 DASHSCOPE_API_KEY 以启用阿里云通义千问。",
            "role": "assistant",
            "model": params.get("model", "mock"),
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "latency_ms": round(latency_ms, 2),
            "finish_reason": "stop",
        }


class LLMCallError(Exception):
    pass


# 全局单例
llm_service = AliyunLLMService()
