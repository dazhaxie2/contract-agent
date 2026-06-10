"""Live runtime metrics for ``model_deployments``.

The static columns on ``model_deployments`` (``current_qps``,
``avg_latency_ms``, ``p99_latency_ms``, ``cpu_usage``, ``memory_usage``,
``ready_replicas``) are only written at create / stop time. To show the
operator something fresher than the stale snapshot, this module pulls
live numbers from Prometheus (QPS / latency / container resources) and
the Kubernetes API (``.status.readyReplicas``) just before serialising
the response.

Both external calls are wrapped in ``try`` / ``except`` and fall back to
``None`` when the dependency is unreachable or unconfigured. Callers
should treat a missing key as "no live data, use the DB column".
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings
from app.models.model_config import ModelDeployment

logger = logging.getLogger(__name__)


# PromQL templates. ``{label}`` is substituted with the configured
# deployment label (default ``deployment``); ``{name}`` with the
# deployment_name; ``{pod_re}`` with the regex matching a deployment's
# pods (``<name>-.*``).
_QPS_PROMQL = 'sum(rate(http_requests_total{{{label}="{name}"}}[1m]))'
_P99_PROMQL = (
    'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket'
    '{{{label}="{name}"}}[5m])) by (le)) * 1000'
)
_AVG_LATENCY_PROMQL = (
    'sum(rate(http_request_duration_seconds_sum{{{label}="{name}"}}[5m]))'
    ' / sum(rate(http_request_duration_seconds_count{{{label}="{name}"}}[5m]))'
    ' * 1000'
)
# Container metrics are joined via the pod-name regex — this is the
# default cAdvisor + kube-state-metrics layout. CPU result is a
# percentage of one core (0.5 core → 50). Memory uses the K8s declared
# limit so it shows as 0-100% utilisation; queries return empty when
# kube-state-metrics is missing → degrades to None.
_CPU_USAGE_PROMQL = (
    'sum(rate(container_cpu_usage_seconds_total{{pod=~"{pod_re}",'
    'container!="POD",image!=""}}[1m])) * 100'
)
_MEM_USAGE_PROMQL = (
    'sum(container_memory_working_set_bytes{{pod=~"{pod_re}",'
    'container!="POD",image!=""}})'
    ' / sum(kube_pod_container_resource_limits'
    '{{pod=~"{pod_re}",resource="memory"}}) * 100'
)


@dataclass
class DeploymentLiveMetrics:
    """Live runtime view of one deployment. Any field may be ``None``."""

    current_qps: float | None = None
    avg_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    cpu_usage: float | None = None
    memory_usage: float | None = None
    ready_replicas: int | None = None

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "current_qps": self.current_qps,
            "avg_latency_ms": self.avg_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "ready_replicas": self.ready_replicas,
        }


async def query_prometheus(promql: str) -> float | None:
    """Run an instant query against Prometheus. Returns ``None`` on any failure.

    Returning ``None`` (not raising) is the contract: callers use it as
    the "no live data" signal so a Prometheus outage cannot take down
    ``list_deployments``.
    """
    cfg = settings.prometheus
    if not cfg.query_url:
        return None
    url = cfg.query_url.rstrip("/") + "/api/v1/query"
    try:
        async with httpx.AsyncClient(timeout=cfg.query_timeout_seconds) as client:
            resp = await client.get(url, params={"query": promql})
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001 — wide on purpose; never propagate
        logger.debug("prometheus query failed: %s — %s", promql, exc)
        return None

    if payload.get("status") != "success":
        return None
    result = (payload.get("data") or {}).get("result") or []
    if not result:
        return None
    # Instant query returns ``[[ts, "value"], ...]`` per series. Take the
    # first series — our PromQL templates aggregate down to a single
    # scalar.
    value = result[0].get("value")
    if not value or len(value) < 2:
        return None
    try:
        scalar = float(value[1])
    except (TypeError, ValueError):
        return None
    # Prometheus reports NaN as the literal string "NaN" — guard.
    if scalar != scalar:  # NaN check
        return None
    return scalar


async def fetch_k8s_deployment_status(name: str) -> dict[str, Any] | None:
    """Fetch ``.status`` for one Deployment. ``None`` on failure / unconfigured."""
    cfg = settings.kubernetes
    if not cfg.api_url or not name:
        return None
    url = (
        f"{cfg.api_url.rstrip('/')}/apis/apps/v1/namespaces/"
        f"{cfg.namespace}/deployments/{name}"
    )
    headers: dict[str, str] = {"Accept": "application/json"}
    if cfg.bearer_token:
        headers["Authorization"] = f"Bearer {cfg.bearer_token}"
    try:
        async with httpx.AsyncClient(
            timeout=cfg.timeout_seconds, verify=cfg.verify_ssl
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("k8s deployment status failed: %s — %s", name, exc)
        return None
    status = payload.get("status")
    return status if isinstance(status, dict) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


async def _live_metrics_for(deployment: ModelDeployment) -> DeploymentLiveMetrics:
    """Pull all six metrics for one deployment in parallel."""
    label = settings.prometheus.deployment_label
    name = deployment.deployment_name or ""
    pod_re = f"{name}-.*"

    qps_q = _QPS_PROMQL.format(label=label, name=name)
    p99_q = _P99_PROMQL.format(label=label, name=name)
    avg_q = _AVG_LATENCY_PROMQL.format(label=label, name=name)
    cpu_q = _CPU_USAGE_PROMQL.format(pod_re=pod_re)
    mem_q = _MEM_USAGE_PROMQL.format(pod_re=pod_re)

    qps, p99, avg_lat, cpu, mem, k8s_status = await asyncio.gather(
        query_prometheus(qps_q),
        query_prometheus(p99_q),
        query_prometheus(avg_q),
        query_prometheus(cpu_q),
        query_prometheus(mem_q),
        fetch_k8s_deployment_status(name),
        return_exceptions=False,
    )

    ready: int | None = None
    if k8s_status is not None:
        raw_ready = k8s_status.get("readyReplicas")
        if isinstance(raw_ready, int):
            ready = raw_ready
        elif raw_ready is not None:
            try:
                ready = int(raw_ready)
            except (TypeError, ValueError):
                ready = None

    return DeploymentLiveMetrics(
        current_qps=_round(qps, 4),
        avg_latency_ms=_round(avg_lat),
        p99_latency_ms=_round(p99),
        cpu_usage=_round(cpu),
        memory_usage=_round(mem),
        ready_replicas=ready,
    )


async def fetch_deployment_live_metrics(
    rows: Iterable[ModelDeployment],
) -> dict[uuid.UUID, DeploymentLiveMetrics]:
    """Batch-fetch live metrics for a list of deployments.

    Returns a mapping ``{deployment.id: DeploymentLiveMetrics}``. Both
    Prometheus and K8s are entirely optional: a totally unreachable
    setup yields a map of all-``None`` metrics, which the response
    serialiser treats as "use the DB column / fall back".
    """
    rows_list = [row for row in rows if row is not None]
    if not rows_list:
        return {}

    # No external integrations configured → skip the network entirely.
    if not settings.prometheus.query_url and not settings.kubernetes.api_url:
        return {row.id: DeploymentLiveMetrics() for row in rows_list}

    results = await asyncio.gather(
        *(_live_metrics_for(row) for row in rows_list),
        return_exceptions=True,
    )
    out: dict[uuid.UUID, DeploymentLiveMetrics] = {}
    for row, result in zip(rows_list, results):
        if isinstance(result, BaseException):
            logger.debug("live metrics gather failed for %s: %s", row.id, result)
            out[row.id] = DeploymentLiveMetrics()
        else:
            out[row.id] = result
    return out
