"""Docker-isolated execution of generated code against unit tests.

The container is locked down: capped memory/CPU/PIDs, no network, and a
read-only workspace. Code and tests are passed in as strings so the agent
loop can call this directly without touching the filesystem itself.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_IMAGE = "python:3.12-slim"
DEFAULT_TIMEOUT_SECONDS = 60

# These names are a contract with the test code: generated tests must
# `from snippet import ...` so the solution module resolves inside the container.
CODE_FILENAME = "snippet.py"
TEST_FILENAME = "test_snippet.py"


@dataclass
class SandboxResult:
    passed: bool
    returncode: int
    output: str
    timed_out: bool = False

    @property
    def summary(self) -> str:
        if self.timed_out:
            return "TIMEOUT"
        return "PASS" if self.passed else "FAIL"


def run_code_with_tests(
    code: str,
    test_code: str,
    image: str = DEFAULT_IMAGE,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> SandboxResult:
    """Run `test_code` against `code` inside a short-lived Docker container."""
    with tempfile.TemporaryDirectory(prefix="executo-sandbox-") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        (tmp_dir / CODE_FILENAME).write_text(code, encoding="utf-8")
        (tmp_dir / TEST_FILENAME).write_text(test_code, encoding="utf-8")
        return _run_in_docker(tmp_dir, image, timeout)


def run_unittest_files(
    code_file: Path,
    test_file: Path,
    image: str = DEFAULT_IMAGE,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> SandboxResult:
    """File-based entry point used by the CLI runner."""
    code_file = Path(code_file)
    test_file = Path(test_file)
    return run_code_with_tests(
        code_file.read_text(encoding="utf-8"),
        test_file.read_text(encoding="utf-8"),
        image=image,
        timeout=timeout,
    )


def _run_in_docker(workspace: Path, image: str, timeout: int) -> SandboxResult:
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--memory",
        "128m",
        "--cpus",
        "0.5",
        "--pids-limit",
        "50",
        "--network",
        "none",
        "--workdir",
        "/workspace",
        "--volume",
        f"{workspace}:/workspace:ro",
        image,
        "python",
        "-m",
        "unittest",
        TEST_FILENAME,
    ]

    try:
        completed = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") + (exc.stderr or "")
        return SandboxResult(
            passed=False,
            returncode=124,
            output=(partial + f"\n[sandbox] timed out after {timeout}s").strip(),
            timed_out=True,
        )

    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return SandboxResult(
        passed=completed.returncode == 0,
        returncode=completed.returncode,
        output=output,
    )


def docker_available() -> bool:
    return shutil.which("docker") is not None
