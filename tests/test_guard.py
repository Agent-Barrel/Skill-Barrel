"""Attach safety: _forbidden_pid refuses self, ancestors (the caller's own live
session), and non-claude / dead pids; _check_guard raises a typed error."""
import os
import sys

import pytest

if sys.platform != "win32":
    pytest.skip(
        "step2step.claude.attach drives the Win32 console (ctypes.WinDLL); "
        "Windows-only and not ported",
        allow_module_level=True,
    )

from step2step.claude.attach import attach_runner as ar
from step2step.claude.attach import target as tgt
from step2step.terminal.attach.winconsole import AttachGuardError, _check_guard


def _fake_procs():
    me = os.getpid()
    return {
        me: {"ppid": 500, "name": "python.exe", "cmd": ""},
        500: {"ppid": 400, "name": "claude.exe", "cmd": ""},   # my parent session
        400: {"ppid": 0, "name": "explorer.exe", "cmd": ""},
        7777: {"ppid": 1, "name": "claude.exe", "cmd": ""},    # unrelated claude
        8888: {"ppid": 1, "name": "notepad.exe", "cmd": ""},
    }


def test_refuses_self(monkeypatch):
    monkeypatch.setattr(tgt, "_all_procs", _fake_procs)
    r = ar._forbidden_pid(os.getpid())
    assert r and "not claude.exe" in r


def test_refuses_ancestor(monkeypatch):
    monkeypatch.setattr(tgt, "_all_procs", _fake_procs)
    r = ar._forbidden_pid(500)
    assert r and "ancestor" in r


def test_allows_unrelated_claude(monkeypatch):
    monkeypatch.setattr(tgt, "_all_procs", _fake_procs)
    assert ar._forbidden_pid(7777) is None


def test_refuses_non_claude(monkeypatch):
    monkeypatch.setattr(tgt, "_all_procs", _fake_procs)
    r = ar._forbidden_pid(8888)
    assert r and "not claude.exe" in r


def test_refuses_dead_pid(monkeypatch):
    monkeypatch.setattr(tgt, "_all_procs", _fake_procs)
    r = ar._forbidden_pid(999999999)
    assert r and "not found" in r


def test_check_guard_mismatch_raises(tmp_path):
    g = tmp_path / "guard.pid"
    g.write_text("12345", encoding="utf-8")
    with pytest.raises(AttachGuardError):
        _check_guard(99999, str(g))


def test_check_guard_missing_file_raises(tmp_path):
    with pytest.raises(AttachGuardError):
        _check_guard(1, str(tmp_path / "nope.pid"))


def test_check_guard_match_ok(tmp_path):
    g = tmp_path / "guard.pid"
    g.write_text("777", encoding="utf-8")
    _check_guard(777, str(g))  # no raise
