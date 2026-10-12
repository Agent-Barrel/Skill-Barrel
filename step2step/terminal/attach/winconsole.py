"""Win32 console attach + input injection + screen scrape (ctypes).

The whole external-injection idea rests on three Win32 calls:

    FreeConsole() -> AttachConsole(targetPid) -> WriteConsoleInputW(INPUT_RECORD[])

A process may be attached to only ONE console, so we FreeConsole first (or run
with no console at all). Once attached we open CONIN$/CONOUT$ and:

    * inject keystrokes  -> WriteConsoleInputW  (KEY_EVENT records)
    * read the screen    -> ReadConsoleOutputCharacterW over the visible viewport

HYGIENE (critical): this module NEVER calls ReadConsoleInput. Two readers on one
input buffer race and steal each other's keys (the classic "press Enter twice"
bug). We only WRITE input and READ output; output reads are non-destructive.

SAFETY: every attach is gated by a guard file (see `_check_guard`). The caller
writes the single sanctioned target PID to that file; if the requested --pid does
not match, we abort BEFORE attaching. This makes it physically impossible for the
harness to attach to the user's real, in-use console session.
"""
from __future__ import annotations

import argparse
import ctypes as C
import json
import pathlib
import subprocess
import sys
from ctypes import wintypes as W

from ...paths import REPO_ROOT

# The module name this file must be re-invoked as (`python -m <_MODULE>`) by
# run_op(); derived from __name__ so directory renames cannot desynchronize it.
_MODULE = __name__ if __name__ != "__main__" else "step2step.terminal.attach.winconsole"

k32 = C.WinDLL("kernel32", use_last_error=True)

# --- constants --------------------------------------------------------------
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE = C.c_void_p(-1).value

KEY_EVENT = 0x0001

# dwControlKeyState flags
SHIFT_PRESSED = 0x0010
LEFT_CTRL_PRESSED = 0x0008
LEFT_ALT_PRESSED = 0x0002

# virtual-key codes we use
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

# CreateProcess creation flags (used by callers via run_op)
DETACHED_PROCESS = 0x00000008
CREATE_NEW_CONSOLE = 0x00000010
CREATE_NO_WINDOW = 0x08000000


# --- structs ----------------------------------------------------------------
class COORD(C.Structure):
    _fields_ = [("X", C.c_short), ("Y", C.c_short)]


class SMALL_RECT(C.Structure):
    _fields_ = [("Left", C.c_short), ("Top", C.c_short),
                ("Right", C.c_short), ("Bottom", C.c_short)]


class CONSOLE_SCREEN_BUFFER_INFO(C.Structure):
    _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD),
                ("wAttributes", W.WORD), ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD)]


class _CHAR(C.Union):
    _fields_ = [("UnicodeChar", W.WCHAR), ("AsciiChar", C.c_char)]


class KEY_EVENT_RECORD(C.Structure):
    _fields_ = [("bKeyDown", W.BOOL), ("wRepeatCount", W.WORD),
                ("wVirtualKeyCode", W.WORD), ("wVirtualScanCode", W.WORD),
                ("uChar", _CHAR), ("dwControlKeyState", W.DWORD)]


class _EVENT(C.Union):
    _fields_ = [("KeyEvent", KEY_EVENT_RECORD)]
    # (MOUSE/BUFFER/etc. events omitted; KEY_EVENT is the largest we build)


class INPUT_RECORD(C.Structure):
    _fields_ = [("EventType", W.WORD), ("Event", _EVENT)]


# --- prototypes (explicit, so 64-bit HANDLEs are not truncated to int) ------
k32.AttachConsole.argtypes = [W.DWORD]
k32.AttachConsole.restype = W.BOOL
k32.FreeConsole.argtypes = []
k32.FreeConsole.restype = W.BOOL
k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p,
                            W.DWORD, W.DWORD, W.HANDLE]
k32.CreateFileW.restype = W.HANDLE
k32.CloseHandle.argtypes = [W.HANDLE]
k32.CloseHandle.restype = W.BOOL
k32.WriteConsoleInputW.argtypes = [W.HANDLE, C.POINTER(INPUT_RECORD),
                                   W.DWORD, C.POINTER(W.DWORD)]
k32.WriteConsoleInputW.restype = W.BOOL
k32.GetConsoleScreenBufferInfo.argtypes = [W.HANDLE,
                                           C.POINTER(CONSOLE_SCREEN_BUFFER_INFO)]
