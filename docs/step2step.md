# step2step — Claude Code and Codex control

Codex CLI control is available separately through `step2step.codex`, using ChatGPT
subscription login and the official app-server protocol. See the
[Codex control guide](codex-control.md) for Python/CLI examples, capabilities,
and live verification. Claude Code control lives in `step2step.claude`; select the
product explicitly when importing or invoking a CLI. Shared contracts are in
`step2step.contracts`, prompt parsing in `step2step.prompts`, and product-independent
PTY, screen rendering, and Windows console I/O in `step2step.terminal`.
The PTY, hook, model picker, and attach sections below describe the Claude backend.

**Breaking module migration:** `step2step.core` and `step2step.attach` have been
removed. Import Claude APIs from `step2step.claude` and use
`python -m step2step.claude` or the `step2step-claude` console script. The former
root Claude exports and `step2step` CLI are removed; the root package now exposes
only shared contracts and prompt utilities. In particular, root `ModelState` is
the neutral contract; Claude model alias matching lives in `step2step.claude.ModelState`.
Codex imports and CLI are unchanged.

Programmatically drive a **fresh interactive Claude Code session**: inject
pre-defined prompts one by one, wait for each to finish, then send the next —
fully hands-off, **without ever using `claude -p`** (the interactive TUI runs on
your subscription; `-p` is intentionally avoided). It spawns the `claude` CLI
inside a pseudo-terminal (ConPTY via pywinpty on Windows; a POSIX pty via
ptyprocess on macOS/Linux), "types" each prompt via bracketed paste, and
detects turn completion via an injected `Stop` hook.

Designed to be called as a **module** so a larger orchestrator (such as the unit
loop in `barrel/core`) can run prompt sequences and react to the results.

## Two modes (caller's choice)

| mode | launch | per-prompt behavior | completion signal |
|------|--------|---------------------|-------------------|
| **`bypass`** (default) | `--dangerously-skip-permissions` | execute directly, hands-off | `Stop` hook |
| **`plan`** | `--dangerously-skip-permissions`, then `shift+tab` → plan mode | Claude **plans**, runner **auto-approves** (option 1, "Yes, and bypass permissions"), then it executes | approval menu (screen) → then `Stop` hook for the execution |

Both are verified end to end (Claude Code v2.1.195 and re-verified on **v2.1.215**,
Python 3.12, Windows 11; the POSIX backend re-verified on **v2.1.227**, Python
3.13, macOS 15 — same screen markers, no re-calibration needed). In plan mode the
runner re-enters plan mode before each prompt (approving returns the session to
bypass mode), so every step is planned + auto-approved + executed.

> Note: `--dangerously-skip-permissions` **and** `--permission-mode plan` as flags
> can't be combined — skip-permissions always wins. Plan mode is therefore
> reached at runtime with `shift+tab`, exactly as a user would.

## Setup

Python 3.12+ (3.13 recommended).

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt       # ptyprocess, pyte
.venv/bin/python -m pip install -r requirements-dev.txt   # + pytest (tests)
```

```powershell
# Windows
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt       # pywinpty, pyte
.\.venv\Scripts\python -m pip install -r requirements-dev.txt   # + pytest (tests)
```

## Tests

```bash
# macOS / Linux
.venv/bin/python -m pytest tests -m 'not live'         # step2step unit suite (no Claude session, ~0 cost)
STEP2STEP_LIVE=1 .venv/bin/python -m pytest tests -m live    # opt-in live smoke
```

```powershell
# Windows
.\.venv\Scripts\python -m pytest tests -m "not live"  # step2step unit suite (no Claude session, ~0 cost)
$env:STEP2STEP_LIVE=1; .\.venv\Scripts\python -m pytest tests -m live   # opt-in live smoke
```

The unit suite (`tests/`) covers prompt parsing, the Stop-hook watcher, screen
predicates (working/mode/approval + the numbered-list and footer regressions),
dialog classification against **real captured screens**
(`tests/fixtures/screens/`), the stall-policy matrix, env scrubbing, transcript
parsing, attach safety, key-record encoding, and the `/model` picker parser plus
its closed-loop navigation (including that no failing path ever writes a commit
key). Live tests
are skipped unless `STEP2STEP_LIVE=1` and default to `haiku` (override with
`STEP2STEP_MODEL`); the mid-session model-switch smoke additionally needs
`STEP2STEP_LIVE_MODEL_CONTROL=1` and asserts your `~/.claude/settings.json` is
byte-identical afterwards.

## Use as a module (primary API)

```python
from step2step.claude import run_session, load_prompts

prompts = load_prompts("prompts.md")          # split on `---` lines
result = run_session(prompts, "test-folder", mode="plan")   # or mode="bypass"

