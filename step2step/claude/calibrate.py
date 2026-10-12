"""Marker-independent calibration capture.

Spawns Claude in a throwaway dir, dumps the rendered screen every ~0.5s with the
current predicate values, presses Enter at t=8s/12s (covers the trust dialog even
before markers are tuned), sends one tiny prompt at t=16s, then waits for the
Stop-hook signal. Read the dump file afterwards to tune screen.py markers and to
confirm the hook fired.

Usage:
    python -m step2step.claude.calibrate <workdir> [prompt] [duration_seconds]
"""
from __future__ import annotations

import os
import pathlib
import sys
import time
import uuid

from . import hooks
from . import screen as scr
from ..terminal.pty_session import PtySession
from ..terminal.screen import ScreenReader
from .runner import BRACKET_START, BRACKET_END, COLS, ENTER, ROWS, child_env, resolve_claude
from ..paths import RUNTIME_DIR


def main() -> int:
    workdir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    prompt = sys.argv[2] if len(sys.argv) > 2 else "reply with exactly PONG"
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 75.0

    runtime = RUNTIME_DIR
    runtime.mkdir(exist_ok=True)
    pathlib.Path(workdir).mkdir(parents=True, exist_ok=True)

    sid = str(uuid.uuid4())
    short = sid[:8]
    hook_script = hooks.write_signal_hook(runtime / "signal_hook.py")
    sig = runtime / ("calib-%s.signal" % short)
    watcher = hooks.SignalWatcher(sig)
    watcher.reset()
    settings_file = runtime / ("calib-settings-%s.json" % short)
    hooks.write_settings(
        settings_file,
        hooks.build_settings(pathlib.Path(sys.executable), hook_script, sig, form="args"),
    )
    debug_file = runtime / ("calib-debug-%s.log" % short)

    argv = [
        resolve_claude(),
        "--session-id", sid,
        "--settings", str(settings_file),
        "--dangerously-skip-permissions",
        "-d", "hooks",
        "--debug-file", str(debug_file),
    ]

    screen = ScreenReader(COLS, ROWS)
    pty = PtySession(
        argv, cwd=workdir, cols=COLS, rows=ROWS, env=child_env(),
        raw_log_path=str(runtime / ("calib-pty-%s.log" % short)), on_data=screen.feed,
    )
    dump_path = runtime / ("calib-dump-%s.txt" % short)
    dump = open(dump_path, "w", encoding="utf-8")
    t0 = time.monotonic()

    def snap(tag: str) -> None:
        t = screen.text()
        dump.write(
            "\n===== %s | t=%.1f working=%s trust=%s idle=%s question=%s signal=%d =====\n"
            % (tag, time.monotonic() - t0, scr.is_working(t), scr.is_trust_dialog(t),
               scr.looks_idle(t), scr.looks_like_question(t), watcher.count())
        )
        dump.write(t + "\n")
        dump.flush()

    pty.spawn()
    enter_marks = [8.0, 12.0]
    send_at = 16.0
    sent = False
    while time.monotonic() - t0 < duration and pty.isalive():
        snap("tick")
        el = time.monotonic() - t0
        while enter_marks and el >= enter_marks[0]:
            enter_marks.pop(0)
            snap("pre-enter")
            pty.write(ENTER)
            time.sleep(1.0)
            snap("post-enter")
        if not sent and el >= send_at:
            snap("pre-send")
            pty.write(BRACKET_START + prompt + BRACKET_END)
            time.sleep(0.2)
            pty.write(ENTER)
            sent = True
            time.sleep(0.4)
            snap("post-send")
        if sent and watcher.count() > 0:
            snap("SIGNAL")
            time.sleep(1.2)
            snap("post-signal-settle")
            break
        time.sleep(0.5)
    snap("final")
    dump.write("\nsignal lines: %r\n" % watcher.lines())
    dump.close()

    try:
        if pty.isalive():
            pty.write("/exit" + ENTER)
            time.sleep(1.0)
        if pty.isalive():
            pty.sendcontrol("c")
            time.sleep(0.4)
        if pty.isalive():
            pty.terminate()
    except Exception:
        pass
    pty.close_log()

    print("DUMP    :", dump_path)
    print("RAW     :", runtime / ("calib-pty-%s.log" % short))
    print("DEBUG   :", debug_file)
    print("SIGNALS :", watcher.count())
    return 0


if __name__ == "__main__":
    sys.exit(main())
