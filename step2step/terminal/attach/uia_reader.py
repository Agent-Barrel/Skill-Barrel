"""OPTIONAL screen reader via UI Automation TextPattern (comtypes).

This is the alternative to winconsole.read_screen(). The experiment showed the
Win32 console read (ReadConsoleOutputCharacterW) already returns the full visible
TUI frame under BOTH classic conhost and Windows Terminal/ConPTY, and it works
regardless of whether the window is focused/occluded (it reads the buffer, not
pixels). So UIA is not required for this use case; it is kept as a reference /
fallback (e.g. if a host ever stops exposing a readable console buffer).

read_window_text(hwnd) returns the terminal's text via the same UIA TextPattern
that screen readers use. hwnd must be the host WINDOW (conhost's window, or the
WindowsTerminal window) -- for a ConPTY tab, locating the exact pane HWND is
fiddly (WT is multi-tab), which is another reason the console read is preferred.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as W

import comtypes
import comtypes.client

_iuia = None
_UIA = None


def _uia():
    global _iuia, _UIA
    if _iuia is None:
        _UIA = comtypes.client.GetModule("UIAutomationCore.dll")
        _iuia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",  # CUIAutomation
            interface=_UIA.IUIAutomation,
        )
    return _iuia, _UIA


def read_window_text(hwnd: int) -> str:
    iuia, UIA = _uia()
    el = iuia.ElementFromHandle(hwnd)
    try:
        pat = el.GetCurrentPatternAs(
            UIA.UIA_TextPatternId, UIA.IUIAutomationTextPattern._iid_)
    except Exception:
        unknown = el.GetCurrentPattern(UIA.UIA_TextPatternId)
        if not unknown:
            raise RuntimeError("window exposes no TextPattern")
        pat = unknown.QueryInterface(UIA.IUIAutomationTextPattern)
    return pat.DocumentRange.GetText(-1)


def main_window_handle(pid: int) -> int:
    """Best-effort top-level visible window owned by `pid` (e.g. a conhost pid)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found = []

    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(hwnd, _):
        wpid = W.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


if __name__ == "__main__":
    import sys
    h = int(sys.argv[1])
    print(read_window_text(h))
