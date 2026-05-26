"""校验评估测试集的结构与覆盖度，作为 CI 质量门禁。

把"扩充评估集"的瓶颈从"手工拼正确的 JSON"降到"法务专家只填内容"：
结构、必填字段、ID 唯一性由本脚本保证，专家只需关注 query/ground_truth 等业务内容。

用法：
    python scripts/validate_evaluation_set.py
退出码 0 表示通过，非 0 表示存在结构错误。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_PATH = BASE / "tests" / "fixtures" / "evaluation_test_set.json"
SCHEMA_PATH = BASE / "tests" / "fixtures" / "evaluation_test_set.schema.json"

_REQUIRED_FIELDS = {
    "id",
    "category",
    "query",
    "expected_intent",
    "expected_agent",
    "expected_tools",
    "expected_references",
    "ground_truth",
    "difficulty",
    "tags",
}


def validate_test_set(data_path: Path = DATA_PATH, schema_path: Path = SCHEMA_PATH) -> list[str]:
    """校验测试集，返回错误信息列表；空列表表示通过。"""
    if not data_path.exists():
        return [f"测试集文件不存在: {data_path}"]
    try:
        cases = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"测试集 JSON 解析失败: {exc}"]
    if not isinstance(cases, list):
        return ["测试集顶层必须是数组"]
    if not cases:
        return ["测试集为空"]

    errors: list[str] = []
    try:
        from jsonschema import Draft202012Validator

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(cases), key=lambda e: list(e.absolute_path)):
            loc = "/".join(str(part) for part in err.absolute_path) or "(root)"
            errors.append(f"schema[{loc}]: {err.message}")
    except ModuleNotFoundError:
        # 没装 jsonschema 时退化为最小必填校验，保证脚本仍可用
        for idx, case in enumerate(cases):
            if not isinstance(case, dict):
                errors.append(f"[{idx}] 用例不是对象")
                continue
            missing = _REQUIRED_FIELDS - set(case)
            if missing:
                errors.append(f"[{case.get('id', idx)}] 缺少字段: {sorted(missing)}")

    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    duplicates = sorted(name for name, count in Counter(ids).items() if name and count > 1)
    if duplicates:
        errors.append(f"重复的用例 ID: {duplicates}")
    return errors


def _coverage_report(cases: list[dict]) -> str:
    by_category = Counter(case.get("category", "?") for case in cases)
    by_difficulty = Counter(case.get("difficulty", "?") for case in cases)
    by_agent = Counter(case.get("expected_agent", "?") for case in cases)
    lines = [
        f"用例总数: {len(cases)}",
        "按类别: " + ", ".join(f"{k}={v}" for k, v in sorted(by_category.items())),
        "按难度: " + ", ".join(f"{k}={v}" for k, v in sorted(by_difficulty.items())),
        "按 Agent: " + ", ".join(f"{k}={v}" for k, v in sorted(by_agent.items())),
    ]
    return "\n".join(lines)


def main() -> int:
    errors = validate_test_set()
    if DATA_PATH.exists():
        try:
            cases = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            if isinstance(cases, list):
                print(_coverage_report(cases))
        except json.JSONDecodeError:
            pass

    if errors:
        print(f"\n[FAIL] 评估测试集存在 {len(errors)} 处问题：")
        for item in errors:
            print(f"  - {item}")
        return 1
    print("\n[OK] 评估测试集结构校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
