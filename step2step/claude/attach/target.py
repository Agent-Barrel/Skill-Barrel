"""Launch a THROWAWAY Claude Code session in its own console to act as the
"already-running external session" the harness attaches to.

Two host variants (the plan tests both equally):
  * conhost : `conhost.exe <claude> ...`  -> forces classic Windows Console Host
  * wt      : `wt.exe -w new <claude> ...` -> forces Windows Terminal (ConPTY)

SAFETY (the user's hard constraint: never touch the real running session):
The target PID is found by DIFFING claude.exe PIDs before/after our launch, so we
can only ever select a process that did NOT exist beforehand. Every pre-existing
session (the user's live one, the desktop app, the VS Code extension) is in the
"before" set and therefore excluded by construction. We additionally require the
new process's parent to be a console host (conhost/OpenConsole/WindowsTerminal),
which pins us to the TUI process rather than a helper child.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import time
import uuid

from ..runner import child_env, resolve_claude
from ...paths import RUNTIME_DIR

RUNTIME = RUNTIME_DIR
HOST_NAMES = {"conhost.exe", "openconsole.exe", "windowsterminal.exe"}


def _all_procs() -> dict[int, dict]:
    """pid -> {ppid, name, cmd} for every process (one CIM call). `cmd` is the
    full command line (used to positively identify our launched target)."""
    out = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process | "
         "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    try:
        data = json.loads(out)
    except Exception:
        return {}
    if isinstance(data, dict):
        data = [data]
    procs = {}
    for p in data:
        try:
            procs[int(p["ProcessId"])] = {
                "ppid": int(p["ParentProcessId"]),
                "name": (p.get("Name") or "").lower(),
                "cmd": p.get("CommandLine") or "",
            }
        except Exception:
            pass
    return procs


def _claude_pids(procs: dict[int, dict]) -> set[int]:
    return {pid for pid, i in procs.items() if i["name"] == "claude.exe"}


class Target:
    def __init__(self, pid: int, host: str, launcher_pid: int, workdir: pathlib.Path):
        self.pid = pid
        self.host = host
        self.launcher_pid = launcher_pid
        self.workdir = workdir

    def kill(self) -> None:
        for pid in (self.pid, self.launcher_pid):
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True)
            except Exception:
                pass


def launch(host: str, workdir: pathlib.Path, guard_file: pathlib.Path,
           claude_exe: str | None = None, extra_args=None, wait: float = 25.0,
           logger=print) -> Target:
    """Launch a throwaway Claude under `host` and return the sanctioned Target.
    Writes the detected PID to `guard_file` (the only PID winconsole may attach).

    The target is identified positively by a unique per-launch marker passed as
    --session-id and matched in the new process's command line, so a session the
    user happens to start during the detection window can never be selected --
    this closes the new-pid-diff race. `extra_args` are forwarded to claude (e.g.
    ["--model", "haiku"])."""
    claude_exe = resolve_claude(claude_exe)
    workdir.mkdir(parents=True, exist_ok=True)
    # Canonical UUID (with hyphens): --session-id requires that exact form, and it
    # is unique enough to positively identify the target in its command line. A
    # bare hex (uuid4().hex) is rejected by claude and the process exits at once.
    marker = str(uuid.uuid4())
    args = [claude_exe, "--dangerously-skip-permissions",
            "--session-id", marker, *(extra_args or [])]

    if host == "conhost":
        argv = ["conhost.exe", *args]
    elif host == "wt":
        argv = ["wt.exe", "-w", "new", "--title", "step2step-ext", *args]
    else:
        raise ValueError("host must be 'conhost' or 'wt', got %r" % host)

    before = _claude_pids(_all_procs())
    logger("[target/%s] launching: %s" % (host, " ".join(argv)))
    logger("[target/%s] cwd=%s marker=%s (%d claude.exe already running, all excluded)"
           % (host, workdir, marker, len(before)))
    proc = subprocess.Popen(argv, cwd=str(workdir), env=child_env())

    # Poll for the NEW claude.exe that carries our unique marker in its command
    # line. Only if command lines are unreadable (rare: access-denied) do we fall
    # back to a host-parented new pid -- never to an arbitrary new claude.
    target_pid = None
    end = time.monotonic() + wait
    while time.monotonic() < end and target_pid is None:
        time.sleep(0.5)
        procs = _all_procs()
        new = _claude_pids(procs) - before
        marked = [pid for pid in new if marker in procs.get(pid, {}).get("cmd", "")]
        if marked:
            target_pid = sorted(marked)[0]
            break
        hosted = [pid for pid in new
                  if not procs.get(pid, {}).get("cmd")  # only when cmd is hidden
                  and procs.get(procs[pid]["ppid"], {}).get("name") in HOST_NAMES]
        if hosted:
            target_pid = sorted(hosted)[0]
            break

    if target_pid is None:
        try:
            proc.kill()
        except Exception:
            pass
        raise RuntimeError("could not detect our launched claude.exe within %ss "
                           "(marker=%s)" % (wait, marker))

    info = _all_procs().get(target_pid, {})
    guard_file.write_text(str(target_pid), encoding="utf-8")
    logger("[target/%s] detected throwaway claude PID=%d (parent=%s) -> sanctioned"
           % (host, target_pid, info.get("ppid")))
    return Target(target_pid, host, proc.pid, workdir)


if __name__ == "__main__":
    # Smoke: launch, print PID, wait a few seconds, kill. (For manual checking.)
    import sys
    h = sys.argv[1] if len(sys.argv) > 1 else "conhost"
    RUNTIME.mkdir(exist_ok=True)
    g = RUNTIME / "attach-target.pid"
    t = launch(h, RUNTIME / "_ext_target_wd", g)
    print("launched", t.pid, "under", h, "- sleeping 6s then killing")
    time.sleep(6)
    t.kill()
    print("killed")
