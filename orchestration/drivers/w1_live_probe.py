"""W1 live probe: incremental two-turn conversation through SessionHandle.

Run with PYTHONPATH pointing at the tree under test (worktree before merge):
    PYTHONPATH=C:/Users/user/Desktop/Projects/s2s-wt/wt-substrate \
        .venv/bin/python orchestration/drivers/w1_live_probe.py
Exit 0 = start/send/wait/stop plus cross-turn memory verified on haiku.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
tree = os.environ.get("PYTHONPATH", str(REPO)).split(os.pathsep)[0]
sys.path.insert(0, tree)

from step2step.claude.session import SessionHandle, TurnOutcome  # noqa: E402

workdir = REPO / "test-folder" / "w1probe"
workdir.mkdir(parents=True, exist_ok=True)

print(f"probe tree={tree}")
handle = SessionHandle.start(
    workdir=str(workdir),
    model="haiku",
    app_dir=str(REPO / "orchestration" / "app_dirs" / "w1probe"),
)
try:
    r1 = handle.run_turn("Reply with exactly this word and nothing else: PING")
    print("turn1:", r1.outcome, repr((r1.response or "")[:120]))
    ok1 = r1.outcome in (TurnOutcome.COMPLETED, TurnOutcome.COMPLETED_IDLE) and "PING" in (r1.response or "")
    r2 = handle.run_turn("What single word did you reply in your previous message? Answer with that word only.")
    print("turn2:", r2.outcome, repr((r2.response or "")[:120]))
    ok2 = r2.outcome in (TurnOutcome.COMPLETED, TurnOutcome.COMPLETED_IDLE) and "PING" in (r2.response or "")
finally:
    handle.stop()

print(f"W1_PROBE ok1={ok1} ok2={ok2}")
sys.exit(0 if (ok1 and ok2) else 1)
