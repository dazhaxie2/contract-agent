"""Replay local contract review regression cases against the plan builder.

This command is intentionally deterministic: it validates that anonymized
samples still produce executable plans without calling an LLM.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.v1.agents import _build_agent_plan  # noqa: E402
from app.schemas.agent import AgentPlanRequest  # noqa: E402


def _load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            cases.append(json.loads(text))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON on line {line_no}: {exc}") from exc
    return cases


def _case_request(case: dict) -> AgentPlanRequest:
    input_payload = case.get("input") if isinstance(case.get("input"), dict) else case
    return AgentPlanRequest(
        query=str(input_payload.get("query") or case.get("query") or ""),
        session_id=uuid.UUID(str(input_payload.get("session_id") or "00000000-0000-0000-0000-000000000001")),
        tenant_id=str(input_payload.get("tenant_id") or case.get("tenant_id") or "default"),
        task_type=str(input_payload.get("task_type") or case.get("task_type") or "contract_review"),
        context=dict(input_payload.get("context") or case.get("context") or {}),
        filters=dict(input_payload.get("filters") or case.get("filters") or {}),
    )


def _validate_case(case: dict) -> tuple[bool, str]:
    request = _case_request(case)
    if not request.query:
        return False, "missing query"

    plan = _build_agent_plan(request)
    step_ids = [item["step_id"] for item in plan["steps"]]
    expected = case.get("expected_step_ids") or ["extract_clauses", "retrieve_legal_basis", "review_risks"]
    missing = [step_id for step_id in expected if step_id not in step_ids]
    if missing:
        return False, f"missing steps: {', '.join(missing)}"
    if case.get("requires_confirmation", True) != plan["requires_confirmation"]:
        return False, "requires_confirmation mismatch"
    return True, f"{len(step_ids)} steps"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        default=str(ROOT / "tests" / "fixtures" / "contract_review_samples.jsonl"),
        help="JSONL regression sample file",
    )
    parser.add_argument("--max-cases", type=int, default=0, help="limit replay count")
    args = parser.parse_args()

    path = Path(args.cases)
    cases = _load_cases(path)
    if args.max_cases:
        cases = cases[: args.max_cases]

    failures: list[str] = []
    for idx, case in enumerate(cases, start=1):
        ok, detail = _validate_case(case)
        case_id = case.get("case_id") or f"case-{idx}"
        status = "PASS" if ok else "FAIL"
        print(f"{status} {case_id}: {detail}")
        if not ok:
            failures.append(str(case_id))

    print(f"Replayed {len(cases)} cases, failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