k32.GetConsoleScreenBufferInfo.restype = W.BOOL
k32.ReadConsoleOutputCharacterW.argtypes = [W.HANDLE, W.LPWSTR, W.DWORD,
                                            COORD, C.POINTER(W.DWORD)]
k32.ReadConsoleOutputCharacterW.restype = W.BOOL


# --- key-record construction ------------------------------------------------
def key_rec(ch: str = "\0", vk: int = 0, ctrl: int = 0, down: bool = True) -> INPUT_RECORD:
    r = INPUT_RECORD()
    r.EventType = KEY_EVENT
    ke = r.Event.KeyEvent
    ke.bKeyDown = 1 if down else 0
    ke.wRepeatCount = 1
    ke.wVirtualKeyCode = vk
    ke.wVirtualScanCode = 0
    ke.uChar.UnicodeChar = ch
    ke.dwControlKeyState = ctrl
    return r


# Named special keys -> the record(s) that produce them. Each value is a factory
# returning a list of INPUT_RECORDs (so a key can expand to down+up if we test
# that variant). Default is keydown-only, which libuv acts on.
def _down(ch="\0", vk=0, ctrl=0):
    return [key_rec(ch, vk, ctrl, down=True)]


def _downup(ch="\0", vk=0, ctrl=0):
    return [key_rec(ch, vk, ctrl, down=True), key_rec(ch, vk, ctrl, down=False)]


SPECIAL_KEYS = {
    "enter": lambda: _down("\r", VK_RETURN),
    "esc": lambda: _down("\x1b", VK_ESCAPE),
    "backspace": lambda: _down("\x08", VK_BACK),          # 0x08 variant
    "backspace_del": lambda: _down("\x7f", VK_BACK),      # 0x7F variant
    "tab": lambda: _down("\t", VK_TAB),
    "shift_tab": lambda: _down("\t", VK_TAB, SHIFT_PRESSED),
    "left": lambda: _down("\0", VK_LEFT),
    "right": lambda: _down("\0", VK_RIGHT),
    "up": lambda: _down("\0", VK_UP),
    "down": lambda: _down("\0", VK_DOWN),
    "ctrl_c": lambda: _down("\x03", 0x43, LEFT_CTRL_PRESSED),
}


def text_records(text: str) -> list[INPUT_RECORD]:
    """One keydown KEY_EVENT per UTF-16 code unit (how a fast paste is delivered).

    A console KEY_EVENT carries a single UTF-16 WCHAR, so a character outside the
    BMP (e.g. an emoji) is emitted as two records -- its high+low surrogate pair
    -- instead of raising 'one character unicode string expected'."""
    recs = []
    for ch in text:
        if ch == "\n":
            recs.append(key_rec("\r", VK_RETURN))
            continue
        b = ch.encode("utf-16-le")
        for i in range(0, len(b), 2):
            unit = b[i] | (b[i + 1] << 8)
            recs.append(key_rec(chr(unit)))
    return recs


# --- attach / handles -------------------------------------------------------
class AttachedConsole:
    """Context manager: detach from our own console, attach to `pid`'s console,
    open CONIN$/CONOUT$. Restores (FreeConsole) on exit. Multiple processes may
    attach to one console, so we join as an extra client."""

    def __init__(self, pid: int):
        self.pid = pid
        self.h_in = None
        self.h_out = None

    def __enter__(self):
        k32.FreeConsole()  # harmless if we have none; required if we do
        if not k32.AttachConsole(self.pid):
            err = C.get_last_error()
            raise OSError("AttachConsole(%d) failed: WinError %d" % (self.pid, err))
        self.h_in = self._open("CONIN$")
        self.h_out = self._open("CONOUT$")
        return self

    def __exit__(self, *exc):
        for h in (self.h_in, self.h_out):
            if h and h != INVALID_HANDLE:
                k32.CloseHandle(W.HANDLE(h))
        k32.FreeConsole()
        return False

    @staticmethod
    def _open(name: str):
        h = k32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                            OPEN_EXISTING, 0, None)
        if h == INVALID_HANDLE or h is None:
            raise OSError("CreateFileW(%s) failed: WinError %d"
                          % (name, C.get_last_error()))
        return h

    # -- injection --
    def write_records(self, records: list[INPUT_RECORD]) -> int:
        if not records:
            return 0
        arr = (INPUT_RECORD * len(records))(*records)
        written = W.DWORD(0)
        ok = k32.WriteConsoleInputW(W.HANDLE(self.h_in), arr, len(records),
                                    C.byref(written))
        if not ok:
            raise OSError("WriteConsoleInputW failed: WinError %d"
                          % C.get_last_error())
        return written.value

    def type_text(self, text: str) -> int:
        return self.write_records(text_records(text))

    def send_key(self, name: str) -> int:
        if name not in SPECIAL_KEYS:
            raise KeyError("unknown key %r" % name)
        return self.write_records(SPECIAL_KEYS[name]())

    # -- screen scrape --
    def read_screen(self, full: bool = False) -> str:
        info = CONSOLE_SCREEN_BUFFER_INFO()
        if not k32.GetConsoleScreenBufferInfo(W.HANDLE(self.h_out), C.byref(info)):
            raise OSError("GetConsoleScreenBufferInfo failed: WinError %d"
                          % C.get_last_error())
        width = info.dwSize.X
        if full:
            top, bottom = 0, info.dwSize.Y - 1
        else:
            top, bottom = info.srWindow.Top, info.srWindow.Bottom
        lines = []
        for y in range(top, bottom + 1):
            buf = C.create_unicode_buffer(width)
            n = W.DWORD(0)
            if k32.ReadConsoleOutputCharacterW(W.HANDLE(self.h_out), buf, width,
                                               COORD(0, y), C.byref(n)):
                lines.append(buf[:n.value])
            else:
                lines.append("")
        return "\n".join(s.rstrip() for s in lines)


