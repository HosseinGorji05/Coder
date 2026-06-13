#!/usr/bin/env python3
"""Executo — ChatGPT-style web UI for the self-correcting code agent.

Run:
    python app.py
Then open http://127.0.0.1:7860 in your browser.
"""

from __future__ import annotations

import gradio as gr

from core.agent import DEFAULT_MAX_ATTEMPTS, stream_executo_events
from core.errors import (
    format_failure_summary,
    format_llm_error,
    format_setup_error,
)

TITLE = "Executo"
TAGLINE = (
    "Describe what you want in plain English. Executo writes Python, "
    "tests it in a sandbox, and fixes itself until it passes."
)

EXAMPLES = [
    "Write a function that checks if a string is a palindrome, ignoring spaces and case.",
    "Write a function that returns the nth Fibonacci number.",
    "Write a function that merges two sorted lists into one sorted list.",
    "Write a function that counts the vowels in a sentence.",
    "Write a function that converts a Roman numeral string to an integer.",
]

SET_LIGHT_JS = """
() => {
    document.documentElement.setAttribute('data-executo-theme', 'light');
    localStorage.setItem('executo-theme', 'light');
    const light = document.querySelector('#executo-light-btn button, #executo-light-btn');
    const dark = document.querySelector('#executo-dark-btn button, #executo-dark-btn');
    if (light) light.classList.add('active');
    if (dark) dark.classList.remove('active');
}
"""

SET_DARK_JS = """
() => {
    document.documentElement.setAttribute('data-executo-theme', 'dark');
    localStorage.setItem('executo-theme', 'dark');
    const light = document.querySelector('#executo-light-btn button, #executo-light-btn');
    const dark = document.querySelector('#executo-dark-btn button, #executo-dark-btn');
    if (dark) dark.classList.add('active');
    if (light) light.classList.remove('active');
}
"""

INIT_THEME_JS = """
() => {
    const saved = localStorage.getItem('executo-theme') || 'light';
    document.documentElement.setAttribute('data-executo-theme', saved);
    setTimeout(() => {
        const light = document.querySelector('#executo-light-btn button, #executo-light-btn');
        const dark = document.querySelector('#executo-dark-btn button, #executo-dark-btn');
        if (light) light.classList.toggle('active', saved === 'light');
        if (dark) dark.classList.toggle('active', saved === 'dark');
    }, 100);
}
"""

