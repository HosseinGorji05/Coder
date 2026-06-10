"""Executo self-correction loop (LangGraph + Groq + Docker).

Flow:
    generate -> execute -> (passed? -> END) | (retries left? -> fix -> execute) | END

Execute runs AI self-tests in Docker. If humaneval_task_id is set, HumanEval
fixed tests run too — both must pass (strict).

Normal: python -m core.agent "your prompt"
HumanEval: run_executo("", humaneval_task_id="HumanEval/0") or eval_humaneval.py
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from core import prompts
from core.sandbox import SandboxResult, docker_available, run_code_with_tests
from core.humaneval import load_task, build_humaneval_test, DEFAULT_DATASET
from pathlib import Path

load_dotenv()

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
DEFAULT_MAX_ATTEMPTS = 4


class AgentState(TypedDict, total=False):
    task: str
    code: str
    test_code: str
    output: str
    passed: bool
    timed_out: bool
    attempts: int
    max_attempts: int
    model: str
    humaneval_test_code: str
    self_test_passed: bool
    humaneval_passed: bool




_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _python_blocks(text: str) -> list[str]:
    return [m.group(1).strip() for m in _FENCE_RE.finditer(text)]


def _section_block(text: str, label: str) -> Optional[str]:
    match = re.search(
        rf"#+\s*{label}\b(.*?)(?=\n#+\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return None
    blocks = _python_blocks(match.group(1))
    return blocks[0] if blocks else None


def parse_solution_and_tests(
    text: str, fallback_test: Optional[str] = None
) -> tuple[str, str]:
    """Pull the SOLUTION and TESTS code blocks out of an LLM response.

    Falls back to positional fences if the labels are missing so a slightly
    off-format reply still works.
    """
    solution = _section_block(text, "SOLUTION")
    tests = _section_block(text, "TESTS")

    if solution is None or tests is None:
        blocks = _python_blocks(text)
        if solution is None:
            solution = blocks[0] if blocks else ""
        if tests is None:
            tests = blocks[1] if len(blocks) > 1 else (fallback_test or "")

    return solution, tests


def _get_llm(model: str):
    # Imported lazily so importing this module doesn't require the package
    # (or an API key) until the agent actually runs.
    from langchain_groq import ChatGroq

    return ChatGroq(model=model, temperature=0)


def _generate_node(state: AgentState) -> dict[str, Any]:
    llm = _get_llm(state.get("model", DEFAULT_MODEL))
    response = llm.invoke(
        [
            SystemMessage(content=prompts.GENERATE_SYSTEM),
            HumanMessage(content=prompts.generate_user(state["task"])),
        ]
    )
    code, test_code = parse_solution_and_tests(str(response.content))
    return {"code": code, "test_code": test_code, "attempts": 0}


def _format_execute_output(
    self_result: SandboxResult,
    he_result: SandboxResult | None,
) -> str:
    parts: list[str] = []
    if not self_result.passed:
        parts.append("=== AI self-tests FAILED ===")
        parts.append(self_result.output or "(no output)")
    if he_result is not None and not he_result.passed:
        parts.append("=== HumanEval tests FAILED ===")
        parts.append(he_result.output or "(no output)")
    if not parts:
        return self_result.output or he_result.output if he_result else ""
    return "\n\n".join(parts)


def _execute_node(state: AgentState) -> dict[str, Any]:
    self_result = run_code_with_tests(state["code"], state["test_code"])
    self_test_passed = self_result.passed

    humaneval_test_code = state.get("humaneval_test_code", "")
    he_result: SandboxResult | None = None
    if humaneval_test_code:
        he_result = run_code_with_tests(state["code"], humaneval_test_code)
        humaneval_passed = he_result.passed
    else:
        humaneval_passed = True

    passed = self_test_passed and humaneval_passed
    timed_out = self_result.timed_out or (he_result.timed_out if he_result else False)

    return {
        "output": _format_execute_output(self_result, he_result),
        "passed": passed,
        "self_test_passed": self_test_passed,
        "humaneval_passed": humaneval_passed,
        "timed_out": timed_out,
        "attempts": state.get("attempts", 0) + 1,
    }


def _fix_node(state: AgentState) -> dict[str, Any]:
    llm = _get_llm(state.get("model", DEFAULT_MODEL))
    has_humaneval = bool(state.get("humaneval_test_code"))
    response = llm.invoke(
        [
            SystemMessage(content=prompts.FIX_SYSTEM),
            HumanMessage(
                content=prompts.fix_user(
                    state["task"],
                    state["code"],
                    state["test_code"],
                    state["output"],
                    self_test_passed=state.get("self_test_passed"),
                    humaneval_passed=state.get("humaneval_passed"),
                    has_humaneval=has_humaneval,
                )
            ),
        ]
    )
    code, test_code = parse_solution_and_tests(
        str(response.content), fallback_test=state["test_code"]
    )
    return {"code": code, "test_code": test_code}


def _route_after_execute(state: AgentState) -> str:
    if state.get("passed"):
        return "done"
    if state.get("attempts", 0) >= state.get("max_attempts", DEFAULT_MAX_ATTEMPTS):
        return "done"
    return "fix"


def build_agent():
    graph = StateGraph(AgentState)
    graph.add_node("generate", _generate_node)
    graph.add_node("execute", _execute_node)
    graph.add_node("fix", _fix_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "execute")
    graph.add_conditional_edges(
        "execute", _route_after_execute, {"fix": "fix", "done": END}
    )
    graph.add_edge("fix", "execute")
    return graph.compile()


def run_executo(
    task: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    model: str = DEFAULT_MODEL,
    humaneval_task_id: str | None = None,
    humaneval_dataset: Path | None = None


) -> AgentState:
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    if not docker_available():
        raise RuntimeError("Docker is not installed or not in PATH.")

    agent = build_agent()

    humaneval_test_code = ""
    if humaneval_task_id:
        dataset = humaneval_dataset or DEFAULT_DATASET
        row = load_task(dataset, humaneval_task_id)
        humaneval_test_code = build_humaneval_test(row["entry_point"], row["test"])
        task = f"Complete the following Python function:\n\n{row['prompt']}"

    final_state: AgentState = agent.invoke(
        {
            "task": task,
            "max_attempts": max_attempts,
            "model": model,
            "humaneval_test_code": humaneval_test_code,
        }
    )
    return final_state

def _status_label(passed: bool | None) -> str:
    if passed is None:
        return "N/A"
    return "PASS" if passed else "FAIL"

def _main() -> int:
    import sys

    task = " ".join(sys.argv[1:]).strip() or (
        "Write a function add(a, b) that returns the sum of two numbers."
    )
    print(f"Task: {task}\n")
    try:
        result = run_executo(task)
    except RuntimeError as exc:
        print(f"Setup error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the user
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message or "rate_limit" in message.lower():
            print(
                "Groq API error: rate limit or quota exceeded.\n"
                "Check usage at https://console.groq.com/ or try a "
                "different model via GROQ_MODEL in .env.",
                file=sys.stderr,
            )
        else:
            print(f"LLM error: {message}", file=sys.stderr)
        return 1

    overall = _status_label(result.get("passed"))
    print("=" * 60)
    print(f"Overall: {overall} after {result.get('attempts')} attempt(s)")
    print(f"AI self-tests: {_status_label(result.get('self_test_passed'))}")
    if result.get("humaneval_test_code"):
        print(f"HumanEval tests: {_status_label(result.get('humaneval_passed'))}")
    print("=" * 60)
    print("\n--- snippet.py ---\n")
    print(result.get("code", ""))
    print("\n--- test_snippet.py ---\n")
    print(result.get("test_code", ""))
    print("\n--- last sandbox output ---\n")
    print(result.get("output", ""))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