# --- safety guard -----------------------------------------------------------
class AttachGuardError(Exception):
    """Raised when a requested attach PID is not the sanctioned target. A normal
    exception (not SystemExit) so a calling library can catch it."""


def _check_guard(pid: int, guard_file: str) -> None:
    """Abort unless `pid` is the exact value the orchestrator wrote to the guard
    file. Prevents ever attaching to a non-sanctioned (real) session."""
    p = pathlib.Path(guard_file)
    if not p.exists():
        raise AttachGuardError("guard file missing: %s (refusing to attach)" % guard_file)
    allowed = p.read_text(encoding="utf-8").strip()
    if str(pid) != allowed:
        raise AttachGuardError("pid %d not sanctioned (guard=%r); refusing to attach"
                               % (pid, allowed))


# --- subprocess helper (isolation) ------------------------------------------
def run_op(python_exe: str, pid: int, guard_file: str, op: str,
           text: str = "", key: str = "", full: bool = False,
           timeout: float = 15.0) -> dict:
    """Run one attach op in a DETACHED (console-less) child so the orchestrator's
    own console is never touched by the Attach/Free dance. Returns parsed JSON."""
    argv = [python_exe, "-m", _MODULE, "--pid", str(pid),
            "--guard-file", guard_file, "--op", op]
    if text:
        argv += ["--text", text]
    if key:
        argv += ["--key", key]
    if full:
        argv += ["--full"]
    proc = subprocess.run(
        argv, cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
        creationflags=DETACHED_PROCESS, timeout=timeout,
    )
    out = proc.stdout.strip()
    try:
        return json.loads(out.splitlines()[-1]) if out else {
            "ok": False, "error": "no output; stderr=%s" % proc.stderr.strip()}
    except Exception as e:
        return {"ok": False, "error": "bad json (%r): %s | stderr=%s"
                % (e, out[:400], proc.stderr.strip()[:400])}


# --- CLI --------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog=_MODULE)
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--guard-file", required=True)
    ap.add_argument("--op", required=True,
                    choices=["inject", "keys", "read", "attach-only"])
    ap.add_argument("--text", default="")
    ap.add_argument("--key", default="", help="one SPECIAL_KEYS name, or several comma-separated")
    ap.add_argument("--full", action="store_true", help="read full buffer, not just viewport")
    args = ap.parse_args(argv)

    try:
        _check_guard(args.pid, args.guard_file)
    except AttachGuardError as e:
        print(json.dumps({"ok": False, "pid": args.pid, "op": args.op,
                          "error": str(e)}, ensure_ascii=True))
        return 2
    result = {"ok": False, "pid": args.pid, "op": args.op}
    try:
        with AttachedConsole(args.pid) as con:
            if args.op == "inject":
                result["written"] = con.type_text(args.text)
            elif args.op == "keys":
                total = 0
                for name in [k for k in args.key.split(",") if k]:
                    total += con.send_key(name.strip())
                result["written"] = total
            elif args.op == "read":
                result["screen"] = con.read_screen(full=args.full)
            elif args.op == "attach-only":
                pass
        result["ok"] = True
    except BaseException as e:  # report, never traceback to the pipe
        result["error"] = "%s: %s" % (type(e).__name__, e)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
