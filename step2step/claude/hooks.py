"""Stop-hook plumbing + completion-signal watcher.

We inject a ``Stop`` hook ONLY into the spawned session (via ``claude --settings
<file>``) that runs a tiny Python script appending one line to a signal file
every time the main agent finishes a turn. The runner watches that file's line
count: the count increasing past a pre-submit baseline means the turn finished.

``Stop`` fires exactly once per main-agent turn; ``SubagentStop`` is a separate
event, so subagent completions do not signal here.

Opt-in (``events_file``): the SAME script can additionally be registered for the
interaction events (PreToolUse/PostToolUse on AskUserQuestion|ExitPlanMode,
Notification, PreCompact, SessionEnd), appending to a SEPARATE events file that
``EventWatcher`` reads — the Stop signal file and its count semantics never
change.
"""
from __future__ import annotations

import json
import pathlib

# Written verbatim to runtime/signal_hook.py. Reads the hook JSON Claude pipes on
# stdin and appends one newline-terminated line to the signal file (argv[1]).
# Columns: ts \t hook_event_name \t session_id \t tool_name (empty for events
# without a tool, e.g. Stop/Notification).
SIGNAL_HOOK_SOURCE = '''\
import sys, json, time, pathlib


def main():
    if len(sys.argv) < 2:
        return
    sig = pathlib.Path(sys.argv[1])
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    line = "%.3f\\t%s\\t%s\\t%s\\n" % (
        time.time(),
        data.get("hook_event_name", "Stop"),
        data.get("session_id", ""),
        data.get("tool_name", ""),
    )
    with sig.open("a", encoding="utf-8") as f:
        f.write(line)


if __name__ == "__main__":
    main()
'''

# PreToolUse/PostToolUse matcher for the interaction tools that pause a turn.
EVENT_MATCHER = "AskUserQuestion|ExitPlanMode"


def write_signal_hook(path: pathlib.Path) -> pathlib.Path:
    path.write_text(SIGNAL_HOOK_SOURCE, encoding="utf-8")
    return path


def _hook_entry(
    python_exe: pathlib.Path,
    hook_script: pathlib.Path,
    out_file: pathlib.Path,
    form: str,
) -> dict:
    if form == "shell":
        cmd = '"{}" "{}" "{}"'.format(
            python_exe.as_posix(), hook_script.as_posix(), out_file.as_posix()
        )
        return {"type": "command", "command": cmd}
    return {
        "type": "command",
        "command": str(python_exe),
        "args": [str(hook_script), str(out_file)],
    }


def build_settings(
    python_exe: pathlib.Path,
    hook_script: pathlib.Path,
    signal_file: pathlib.Path,
    form: str = "args",
    events_file: pathlib.Path | None = None,
) -> dict:
    """Settings dict registering the Stop hook (and, opt-in, interaction-event
    hooks).

    form="args"  -> run the interpreter directly with args (no shell; most robust)
    form="shell" -> single command string, forward slashes (Git-Bash friendly)

    events_file=None (default) registers ONLY the Stop hook — the exact
    pre-existing shape. When a path is given, the SAME hook script is also
    registered for PreToolUse/PostToolUse (matcher EVENT_MATCHER), Notification,
    PreCompact and SessionEnd, appending to `events_file` instead. Stop keeps its
    own signal file, so SignalWatcher.count() semantics never change.
    """
    stop_hook = _hook_entry(python_exe, hook_script, signal_file, form)
    hooks_cfg: dict = {"Stop": [{"hooks": [stop_hook]}]}
    if events_file is not None:
        ev_hook = _hook_entry(python_exe, hook_script, events_file, form)
        hooks_cfg["PreToolUse"] = [{"matcher": EVENT_MATCHER, "hooks": [ev_hook]}]
        hooks_cfg["PostToolUse"] = [{"matcher": EVENT_MATCHER, "hooks": [ev_hook]}]
        hooks_cfg["Notification"] = [{"hooks": [ev_hook]}]
        hooks_cfg["PreCompact"] = [{"hooks": [ev_hook]}]
        hooks_cfg["SessionEnd"] = [{"hooks": [ev_hook]}]
    return {"hooks": hooks_cfg}


def write_settings(path: pathlib.Path, settings: dict) -> pathlib.Path:
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return path


class SignalWatcher:
    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)

    def reset(self) -> None:
        self.path.write_text("", encoding="utf-8")

    def count(self) -> int:
        try:
            return self.path.read_text(encoding="utf-8", errors="replace").count("\n")
        except FileNotFoundError:
            return 0

    def lines(self) -> list[str]:
        try:
            return self.path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except FileNotFoundError:
            return []


class EventWatcher:
    """Watch the tab-separated event file the hook script appends to.

    Lines are "ts\\tevent\\tsession_id\\ttool_name"; legacy three-column lines
    (no tool_name) parse with tool == ""."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)

    def reset(self) -> None:
        self.path.write_text("", encoding="utf-8")

    def events(self) -> list[tuple]:
        """Ordered (ts, event, session_id, tool) tuples; [] if no file yet."""
        try:
            raw = self.path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return []
        out = []
        for ln in raw.splitlines():
            if not ln.strip():
                continue
            parts = ln.split("\t")
            if len(parts) < 3:
                continue
            try:
                ts = float(parts[0])
            except ValueError:
                ts = 0.0
            tool = parts[3] if len(parts) > 3 else ""
            out.append((ts, parts[1], parts[2], tool))
        return out

    def count(self, event: str | None = None, tool: str | None = None) -> int:
        n = 0
        for _ts, ev, _sid, tl in self.events():
            if event is not None and ev != event:
                continue
            if tool is not None and tl != tool:
                continue
            n += 1
        return n