# result = {
#   "mode": "plan", "session_id": "...", "workdir": "...",
#   "transcript": ".../<sid>.jsonl" or None,   # clean JSONL if Claude persisted it
#   "total": 2, "completed": 2, "aborted": False,
#   "results": [{"index": 1, "status": "approved+signal", "signal_lines": 1,
#                "response": "…assistant text…", "tools": ["Write"]}, ...]
# }
for r in result["results"]:
    print(r["index"], r["status"], "->", r["response"][:60])
```

`run_session(prompts, workdir, *, mode="bypass", on_stall="pause", claude_exe=None,
extra_args=None, send_mode="paste", hook_form="args", model=None, effort=None,
app_dir=None, logger=None, on_turn=None)` — `prompts` is a list of strings.
Per-prompt `status` is one of `signal`, `idle-fallback`, `approved+signal` (plan
mode), `skipped`, `aborted`, `eof`. Each result also carries the turn's clean
`response` text and the `tools` the assistant used (e.g. `AskUserQuestion`,
`ExitPlanMode`).

- `model` / `effort`: the session's model and reasoning effort (`--model` /
  `--effort`). See **Model and effort** below.
- `extra_args`: forwarded to `claude` (e.g. `["--model", "haiku"]`). A
  `--model`/`--effort` here wins over the `model=`/`effort=` arguments.
- `on_turn`: callback `on_turn(rec)` fired after each turn with the per-turn dict —
  a calling harness can answer a question or branch without waiting for the run.
- `on_stall`: `"pause" | "skip" | "abort"`. **A headless caller should use `skip`
  or `abort`** — `pause` cannot prompt and falls back to abort.
- Response capture helpers: `from step2step.claude import find_transcript, parse_transcript,
  turn_asks_question` parse the JSONL transcript into per-turn `{prompt, response,
  tools}` — the basis for a planning/Q&A loop.

## Use from the CLI

```bash
# macOS / Linux — preview how a file splits into prompts (0 cost, no Claude):
.venv/bin/python -m step2step.claude --list --prompts prompts.md

# bypass mode (default):
.venv/bin/python -m step2step.claude --workdir test-folder --prompts prompts.md

# plan mode with auto-approve:
.venv/bin/python -m step2step.claude --mode plan --workdir test-folder --prompts prompts.md
```

```powershell
# Windows equivalents:
.\.venv\Scripts\python -m step2step.claude --list --prompts prompts.md
.\.venv\Scripts\python -m step2step.claude --workdir test-folder --prompts prompts.md
.\.venv\Scripts\python -m step2step.claude --mode plan --workdir test-folder --prompts prompts.md
```

| flag | default | meaning |
|------|---------|---------|
| `--workdir <dir>` | (required) | directory Claude runs in (created if missing) |
| `--prompts <file>` | (required) | the prompts markdown |
| `--mode bypass\|plan` | `bypass` | execution mode (see table above) |
| `--model <name>` | (claude's default) | model alias (`haiku`/`sonnet`/`opus`/`fable`) or full name |
| `--effort <level>` | (your global default) | `low\|medium\|high\|xhigh\|max` |
| `--on-stall pause\|skip\|abort` | `pause` | what to do if a turn stalls |
| `--send-mode paste\|plain` | `paste` | how prompt text is entered (paste handles multi-line) |
| `--hook-form args\|shell` | `args` | how the Stop hook is invoked |
| `--claude <path>` | auto | path to `claude.exe` |
| `--list` | – | parse & print the prompts, then exit |

### Prompts file format

Plain markdown; prompts separated by a line containing only `---`:

```
First prompt, can span
multiple lines.
---
Second prompt.
```

A leading YAML frontmatter block (genuine `key:` lines) is skipped; `---` inside
fenced code blocks (```` ``` ````/`~~~`) is kept, not treated as a separator.

## Model and effort

A session's model and reasoning effort can be set at launch, or changed
mid-session by driving the `/model` picker exactly as a person would — arrow up
and down between models, left and right across effort levels.

```python
from step2step.claude import SessionHandle

# At launch: cheap, deterministic, no TUI involved. Prefer this.
h = SessionHandle.start(workdir="proj", model="sonnet", effort="low")
h.run_turn("do the easy part")

# Mid-session, keeping the conversation: opens /model, navigates, verifies,
# commits with 's' ("use this session only").
h.set_model("opus")
h.model_state()          # ModelState(model='claude-opus-5', …, source='transcript')
h.available_models()     # read the picker's rows and Esc out; never commits
```

