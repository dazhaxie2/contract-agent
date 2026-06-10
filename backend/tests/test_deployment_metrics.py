"""Tests for deployment_metrics_service fallback paths.

These are pure unit tests that mock all external I/O (Prometheus, K8s API,
database). They override the autouse ``cleanup_db`` fixture from conftest.py
to avoid requiring a SQLite test database.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

os.environ.setdefault("ENVIRONMENT", "test")

from app.models.model_config import ModelDeployment
from app.services.deployment_metrics_service import (
    DeploymentLiveMetrics,
    fetch_deployment_live_metrics,
    fetch_k8s_deployment_status,
    query_prometheus,
)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db():
    yield


def _make_deployment(
    *,
    name: str = "test-deploy",
    status: str = "running",
    health_status: str = "healthy",
    replicas: int = 1,
) -> ModelDeployment:
    return ModelDeployment(
        id=uuid.uuid4(),
        model_config_id=uuid.uuid4(),
        tenant_id="default",
        deployment_name=name,
        deployment_type="cloud_api",
        endpoint_url=None,
        replicas=replicas,
        gpu_type=None,
        gpu_count=0,
        cpu_limit=None,
        memory_limit=None,
        status=status,
        health_status=health_status,
        current_qps=0.0,
        max_qps=0.0,
        avg_latency_ms=0.0,
        p99_latency_ms=0.0,
        deploy_config={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestDeploymentLiveMetrics:
    def test_as_dict(self):
        m = DeploymentLiveMetrics(
            current_qps=1.5,
            avg_latency_ms=42.0,
            p99_latency_ms=120.0,
            cpu_usage=30.0,
            memory_usage=55.0,
            ready_replicas=3,
        )
        d = m.as_dict()
        assert d["current_qps"] == 1.5
        assert d["ready_replicas"] == 3

    def test_defaults_all_none(self):
        m = DeploymentLiveMetrics()
        assert m.current_qps is None
        assert m.cpu_usage is None
        assert m.ready_replicas is None


class TestQueryPrometheus:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_url(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = ""
            result = await query_prometheus("up")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = "http://prometheus:9090"
            mock_settings.prometheus.query_timeout_seconds = 1.0
            with patch(
                "app.services.deployment_metrics_service.httpx.AsyncClient"
            ) as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                result = await query_prometheus("up")
                assert result is None

    @pytest.mark.asyncio
    async def test_returns_value_on_success(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = "http://prometheus:9090"
            mock_settings.prometheus.query_timeout_seconds = 2.0
            mock_resp = MagicMock()
            mock_resp.raise_for_status = lambda: None
            mock_resp.json.return_value = {
                "status": "success",
                "data": {
                    "result": [{"metric": {}, "value": [1700000000, "3.14"]}]
                },
            }
            with patch(
                "app.services.deployment_metrics_service.httpx.AsyncClient"
            ) as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                result = await query_prometheus("up")
                assert result == 3.14

    @pytest.mark.asyncio
    async def test_returns_none_on_nan(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = "http://prometheus:9090"
            mock_settings.prometheus.query_timeout_seconds = 2.0
            mock_resp = MagicMock()
            mock_resp.raise_for_status = lambda: None
            mock_resp.json.return_value = {
                "status": "success",
                "data": {"result": [{"metric": {}, "value": [0, "NaN"]}]},
            }
            with patch(
                "app.services.deployment_metrics_service.httpx.AsyncClient"
            ) as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                result = await query_prometheus("up")
                assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_result(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = "http://prometheus:9090"
            mock_settings.prometheus.query_timeout_seconds = 2.0
            mock_resp = MagicMock()
            mock_resp.raise_for_status = lambda: None
            mock_resp.json.return_value = {
                "status": "success",
                "data": {"result": []},
            }
            with patch(
                "app.services.deployment_metrics_service.httpx.AsyncClient"
            ) as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                result = await query_prometheus("up")
                assert result is None


class TestFetchK8sDeploymentStatus:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_url(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.kubernetes.api_url = ""
            result = await fetch_k8s_deployment_status("my-deploy")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.kubernetes.api_url = "https://k8s-api"
            mock_settings.kubernetes.namespace = "default"
            mock_settings.kubernetes.bearer_token = "tok"
            mock_settings.kubernetes.verify_ssl = False
            mock_settings.kubernetes.timeout_seconds = 1.0
            with patch(
                "app.services.deployment_metrics_service.httpx.AsyncClient"
            ) as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                result = await fetch_k8s_deployment_status("my-deploy")
                assert result is None

    @pytest.mark.asyncio
    async def test_returns_ready_replicas_on_success(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.kubernetes.api_url = "https://k8s-api"
            mock_settings.kubernetes.namespace = "contract-agent"
            mock_settings.kubernetes.bearer_token = "tok"
            mock_settings.kubernetes.verify_ssl = False
            mock_settings.kubernetes.timeout_seconds = 2.0
            mock_resp = MagicMock()
            mock_resp.raise_for_status = lambda: None
            mock_resp.json.return_value = {
                "status": {"readyReplicas": 2, "replicas": 3}
            }
            with patch(
                "app.services.deployment_metrics_service.httpx.AsyncClient"
            ) as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                result = await fetch_k8s_deployment_status("my-deploy")
                assert result == {"readyReplicas": 2, "replicas": 3}


class TestFetchDeploymentLiveMetricsFallback:
    @pytest.mark.asyncio
    async def test_no_integrations_configured_returns_all_none(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = ""
            mock_settings.kubernetes.api_url = ""
            rows = [_make_deployment()]
            result = await fetch_deployment_live_metrics(rows)
            assert len(result) == 1
            live = result[rows[0].id]
            assert live.current_qps is None
            assert live.cpu_usage is None
            assert live.ready_replicas is None

    @pytest.mark.asyncio
    async def test_prom_unreachable_k8s_unreachable_all_none(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = "http://prometheus:9090"
            mock_settings.prometheus.query_timeout_seconds = 1.0
            mock_settings.prometheus.deployment_label = "deployment"
            mock_settings.kubernetes.api_url = "https://k8s-api"
            mock_settings.kubernetes.namespace = "default"
            mock_settings.kubernetes.bearer_token = ""
            mock_settings.kubernetes.verify_ssl = False
            mock_settings.kubernetes.timeout_seconds = 1.0

            with patch(
                "app.services.deployment_metrics_service.httpx.AsyncClient"
            ) as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=ConnectionError("down"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                rows = [_make_deployment()]
                result = await fetch_deployment_live_metrics(rows)
                live = result[rows[0].id]
                assert live.current_qps is None
                assert live.p99_latency_ms is None
                assert live.cpu_usage is None
                assert live.memory_usage is None
                assert live.ready_replicas is None

    @pytest.mark.asyncio
    async def test_empty_rows_returns_empty_map(self):
        result = await fetch_deployment_live_metrics([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_exception_in_gather_produces_all_none(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = "http://prom:9090"
            mock_settings.kubernetes.api_url = "https://k8s"
            with patch(
                "app.services.deployment_metrics_service._live_metrics_for",
                new_callable=AsyncMock,
                side_effect=RuntimeError("boom"),
            ):
                rows = [_make_deployment()]
                result = await fetch_deployment_live_metrics(rows)
                live = result[rows[0].id]
                assert live.current_qps is None

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        with patch(
            "app.services.deployment_metrics_service.settings"
        ) as mock_settings:
            mock_settings.prometheus.query_url = "http://prom:9090"
            mock_settings.kubernetes.api_url = "https://k8s"

            good = _make_deployment(name="good")
            bad = _make_deployment(name="bad")

            async def _fake_live(deployment: ModelDeployment):
                if deployment.deployment_name == "bad":
                    raise RuntimeError("fail")
                return DeploymentLiveMetrics(
                    current_qps=5.0, ready_replicas=2
                )

            with patch(
                "app.services.deployment_metrics_service._live_metrics_for",
                new_callable=AsyncMock,
                side_effect=_fake_live,
            ):
                result = await fetch_deployment_live_metrics([good, bad])
                assert result[good.id].current_qps == 5.0
                assert result[good.id].ready_replicas == 2
                assert result[bad.id].current_qps is None
