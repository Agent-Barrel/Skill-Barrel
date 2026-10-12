"""Phase B-D orchestrator: attach to a throwaway Claude session and measure what
actually works. Runs against one host ("conhost" or "wt") per invocation.

  Phase B  launch throwaway Claude, wait until the input box is idle/ready
  Phase C1 inject text WITHOUT submitting -> is it visible in the prompt? (crux)
  Phase C2 special-key matrix (backspace / esc / shift+tab / ctrl-c), observed
           via screen deltas
  Phase D  end-to-end: inject a trivial prompt + Enter, confirm it runs and
           completes (screen-only completion detection, reusing step2step.claude.screen)

Results (and every scraped screen, as evidence) are written to
runtime/attach-experiment-<host>.log and echoed to stdout.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

from .. import screen as scr
from ...paths import RUNTIME_DIR
from . import target as tgt
from ...terminal.attach import winconsole as wc

RUNTIME = RUNTIME_DIR
PY = sys.executable
PROBE_TEXT = "step2step external-inject probe 12345"


def _utf8_stdout():
    # The TUI screen contains box-drawing chars; the default Windows console
    # codepage (cp949 here) can't encode them. Force UTF-8 like the Claude CLI.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class Log:
    def __init__(self, path: pathlib.Path):
        self.fh = open(path, "w", encoding="utf-8")

    def __call__(self, msg=""):
        line = str(msg)
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(line.encode("utf-8", "replace") + b"\n")
            sys.stdout.flush()
        self.fh.write(line + "\n")
        self.fh.flush()

    def screen(self, tag, text):
        self("---- screen [%s] ----" % tag)
        self(text)
        self("---- /screen ----")


def _read(pid, guard, full=False) -> str:
    r = wc.run_op(PY, pid, guard, "read", full=full)
    return r.get("screen", "") if r.get("ok") else ""


def _inject(pid, guard, text) -> dict:
    return wc.run_op(PY, pid, guard, "inject", text=text)


def _keys(pid, guard, names) -> dict:
    return wc.run_op(PY, pid, guard, "keys", key=",".join(names))


def _wait_idle(pid, guard, log, timeout=60.0) -> bool:
    end = time.monotonic() + timeout
    last = ""
    while time.monotonic() < end:
        s = _read(pid, guard)
        if s and s != last:
            last = s
        if scr.looks_idle(s):
            return True
        time.sleep(1.0)
    log("[wait_idle] timed out; last screen follows")
    log.screen("idle-timeout", last)
    return False


def _clear_input(pid, guard, n=100):
    # Measured: ESC does NOT clear the Claude input line; backspaces do. ESC is
    # sent first only to dismiss any transient popup, then backspaces clear text.
    _keys(pid, guard, ["esc"])
    time.sleep(0.15)
    _keys(pid, guard, ["backspace"] * n)
    time.sleep(0.2)


def run(host: str) -> dict:
    _utf8_stdout()
    RUNTIME.mkdir(exist_ok=True)
    log = Log(RUNTIME / ("attach-experiment-%s.log" % host))
    guard = str(RUNTIME / "attach-target.pid")
    workdir = RUNTIME / ("_ext_target_wd_" + host)
    results = {"host": host, "phases": {}}
    target = None
    log("=" * 72)
    log("[experiment] host=%s  python=%s" % (host, PY))
    try:
        # ---- Phase B: launch + idle ----
        target = tgt.launch(host, workdir, pathlib.Path(guard), logger=log)
        pid = target.pid
        results["target_pid"] = pid
        idle = _wait_idle(pid, guard, log)
        results["phases"]["B_idle"] = idle
        log("[B] input box idle/ready: %s" % idle)
        s0 = _read(pid, guard)
        log.screen("B-initial", s0)
        results["initial_mode"] = scr.current_mode(s0)

        # ---- Phase C1: inject text, DO NOT submit ----
        _clear_input(pid, guard)
        inj = _inject(pid, guard, PROBE_TEXT)
        time.sleep(0.5)
        s1 = _read(pid, guard)
        log.screen("C1-after-inject", s1)
        visible = PROBE_TEXT in s1
        # tolerate soft-wrap: also check the tail fragment
        if not visible:
            visible = "external-inject probe 12345" in s1.replace("\n", "")
        results["phases"]["C1_inject_visible"] = visible
        results["C1_written"] = inj.get("written")
        log("[C1] inject ok=%s written=%s  VISIBLE_IN_PROMPT=%s  <<< crux"
            % (inj.get("ok"), inj.get("written"), visible))

        # ---- Phase C2: special keys ----
        c2 = {}
        # backspace: remove the trailing "45" from the probe
        before = _read(pid, guard)
        _keys(pid, guard, ["backspace", "backspace"])
        time.sleep(0.3)
        after = _read(pid, guard)
        c2["backspace"] = ("12345" in before) and ("123" in after) and ("12345" not in after)
        log("[C2] backspace effective: %s" % c2["backspace"])

        # shift+tab: expect the footer permission-mode to change
        m_before = scr.current_mode(_read(pid, guard))
        _keys(pid, guard, ["shift_tab"])
        time.sleep(0.6)
        m_after = scr.current_mode(_read(pid, guard))
        c2["shift_tab_mode_change"] = (m_before != m_after) and (m_after is not None)
        log("[C2] shift+tab mode: %s -> %s (changed=%s)"
            % (m_before, m_after, c2["shift_tab_mode_change"]))
        # cycle back toward bypass so Phase D runs hands-off
        for _ in range(6):
            if scr.current_mode(_read(pid, guard)) == "bypass":
                break
            _keys(pid, guard, ["shift_tab"])
            time.sleep(0.5)

        # esc: clear the line
        _inject(pid, guard, "ephemeral")
        time.sleep(0.3)
        had = "ephemeral" in _read(pid, guard)
        _keys(pid, guard, ["esc"])
        time.sleep(0.3)
        gone = "ephemeral" not in _read(pid, guard)
        c2["esc_clears"] = had and gone
        log("[C2] esc clears line: %s (had=%s gone=%s)" % (c2["esc_clears"], had, gone))
        results["phases"]["C2_keys"] = c2

        # ---- Phase D: end-to-end submit (tiny cost) ----
        _clear_input(pid, guard)
        prompt = "Reply with exactly this token and nothing else: PROBE_OK"
        _inject(pid, guard, prompt)
        time.sleep(0.4)
        pre = _read(pid, guard)
        log.screen("D-before-submit", pre)
        _keys(pid, guard, ["enter"])
        # started?
        started = False
        end = time.monotonic() + 15
        while time.monotonic() < end:
            if scr.is_working(_read(pid, guard)):
                started = True
                break
            time.sleep(0.5)
        log("[D] turn started (working detected): %s" % started)
        # completed? wait for idle again
        done = False
        end = time.monotonic() + 120
        while time.monotonic() < end:
            s = _read(pid, guard)
            if not scr.is_working(s) and scr.looks_idle(s):
                done = True
                break
            time.sleep(1.0)
        s_final = _read(pid, guard)
        log.screen("D-final", s_final)
        got = "PROBE_OK" in s_final
        results["phases"]["D_submit_started"] = started
        results["phases"]["D_completed"] = done
        results["phases"]["D_reply_seen"] = got
        log("[D] started=%s completed=%s reply_seen=%s" % (started, done, got))

    except BaseException as e:
        log("[experiment] ERROR: %s: %s" % (type(e).__name__, e))
        results["error"] = "%s: %s" % (type(e).__name__, e)
    finally:
        if target is not None:
            log("[experiment] killing throwaway target pid=%d" % target.pid)
            target.kill()
        pathlib.Path(guard).unlink(missing_ok=True)
        log("[experiment] RESULTS: %s" % results)
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="step2step.claude.attach.experiment")
    ap.add_argument("--host", choices=["conhost", "wt"], default="conhost")
    args = ap.parse_args(argv)
    r = run(args.host)
    return 0 if r.get("phases", {}).get("C1_inject_visible") else 1


if __name__ == "__main__":
    sys.exit(main())
