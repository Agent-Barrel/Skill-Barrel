"""ExternalSession: hold an attach to a foreign terminal console for a whole run.

This input sink and screen source uses WriteConsoleInput and
ReadConsoleOutputCharacter on a process we did not spawn. Callers decide what
the target's screen means and which input sequences its application requires.

Unlike the experiment harness (which ran each attach op in a detached subprocess
for isolation), the runner holds ONE attach for its whole lifetime and calls the
console APIs in-process, so polling the screen is fast. That is safe because the
runner process is throwaway: FreeConsole()/AttachConsole() only affect it, never
the caller's real session.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes as W

from . import winconsole as wc

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
_k32.OpenProcess.restype = W.HANDLE
_k32.GetExitCodeProcess.argtypes = [W.HANDLE, ctypes.POINTER(W.DWORD)]
_k32.GetExitCodeProcess.restype = W.BOOL
_k32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, W.BOOL]
_k32.SetConsoleCtrlHandler.restype = W.BOOL

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


def pid_alive(pid: int) -> bool:
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return False
    try:
        code = W.DWORD(0)
        if not _k32.GetExitCodeProcess(W.HANDLE(h), ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        _k32.CloseHandle(W.HANDLE(h))


class ExternalSession:
    """Attach to `pid`'s console and drive it. Use as a context manager or call
    attach()/detach() explicitly. All input goes via WriteConsoleInput; all screen
    reads via ReadConsoleOutputCharacter (never ReadConsoleInput -> never steals
    the target's keys)."""

    def __init__(self, pid: int, *, guard_file=None):
        self.pid = int(pid)
        self.guard_file = str(guard_file) if guard_file else None
        self._con: wc.AttachedConsole | None = None
        self._last_text = ""
        self._last_change_ts = time.monotonic()

    # -- lifecycle --
    def attach(self) -> "ExternalSession":
        if self.guard_file:
            wc._check_guard(self.pid, self.guard_file)  # aborts if not sanctioned
        if not pid_alive(self.pid):
            raise RuntimeError("target pid %d is not alive" % self.pid)
        self._con = wc.AttachedConsole(self.pid)
        self._con.__enter__()  # hold the attach for the whole session
        # Don't let a Ctrl-C/Break in the TARGET's console kill this runner.
        _k32.SetConsoleCtrlHandler(None, True)
        self._last_text = self._con.read_screen()
        self._last_change_ts = time.monotonic()
        return self

    def detach(self) -> None:
        try:
            _k32.SetConsoleCtrlHandler(None, False)
        except Exception:
            pass
        if self._con is not None:
            try:
                self._con.__exit__(None, None, None)
            finally:
                self._con = None

    def __enter__(self):
        return self.attach()

    def __exit__(self, *exc):
        self.detach()
        return False

    # -- input sink --
    def type_text(self, text: str) -> None:
        self._con.type_text(text)

    def key(self, name: str) -> None:
        self._con.send_key(name)

    def submit(self) -> None:
        self._con.send_key("enter")

    def backspace(self, count: int) -> None:
        """Send exactly `count` backspaces in one input batch."""
        self._con.write_records([wc.key_rec("\x08", wc.VK_BACK) for _ in range(count)])

    # -- screen source --
    def text(self) -> str:
        s = self._con.read_screen()
        if s != self._last_text:
            self._last_text = s
            self._last_change_ts = time.monotonic()
        return s

    def idle_for(self) -> float:
        """Seconds since the scraped screen last changed (replaces the owned
        session's pty.last_output_ts)."""
        return time.monotonic() - self._last_change_ts

    def isalive(self) -> bool:
        return pid_alive(self.pid)
