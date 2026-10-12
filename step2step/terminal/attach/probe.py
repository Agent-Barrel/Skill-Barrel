"""Phase A: validate the Win32 attach/inject/read plumbing with a dummy console app.

Launch a benign dummy console app in its own new console, inject "hello world" +
Enter, then scrape the console and confirm both the echoed input and the dummy's
"GOT[hello world]" reply are on screen. This de-risks every ctypes struct and the
AttachConsole/WriteConsoleInput/ReadConsoleOutput calls independently of any AI product.

The guard file is pointed at the dummy's own
self-reported PID.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

from . import winconsole as wc
from ...paths import RUNTIME_DIR

RUNTIME = RUNTIME_DIR

DUMMY_SRC = '''\
import os, sys, pathlib
pathlib.Path(sys.argv[1]).write_text(str(os.getpid()), encoding="utf-8")
print("PROBE DUMMY READY (pid %d)" % os.getpid(), flush=True)
while True:
    line = sys.stdin.readline()
    if not line:
        break
    sys.stdout.write("GOT[" + line.rstrip("\\r\\n") + "]\\n")
    sys.stdout.flush()
'''


def _wait_file(p: pathlib.Path, timeout=10.0) -> str | None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if p.exists():
            txt = p.read_text(encoding="utf-8").strip()
            if txt:
                return txt
        time.sleep(0.1)
    return None


def main() -> int:
    RUNTIME.mkdir(exist_ok=True)
    py = sys.executable
    dummy_py = RUNTIME / "_probe_dummy.py"
    dummy_py.write_text(DUMMY_SRC, encoding="utf-8")
    pidfile = RUNTIME / "_probe_dummy.pid"
    guard = RUNTIME / "attach-target.pid"
    for f in (pidfile, guard):
        f.unlink(missing_ok=True)

    print("[probeA] launching dummy console app (CREATE_NEW_CONSOLE)")
    proc = subprocess.Popen(
        [py, str(dummy_py), str(pidfile)],
        creationflags=wc.CREATE_NEW_CONSOLE,
    )
    try:
        pid = _wait_file(pidfile)
        if not pid:
            print("[probeA] FAIL: dummy never reported its PID")
            return 1
        pid = int(pid)
        print("[probeA] dummy self-reported PID=%d (launcher pid=%d)" % (pid, proc.pid))
        guard.write_text(str(pid), encoding="utf-8")  # sanction ONLY this pid
        time.sleep(0.4)

        # 1) guard rejects a non-sanctioned pid
        bad = wc.run_op(py, pid + 1, str(guard), "attach-only")
        assert not bad.get("ok"), "guard should have rejected a wrong pid"
        print("[probeA] guard correctly rejected wrong pid -> %s" % bad.get("error", "")[:60])

        # 2) inject text + Enter
        r1 = wc.run_op(py, pid, str(guard), "inject", text="hello world")
        print("[probeA] inject ->", r1)
        r2 = wc.run_op(py, pid, str(guard), "keys", key="enter")
        print("[probeA] enter  ->", r2)
        time.sleep(0.4)

        # 3) read the screen back
        r3 = wc.run_op(py, pid, str(guard), "read")
        screen = r3.get("screen", "")
        print("[probeA] --- scraped screen ---")
        print(screen)
        print("[probeA] -----------------------")

        got_echo = "hello world" in screen
        got_reply = "GOT[hello world]" in screen
        ok = r1.get("ok") and r2.get("ok") and r3.get("ok") and got_echo and got_reply
        print("[probeA] echo_visible=%s reply_visible=%s -> %s"
              % (got_echo, got_reply, "PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        except Exception:
            pass
        for f in (pidfile, guard, dummy_py):
            f.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
