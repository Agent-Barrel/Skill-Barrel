"""Turn the JSONL transcript Claude Code persists into structured per-turn data.

A calling harness (concept -> planning Q&A -> build -> test -> deploy) needs the
actual assistant response for each prompt, not just a completion status, so it can
decide the next prompt (answer a clarifying question, react to a result, etc.).
Screen scraping is lossy; the JSONL transcript has the clean text and the tool
calls. On the current Claude Code, PTY-driven sessions DO persist this file, so we
parse it directly.

    from step2step.claude import find_transcript, parse_transcript
    turns = parse_transcript(find_transcript(session_id))
    # turns[i] == {"index", "prompt", "response", "tools", "tool_inputs"}
"""
from __future__ import annotations

import glob
import json
import os
import pathlib

# Tools that mean "the turn is waiting on the user", useful for a Q&A loop.
QUESTION_TOOLS = {"AskUserQuestion", "ExitPlanMode"}


def find_transcript(session_id: str, base: str | None = None) -> str | None:
    """Locate the clean JSONL Claude writes for `session_id`, or None."""
    base = base or os.path.join(os.path.expanduser("~"), ".claude", "projects")
    matches = glob.glob(
        os.path.join(base, "**", session_id + ".jsonl"), recursive=True
    )
    return matches[0] if matches else None


def parse_transcript(path) -> list[dict]:
    """Parse a Claude Code JSONL transcript into ordered per-turn dicts:
    {"index", "prompt", "response", "tools", "tool_inputs"}.

    A turn starts at a user message whose content is a plain string (the real
    prompt); tool_result user messages (list content) are folded into the turn.
    `response` is the concatenation of the assistant text blocks in that turn;
    `tools` is the list of tool names the assistant invoked. `tool_inputs`
    keeps the {"name", "id", "input"} of each QUESTION_TOOLS tool_use (the
    question/plan payload, for auditing and answering)."""
    if not path:
        return []
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    events = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            events.append(json.loads(ln))
        except Exception:
            continue

    turns: list[dict] = []
    cur: dict | None = None

    def flush():
        nonlocal cur
        if cur is not None:
            cur["response"] = "\n".join(cur.pop("_texts")).strip()
            turns.append(cur)
            cur = None

    for o in events:
        t = o.get("type")
        if t == "user":
            content = (o.get("message") or {}).get("content")
            if isinstance(content, str):  # real prompt (not a tool_result) -> new turn
                flush()
                cur = {"index": len(turns) + 1, "prompt": content,
                       "_texts": [], "tools": [], "tool_inputs": []}
        elif t == "assistant" and cur is not None:
            for b in ((o.get("message") or {}).get("content") or []):
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text"):
                    cur["_texts"].append(b["text"])
                elif b.get("type") == "tool_use" and b.get("name"):
                    cur["tools"].append(b["name"])
                    if b["name"] in QUESTION_TOOLS:
                        cur["tool_inputs"].append({
                            "name": b["name"],
                            "id": b.get("id"),
                            "input": b.get("input") or {},
                        })
    flush()
    return turns


def pending_tool_use(path) -> dict | None:
    """The last AskUserQuestion/ExitPlanMode tool_use with no matching
    tool_result. Returns {"name", "id", "input"} or None.

    **Not a live detector.** Measured on 2.1.224: a waiting interaction's
    tool_use is NOT in the JSONL while it waits — it is flushed only when the
    interaction resolves, and then written back with its ORIGINAL timestamp, so
    after the fact it looks as if it had been there all along. One session sat
    on an AskUserQuestion for 7.5 hours with 0 matching rows in a 415-record
    transcript; the row appeared (at index 417, ts = the moment the menu opened)
    only after the menu was answered.

    So this returns None for exactly the window a caller cares about. To detect
    or read a WAITING dialog use screen.classify_dialog /
    screen.parse_question_dialog. This function is for auditing a finished
    conversation, and for enriching content once the tool has resolved."""
    if not path:
        return None
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    pending: dict[str, dict] = {}
    order: list[str] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        t = o.get("type")
        content = (o.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        if t == "assistant":
            for b in content:
                if (isinstance(b, dict) and b.get("type") == "tool_use"
                        and b.get("name") in QUESTION_TOOLS):
                    tid = b.get("id") or ""
                    pending[tid] = {"name": b["name"], "id": b.get("id"),
                                    "input": b.get("input") or {}}
                    order.append(tid)
        elif t == "user":
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    pending.pop(b.get("tool_use_id") or "", None)
    for tid in reversed(order):
        if tid in pending:
            return pending[tid]
    return None


def last_model_effort(path) -> dict | None:
    """What the session ACTUALLY ran on, from the last assistant record:
    {"model", "effort", "records"} — or None when there is no assistant record
    yet (or the transcript is missing/unreadable).

    This is the highest-authority answer to "which model/effort is this session
    using". The screen only shows what we asked for; a settings override, an org
    effort cap or a model that does not support the requested level can all make
    the two disagree. `model` lives on message.model, `effort` is a top-level
    record field, and `effort` is None on models that do not report one."""
    if not path:
        return None
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    model = effort = None
    records = 0
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if o.get("type") != "assistant":
            continue
        records += 1
        m = (o.get("message") or {}).get("model")
        if m:
            model = m
        # Read effort per record rather than "last non-null": a switch to a model
        # that reports no effort must show as None, not as the stale old value.
        effort = o.get("effort")
    if not records:
        return None
    return {"model": model, "effort": effort, "records": records}


def turn_asks_question(turn: dict) -> bool:
    """True if the turn ended by asking the user something (AskUserQuestion) or
    proposing a plan for approval (ExitPlanMode)."""
    return any(name in QUESTION_TOOLS for name in turn.get("tools", []))
