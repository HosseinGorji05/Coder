#!/usr/bin/env python3
"""
Run a Python unit test against a code snippet in an isolated Docker container.

Usage:
  python run_isolated_unittest.py --code-file snippet.py --test-file test_snippet.py
  python run_isolated_unittest.py --code-file snippet.py --test-file test_snippet.py --image python:3.12-slim
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.sandbox import (
    DEFAULT_IMAGE,
    DEFAULT_TIMEOUT_SECONDS,
    docker_available,
    run_unittest_files,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Launch a short-lived Docker container, run python -m unittest, "
            "and report pass/fail."
        )
    )
    parser.add_argument(
        "--code-file",
        required=True,
        type=Path,
        help="Path to the Python code snippet file under test.",
    )
    parser.add_argument(
        "--test-file",
        required=True,
        type=Path,
        help="Path to the Python unittest file.",
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help=f"Docker image to use (default: {DEFAULT_IMAGE}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Seconds before the run is killed (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    return parser.parse_args()


def validate_input_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} must be a file: {path}")


def main() -> int:
    args = parse_args()

    try:
        validate_input_file(args.code_file, "--code-file")
        validate_input_file(args.test_file, "--test-file")
    except (FileNotFoundError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    if not docker_available():
        print(
            "Docker is not installed or not available in PATH. "
            "Install Docker and try again.",
            file=sys.stderr,
        )
        return 3

    result = run_unittest_files(
        args.code_file, args.test_file, image=args.image, timeout=args.timeout
    )

    if result.output:
        print(result.output)
    print(result.summary)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
