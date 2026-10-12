"""H1-H3: event-hook settings registration, 4-column signal lines, EventWatcher."""
import json
import pathlib
import subprocess
import sys

from step2step.claude import hooks

EV_EVENTS = ["PreToolUse", "PostToolUse", "Notification", "PreCompact", "SessionEnd"]


# --- H1: build_settings(events_file=...) -------------------------------------
def test_build_settings_default_shape_unchanged(tmp_path):
    # events_file omitted -> the exact pre-existing shape (only Stop), both forms.
    for form in ("args", "shell"):
        s = hooks.build_settings(pathlib.Path(sys.executable),
                                 tmp_path / "hook.py", tmp_path / "sig.txt",
                                 form=form)
        assert list(s["hooks"].keys()) == ["Stop"]


def test_build_settings_events_registers_all(tmp_path):
    s = hooks.build_settings(pathlib.Path(sys.executable),
                             tmp_path / "hook.py", tmp_path / "sig.txt",
                             form="args", events_file=tmp_path / "ev.txt")
    assert list(s["hooks"].keys()) == ["Stop"] + EV_EVENTS
    for ev in ("PreToolUse", "PostToolUse"):
        assert s["hooks"][ev][0]["matcher"] == "AskUserQuestion|ExitPlanMode"
    for ev in ("Notification", "PreCompact", "SessionEnd"):
        assert "matcher" not in s["hooks"][ev][0]


def test_build_settings_events_separate_files(tmp_path):
    # Stop keeps the signal file; every event hook points at the events file.
    sig, ev = tmp_path / "sig.txt", tmp_path / "ev.txt"
    s = hooks.build_settings(pathlib.Path(sys.executable),
                             tmp_path / "hook.py", sig,
                             form="args", events_file=ev)
    assert s["hooks"]["Stop"][0]["hooks"][0]["args"][-1] == str(sig)
    for name in EV_EVENTS:
        assert s["hooks"][name][0]["hooks"][0]["args"][-1] == str(ev)


def test_build_settings_events_shell_form(tmp_path):
    sig, ev = tmp_path / "sig.txt", tmp_path / "ev.txt"
    s = hooks.build_settings(pathlib.Path(sys.executable),
                             tmp_path / "hook.py", sig,
                             form="shell", events_file=ev)
    stop_hook = s["hooks"]["Stop"][0]["hooks"][0]
    assert "args" not in stop_hook and sig.as_posix() in stop_hook["command"]
    for name in EV_EVENTS:
        h = s["hooks"][name][0]["hooks"][0]
        assert "args" not in h and ev.as_posix() in h["command"]


# --- H2: the hook script writes a 4th tool_name column -----------------------
def _run_hook(tmp_path, payload):
    script = hooks.write_signal_hook(tmp_path / "hook.py")
    out = tmp_path / "out.txt"
    subprocess.run([sys.executable, str(script), str(out)],
                   input=json.dumps(payload), text=True,
                   capture_output=True, check=True)
    return out.read_text(encoding="utf-8")


def test_hook_script_records_tool_name(tmp_path):
    line = _run_hook(tmp_path, {"hook_event_name": "PreToolUse",
                                "session_id": "sid-1",
                                "tool_name": "AskUserQuestion"})
    parts = line.rstrip("\n").split("\t")
    assert parts[1:] == ["PreToolUse", "sid-1", "AskUserQuestion"]
    float(parts[0])  # timestamp column parses


def test_hook_script_empty_tool_when_missing(tmp_path):
    line = _run_hook(tmp_path, {"hook_event_name": "Stop", "session_id": "sid-1"})
    parts = line.rstrip("\n").split("\t")
    assert parts[1:] == ["Stop", "sid-1", ""]


# --- H3: EventWatcher --------------------------------------------------------
def _sample(tmp_path):
    p = tmp_path / "ev.txt"
    p.write_text(
        "1.0\tPreToolUse\tsid\tAskUserQuestion\n"
        "2.0\tPostToolUse\tsid\tAskUserQuestion\n"
        "3.0\tPreToolUse\tsid\tExitPlanMode\n"
        "4.0\tNotification\tsid\t\n"
        "5.0\tStop\tsid\n",  # legacy 3-column line (no tool column)
        encoding="utf-8")
    return hooks.EventWatcher(p)


def test_eventwatcher_missing_file(tmp_path):
    w = hooks.EventWatcher(tmp_path / "nope.txt")
    assert w.count() == 0
    assert w.events() == []


def test_eventwatcher_events_tuples(tmp_path):
    evs = _sample(tmp_path).events()
    assert evs[0] == (1.0, "PreToolUse", "sid", "AskUserQuestion")
    assert evs[4] == (5.0, "Stop", "sid", "")  # legacy line -> tool ""


def test_eventwatcher_count_filters(tmp_path):
    w = _sample(tmp_path)
    assert w.count() == 5
    assert w.count(event="PreToolUse") == 2
    assert w.count(event="PreToolUse", tool="AskUserQuestion") == 1
    assert w.count(tool="AskUserQuestion") == 2
    assert w.count(event="Notification", tool="") == 1


def test_eventwatcher_reset(tmp_path):
    w = _sample(tmp_path)
    assert w.count() == 5
    w.reset()
    assert w.count() == 0
    assert w.events() == []
