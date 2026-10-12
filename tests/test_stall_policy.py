"""D1 regression: the on_stall policy matrix, especially that 'skip' skips even
when stdin is non-interactive (headless), and 'pause' falls back to abort."""
import pytest

from step2step.claude.runner import Runner, StallAbort


class _FakeScreen:
    def tail(self, n=20):
        return "● 1. alpha\n  2. beta"


def _runner(on_stall):
    r = Runner(workdir="test-folder/_probe", prompts=["x"],
               app_dir=".", claude_exe="dummy-claude",  # explicit => no PATH lookup
               on_stall=on_stall, logger=lambda m: None)
    r.screen = _FakeScreen()
    return r


class _TTY:
    def __init__(self, tty):
        self._tty = tty

    def isatty(self):
        return self._tty


def test_skip_nontty_skips(monkeypatch):
    monkeypatch.setattr("sys.stdin", _TTY(False))
    assert _runner("skip")._stall(1) == "skip"


def test_abort_always_aborts(monkeypatch):
    monkeypatch.setattr("sys.stdin", _TTY(True))
    with pytest.raises(StallAbort):
        _runner("abort")._stall(1)


def test_pause_nontty_aborts(monkeypatch):
    monkeypatch.setattr("sys.stdin", _TTY(False))
    with pytest.raises(StallAbort):
        _runner("pause")._stall(1)
