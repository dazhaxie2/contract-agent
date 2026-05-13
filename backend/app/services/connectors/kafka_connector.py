"""Kafka producer/consumer connector with graceful fallback."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.connectors.types import ConnectorHealth

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

    HAS_KAFKA = True
except Exception:  # pragma: no cover - optional runtime dependency failures.
    AIOKafkaConsumer = Any  # type: ignore[assignment]
    AIOKafkaProducer = Any  # type: ignore[assignment]
    HAS_KAFKA = False


KafkaHandler = Callable[[dict[str, Any]], Awaitable[None]]


class KafkaConnector:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None
        self._consumer_tasks: list[asyncio.Task] = []

    @property
    def enabled(self) -> bool:
        return bool(HAS_KAFKA and settings.kafka.bootstrap_servers)

    async def start_producer(self) -> bool:
        if not self.enabled:
            return False
        if self._producer is not None:
            return True

        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka.bootstrap_servers,
            value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda value: str(value).encode("utf-8") if value is not None else None,
            acks="all",
        )
        try:
            await producer.start()
            self._producer = producer
            return True
        except Exception as exc:
            logger.warning(f"Kafka producer start failed: {exc}")
            try:
                await producer.stop()
            except Exception:
                pass
            return False

    async def stop(self) -> None:
        while self._consumer_tasks:
            task = self._consumer_tasks.pop()
            task.cancel()
        if self._producer is not None:
            try:
                await self._producer.stop()
            finally:
                self._producer = None

    async def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> bool:
        if not await self.start_producer():
            return False
        assert self._producer is not None
        try:
            await self._producer.send_and_wait(topic, payload, key=key)
            return True
        except Exception as exc:
            logger.warning(f"Kafka publish failed topic={topic}: {exc}")
            return False

    async def start_consumer(self, topic: str, handler: KafkaHandler) -> bool:
        if not self.enabled:
            return False

        async def _consume_loop() -> None:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=settings.kafka.bootstrap_servers,
                group_id=settings.kafka.group_id,
                enable_auto_commit=True,
                auto_offset_reset=settings.kafka.auto_offset_reset,
                max_poll_records=settings.kafka.max_poll_records,
                value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            )
            try:
                await consumer.start()
                async for message in consumer:
                    try:
                        payload = message.value if isinstance(message.value, dict) else {}
                        await handler(payload)
                    except Exception as exc:
                        logger.exception(f"Kafka handler failed for topic={topic}: {exc}")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"Kafka consumer loop failed topic={topic}: {exc}")
            finally:
                try:
                    await consumer.stop()
                except Exception:
                    pass

        task = asyncio.create_task(_consume_loop(), name=f"kafka-consumer:{topic}")
        self._consumer_tasks.append(task)
        return True

    async def health(self) -> ConnectorHealth:
        started = time.perf_counter()
        ok = await self.start_producer()
        latency_ms = (time.perf_counter() - started) * 1000
        detail = f"bootstrap={settings.kafka.bootstrap_servers}" if ok else "producer unavailable"
        return ConnectorHealth(name="kafka", ok=ok, latency_ms=latency_ms, detail=detail)


kafka_connector = KafkaConnector()

