"""Test the evaluation infrastructure: test set loading, runner, and API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.test_evaluation_suite import load_test_cases


def test_load_test_cases():
    cases = load_test_cases()
    assert len(cases) >= 10, f"Expected at least 10 test cases, got {len(cases)}"
    required_fields = {"id", "category", "query", "expected_intent", "expected_agent", "expected_tools", "ground_truth"}
    for case in cases:
        missing = required_fields - set(case.keys())
        assert not missing, f"Test case {case.get('id', '?')} missing fields: {missing}"


def test_test_set_categories():
    cases = load_test_cases()
    categories = {c["category"] for c in cases}
    expected_categories = {"contract_review", "legal_search", "comparison", "drafting", "calculation", "retrieval", "validation", "compliance", "multi_step"}
    overlap = categories & expected_categories
    assert len(overlap) >= 5, f"Expected diverse categories, got: {categories}"


def test_test_set_difficulty_distribution():
    cases = load_test_cases()
    difficulties = {c.get("difficulty", "unknown") for c in cases}
    assert len(difficulties) >= 2, f"Expected mixed difficulty levels, got: {difficulties}"


@pytest.mark.asyncio
async def test_evaluation_api_endpoints(app_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    metrics_resp = await app_client.get("/api/v1/evaluation/metrics", headers=auth_headers)
    assert metrics_resp.status_code == 200, metrics_resp.text
    data = metrics_resp.json()
    if "data" in data:
        data = data["data"]
    assert "total_scored" in data
    assert "avg_relevance" in data
    assert "avg_factuality" in data


@pytest.mark.asyncio
async def test_evaluation_batch_endpoint(app_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    batch_resp = await app_client.post(
        "/api/v1/evaluation/batch",
        params={"limit": 5},
        headers=auth_headers,
    )
    assert batch_resp.status_code == 200, batch_resp.text
    data = batch_resp.json()
    if "data" in data:
        data = data["data"]
    assert "scored" in data
    assert "errors" in data
    assert "total" in data