CSS = """
/* ── Layout ── */
html, body {
    min-height: 100%;
}
.gradio-container {
    max-width: 920px !important;
    margin: 0 auto !important;
    background: transparent !important;
}
.main, .wrap, .contain {
    background: transparent !important;
}

/* ── Header & toolbar ── */
.executo-top {
    max-width: 920px;
    margin: 0 auto;
    padding: 0 8px;
}
#executo-header {
    text-align: center;
    padding: 24px 16px 12px;
}
#executo-header h1 {
    font-size: 2.35rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #ec4899);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 6px;
}
#executo-header p {
    color: #64748b;
    font-size: 0.98rem;
    max-width: 640px;
    margin: 0 auto;
    line-height: 1.5;
}
.executo-toolbar {
    display: flex !important;
    justify-content: flex-end !important;
    align-items: center !important;
    margin-bottom: 12px !important;
    background: transparent !important;
    border: none !important;
}

/* ── Theme pill toggle (Gradio buttons) ── */
.executo-theme-pill {
    display: inline-flex !important;
    align-items: center;
    gap: 0 !important;
    padding: 4px !important;
    border-radius: 999px !important;
    background: #e2e8f0 !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.06);
    width: auto !important;
    max-width: fit-content !important;
    margin-left: auto !important;
}
.executo-theme-pill > div,
.executo-theme-pill .wrap {
    gap: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
#executo-light-btn button,
#executo-dark-btn button {
    appearance: none !important;
    border: none !important;
    background: transparent !important;
    color: #64748b !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 7px 16px !important;
    border-radius: 999px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    min-width: 0 !important;
    box-shadow: none !important;
}
#executo-light-btn button:hover,
#executo-dark-btn button:hover {
    color: #334155 !important;
    background: rgba(255,255,255,0.45) !important;
}
#executo-light-btn.active button,
#executo-dark-btn.active button,
#executo-light-btn button.active,
#executo-dark-btn button.active {
    background: #ffffff !important;
    color: #4f46e5 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.12) !important;
}

/* ── Chat stream box (always a light card) ── */
.executo-chat {
    border: 1px solid #e2e8f0 !important;
    border-radius: 16px !important;
    background: #ffffff !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.06) !important;
}
.executo-chat .message,
.executo-chat .prose,
.executo-chat [class*="message"] {
    color: #1e293b !important;
}

.executo-code-panel { margin-top: 12px; }
.executo-tip {
    text-align: center;
    color: #64748b;
    font-size: 0.85rem;
    margin-top: 10px;
}
footer { display: none !important; }

/* ══════════════════════════════════════
   DARK MODE — dark page, LIGHT chat box
   ══════════════════════════════════════ */
[data-executo-theme="dark"] {
    color-scheme: dark;
}
[data-executo-theme="dark"] html,
[data-executo-theme="dark"] body {
    background: #08080c !important;
}
[data-executo-theme="dark"] .gradio-container,
[data-executo-theme="dark"] .main,
[data-executo-theme="dark"] .wrap,
[data-executo-theme="dark"] .contain,
[data-executo-theme="dark"] .app {
    background: #08080c !important;
}
[data-executo-theme="dark"] .block:not(.executo-chat *) {
    background: transparent !important;
    border-color: #2a2a3a !important;
}
[data-executo-theme="dark"] #executo-header p,
[data-executo-theme="dark"] .executo-tip,
[data-executo-theme="dark"] .markdown-text,
[data-executo-theme="dark"] h3 {
    color: #94a3b8 !important;
}

/* Theme pill in dark mode */
[data-executo-theme="dark"] .executo-theme-pill {
    background: #1a1a28 !important;
    border-color: #2e2e42 !important;
}
[data-executo-theme="dark"] #executo-light-btn button,
[data-executo-theme="dark"] #executo-dark-btn button {
    color: #64748b !important;
    background: transparent !important;
}
[data-executo-theme="dark"] #executo-light-btn button:hover,
[data-executo-theme="dark"] #executo-dark-btn button:hover {
    color: #cbd5e1 !important;
    background: rgba(255,255,255,0.06) !important;
}
[data-executo-theme="dark"] #executo-light-btn.active button,
[data-executo-theme="dark"] #executo-dark-btn.active button {
    background: #2d2d44 !important;
    color: #a5b4fc !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.4) !important;
}

/* Chat box stays LIGHT in dark mode */
[data-executo-theme="dark"] .executo-chat {
    background: #f8f9fc !important;
    border-color: #e2e8f0 !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.45) !important;
}
[data-executo-theme="dark"] .executo-chat .message,
[data-executo-theme="dark"] .executo-chat .prose,
[data-executo-theme="dark"] .executo-chat [class*="message"] {
    color: #1e293b !important;
    background: transparent !important;
}

/* Input, buttons, accordions — dark */
[data-executo-theme="dark"] textarea,
[data-executo-theme="dark"] input[type="text"] {
    background: #12121c !important;
    color: #e2e8f0 !important;
    border-color: #2e2e42 !important;
}
[data-executo-theme="dark"] .form,
[data-executo-theme="dark"] .panel,
[data-executo-theme="dark"] details,
[data-executo-theme="dark"] .accordion {
    background: #0e0e16 !important;
    border-color: #2a2a3a !important;
    color: #cbd5e1 !important;
}
[data-executo-theme="dark"] button.secondary {
    background: #1a1a28 !important;
    color: #cbd5e1 !important;
    border-color: #2e2e42 !important;
}
[data-executo-theme="dark"] .tab-nav button {
    background: #12121c !important;
    color: #94a3b8 !important;
}
[data-executo-theme="dark"] .tab-nav button.selected {
    background: #1e1e2e !important;
    color: #a5b4fc !important;
}
"""


def _render(steps: list[str], final: dict | None = None) -> str:
    md = "\n\n".join(steps) if steps else "..."

    if final is None:
        return md

    passed = final.get("passed")
    attempts = final.get("attempts", 0) or 0

    md += "\n\n---\n\n"
    if passed:
        md += f"### ✅ Solved in {attempts} attempt(s)\nAll tests passed in the sandbox.\n"
    else:
        md += f"### ⚠️ Not fully solved after {attempts} attempt(s)\n"
        note = format_failure_summary(final)
        if note:
            md += f"\n{note}\n"

    output = (final.get("output") or "").strip()
    if output and not passed:
        md += (
            "\n<details><summary>📋 Last sandbox output</summary>\n\n"
            f"```\n{output}\n```\n</details>\n"
        )

    md += "\n*See the **Solution** and **Tests** tabs below for the full code.*"
    return md


def _stream_response(message: str, max_attempts: int):
    """Yield (chat_text, solution_code, test_code) as the agent runs."""
    steps: list[str] = []
    solution = ""
    tests = ""

    events = stream_executo_events(message.strip(), max_attempts=int(max_attempts))
    for event, state in events:
        if event == "start":
            steps = ["🧠 Understanding your request…"]
            yield _render(steps), solution, tests
        elif event == "generate":
            steps.append("✍️ Writing the code and its tests…")
            yield _render(steps), solution, tests
        elif event == "execute":
            attempt = state.get("attempts", 0)
            ai_ok = state.get("self_test_passed")
            badge = "✅ passed" if ai_ok else "❌ failed"
            steps.append(f"🧪 Attempt {attempt}: tests {badge}")
            yield _render(steps), solution, tests
        elif event == "fix":
            steps.append("🔧 Reading the errors and fixing the code…")
            yield _render(steps), solution, tests
        elif event == "done":
            solution = (state.get("code") or "").strip()
            tests = (state.get("test_code") or "").strip()
            yield _render(steps, final=state), solution, tests


