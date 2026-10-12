"""V3 probe: does interactive `claude --append-system-prompt` take effect?

Spawns a haiku session with an appended system instruction defining a secret
token, asks for the token, and checks the response. Exit 0 = V3 OK.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from step2step.claude import run_session  # noqa: E402

workdir = REPO / "test-folder" / "v3probe"
workdir.mkdir(parents=True, exist_ok=True)

res = run_session(
    ["What is your reply token? Reply with the token only."],
    str(workdir),
    mode="bypass",
    on_stall="skip",
    app_dir=str(REPO / "orchestration" / "app_dirs" / "w0-v3"),
    extra_args=[
        "--model", "haiku",
        "--append-system-prompt",
        "When asked for your reply token, reply with exactly: BARREL_V3_OK",
    ],
)
resp = (res["results"][0].get("response") or "") if res["results"] else ""
ok = "BARREL_V3_OK" in resp
print(f"V3_PROBE ok={ok} status={res['results'][0]['status'] if res['results'] else 'none'}")
print(resp[:300])
sys.exit(0 if ok else 1)
