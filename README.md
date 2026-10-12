# Barrel

Barrel is being rebuilt as a skill for Claude Code and Codex. Invoking the skill
changes how the coding agent works:

- The orchestrating session does not carry the project context in its own
  conversation. Each session is used only as a brain; the context lives in
  documents that every session reads, so the orchestrator can be restarted
  whenever needed.
- Before any real work starts, it draws out precise requirements and
  specifications from the user, so the result matches the user's intent.
- It splits the work into a topic tree and orchestrates both subagents and
  fresh coding-agent sessions, giving each one only the context its task needs.
- It keeps working until the result is aligned with that intent.

**Status (2026-10-06):** the direction is set; the design is not yet confirmed
and no skill code exists. Until 2026-10-06 this repository built the product
as a standalone desktop app (Rust/Tauri) that drove Claude
Code and Codex from outside. That work is preserved on the
`archive/tauri-desktop-app` branch of the previous repository. This
repository, `Agent-Barrel/Skill-Barrel`, started on 2026-10-12 from that
repository's files, without its history.

## Start here

[docs/plan/README.md](docs/plan/README.md) records the request for this
direction, the original product flow, the working principles, the
2026-09-29 skill/plugin draft and where it conflicts with the latest request,
and the next steps. [docs/README.md](docs/README.md) indexes the rest of the
documentation.

## What is in this repository

| Path | Role |
| --- | --- |
| `step2step/` | Drives a fresh interactive Claude Code session through a PTY (never `claude -p`) and Codex through its app-server. See [docs/step2step.md](docs/step2step.md) and [docs/codex-control.md](docs/codex-control.md). |
| `barrel/core/` | The unit loop: runs a roadmap of units, one fresh step2step session per unit, with deterministic gates, failure classification, an escalation ladder, and budgets. |
| `orchestration/drivers/` | Command-line drivers for the unit loop and for single worker sessions. See [orchestration/README.md](orchestration/README.md). |
| `docs/archive/` | The desktop app's planning documents, kept for reference. |

## Setup

Python 3.12+ (3.13 recommended).

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt   # ptyprocess, pyte, pyyaml, pytest
```

```powershell
# Windows
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt   # pywinpty, pyte, pyyaml, pytest
```

## Tests

```bash
# macOS / Linux
.venv/bin/python -m pytest tests barrel/tests -m 'not live'    # no CLI session, ~0 cost
STEP2STEP_LIVE=1 .venv/bin/python -m pytest tests -m live       # opt-in live smoke
```

```powershell
# Windows
.\.venv\Scripts\python -m pytest tests barrel/tests -m "not live"
$env:STEP2STEP_LIVE=1; .\.venv\Scripts\python -m pytest tests -m live
```

Live-test options are described in [docs/step2step.md](docs/step2step.md#tests)
for Claude Code and in [docs/codex-control.md](docs/codex-control.md) for Codex.