def chat(
    message: str,
    history: list,
    max_attempts: int,
):
    """Handle a new user message with streaming updates."""
    if not message or not message.strip():
        yield history, "", "", "", ""
        return

    history = list(history or [])
    history.append({"role": "user", "content": message.strip()})
    history.append({"role": "assistant", "content": "..."})

    try:
        for text, solution, tests in _stream_response(message, max_attempts):
            history[-1] = {"role": "assistant", "content": text}
            yield history, "", solution, tests, message.strip()
    except RuntimeError as exc:
        history[-1] = {"role": "assistant", "content": f"⚠️ **Setup needed**\n\n{format_setup_error(str(exc))}"}
        yield history, "", "", "", message.strip()
    except Exception as exc:  # noqa: BLE001
        history[-1] = {"role": "assistant", "content": f"⚠️ **Something went wrong**\n\n{format_llm_error(str(exc))}"}
        yield history, "", "", "", message.strip()


def run_again(history: list, max_attempts: int, last_prompt: str):
    """Re-run the last prompt."""
    if not last_prompt:
        gr.Info("No previous prompt to run again.")
        yield history, "", "", "", last_prompt
        return
    yield from chat(last_prompt, history, max_attempts)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title=TITLE, fill_height=True) as demo:
        gr.HTML(
            f"""
            <div class="executo-top">
                <div id="executo-header">
                    <h1>⚡ {TITLE}</h1>
                    <p>{TAGLINE}</p>
                </div>
            </div>
            """
        )

        with gr.Row(elem_classes="executo-toolbar"):
            with gr.Row(elem_classes="executo-theme-pill"):
                light_btn = gr.Button("☀️ Light", elem_id="executo-light-btn", size="sm")
                dark_btn = gr.Button("🌙 Dark", elem_id="executo-dark-btn", size="sm")

        last_prompt = gr.State("")

        chatbot = gr.Chatbot(
            height=420,
            show_label=False,
            elem_classes="executo-chat",
            sanitize_html=False,
            placeholder="Ask Executo to write a Python function…",
        )

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Describe the Python function you want…",
                show_label=False,
                scale=8,
                container=False,
            )
            send = gr.Button("Send", variant="primary", scale=1, min_width=80)

        with gr.Row():
            run_again_btn = gr.Button("↻ Run again", scale=1)
            clear = gr.Button("Clear chat", scale=1)

        with gr.Accordion("💡 Example prompts", open=False):
            gr.Examples(
                examples=[[e] for e in EXAMPLES],
                inputs=msg,
                label="",
            )

        with gr.Accordion("⚙️ Settings", open=False):
            max_attempts = gr.Slider(
                minimum=1,
                maximum=8,
                value=DEFAULT_MAX_ATTEMPTS,
                step=1,
                label="Max self-correction attempts",
            )

        gr.Markdown("### Generated code")
        with gr.Tabs(elem_classes="executo-code-panel") as code_tabs:
            with gr.Tab("Solution"):
                solution_code = gr.Code(
                    language="python",
                    label="snippet.py",
                    lines=16,
                    interactive=False,
                )
            with gr.Tab("Tests"):
                test_code = gr.Code(
                    language="python",
                    label="test_snippet.py",
                    lines=16,
                    interactive=False,
                )

        gr.HTML(
            '<p class="executo-tip">Code runs in an isolated Docker sandbox. '
            "Always review before using in production.</p>"
        )

        demo.load(fn=None, js=INIT_THEME_JS)
        light_btn.click(fn=None, js=SET_LIGHT_JS)
        dark_btn.click(fn=None, js=SET_DARK_JS)

        send.click(
            chat,
            inputs=[msg, chatbot, max_attempts],
            outputs=[chatbot, msg, solution_code, test_code, last_prompt],
        )
        msg.submit(
            chat,
            inputs=[msg, chatbot, max_attempts],
            outputs=[chatbot, msg, solution_code, test_code, last_prompt],
        )
        run_again_btn.click(
            run_again,
            inputs=[chatbot, max_attempts, last_prompt],
            outputs=[chatbot, msg, solution_code, test_code, last_prompt],
        )
        clear.click(lambda: ([], "", "", "", ""), outputs=[chatbot, msg, solution_code, test_code, last_prompt])

    return demo


if __name__ == "__main__":
    theme = gr.themes.Soft(
        primary_hue="violet",
        secondary_hue="indigo",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
    )
    build_ui().launch(theme=theme, css=CSS)
