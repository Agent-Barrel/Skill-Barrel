"""Generic worker driver: spawn one Claude Code worker session via step2step.

Usage:
    .venv/bin/python orchestration/drivers/run_worker.py <worker-name> [--model MODEL]
    (Windows: .venv\\Scripts\\python)

Reads prompts from   orchestration/prompts/<worker-name>.md   (split on `---` lines),
runs the session in the worktree configured in WORKERS (fix-* workers run in the
main repo), logs turn-by-turn to orchestration/logs/<worker-name>.log, and writes
the run_session result dict to orchestration/results/<worker-name>.json.

Exit 0 iff every prompt completed and the run was not aborted.
"""
import io
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from step2step.claude import load_prompts, run_session  # noqa: E402

# Worktree root for the overnight-build workers. The original build ran on a
# dedicated Windows box; override with S2S_WT_ROOT anywhere else.
WT = Path(os.environ.get("S2S_WT_ROOT", r"C:\Users\user\Desktop\Projects\s2s-wt"))

WORKERS = {
    "w1-session-handle": {"workdir": WT / "wt-substrate", "model": "claude-fable-5"},
    "w2-barrel-core": {"workdir": WT / "wt-barrel", "model": "claude-opus-5"},
    "w3-web": {"workdir": WT / "wt-web", "model": "claude-opus-5"},
    "w4-pipeline": {"workdir": WT / "wt-pipeline", "model": "claude-opus-5"},
    "w5-runtime": {"workdir": WT / "wt-runtime", "model": "claude-fable-5"},
    "w6-maintenance": {"workdir": WT / "wt-maint", "model": "claude-opus-5"},
    "w7-docs": {"workdir": WT / "wt-docs", "model": "claude-opus-5"},
}


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    name = sys.argv[1]
    cfg = dict(WORKERS.get(name) or {"workdir": REPO, "model": "claude-opus-5"})
    if "--model" in sys.argv:
        cfg["model"] = sys.argv[sys.argv.index("--model") + 1]

    prompts = load_prompts(str(REPO / "orchestration" / "prompts" / f"{name}.md"))
    for d in ("logs", "results", "app_dirs"):
        (REPO / "orchestration" / d).mkdir(parents=True, exist_ok=True)
    logf = open(REPO / "orchestration" / "logs" / f"{name}.log", "a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    def on_turn(rec: dict) -> None:
        resp = (rec.get("response") or "").replace("\r", "")[:800]
        log(f"TURN {rec['index']} status={rec['status']} tools={rec.get('tools')}\n{resp}\n---")

    log(f"START worker={name} model={cfg['model']} workdir={cfg['workdir']} prompts={len(prompts)}")
    res = run_session(
        prompts,
        str(cfg["workdir"]),
        mode="bypass",
        on_stall="skip",
        app_dir=str(REPO / "orchestration" / "app_dirs" / name),
        extra_args=["--model", cfg["model"]],
        logger=lambda m: (logf.write(str(m) + "\n"), logf.flush()),
        on_turn=on_turn,
    )
    out = REPO / "orchestration" / "results" / f"{name}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = (not res["aborted"]) and res["completed"] == res["total"]
    log(f"END completed={res['completed']}/{res['total']} aborted={res['aborted']} ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
