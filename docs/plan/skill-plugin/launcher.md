# Launcher

The launcher is the one Barrel process on a PC (Q11). It owns:
- every session it starts (Q03-3, Q04-2)
- the single Slack Socket Mode connection (Q11)
- the PC views (Q10-2)
- the event log (Q10 default)
- the choice of engine and account for every session, across all projects and runs (Q11, Q12, Q16)
- each project's memory queue, which also does the git work in the integration worktrees ([memory.md](memory.md#queue)) (Q24)
- the writes to shared memory ([memory.md](memory.md#shared)) (AI)
- Barrel's own updates ([updates](#versions)) (Q21)

It is built on `step2step`: Claude Code runs in a PTY, Codex through app-server (Q04-2). `claude --bg` stays an option for Claude, not a requirement (Q04-2).

<a id="process"></a>
## Process

- **Install.** The launcher is installed once per PC as the `barrel` command ([plugin.md](plugin.md#install)).
- **Dependencies:**
  - Python 3.12 or later.
  - What `step2step` already needs.
  - `slack_sdk`, whose built-in Socket Mode client needs no third-party package (AI; [research.md](research.md#vendors)).
- **Start.**
  - The invoking session starts the launcher detached from itself, so it survives that session (Q03-3).
  - The skill, Barrel.app and every `barrel` command except `barrel setup` start the launcher when it is not running (AI). Setup runs without it and starts it as its last step ([plugin.md](plugin.md#setup)).
- **Never at login, never resident on its own** (Q22-2). Barrel is a skill, so the launcher is not a login item.
  - It runs while it has runs to drive, including stopped runs, runs waiting for a merge, and cancelled runs waiting for keep or discard.
  - When no project has such a run, it exits after a short idle time (AI). The next skill, Barrel.app or `barrel` command starts it again.
- **The launchd fallback** (Q11 option text; Q22-2). The spike may show that a detached launcher does not survive, or that it inherits a Codex invoking session's sandbox (no network, limited writes) ([validation.md](validation.md) item 1). Then the launcher runs as a launchd job instead (details AI; spike):
  - The job's plist lives in `~/.barrel/launchd/`. It is never put in `~/Library/LaunchAgents`, because launchd loads every agent there at login.
  - Barrel loads the job with `launchctl bootstrap` and starts it with `launchctl kickstart` when it starts the launcher. So it never starts at login and is not a login item.
  - launchd never restarts it. The plist sets neither `RunAtLoad` nor `KeepAlive`; `KeepAlive.SuccessfulExit` would even imply `RunAtLoad` (launchd.plist(5)). After a crash, the launcher waits, like a detached one, until the skill, Barrel.app or a `barrel` command starts it (Q22-2: "재부팅이나 장애 뒤에는 이 중 하나를 실행할 때까지").
- **Lower priority** (archived D-016). Barrel shares the user's everyday Mac. The launcher starts every session and every gate command at a lower scheduling priority, so the user's own apps stay responsive (method AI, for example `taskpolicy` or `nice`; spike).
- **One per PC.** A lock file in `~/.barrel/` keeps a second launcher from starting (AI).
- **Restart** (AI).
  - **Detached:** nothing watches the launcher. It starts again the next time the skill, Barrel.app or a `barrel` command runs, and the runs wait until then (Q22-2; AI default 1).
  - **As a launchd job:** the same. launchd neither restarts it nor starts it at login.
  - **After a restart**, the launcher:
    1. reconciles what was in flight ([recovery](#recovery))
    2. posts that it restarted (Q10 default), unless the restart was an update, which stays silent (Q21)
    3. resumes the runs that were running; runs the user stopped stay stopped, and cancelled runs stay cancelled (archived Q-007, Q-009; AI)
- **Sessions are its children** (AI). If the launcher dies, the sessions of every project end with it. The restart resumes them from files exactly like [resume](#stop), after the [recovery](#recovery) steps.
- **Threads.** Each Codex session is driven from its own thread, because step2step's Codex handle accepts calls that change or wait on the session only from the thread that created it (`step2step/codex/session.py:167-171`).

<a id="sleep"></a>
- **Sleep** (archived D-047; Q17). The policy lives in `~/.barrel/settings.json`. The default is `ac` (AI). It can be changed with the Slack word "절전" ([slack.md](slack.md#commands)) or with `barrel settings sleep <policy>`.

  | Policy | While a run is active |
  | --- | --- |
  | `os` | Follow macOS |
  | `ac` | Prevent idle sleep while on power: `caffeinate -s -w <launcher pid>` |
  | `always` | Prevent idle sleep on battery too: `caffeinate -i -w <launcher pid>` |

  - The launcher starts `caffeinate` when the first run becomes active and stops it when no run is active. `-w` only makes sure it ends if the launcher dies (AI).
  - Display sleep and the lock screen are not affected (archived D-047).
  - Closing a laptop's lid still sleeps the Mac ([research.md](research.md#vendors)). On wake, the launcher reconnects to Slack, catches up on what was sent meanwhile ([recovery](#recovery)), and the sessions continue.

<a id="versions"></a>
## Updates and versions

From [Q21](../interview/q21-auto-update-consent.md), which replaced two archived decisions: the consent of D-058, and the pinned CLI of D-049 through Q17-2. Details AI where tagged.

- **No consent and no notice.**
  - Like Claude Code, Barrel compares its version with the latest one on its remote and updates itself when they differ.
  - Nothing goes to Slack. The launcher log and the event log record the update, as an event that is never routed to Slack (Q21).
- **When it checks** (AI, following Q21's "when it runs, like Claude Code"):
  - every time the skill runs (Q21: "스킬도 실행할 때")
  - when another `barrel` command runs, at most once every ten minutes
  - when the launcher starts
  - every six hours while the launcher runs
  - right after a CLI update breaks screen calibration, the reason Q17-2 asked for this
- **What it updates, together** (Q21 analysis): the launcher, with the sudo tool, and the Barrel plugin in every account folder, both the user's own folders and the Barrel-managed ones. So their versions never differ.
  - Claude: `claude plugin marketplace update <marketplace>`, then `claude plugin update barrel@<marketplace>`, with `CLAUDE_CONFIG_DIR` set to each folder. A running session keeps the old version until it restarts.
  - Codex: `codex plugin marketplace upgrade <marketplace>`, then the plugin is installed again, with `CODEX_HOME` set to each folder.
  - The launcher: `uv tool install` again, from the updated plugin folder.
  - These commands exist in the installed versions, Claude Code 2.1.301 and codex-cli 0.162.1 on 2026-10-16 ([research.md](research.md#environment)).
- **When it applies** (Q21 analysis):
  - It downloads the new version at once.
  - It swaps at a point with no running turn: the launcher stops starting new turns, waits for the running ones to end, updates, and restarts itself.
  - Then it resumes every run from files, as after a crash ([recovery](#recovery)).
  - The restart posts nothing (Q21).
- **The marketplace address** is the public repo [Agent-Barrel/Skill-Barrel](https://github.com/Agent-Barrel/Skill-Barrel), used from the start (Q17-2, Q21). If the repo moves again, the update check follows the move and registers the new address in each account folder (Q21 analysis).
- **The sudo tool** keeps its Keychain access only while its code signature stays the same (AI; spike).
  - Setup creates a local signing identity on this Mac and signs every new build of the tool with it, so updates keep the access ([plugin.md](plugin.md#install)).
  - If the access is lost anyway, a request asks the user to save the password again (Q20 analysis).

**Plugin markers** (AI):
- Each Barrel hook event writes a marker with the plugin version the first time it fires in a session ([plugin.md](plugin.md#trust)).
- A session is stopped in either of these cases:
  - its SessionStart or PreToolUse marker is missing
  - its account folder holds a different version than the launcher

  The launcher then updates that folder. If that fails, the account is marked unusable, and a request asks the user to run the skill again, which repeats setup.

**CLIs** (Q17-2; details AI):
- CLI updates cannot be stopped (Q17-2). The launcher logs each CLI's version for every session.
- A harness failure right after a version change triggers step2step's calibration check (`python -m step2step.claude.calibrate_dialogs`).
- If the check fails, Barrel looks for its own update at once (Q21). If no update fixes it, that CLI's options drop out of the tiers, and a notice without a mention is posted, since the user has nothing to do ([slack.md](slack.md#launcher-requests)).

<a id="commands"></a>
## Commands

Sessions, tools and the user talk to the launcher through the `barrel` command, which connects to `~/.barrel/launcher.sock`. That the launcher has a command comes from the Q10 default ("실행기 명령"). The command names are AI.

| Command | Called by | Does |
| --- | --- | --- |
| `barrel setup [--add-account]` | Invoking session | The setup steps after the command itself is installed; later, re-checks and adding an account ([plugin.md](plugin.md#setup)) |
| `barrel run start --repo <path> --input <file> --name <request name>` | Invoking session | Starts a new run, always (Q18; [runs.md](runs.md#start)) |
| `barrel view open [--project]` | Barrel.app, the invoking session, the Slack word "화면" | Starts the launcher if needed and opens the PC view ([pc-view.md](pc-view.md#reopen)) |
| `barrel task start\|approve\|reject\|answer\|review\|cancel <id>` | Orchestrator | Controls a leaf ([task-execution.md](task-execution.md#lifecycle); `cancel` in [workflow.md](workflow.md#cascade)). `start` only forces a leaf; the launcher starts ready leaves itself |
| `barrel session start --role <role> --input <files> --output <file>` | Orchestrator | Starts a fresh auxiliary session: a designer, an experiment, the Korean writer, or a subagent role whose engine is on another CLI ([sessions.md](sessions.md#roles)). Its output goes to the run state's `outputs/` or `experiments/` |
| `barrel memory begin` / `barrel memory end` | Orchestrator, fresh auxiliary sessions; task sessions call only `end` | Waits for the caller's turn in the project's memory queue. `end` hands the turn's changes to the launcher's check and commit, and frees the queue ([memory.md](memory.md#queue)) (Q24). A task session is queued by the launcher when it finishes |
| `barrel post --kind question\|review\|request\|report\|reply --file <md> [--unit <id>] [--task <id>] [--thread <post>] [--options <file>]` | Orchestrator | Posts to Slack, with option buttons when `--options` is given ([interviews.md](interviews.md#posting)) |
| `barrel event --type <type> --text <text>` | Orchestrator, task sessions | Adds an event to the log (Q10 default) |
| `barrel handoff --note <file>` | Orchestrator | Asks for a successor orchestrator. The note is a file in the orchestrator's run-state folder ([sessions.md](sessions.md#orchestrator)) |
| `barrel memory index [--repo <path>]` | Orchestrator, the user | Regenerates the uncommitted index files: in the integration worktree for the orchestrator, in the given repo or the current folder for the user ([memory.md](memory.md#index), [runs.md](runs.md#sharing)) |
| `barrel memory render --spec requirements\|features` | Orchestrator | Renders a spec from the units ([interviews.md](interviews.md#review)) |
| `barrel shared put\|disable\|delete …` | Orchestrator | Writes, disables or deletes an entry of shared memory, one writer at a time for the PC ([memory.md](memory.md#shared)) |
| `barrel secret ask <name> --reason <text>` | Orchestrator | Posts the request for a credential and opens the macOS input dialog on the Mac. The value goes to the Keychain under that name (Q20; [memory.md](memory.md#secrets)) |
| `barrel slack read --thread <post> \| --channel` | Orchestrator, task sessions | Reads Slack with the bot token, for Codex sessions when the official Slack MCP's OAuth does not work. The bot is only in Barrel's own channels, so it reads nothing else (spike fallback; [slack.md](slack.md#setup)) |
| `barrel secret set <name>` | The user | Stores a secret from a terminal; an option for developers (Q20) |
| `barrel secret run --env <VAR>=<name> … -- <command>` / `barrel secret capture <name> [--field <path>] -- <command>` | Task sessions | Runs a command with a secret in its environment, or stores a secret from a command's output, without the value ever reaching the session, for the names in its contract ([memory.md](memory.md#secrets)) |
| `barrel settings sleep os\|ac\|always` | The user | Sets the [sleep policy](#sleep) |
| `barrel project archive\|remove <id>` | The user, also through the skill | Archives a project, or removes its records ([runs.md](runs.md#archive)) (archived Q-020) |

- **No `instruct`.** The skill always starts a new run, and instructions to a running run come only from Slack (Q18). The 2026-10-11 design's `barrel instruct` is gone.
- **No terminal status command.** Status is in Slack and the PC view (Q10-2 default 4). The PC view is served by the launcher itself.
- **No terminal stop, resume or cancel** (AI). These are internal to the launcher: its Slack handler and the PC view call them, the places Q10, Q10-2 and Q17 give the user ([stop](#stop)).
- **No update command.** Updates are automatic (Q21).

<a id="access"></a>
### Who may call what (AI)

The launcher checks every command against the caller's role. Example: a task session must not approve its own plan or read a secret its contract does not list.

| Commands | Allowed callers |
| --- | --- |
| `setup`, `run start`, `secret set`, `settings sleep`, `project archive`, `project remove` | The user: any process that is not inside a Barrel session, including the invoking session |
| `view open` | Anyone |
| `memory index` | The orchestrator and the user |
| `task …`, `session start`, `post`, `handoff`, `memory render`, `shared …`, `secret ask` | The orchestrator. Its subagents run inside the same session, so this check cannot tell them apart; a hook denies every `barrel` command in subagent calls instead ([plugin.md](plugin.md#hooks)) |
| `memory begin` | The orchestrator and fresh auxiliary sessions, for their own turn |
| `memory end` | The orchestrator, task sessions and fresh auxiliary sessions, for their own turn |
| `event`, `slack read` | The orchestrator and task sessions |
| `secret run`, `secret capture` | Task sessions, for the names in their contract's `secrets` |

How the caller is identified:
- macOS reports the peer process of a Unix-socket connection (`LOCAL_PEERPID`). The launcher walks that process's ancestors up to the session it started, if there is one.
- Environment variables are not trusted for this, because an agent can change them (spike).

**A guard rail, not a security boundary.** The check stops a session from calling a command out of habit or by mistake.
- Every Barrel session runs with the user's permissions, with permission prompts bypassed ([sessions.md](sessions.md#modes)).
- A process that a session detaches on purpose is re-parented, and then looks like the user's own.

<a id="driving"></a>
## Driving the orchestrator

- The orchestrator works in event-driven turns ([sessions.md](sessions.md#orchestrator)).
- The launcher queues events while a turn is running, and injects them as one new turn when the orchestrator is idle:
  - Claude: `send_prompt` on an idle screen (`step2step/claude/session.py:199-236`).
  - Codex: a new turn on the thread (`step2step/codex/session.py:252-268`).
- After every turn, the launcher:
  - ends a memory turn the orchestrator left open, with the usual check and commit (AI)
  - measures the orchestrator's context use
  - asks for a handoff when the use passes the threshold
- Commits of `.barrel/` happen when a memory turn ends, and the indexes are regenerated after each such commit ([memory.md](memory.md#queue)).

<a id="events"></a>
## Event log

Each run has one `events.jsonl` in its run state (Q10 default). Events that belong to no run, such as updates and launcher restarts, go to the PC-wide `~/.barrel/events.jsonl` (AI). The logs merge three existing sources with new events:

| Source | Events |
| --- | --- |
| `Notifier` (`barrel/core/unitloop.py:327-368`) | Preflight failure, stopped (stop file), halt, blocked, gate defect, usage limit, commit or push failure |
| `RunState` (`barrel/core/unitloop.py:373-423`) | Unit running and done. These are recorded today but never sent |
| Claude watchdog (`step2step/claude/watchdog.py:17-25`, `:40-124`) | `died`, `usage_limited`, `dialog_waiting`, `silent`, `no_progress`, `recovered` |
| New | The catalog below |

**Fields of a record** (AI):
- the time, the project and the run
- the type, and the related IDs (topic, task, post)
- where it goes in Slack: the channel, a thread, or nowhere ([slack.md](slack.md#what))
- the values its message template needs, including the run's request name (Q18)

**Readers.** The Slack sender, the snapshot builder, the PC view and the orchestrator's turns all read this one log (Q10 default).

**Codex health.** Codex has no watchdog. Its health events come from app-server events instead (AI).

**Catalog.** The routing follows Q10 and its defaults; the names are AI.

| Event | Emitted by | Slack | Mention | Starts an orchestrator turn |
| --- | --- | --- | --- | --- |
| `run_started` | Launcher | Channel | | |
| `stage_started`, `stage_done` | Orchestrator (`barrel event`) | Channel | | |
| `stage_detail`, such as research started or finished | Orchestrator | Thread of the stage's start message | | |
| `topic_started`, `topic_done` (large and medium) | Orchestrator | Channel | | |
| `leaf_started`, `plan_approved`, `leaf_retried` | Launcher | Thread of the medium topic's start message; batched per minute | | |
| `task_done`, after the leaf's finishing turn committed its memory update | Launcher | Same thread | | Yes |
| `leaf_abandoned` | Launcher | Channel | | Yes |
| `question_posted`, `review_posted`, `request_posted`, `report_posted` | Launcher (`barrel post`, or the launcher's own requests) | Channel; the post starts its own thread | Yes | |
| `reply_posted` | Launcher | The question's thread | | |
| `reminder` | Launcher | The question's thread | Yes | |
| `answer_recorded`, `instruction_received` | Launcher | | | Yes |
| `plan_ready`, `task_question`, `review_needed`, `task_failed` | Launcher | | | Yes |
| `session_done` (a fresh auxiliary session finished, after its memory turn) | Launcher | | | Yes |
| `memory_turn_lost` (a turn timed out, and its update must be redone) | Launcher | | | Yes |
| `user_edit` (commits that change `.barrel/` without Barrel's trailer) | Launcher | | | Yes |
| `preflight_done`, `topic_check_done`, `delivery_done` | Launcher | | | Yes |
| `snapshot` | Launcher | Channel, with [작업 중지] | | |
| `usage_stop`, `usage_resume` | Launcher | Channel | | |
| `run_stopped`, `run_resumed` | Launcher | Channel; "stopped" carries [재개]. Both cover every run of the project | | |
| `cancel_requested` | Launcher | The run's thread, with [보관] and [폐기] | Yes | |
| `run_cancelled` | Launcher | Channel | | |
| `launcher_restarted` (PC-wide log) | Launcher | Channel of each active project, unless the restart was an update | | |
| `update_applied` (PC-wide log) | Launcher | None (Q21) | | |
| `sudo_command` | Launcher, for each command run through `barrel-sudo` | None. Also in the leaf's result report (Q20) | | |
| `pr_closed` (a pull request closed without a merge) | Launcher | | | Yes; an orchestrator starts to ask the user ([runs.md](runs.md#waiting)) |
| `reply_deleted` (a recorded reply deleted in Slack) | Launcher | | | Yes ([interviews.md](interviews.md#replies)) |
| `model_dropped` (a model ID or effort the CLI does not know) | Launcher | Channel, no mention | | Yes ([sessions.md](sessions.md#selection)) |
| `task_compacted` | Launcher | None. Recorded for the size measurement only; compaction changes nothing in how a leaf is judged (archived Q-016) | | |
| `run_done` | Launcher, after the final report is posted | None. The `report_posted` message already marks completion with its mention ([task-execution.md](task-execution.md#acceptance)) | | |
| Health events from the watchdog or app-server | Launcher | None. Only the state changes they cause are posted (Q10 default) | | |

**Text in Slack and the PC view** (AI; Q10 option 10-c K, Q10 "정한 언어로"):
- Both are built from fixed templates and values: IDs, display names, request names, counts, links, and a fixed set of reasons why a leaf is not running.
- The free text an event carries (`barrel event --text`) is English. It stays in the log and is never shown in Slack or the PC view.
- Anything the user needs explained goes through `barrel post`, so it reaches the user in the set language ([interviews.md](interviews.md#posting)).

**Why a leaf is not running.** These match the two counters in Q10's progress line, "막힘" and "답 대기" (Q10 default 2):

| Counter | Reasons |
| --- | --- |
| 답 대기 (waiting for an answer) | A question to the user, with a link to its thread |
| 막힘 (blocked) | Something only the user can do, also with a link; a usage limit, until a given time; repeated failures, handed to the orchestrator |

- **Waiting for another leaf.** A leaf that waits for another leaf in `depends_on`, or for its turn in the memory queue, is neither. It is simply not ready yet.
- **"Blocked" elsewhere.** Outside these two counters, the docs say "blocked" in Q01's general sense ("막힌 작업"): any leaf that cannot go on until something happens, an answer included.

<a id="recovery"></a>
## Recovery after a crash

Before resuming any run after a restart, the launcher reconciles what was in flight (AI; archived memory-and-lifecycle.md: confirm old processes are gone, never repeat a merge, mark unknown outcomes):

1. **Old processes.** It ends every process recorded in `run.json` that is still alive: CLI sessions, app-servers and gate commands. No orphan keeps writing into a lane.
2. **Lanes, merges and memory turns.**
   - A merge that was in progress in an integration worktree (`MERGE_HEAD` exists) is aborted and queued again.
   - A memory turn that was in progress is discarded: its uncommitted `.barrel/` changes are reset, and the turn is queued again (Q24 default).
   - For each leaf that was running:
     - A commit in its lane that is not yet on the run branch, from a leaf whose gates had passed, is queued for its finishing turn. A new session writes the memory update from the result report and the leftover changes (Q24 default).
     - Otherwise the leaf is resumed ([task-execution.md](task-execution.md#stop)).
   - A leaf whose merge is on the run branch but whose memory update was never committed: a new session for that leaf writes the update from the merged code and the result report, in a memory turn. Only then is `task_done` emitted (Q24 default: until then the leaf does not count as done).
3. **Outgoing Slack posts.**
   - Every post carries its event ID in the message metadata.
   - The launcher reads the channel's recent history, and the replies in every thread in its thread map (`conversations.replies`, because channel history leaves thread replies out). An event that was already posted is never posted twice.
   - The thread map is rebuilt from the same metadata.
4. **Incoming Slack messages.**
   - Slack re-sends an unacknowledged event only three times, within about five minutes, and drops anything more than two hours late ([research.md](research.md#vendors)).
   - So after a restart, and after every reconnect, the launcher reads the channel and the open threads since the last message it handled. It processes what it missed: answers, button presses, instructions and command words. It skips messages it already recorded, by their timestamp. An edit or a deletion made before the launcher recorded a message follows archived D-044 ([interviews.md](interviews.md#replies)).
   - During normal running it records a message first and acknowledges it after, so a crash in between causes a re-send, never a loss (AI).
5. **Events.** Events that no orchestrator turn handled go to the next orchestrator ([sessions.md](sessions.md#orchestrator)).
6. **Waiting states.**
   - A cancel that waits for keep or discard keeps waiting, and its buttons still work.
   - A run that waits for a pull request goes back to checking it.
7. **External effects.** A resumed leaf is told the effects its result report recorded, so it does not create a second key or resource ([task-execution.md](task-execution.md#report); archived accounts-and-budget.md).

<a id="scheduling"></a>
## Scheduling

- **Engine and account choice** follows [sessions.md](sessions.md#selection).
- **Accounts are shared** by every project and run on the PC. An account's usage limit counts for all of them (Q11).
- **Implementation concurrency** is per project: `concurrency.implementation`, default 2 (Q14). The project's runs share it; the launcher gives free lanes to their ready leaves in turn, oldest waiting first (Q18; [task-execution.md](task-execution.md#lanes)).
- **Starts are staggered** across accounts (Q14), and every session runs at a lower priority (archived D-016).

<a id="stop"></a>
## Stop, resume and cancel

Stop halts every run of one project at once, from Slack or from the PC view (Q10, Q10-2, Q18). The steps (Q10-2):

1. Mark the project's runs stopped. Start no new session, and never restart one while the runs are stopped.
2. Interrupt every running turn:
   - **Claude:** `interrupt()`, which sends ESC (`step2step/claude/session.py:511-515`).
   - **Codex:**
     - `interrupt()`, which sends `turn/interrupt` (`step2step/codex/session.py:441-462`).
     - Then request `thread/backgroundTerminals/clean`.
     - Today only `stop(force=False)` sends that request (`step2step/codex/session.py:580-582`); `stop(force=True)` skips it. So the launcher sends it before any forced stop.
3. End the gate processes and abort a merge in progress in the integration worktrees (AI). A memory turn in progress is not awaited; it is done again after the resume (Q24 default).
4. Close the sessions. A session that has not stopped within 15 seconds is killed with `stop(force=True)` (`step2step/claude/session.py:186-196`, `step2step/terminal/pty_session.py:201-236`).
5. Record "stopped" and the interrupted leaves in run state, and announce it in Slack and on the PC view.

While stopped:
- File changes stay as they are.
- Question reminders and the three-hour snapshot pause.
- Answers and instructions that arrive are recorded and applied on resume (Q10-2).

Resume:
- A new orchestrator starts for each stopped run, from the memory and the run state.
- Interrupted leaves run again in new sessions on top of the leftover changes ([task-execution.md](task-execution.md#stop)) (Q10-2).

Ways to stop and resume:

| Where | Stop | Resume |
| --- | --- | --- |
| Slack button | [작업 중지] on a snapshot, with Slack's confirm dialog (Q10-2 default) | [재개] on the "stopped" message (Q10-2) |
| Slack word | "중지", no confirmation (Q10-2 default) | "재개" (Q10-2) |
| PC view | [중지], confirmed once (Q10; the confirmation is AI) | [재개] (Q10-2) |

Only the registered user can stop or resume (Q10-2 default). This stop replaces the unit loop's stop file, which only takes effect between units, attempts and turns (`barrel/core/unitloop.py:464-469`, checked at `:536`, `:607`, `:676`).

**Cancelling one run** (archived Q-009; Q17; [runs.md](runs.md#cancel)):
- Only from Slack, and only by the registered user ([slack.md](slack.md#commands)). The PC view keeps stop and resume only (Q10-2).
- The launcher runs the stop sequence for that run's sessions alone, then posts what the run changed with [보관] (keep) and [폐기] (discard), and acts on the user's choice.
- The project's other runs go on.

<a id="reuse"></a>
## Reuse and gaps in the existing code

Line numbers are on main at `5c15481`, checked on 2026-10-13. Status values:
- **reuse:** works as is
- **extend:** works and needs additions
- **gap:** missing
- **replace:** current behavior contradicts a decision

| Need | Existing code | Status | Change |
| --- | --- | --- | --- |
| Fresh interactive Claude session | `SessionHandle.start` (`step2step/claude/session.py:100-147`); argv (`step2step/claude/runner.py:362-381`), with `extra_args` appended at `:381` | reuse | Add a per-session environment for the account folder and the role markers. Per-session MCP config goes through `extra_args` |
| Fresh Codex session | `step2step/codex/session.py:43-48`; `thread/start` (`:105-119`); app-server (`step2step/codex/transport.py:75-89`) | extend | Point `app_dir` at run state; the default is `<workdir>/.step2step` inside the repo (`step2step/codex/session.py:61-64`). Pass more `config` overrides on `thread/start`: the hook-trust bypass and MCP servers ([research.md](research.md#vendors)) |
| Account per session | Both drivers copy the launcher's own environment and take no per-session values. Claude's `child_env()` also drops every `CLAUDE*` variable (`step2step/claude/runner.py:153-163`, at `:160`), and `tests/test_env_scrub.py:6-13` asserts that none survives. `~/.claude` is hard-coded for transcripts (`step2step/claude/transcript.py:27`; `find_transcript`'s `base` parameter, `:25-31`, is never passed), for settings (`step2step/claude/calibrate_model.py:37`) and in `tests/test_live.py:22`. Codex passes the launcher's `CODEX_HOME` through (`step2step/codex/transport.py:56-62`) | gap | A per-session environment parameter in both drivers, set after the scrub, and the scrub test adjusted. Transcript and settings lookup under the session's config folder |
| Barrel-managed config folders | None. `CLAUDE_CONFIG_DIR` appears nowhere in the code | gap | Create one per account; reuse the account's login (Claude's Keychain item per folder, Codex's `auth.json`), or sign in once (spike) ([sessions.md](sessions.md#barrel-folders)) |
| Subscription logins only | Codex accepts only a ChatGPT login (`step2step/codex/session.py:97-99`, `step2step/codex/transport.py:76`). Claude only removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and the `CLAUDE*` variables (`step2step/claude/runner.py:72-83`, `:153-163`); `Runner.preflight` checks the executable, the runtime folder and disk space only (`:245-278`) | extend | Check each Claude account's login method at setup ([sessions.md](sessions.md#paid)) |
| Plan text before approval | Codex: yes (`step2step/codex/session.py:274-290`). Claude: only from the transcript (`step2step/claude/session.py:358-375`), and the hook keeps no `tool_input` (`step2step/claude/hooks.py:38-43`) | gap (Claude) | Record ExitPlanMode's `tool_input` |
| Approve or reject a plan | `step2step/claude/session.py:486-509`, `step2step/codex/session.py:420-439`. Claude picks option 1 of the plan menu (`step2step/claude/runner.py:1288-1310`) | reuse | Claude `reject_plan` was never verified live |
| Intent check before approval | Plans are approved blindly (`barrel/core/unitloop.py:767-783`) | replace | `plan_ready` event, then the orchestrator decides |
| Questions | The fixed default answer (`barrel/core/unitloop.py:82`, `:774-776`) | replace | `task_question` event; only that leaf blocks |
| Multi-question widget (Claude) | Refused (`step2step/claude/session.py:426-429`) | gap | Ask again one question at a time (spike) |
| Inject a turn hours later | Claude `send_prompt` needs an idle screen (`step2step/claude/session.py:199-236`); Codex `send_prompt` (`step2step/codex/session.py:252-268`) | reuse | Verify after a long idle (spike) |
| Interrupt and stop | `step2step/claude/session.py:511-515`, `:186-196`; `step2step/codex/session.py:441-462`, `:575-590` | extend | The stop sequence lives in the launcher. Codex background terminals are cleaned only by a non-forced `stop()` (`step2step/codex/session.py:580-582`), so the launcher cleans them before forcing |
| Health events | Claude watchdog (`step2step/claude/watchdog.py:40-124`) | extend | Codex has no watchdog, but its `peek_state()` and `health()` can be polled (`step2step/codex/session.py:521-557`) |
| Context measurement | None for Claude. Codex token usage is stored raw (`step2step/codex/events.py:86-87`, `step2step/codex/session.py:327-328`) | gap | Readers for both engines |
| Usage-limit detection | Claude screen markers (`step2step/claude/screen.py:104-110`), not calibrated live, with the reset kept as text such as "7pm" (`:111-114`). Codex turn error (`step2step/codex/session.py:305-308`), with `resetsAt` joined as text (`:504-516`). The unit loop then sleeps `min(usage_wait_seconds, the remaining run budget)` on the same session (`barrel/core/unitloop.py:703-708`) | extend | Calibrate; parse the reset into a time (nothing parses it today); move to another account instead of sleeping |
| Task runner | `barrel/core/unitloop.py`: flat roadmap (`:194-239`), file order (`:532`), one session at a time | extend | Tree, ready queue, lanes over several repos, read sets, resources and memory units |
| Codex in the task runner | Claude-only factory (`barrel/core/unitloop.py:433-442`); Codex `wait_turn` lacks `progress_seconds` (`step2step/codex/session.py:338` vs `barrel/core/unitloop.py:779-782`) | gap | An engine-neutral factory and wait adapter |
| Gates, failures, ladder | `barrel/core/gates.py`, `barrel/core/failures.py`. On a refusal the ladder jumps to a different model (`barrel/core/failures.py:246-257`) | extend; replace for refusals | Ladder over tiers and engines; a `repo` key on gates. A refusal goes to the orchestrator and is never routed to another model or engine (archived D-041) |
| Whole-run halts | The unit loop halts the whole run on any of these:<br>• a blocked dependency (`barrel/core/unitloop.py:546-547`) and a blocked unit (`:567-571`), under the default `on_unit_blocked: "halt"` (`:78`)<br>• a gate defect, at baseline (`:589-602`, halting at `:565-566`) or during an attempt (`:738-739`, halting at `:623`)<br>• an environment failure (`:752`, `:755`)<br>• the run budget (`:541`, `:673`) | replace | None of them stops the run (Q01):<br>• a leaf whose dependency is not done simply waits<br>• each of the other cases sends only that leaf back to the orchestrator<br>• the run budget is dropped<br><br>The whole run stops only for the user's stop and for the usage-limit stop, when nothing can run (Q01, Q10). A cancel ends one run (archived Q-009) |
| Budgets | `Budget` requires every field to be finite (`barrel/core/failures.py:262-288`), and the loop checks the run clock (`barrel/core/unitloop.py:540-541`, `:671-673`) | extend | Drop the run-wide clock ([task-execution.md](task-execution.md#failures)) |
| Preflight | Runs once and exits with code 3 on a fatal finding (`barrel/core/unitloop.py:516-527`) | extend | Results go to the orchestrator; add the baseline run ([task-execution.md](task-execution.md#preflight)) |
| Environment recovery | One recovery command, then the whole run halts (`barrel/core/unitloop.py:740-755`, halts at `:752`, `:755`) | replace | Only that leaf stops |
| Dependency setup | None | gap | `env.setup` ([sessions.md](sessions.md#engines)) |
| Commit | `_commit` (`barrel/core/unitloop.py:823-845`) uses `commit_all`, which is `git add -A` (`barrel/core/gitops.py:148-216`); the path-scoped `commit` (`:78-134`) is used only by tests | extend | Commit only the write set, per repo; never product secret files |
| Worktrees, branches, merges, delivery | `barrel/core/gitops.py` works on one repo and creates neither worktrees nor branches. It only checks a branch (`expect_branch`, `:318`) and pushes (`:333`) | gap | Integration worktrees per run and repo, detached lanes over every repo, merges, delivery, pull request state through `gh` ([runs.md](runs.md#branches)) |
| Memory queue between processes | None. There is no lock between processes anywhere in the code; step2step has thread locks only (`step2step/codex/transport.py:20`, `:70`; `step2step/codex/session.py:70`; `step2step/terminal/pty_session.py:59`; `step2step/terminal/screen.py:16`) | gap | The per-project queue in the launcher ([memory.md](memory.md#queue)) |
| Notifications | `Notifier` (`barrel/core/unitloop.py:327-368`) | replace | Event log and Slack bot |
| Run state | `RunState` (`barrel/core/unitloop.py:373-423`) | extend | `run.json` and result reports |
| Stop | Stop file (`barrel/core/unitloop.py:464-469`) | replace | Immediate stop; per-run cancel |
| step2step's own hooks | Written at `step2step/claude/runner.py:343-360` from `build_settings` (`step2step/claude/hooks.py:79-107`), passed with `--settings` at `runner.py:367-368` | reuse | Claude's docs say settings hooks and plugin hooks merge (spike item 5) |
| Supervisor and IPC | None in step2step: one handle owns one child, and no other process can command it | gap | The launcher process, its socket, and the [access check](#access) |
| Credential dialog, sudo tool, package checks, updates | None | gap | The macOS dialog ([memory.md](memory.md#secrets)), `barrel-sudo` ([task-execution.md](task-execution.md#sudo)), registry and OSV checks ([task-execution.md](task-execution.md#packages)), the update flow ([updates](#versions)) |
| Calibration | Claude verified at 2.1.272 ([docs/step2step.md](../../step2step.md)); 2.1.301 installed. Codex verified at 0.153.4 ([docs/codex-control.md](../../codex-control.md)); 0.162.1 installed (both on 2026-10-16) | re-check | Spike |