**Prefer the launch flags.** A mid-session change makes Claude re-read the whole
conversation on the next turn (the TUI says so: *"the full history gets re-read
on your next message"*), which on a long session is a real cost. `set_model`
short-circuits and sends no keys at all when the session already matches.

### What touches your global config, and what doesn't

`/model`'s `Enter` means "set as default" and rewrites `model` in your
`~/.claude/settings.json`; `s` means "use this session only". Measured on
2.1.220 by reading those keys before and after every keystroke:

| how | your global `model` | your global `effortLevel` |
|-----|--------------------|---------------------------|
| `--model` / `--effort` at launch | not written | not written |
| `set_model(m)` → picker + `s` | **not written** | **not written** |
| `set_model(m, effort=e, persist=True)` | not written | **written** |
| `set_model(m, persist=True)` → `/model <m>` | **written** | not written |
| `set_effort(e)` → `/effort <e>` | not written | **written** |

So `set_model()` defaults to `persist=False` and is safe. **Effort is different:
every mid-session path writes the global `effortLevel`** — even the picker's
"this session only" commit — so `set_model(..., effort=...)` and `set_effort()`
require `persist=True` and raise otherwise. For a session-scoped effort, pass
`effort=` to `start()`.

### Safety of the navigation

This is the one place the module injects keys into a TUI menu (the
AskUserQuestion path deliberately does not; see the questions/autopilot guide).
It is safe here because nothing is committed until it has been re-verified:
before pressing `s`, the driver re-reads the dialog and requires the highlighted
row to be the requested model and the effort widget to read the requested level.
Every failure — arrows ignored, dialog vanished, a turn completing underneath
it, an AskUserQuestion menu appearing, an ambiguous model name, an unreadable
highlight — presses `Esc` and raises `ModelControlError` with the stage and the
screen tail. No path that fails verification ever writes a commit key.

Re-tune the markers after a Claude Code upgrade with
`python -m step2step.claude.calibrate_model <throwaway-dir>`; it drives the whole
picker, dumps the screen plus style flags at every keystroke, and restores your
global settings afterwards.

## Attach to an already-running session (experimental, Windows-only)

Besides spawning + owning a session, step2step can **attach to a Claude session it
did *not* launch** and drive it by injecting keystrokes into its console
(`AttachConsole` + `WriteConsoleInput`) and reading the screen back
(`ReadConsoleOutputCharacter`). Works under both classic **conhost** and **Windows
Terminal (ConPTY)**. Bypass only; completion is detected from the screen
(working → idle edge), since a `Stop` hook can't be injected into a foreign session.

```powershell
# attach to an existing session (refuses your own session / non-claude PIDs):
.\.venv\Scripts\python -m step2step.claude.attach.attach_runner --pid <PID> --prompts prompts.md

# testing/demo: launch a throwaway session, attach to it, then clean up:
.\.venv\Scripts\python -m step2step.claude.attach.attach_runner --launch conhost --kill
.\.venv\Scripts\python -m step2step.claude.attach.attach_runner --launch wt --prompts prompts.md
```

Safety: it only ever attaches to a PID it launched (`--launch`, via new-pid-diff) or
a PID you pass that is a live `claude.exe` and **not your own session** (self/ancestor
refused). The mechanism, measured key encodings, and limitations are recorded in
the **external-injection-findings** document (the attach-mode PoC log; see the
docs index).

## Layout

```text
step2step/
  __init__.py       shared contracts and prompt utilities; no default product
  contracts.py      SessionControl and shared result/state types
  prompts.py        product-independent markdown prompt parsing
  refusal.py        safeguard-refusal phrase detection (a signal, not a verdict)
  paths.py          REPO_ROOT / RUNTIME_DIR
  claude/           Claude Code PTY session, hooks, transcript and TUI policy
    __main__.py       python -m step2step.claude / step2step-claude
    runner.py         batch state machine, stall policy, budgets, dialog loops
    session.py        incremental SessionHandle and Claude ModelState
    watchdog.py       read-only SessionWatchdog (died / usage limit / dialog / stagnation)
    screen.py         Claude TUI markers and dialog/model parsing
    hooks.py          Claude hook settings and event watchers
    transcript.py     Claude JSONL parsing
    calibrate*.py     Claude screen/model/dialog calibration tools
    attach/           Claude AttachRunner, target launch and experiment tools
  codex/            Codex app-server transport, events, session and CLI
  terminal/         product-independent terminal primitives
    pty_session.py    owned PTY, reader thread, writes and process cleanup
    screen.py         pyte rendering and row style inspection
    attach/           Windows console I/O; imported only when used
      winconsole.py     attach, key records, screen scrape, guard and run_op CLI
      session.py        ExternalSession: lifecycle, type/key/backspace, screen
      uia_reader.py     optional UIA screen reader
      probe.py          dummy-console smoke test, independent of AI products
tests/              step2step unit suite and opt-in live tests
runtime/            generated settings, hook scripts, signals and logs
```

## How it works

1. **Spawn** `claude.exe` in a ConPTY with `--session-id <uuid> --settings
   <generated.json> --dangerously-skip-permissions`, `cwd = workdir`. No `-p`.
2. **Stop hook (injected, deterministic)** — the generated settings register a
   `Stop` hook that appends a line to a per-run signal file each time a turn ends.
   The runner records the count before submitting and waits for it to increase.
3. **bypass**: inject prompt (bracketed paste) → submit → wait for the Stop
   signal (adaptive stall watchdog avoids killing slow turns).
4. **plan**: `shift+tab` until the footer shows `plan mode on` → inject prompt →
   wait for the **approval menu** (the Stop hook does *not* fire there) →
   auto-approve by selecting option 1 ("Yes, and bypass permissions" for a
   --dangerously-skip-permissions launch) → wait for the execution turn's Stop
   signal.
5. **On stall** (`--on-stall`, default `pause`): `skip` advances to the next
   prompt (honored even headless); `abort` stops the run; `pause` lets you take
   over on an interactive terminal (`a/w/s/t`) and falls back to abort with no TTY.
   Every wait is finite: a turn budget (`DEFAULT_TURN_TIMEOUT`, 2h) ends a turn
   as a stall in batch mode and as `DEADLINE_EXCEEDED` in `SessionHandle`, and
   a turn whose output keeps flowing while nothing progresses (transcript, hook
   events, worktree) ends as `NOISY_STAGNATION`. `SessionHandle` also confirms
   the prompt actually started and reports `SUBMIT_FAILED` instead of recycling
   the previous response.
6. **Shutdown**: interrupt post-turn work (ESC) until idle, then a tight Ctrl-C
   pair (force-terminate as last resort).

## Findings & honest limitations

- Driving the TUI is **not an officially supported integration**; completion
  rests on the documented `Stop` hook, but screen-dependent parts (mode/idle/
  approval detection) live in `step2step.claude.screen` and may need re-tuning
  across Claude versions — use `python -m step2step.claude.calibrate <throwaway-dir>`,
  and `python -m step2step.claude.calibrate_dialogs <throwaway-dir>` for the two
  interactive dialogs.
- **A waiting dialog is detected from the screen, not the transcript.** A pending
  `AskUserQuestion`/`ExitPlanMode` `tool_use` may be absent from the session JSONL
  for as long as it waits, then written back with its original timestamp once it
  resolves (measured on 2.1.224–225; one session showed 0 matching rows for 7.5
  hours). `transcript.pending_tool_use()` is therefore an auditing tool —
  `screen.classify_dialog()` is what a live caller asks.
- **Clean JSONL transcript**: on the current Claude Code (verified 2.1.215) these
  PTY-driven sessions DO persist `~/.claude/projects/**/<sid>.jsonl` — copied to
  `runtime/transcript-*.jsonl` and surfaced as `result["transcript"]`. The raw PTY
  log (`runtime/pty-*.log`, rotated to `.log.1`/`.log.2` every 50 MB so the tail
  of a long session is never lost) is the always-present fallback. The core
  `transcript` module parses either into per-turn `{prompt, response, tools}`.
- **Answering dialogs is a verified closed loop.** `answer_menu`, `approve_plan`
  and `reject_plan` press arrows one at a time, read the highlight back, commit
  only on a verified target row, and confirm the dialog went away; never a digit,
  never a second Enter. Verified live on 2.1.272 for `answer_menu` and
  `approve_plan` (`python -m step2step.claude.calibrate_dialogs <dir> --answer`);
  multi-question widgets are refused (`UnsupportedOperation`) until calibrated.
- **Boot handles the 2.1.272 trust menu.** With `--dangerously-skip-permissions`
  the workspace-trust dialog now appears as a two-row select whose default is
  "No, exit"; the runner arrows onto "Yes, I trust this folder" and verifies the
  highlight before Enter (a blind Enter exits the session).
- After each turn Claude runs **auto-memory** (creates `memory/` under
  `~/.claude/projects/<slug>/`); the runner waits it out before exiting.
- Plan mode is slower than bypass (each step plans + approves + executes).
- Prompts that are slash commands (start with `/`) aren't handled specially; the
  approval auto-select assumes option 1 (the highlighted "Yes, …" proceed choice)
  is the default — verified for the --dangerously-skip-permissions launch.

## Cost

Every spawned session is the **interactive** Claude TUI on your subscription
(never `-p`).

## Platform support

- **macOS / Linux** — full support for the spawn-and-own path (step2step core,
  the unit loop, calibration, model control) via `ptyprocess`. The experimental
  `attach/` subsystem is Windows-only (Win32 console APIs have no POSIX
  equivalent) and its tests are skipped off Windows.
- **Windows** — the original platform; ConPTY via `pywinpty`, everything
  including attach mode.
