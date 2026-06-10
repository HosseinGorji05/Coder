#!/usr/bin/env python3
"""Run Executo on a HumanEval task (AI + HumanEval tests in one loop).

Usage:
  python eval_humaneval.py
  python eval_humaneval.py HumanEval/0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.agent import run_executo
from core.humaneval import DEFAULT_DATASET, load_task


def _status(passed: bool | None) -> str:
    if passed is None:
        return "N/A"
    return "PASS" if passed else "FAIL"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Executo against a HumanEval task."
    )
    parser.add_argument(
        "task_id",
        nargs="?",
        default="HumanEval/0",
        help="HumanEval task id (default: HumanEval/0).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"Path to HumanEval.jsonl (default: {DEFAULT_DATASET}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.dataset.exists():
        print(f"Dataset not found: {args.dataset}", file=sys.stderr)
        print("Run: python download_coding_datasets.py", file=sys.stderr)
        return 2

    task = load_task(args.dataset, args.task_id)
    print(f"HumanEval task: {task['task_id']}")
    print(f"Function: {task['entry_point']}\n")

    try:
        result = run_executo(
            "",
            humaneval_task_id=args.task_id,
            humaneval_dataset=args.dataset,
        )
    except RuntimeError as exc:
        print(f"Setup error: {exc}", file=sys.stderr)
        return 2

    if not result.get("code"):
        print("Agent returned no code.", file=sys.stderr)
        return 1

    print("=" * 60)
    print(f"Overall: {_status(result.get('passed'))} after {result.get('attempts', 0)} attempt(s)")
    print(f"AI self-tests: {_status(result.get('self_test_passed'))}")
    print(f"HumanEval tests: {_status(result.get('humaneval_passed'))}")
    print("=" * 60)
    print("\n--- generated code ---\n")
    print(result.get("code", ""))
    if result.get("output"):
        print("\n--- last sandbox output ---\n")
        print(result.get("output", ""))

    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
