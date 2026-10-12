"""AttachRunner: drive a prompt sequence through an ALREADY-RUNNING Claude Code
session by attaching to its console (bypass mode, screen-based completion).

This is the "attach" counterpart to step2step.claude.runner.Runner (the ConPTY
owner). It does NOT spawn Claude; it attaches to a live session via
step2step.terminal.attach.session.ExternalSession and reuses step2step.claude.screen's state
predicates unchanged. Completion is detected from the screen (working -> idle
edge) because we cannot inject a Stop hook into a session we did not launch.

Entry points:
    python -m step2step.claude.attach.attach_runner --pid <PID> [--prompts f.md]
    python -m step2step.claude.attach.attach_runner --launch conhost|wt [--prompts f.md] [--kill]

--pid attaches to an existing session (refuses your own session / non-claude pids).
--launch spawns a throwaway session first (for testing/demo) using
step2step.claude.attach.target, whose new-pid-diff excludes every pre-existing session by
construction.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from typing import TYPE_CHECKING

from .. import screen as scr
from ...prompts import load_prompts
from ..runner import CONFIRM_WAIT, INIT_IDLE_WAIT, POLL, SETTLE_QUIET, STALL_SECONDS, StallAbort
from ...paths import RUNTIME_DIR

from . import target as tgt

if TYPE_CHECKING:
    from ...terminal.attach.session import ExternalSession

RUNTIME = RUNTIME_DIR
SETTLE = max(SETTLE_QUIET, 1.2)  # a touch longer than owned mode: no Stop-hook truth
DEFAULT_PROMPTS = ["Reply with exactly this token and nothing else: ATTACH_OK"]


def _norm(text: str) -> str:
    return "\n".join(ln.rstrip() for ln in text.splitlines() if ln.strip())


def _tail(text: str, n: int = 20) -> str:
    rows = [r for r in text.splitlines() if r.strip()]
    return "\n".join(rows[-n:])


def _utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class Log:
    def __init__(self, path):
        self.fh = open(path, "w", encoding="utf-8")

    def __call__(self, msg=""):
        line = str(msg)
        try:
            print(line, flush=True)
        except Exception:
            pass
        self.fh.write(line + "\n")
        self.fh.flush()


class AttachRunner:
    def __init__(self, session: ExternalSession, prompts, *,
                 on_stall="abort", logger=None):
        self.s = session
        self.prompts = list(prompts)
        self.on_stall = on_stall
        self.log = logger or (lambda m="": print(m, flush=True))

    # -- generic waiter --
    def _wait(self, pred, timeout, poll=POLL) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not self.s.isalive():
                return False
            try:
                if pred():
                    return True
            except Exception:
                pass
            time.sleep(poll)
        return False

    def _wait_initial_idle(self) -> bool:
        ok = self._wait(lambda: scr.looks_idle(self.s.text()), INIT_IDLE_WAIT)
        self.log("[idle] input box ready" if ok
                 else "[idle] WARNING initial idle not confirmed; proceeding")
        return ok

    # -- send / confirm / wait-done --
    def _send(self, idx: int, text: str):
        # Claude input is cleared by backspaces, not Escape (calibrated).
        self.s.backspace(200)
        time.sleep(0.15)
        norm = text.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" in norm:
            self.log("[send] WARNING multi-line prompt: newlines submit as Enter "
                     "in this iteration (bracketed paste is future work)")
        self.log("[send %d/%d] %d chars: %s"
                 % (idx, len(self.prompts), len(norm), norm.replace("\n", "\\n")[:80]))
        self.s.type_text(norm)
        time.sleep(0.3)
        pre = self.s.text()  # prompt now sitting in the input box
        self.s.submit()
        return pre

    def _confirm_started(self, pre: str) -> bool:
        def started():
            t = self.s.text()
            return scr.is_working(t) or _norm(t) != _norm(pre)

        if self._wait(started, CONFIRM_WAIT):
            return True
        self.log("[confirm] no working/change in %ss; resending Enter" % CONFIRM_WAIT)
        self.s.submit()
        return self._wait(started, CONFIRM_WAIT)

    def _wait_done(self, pre: str) -> str:
        """Screen-based turn completion: once we've seen the working state (or the
        screen changed since submit), the turn is done when it is no longer working,
        looks idle, and has been quiet for SETTLE. Adaptive stall only after a long
        frozen period."""
        saw_working = False
        while True:
            if not self.s.isalive():
                return "eof"
            txt = self.s.text()
            if scr.is_working(txt):
                saw_working = True
                time.sleep(POLL)
                continue
            changed = _norm(txt) != _norm(pre)
            if (saw_working or changed) and scr.looks_idle(txt) and self.s.idle_for() >= SETTLE:
                return "done"
            if self.s.idle_for() >= STALL_SECONDS:
                return "idle-fallback" if scr.looks_idle(txt) else "stall"
            time.sleep(POLL)

    def _settle(self, quiet=SETTLE, timeout=8.0):
        self._wait(lambda: not scr.is_working(self.s.text())
                   and self.s.idle_for() >= quiet, timeout)

    # -- stall handling --
    def _stall(self, idx: int) -> str:
        self.log("\n" + "=" * 70)
        self.log("[STALL] prompt %d/%d did not complete cleanly" % (idx, len(self.prompts)))
        self.log("--- current screen ---\n%s\n----------------------" % _tail(self.s.text(), 20))
        # Honor the policy first: "skip" must skip regardless of TTY (a headless
        # harness relies on that); only "pause" needs a human and falls back to
        # abort when stdin cannot be prompted.
        if self.on_stall == "abort":
            self.log("[stall] aborting (policy=abort)")
            raise StallAbort()
        if self.on_stall == "skip":
            self.log("[stall] skipping to next prompt (policy=skip)")
            return "skip"
        interactive = bool(getattr(sys.stdin, "isatty", lambda: False)())
        if not interactive:
            self.log("[stall] pause requested but stdin is non-interactive -> aborting")
            raise StallAbort()
        while True:
            try:
                c = input("\n[paused] (a)bort (w)ait (s)kip (t)akeover > ").strip().lower()
            except EOFError:
                raise StallAbort()
            if c == "a":
                raise StallAbort()
            if c == "w":
                return "wait"
            if c == "s":
                return "skip"
            if c == "t":
                self._takeover()
            else:
                print("choose a / w / s / t")

    def _takeover(self):
        print("\n--- TAKEOVER: each line is sent to the session; ':resume' to return ---")
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == ":resume":
                break
            self.s.type_text(line)
            self.s.submit()

    # -- per-prompt --
    def _process(self, idx: int, text: str) -> str:
        pre = self._send(idx, text)
        if not self._confirm_started(pre):
            if self._stall(idx) == "skip":
                return "skipped"
        while True:
            status = self._wait_done(pre)
            if status in ("done", "idle-fallback"):
                break
            if status == "eof":
                return "eof"
            if self._stall(idx) == "skip":
                return "skipped"
            self.s._last_change_ts = time.monotonic()  # "wait": restart stall timer
        self._settle()
        # Only second-guess an idle-fallback completion. A confident "done" (saw
        # the working->idle edge) means the turn ended; a numbered list on screen
        # is then the response body, not a pending menu.
        if status == "idle-fallback" and scr.looks_like_question(_tail(self.s.text(), 12)):
            self.log("[guard] question/menu detected after idle-fallback turn %d" % idx)
            if self._stall(idx) == "skip":
                return "skipped"
        return status

    def run(self) -> dict:
        self.s.attach()
        results: list[dict] = []
        aborted = False
        try:
            self._wait_initial_idle()
            for i, prompt in enumerate(self.prompts, 1):
                try:
                    status = self._process(i, prompt)
                except StallAbort:
                    self.log("[run] aborted by stall policy/user at prompt %d" % i)
                    results.append({"index": i, "status": "aborted"})
                    aborted = True
                    break
                results.append({"index": i, "status": status})
                self.log("[turn %d/%d] status=%s" % (i, len(self.prompts), status))
                if status == "eof":
                    self.log("[run] session ended early; stopping")
                    break
            else:
                self.log("[complete] all %d prompts processed" % len(self.prompts))
        finally:
            self.s.detach()
        completed = sum(1 for r in results if str(r["status"]) in ("done", "idle-fallback"))
        return {"mode": "attach-bypass", "pid": self.s.pid, "total": len(self.prompts),
                "completed": completed, "aborted": aborted, "results": results}


# --- CLI safety -------------------------------------------------------------
def _forbidden_pid(pid: int) -> str | None:
    """Return a reason string if `pid` must NOT be attached, else None. Refuses
    our own session (self or any ancestor) and any non-claude process."""
    procs = tgt._all_procs()
    info = procs.get(pid)
    if not info:
        return "pid %d not found" % pid
    if info["name"] != "claude.exe":
        return "pid %d is %r, not claude.exe" % (pid, info["name"])
    if pid == os.getpid():
        return "refusing to attach to self"
    anc, cur = set(), os.getpid()
    for _ in range(64):
        i = procs.get(cur)
        if not i:
            break
        cur = i["ppid"]
        if cur in anc:
            break
        anc.add(cur)
    if pid in anc:
        return "pid %d is an ancestor of this process (your own live session)" % pid
    return None


def main(argv=None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(prog="step2step.claude.attach.attach_runner",
                                 description="Drive an already-running Claude session by attaching to its console.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pid", type=int, help="attach to an existing Claude session PID")
    g.add_argument("--launch", choices=["conhost", "wt"],
                   help="spawn a throwaway session first (testing/demo)")
    ap.add_argument("--prompts", help="prompts markdown file (default: a tiny demo prompt)")
    ap.add_argument("--on-stall", default="abort", choices=["abort", "skip", "pause"])
    ap.add_argument("--claude-arg", action="append", default=[],
                    help="extra arg forwarded to the launched claude (repeatable), "
                         "e.g. --claude-arg=--model --claude-arg=haiku")
    ap.add_argument("--kill", action="store_true",
                    help="kill the target when done (default: leave it running, just detach)")
    args = ap.parse_args(argv)

    from ...terminal.attach.session import ExternalSession

    RUNTIME.mkdir(exist_ok=True)
    log = Log(RUNTIME / "attach-run.log")
    prompts = load_prompts(args.prompts) if args.prompts else DEFAULT_PROMPTS
    if not prompts:
        log("no prompts found in %s" % args.prompts)
        return 2
    guard = RUNTIME / "attach-target.pid"
    workdir = RUNTIME / ("_attach_wd_" + (args.launch or "pid"))
    target = None
    summary = None
    try:
        if args.launch:
            target = tgt.launch(args.launch, workdir, guard,
                                extra_args=args.claude_arg, logger=log)
            pid = target.pid
        else:
            bad = _forbidden_pid(args.pid)
            if bad:
                log("[abort] %s" % bad)
                return 2
            guard.write_text(str(args.pid), encoding="utf-8")
            log("[attach] sanctioned existing pid %d" % args.pid)
            pid = args.pid

        session = ExternalSession(pid, guard_file=guard)
        summary = AttachRunner(session, prompts, on_stall=args.on_stall, logger=log).run()
        log("[summary] %s" % summary)
        for r in summary["results"]:
            log("  prompt %d: %s" % (r["index"], r["status"]))
    finally:
        if args.kill:
            if target is not None:
                log("[cleanup] killing throwaway target")
                target.kill()
            elif args.pid:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(args.pid)],
                               capture_output=True)
            shutil.rmtree(workdir, ignore_errors=True)
        elif target is not None:
            log("[cleanup] leaving throwaway session RUNNING (pid=%d); use --kill to stop it"
                % target.pid)
        guard.unlink(missing_ok=True)

    if summary is None:
        return 1
    return 0 if summary["completed"] == summary["total"] and not summary["aborted"] else 1


if __name__ == "__main__":
    sys.exit(main())
