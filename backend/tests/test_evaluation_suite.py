"""Evaluation test runner: executes test cases from the evaluation test set and reports metrics."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger


TEST_SET_PATH = Path(__file__).resolve().parent / "fixtures" / "evaluation_test_set.json"


def load_test_cases() -> list[dict]:
    if not TEST_SET_PATH.exists():
        return []
    with open(TEST_SET_PATH, encoding="utf-8") as f:
        return json.load(f)


async def run_single_test(
    test_case: dict,
    tenant_id: str = "default",
) -> dict[str, Any]:
    from app.agents.orchestrator import orchestrator_agent

    query = test_case["query"]
    expected_agent = test_case.get("expected_agent", "")
    expected_tools = set(test_case.get("expected_tools", []))

    start = time.perf_counter()
    try:
        result = await orchestrator_agent.execute(
            query=query,
            context={"tenant_id": tenant_id},
        )
        latency_ms = (time.perf_counter() - start) * 1000

        actual_tools = {
            step.tool_name
            for step in result.steps
            if step.tool_name
        }

        tool_match = expected_tools.issubset(actual_tools) if expected_tools else True
        has_output = bool(result.output and len(result.output) > 20)
        agent_match = not expected_agent or any(
            expected_agent in step.tool_name or expected_agent in step.action
            for step in result.steps
        ) or expected_agent == "orchestrator"

        return {
            "test_id": test_case["id"],
            "status": "pass" if (has_output and tool_match) else "partial" if has_output else "fail",
            "latency_ms": round(latency_ms, 2),
            "tool_match": tool_match,
            "agent_match": agent_match,
            "expected_tools": sorted(expected_tools),
            "actual_tools": sorted(actual_tools),
            "output_length": len(result.output or ""),
            "steps_count": len(result.steps),
            "tokens_used": result.total_tokens,
            "error": None,
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "test_id": test_case["id"],
            "status": "error",
            "latency_ms": round(latency_ms, 2),
            "tool_match": False,
            "agent_match": False,
            "expected_tools": sorted(expected_tools),
            "actual_tools": [],
            "output_length": 0,
            "steps_count": 0,
            "tokens_used": 0,
            "error": str(exc),
        }


async def run_evaluation_suite(
    tenant_id: str = "default",
    category: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    cases = load_test_cases()
    if not cases:
        return {"error": "No test cases found", "total": 0}

    if category:
        cases = [c for c in cases if c.get("category") == category]
    if tags:
        tag_set = set(tags)
        cases = [c for c in cases if tag_set.intersection(c.get("tags", []))]

    results = []
    for case in cases:
        logger.info(f"Running test case {case['id']}: {case['query'][:60]}...")
        r = await run_single_test(case, tenant_id)
        results.append(r)

    passed = sum(1 for r in results if r["status"] == "pass")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "fail")
    errored = sum(1 for r in results if r["status"] == "error")

    return {
        "total": len(results),
        "passed": passed,
        "partial": partial,
        "failed": failed,
        "errored": errored,
        "pass_rate": round(passed / max(len(results), 1), 3),
        "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / max(len(results), 1), 2),
        "total_tokens": sum(r["tokens_used"] for r in results),
        "results": results,
    }


evaluation_runner = type("EvaluationRunner", (), {
    "load_test_cases": staticmethod(load_test_cases),
    "run_single_test": staticmethod(run_single_test),
    "run_suite": staticmethod(run_evaluation_suite),
})()
