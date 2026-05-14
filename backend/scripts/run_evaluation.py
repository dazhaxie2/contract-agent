"""CLI script to run the evaluation test suite.

Usage:
    python -m scripts.run_evaluation [--category CATEGORY] [--tags TAG1,TAG2] [--tenant-id TENANT]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_evaluation_suite import run_evaluation_suite


async def main():
    parser = argparse.ArgumentParser(description="Run evaluation test suite")
    parser.add_argument("--category", default=None, help="Filter by test category")
    parser.add_argument("--tags", default=None, help="Comma-separated tags to filter")
    parser.add_argument("--tenant-id", default="default", help="Tenant ID for scoped evaluation")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    tags = args.tags.split(",") if args.tags else None

    print(f"Running evaluation suite (category={args.category}, tags={tags})...")
    report = await run_evaluation_suite(
        tenant_id=args.tenant_id,
        category=args.category,
        tags=tags,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport saved to {args.output}")

    if report.get("pass_rate", 0) < 0.7:
        print(f"\nWARNING: Pass rate {report['pass_rate']} is below 0.7 threshold")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
