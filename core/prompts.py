"""System and user prompts for the Executo self-correction loop.

The model must always answer with two labeled Python blocks so the agent can
split solution from tests deterministically:

    ### SOLUTION
    ```python
    ...
    ```
    ### TESTS
    ```python
    ...
    ```
"""

from __future__ import annotations

_OUTPUT_CONTRACT = """\
Respond with EXACTLY two sections and nothing else:

### SOLUTION
```python
# The solution. It must be importable as a module named `snippet`.
```

### TESTS
```python
import unittest
from snippet import <names you defined>
# unittest.TestCase classes that verify the solution.
```

Rules:
- The solution lives in a module that will be saved as `snippet.py`.
- Tests MUST import from `snippet` (e.g. `from snippet import add`).
- Use only the Python standard library. No third-party packages, no network, no file I/O.
- Do not include explanations, prose, or extra code fences outside the two sections."""

GENERATE_SYSTEM = (
    "You are Executo, an expert Python engineer. You turn a natural-language "
    "request into correct, self-contained Python plus unit tests that prove it "
    "works.\n\n" + _OUTPUT_CONTRACT
)

FIX_SYSTEM = (
    "You are Executo, debugging your own Python. You are given the original "
    "task, your previous solution, your tests, and sandbox unittest output. "
    "Diagnose the failure and return corrected code.\n\n"
    "Keep the public interface stable unless the task requires changing it. "
    "If your self-tests are wrong, fix them; if the solution is wrong, fix "
    "the solution. When HumanEval fixed tests are present, you cannot change "
    "those — fix the solution so they pass too.\n\n"
    + _OUTPUT_CONTRACT
)


def generate_user(task: str) -> str:
    return f"Task:\n{task}\n\nWrite the solution and its unit tests."


def fix_user(
    task: str,
    code: str,
    test_code: str,
    output: str,
    *,
    self_test_passed: bool | None = None,
    humaneval_passed: bool | None = None,
    has_humaneval: bool = False,
) -> str:
    lines = [
        f"Original task:\n{task}\n",
        f"Current solution (snippet.py):\n```python\n{code}\n```\n",
        f"Current self-tests (test_snippet.py):\n```python\n{test_code}\n```\n",
        "Sandbox results:",
    ]

    if self_test_passed is not None:
        lines.append(f"- AI self-tests: {'PASS' if self_test_passed else 'FAIL'}")
    if has_humaneval:
        status = "PASS" if humaneval_passed else "FAIL"
        lines.append(f"- HumanEval fixed tests: {status} (you cannot edit these)")
    else:
        lines.append("- HumanEval fixed tests: not used for this task")

    lines.append(f"\nSandbox unittest output:\n```\n{output}\n```\n")
    lines.append(
        "Return the corrected SOLUTION and TESTS so all failing suites pass."
    )
    return "\n".join(lines)
