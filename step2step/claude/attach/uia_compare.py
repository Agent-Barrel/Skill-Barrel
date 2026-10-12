"""One-shot: compare the Win32 console reader vs the UIA reader on a throwaway
conhost Claude session, to justify the reader choice in the findings.

conhost is used because it owns a clean top-level window (easy UIA target); the
WT/ConPTY pane-HWND is fiddly, which is itself part of the conclusion.
"""
from __future__ import annotations

import sys
import time

from .. import screen as scr
from ...paths import RUNTIME_DIR
from . import target as tgt
from ...terminal.attach import winconsole as wc
from ...terminal.attach import uia_reader as uia

RUNTIME = RUNTIME_DIR
PY = sys.executable


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    RUNTIME.mkdir(exist_ok=True)
    guard = RUNTIME / "attach-target.pid"
    workdir = RUNTIME / "_uia_cmp_wd"
    target = tgt.launch("conhost", workdir, guard)
    try:
        # wait until idle via the console reader
        for _ in range(60):
            s = wc.run_op(PY, target.pid, str(guard), "read").get("screen", "")
            if scr.looks_idle(s):
                break
            time.sleep(1.0)
        console_text = wc.run_op(PY, target.pid, str(guard), "read").get("screen", "")

        # find the conhost window and read via UIA
        procs = tgt._all_procs()
        conhost_pid = procs.get(target.pid, {}).get("ppid")
        hwnd = uia.main_window_handle(conhost_pid) if conhost_pid else 0
        print("[uia] claude=%d conhost=%s hwnd=%s" % (target.pid, conhost_pid, hwnd))
        uia_text = ""
        uia_err = ""
        try:
            uia_text = uia.read_window_text(hwnd) if hwnd else "(no hwnd)"
        except Exception as e:
            uia_err = "%s: %s" % (type(e).__name__, e)

        print("[uia] console_read idle=%s len=%d  has_input_box=%s"
              % (scr.looks_idle(console_text), len(console_text),
                 scr.has_input_box(console_text)))
        print("[uia] uia_read len=%d err=%r" % (len(uia_text), uia_err))
        # do both readers see the version banner + footer marker?
        for tag, t in (("console", console_text), ("uia", uia_text)):
            print("[uia] %-7s sees: banner=%s footer=%s"
                  % (tag, "Claude Code v" in t, "shift+tab to cycle" in t))
        print("[uia] ---- UIA text (first 600 chars) ----")
        print(uia_text[:600])
        print("[uia] --------------------------------------")
        return 0
    finally:
        target.kill()
        guard.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
