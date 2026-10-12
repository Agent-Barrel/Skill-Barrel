import pathlib
import sys

from step2step.claude import hooks


def test_signalwatcher_count_and_reset(tmp_path):
    sig = tmp_path / "sig.txt"
    w = hooks.SignalWatcher(sig)
    assert w.count() == 0  # missing file
    w.reset()
    assert w.count() == 0
    with sig.open("a", encoding="utf-8") as f:
        f.write("1\tStop\tsid\n2\tStop\tsid\n")
    assert w.count() == 2
    assert len(w.lines()) == 2


def test_build_settings_args_form(tmp_path):
    s = hooks.build_settings(pathlib.Path(sys.executable),
                             tmp_path / "hook.py", tmp_path / "sig.txt", form="args")
    assert list(s["hooks"].keys()) == ["Stop"]  # only Stop, never SubagentStop
    hook = s["hooks"]["Stop"][0]["hooks"][0]
    assert hook["type"] == "command"
    assert "args" in hook and len(hook["args"]) == 2


def test_build_settings_shell_form(tmp_path):
    s = hooks.build_settings(pathlib.Path(sys.executable),
                             tmp_path / "hook.py", tmp_path / "sig.txt", form="shell")
    hook = s["hooks"]["Stop"][0]["hooks"][0]
    assert "args" not in hook and "command" in hook
