# Launcher

The launcher is the one Barrel process on a PC (Q11). It owns:
- every session it starts (Q03-3, Q04-2)
- the single Slack Socket Mode connection (Q11)
- the PC views (Q10-2)
- the event log (Q10 default)
- the choice of engine and account for every session, across all projects (Q11, Q12, Q16)
- the git queue of every integration worktree ([runs.md](runs.md#branches)) (AI)

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
  - If the spike shows that a detached launcher does not survive, or that it inherits the sandbox of a Codex invoking session (no network, limited writes), the launcher runs as a launchd user agent instead (Q11 option text; [validation.md](validation.md) item 1).
  - The skill, Barrel.app and every `barrel` command except `barrel setup` start the launcher when it is not running (AI). Setup runs without it and starts it only in its last step ([plugin.md](plugin.md#setup)).
- **One per PC.** A lock file in `~/.barrel/` keeps a second launcher from starting (AI).
- **Restart** (AI).
  - **As a launchd agent:** launchd starts the launcher again after a crash and at login (`RunAtLoad`; `KeepAlive` on abnormal exit).
  - **Detached:** nothing watches the launcher. It starts again the next time the skill, Barrel.app or a `barrel` command runs, and the runs wait until then. The spike decides which mode Barrel uses ([open-decisions.md](open-decisions.md#ai-defaults)).
  - **After a restart**, the launcher:
    1. reconciles what was in flight ([recovery](#recovery))
    2. posts that it restarted (Q10 default)
    3. resumes the runs that were running; runs the user stopped stay stopped (archived Q-007, AI)
- **Sessions are its children** (AI). If the launcher dies, the sessions of every project end with it. The restart resumes them from files exactly like [resume](#stop), after the [recovery](#recovery) steps. An upgrade never causes this, because it waits until no run is active ([versions](#versions)).
- **Threads.** Each Codex session is driven from its own thread, because step2step's Codex handle accepts calls only from the thread that created it (`step2step/codex/session.py:167-171`).

<a id="sleep"></a>
- **Sleep** (archived D-047). The policy lives in `~/.barrel/settings.json`. The default is `ac` (AI), and `barrel settings sleep <policy>` changes it.

  | Policy | While a run is active |
  | --- | --- |
  | `os` | Follow macOS |
  | `ac` | Prevent idle sleep while on power: `caffeinate -s -w <launcher pid>` |
  | `always` | Prevent idle sleep on battery too: `caffeinate -i -w <launcher pid>` |

  - The launcher starts `caffeinate` when the first run becomes active and stops it when no run is active. `-w` only makes sure it ends if the launcher dies (AI).
  - Display sleep and the lock screen are not affected (archived D-047).
  - Closing a laptop's lid still sleeps the Mac ([research.md](research.md#vendors)). On wake, the launcher reconnects to Slack, catches up on what was sent meanwhile ([recovery](#recovery)), and the sessions continue.

<a id="versions"></a>
- **Versions** (AI).
  - **Plugin.** The launcher, the hooks and the playbooks ship together in one plugin version.
    - Each Barrel hook event writes a marker with the plugin version the first time it fires in a session ([plugin.md](plugin.md#trust)).
    - A session is stopped when its SessionStart or PreToolUse marker is missing ([plugin.md](plugin.md#trust)), or when its account folder holds a different version.
    - The launcher then updates the plugin in that folder itself (spike). If that fails, the folder is marked unusable, and a request asks the user to run the skill again, which repeats setup.
  - **Launcher.** When the skill finds an older launcher, it upgrades it once no run is active. Until then the old launcher keeps running.
  - **CLIs.**
    - The launcher logs each CLI's version for every session. Claude Code updates itself in the background, so the version can change under a running launcher.
    - A harness failure right after a version change triggers step2step's calibration check (`python -m step2step.claude.calibrate_dialogs`).
    - If the check fails, that CLI's options drop out of the tiers and a request is posted.

<a id="commands"></a>
## Commands

Sessions, tools and the user talk to the launcher through the `barrel` command, which connects to `~/.barrel/launcher.sock`. That the launcher has a command comes from the Q10 default ("실행기 명령"). The command names are AI.

| Command | Called by | Does |
| --- | --- | --- |
| `barrel setup [--add-account]` | Invoking session | The setup steps after the command itself is installed; later, re-checks and adding an account ([plugin.md](plugin.md#setup)) |
| `barrel run start --repo <path> --input <file>` | Invoking session | Starts a run ([runs.md](runs.md#start)) |
| `barrel instruct --repo <path> --input <file>` | Invoking session | Passes a new request to the active run's orchestrator as an instruction ([runs.md](runs.md#start)) |
| `barrel view open [--project]` | Barrel.app, the invoking session, the Slack word "화면" | Starts the launcher if needed and opens the PC view ([pc-view.md](pc-view.md#reopen)) |
| `barrel task start\|approve\|reject\|answer\|review\|cancel <id>` | Orchestrator | Controls a leaf ([task-execution.md](task-execution.md#lifecycle); `cancel` in [workflow.md](workflow.md#cascade)) |
| `barrel session start --role <role> --input <files> --output <file>` | Orchestrator | Starts a fresh auxiliary session: the Korean writer, or a subagent role whose engine is on another CLI ([sessions.md](sessions.md#roles)). Its output goes to the run state's `outputs/` |
| `barrel post --kind question\|review\|request\|report\|reply --file <md> [--unit <id>] [--task <id>] [--thread <post>]` | Orchestrator | Posts to Slack ([interviews.md](interviews.md#posting)) |
| `barrel event --type <type> --text <text>` | Orchestrator, task sessions | Adds an event to the log (Q10 default) |
| `barrel handoff --note <file>` | Orchestrator | Asks for a successor orchestrator. The note is a file in the orchestrator's run-state folder ([sessions.md](sessions.md#orchestrator)) |
| `barrel memory index [--repo <path>]` | Orchestrator, the user | Regenerates the uncommitted index files: in the integration worktree for the orchestrator, in the given repo or the current folder for the user ([memory.md](memory.md#index), [runs.md](runs.md#sharing)) |
| `barrel memory render --spec requirements\|features` | Orchestrator | Renders a spec from the units ([interviews.md](interviews.md#review)) |
| `barrel secret set <name>` / `barrel secret get <name>` | The user / task sessions | Stores or reads a secret in the Keychain ([memory.md](memory.md#secrets)) |
| `barrel settings sleep os\|ac\|always` | The user | Sets the [sleep policy](#sleep) |
| `barrel project remove <id>` | The user | Deletes a project's worktrees and run state ([runs.md](runs.md#after)) |

- **No terminal status command.** Status is in Slack and the PC view (Q10-2 default 4). The PC view is served by the launcher itself.
- **No terminal stop** (AI). Stop and resume are internal to the launcher: its Slack handler and the PC view call them, the two places Q10 and Q10-2 give the user ([stop](#stop)).

<a id="access"></a>
### Who may call what (AI)

The launcher checks every command against the caller's role. Example: a task session must not approve its own plan or read a secret its contract does not list.

| Commands | Allowed callers |
| --- | --- |
| `setup`, `run start`, `instruct`, `secret set`, `settings sleep`, `project remove` | The user: any process that is not inside a Barrel session, including the invoking session |
| `view open` | Anyone |
| `memory index` | The orchestrator and the user |
| `task …`, `session start`, `post`, `handoff`, `memory render` | The orchestrator. Its subagents run inside the same session, so this check cannot tell them apart; a hook denies every `barrel` command in subagent calls instead ([plugin.md](plugin.md#hooks)) |
| `event` | The orchestrator and task sessions |
| `secret get` | Task sessions, for the names in their contract's `secrets` |

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
- After every turn, the launcher does four things:
  - regenerates the indexes if a unit changed ([runs.md](runs.md#sharing))
  - commits `.barrel/` if it changed ([memory.md](memory.md#rules))
  - measures the orchestrator's context use
  - asks for a handoff when the use passes the threshold

<a id="events"></a>
## Event log

Each run has one `events.jsonl` in its run state (Q10 default). It merges three existing sources with new events:

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
- the values its message template needs

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
| `task_done` | Launcher | Same thread | | Yes |
| `leaf_abandoned` | Launcher | Channel | | Yes |
| `question_posted`, `review_posted`, `request_posted`, `report_posted` | Launcher (`barrel post`) | Channel; the post starts its own thread | Yes | |
| `reply_posted` | Launcher | The question's thread | | |
| `reminder` | Launcher | The question's thread | Yes | |
| `answer_recorded`, `instruction_received` | Launcher | | | Yes |
| `plan_ready`, `task_question`, `review_needed`, `task_failed`, `task_compacted` | Launcher | | | Yes |
| `session_done` (a fresh auxiliary session finished) | Launcher | | | Yes |
| `preflight_done`, `topic_check_done`, `delivery_done` | Launcher | | | Yes |
| `snapshot` | Launcher | Channel, with [작업 중지] | | |
| `usage_stop`, `usage_resume` | Launcher | Channel | | |
| `run_stopped`, `run_resumed` | Launcher | Channel; "stopped" carries [재개] | | |
| `launcher_restarted` | Launcher | Channel of each active project | | |
| `run_done` | Launcher, after the final report is posted | None. The `report_posted` message already marks completion with its mention ([task-execution.md](task-execution.md#acceptance)) | | |
| Health events from the watchdog or app-server | Launcher | None. Only the state changes they cause are posted (Q10 default) | | |

**Text in Slack and the PC view** (AI; Q10 option 10-c K, Q10 "정한 언어로"):
- Both are built from fixed templates and values: IDs, display names, counts, links, and a fixed set of reasons why a leaf is not running.
- The free text an event carries (`barrel event --text`) is English. It stays in the log and is never shown in Slack or the PC view.
- Anything the user needs explained goes through `barrel post`, so it reaches the user in the set language ([interviews.md](interviews.md#posting)).

**Why a leaf is not running.** These match the two counters in Q10's progress line, "막힘" and "답 대기" (Q10 default 2):

| Counter | Reasons |
| --- | --- |
| 답 대기 (waiting for an answer) | A question to the user, with a link to its thread |
| 막힘 (blocked) | Something only the user can do, also with a link; a usage limit, until a given time; repeated failures, handed to the orchestrator |

- **Waiting for another leaf.** A leaf that waits for another leaf in `depends_on` is neither. It is simply not ready yet.
- **"Blocked" elsewhere.** Outside these two counters, the docs say "blocked" in Q01's general sense ("막힌 작업"): any leaf that cannot go on until something happens, an answer included.

<a id="recovery"></a>
## Recovery after a crash

Before resuming any run after a restart, the launcher reconciles what was in flight (AI; archived memory-and-lifecycle.md: confirm old processes are gone, never repeat a merge, mark unknown outcomes):

1. **Old processes.** It ends every process recorded in `run.json` that is still alive: CLI sessions, app-servers and gate commands. No orphan keeps writing into a lane.
2. **Lanes and merges.**
   - A merge that was in progress in the integration worktree (`MERGE_HEAD` exists) is aborted and queued again.
   - For each leaf that was running:
     - A commit in its lane that is not yet on the run branch, from a leaf whose gates had passed, is merged now.
     - Otherwise the leaf is resumed ([task-execution.md](task-execution.md#stop)).
   - A merge that is on the run branch but that the orchestrator never saw gets its `task_done` event.
3. **Outgoing Slack posts.**
   - Every post carries its event ID in the message metadata.
   - The launcher reads the channel's recent history, and the replies in every thread in its thread map (`conversations.replies`, because channel history leaves thread replies out). An event that was already posted is never posted twice.
   - The thread map is rebuilt from the same metadata.
4. **Incoming Slack messages.**
   - Slack re-sends an unacknowledged event only three times, within about five minutes, and drops anything more than two hours late ([research.md](research.md#vendors)).
   - So after a restart, and after every reconnect, the launcher reads the channel and the open threads since the last message it handled. It processes what it missed: answers, instructions and command words. It skips messages it already recorded, by their timestamp.
   - During normal running it records a message first and acknowledges it after, so a crash in between causes a re-send, never a loss (AI).
5. **Events.** Events that no orchestrator turn handled go to the next orchestrator ([sessions.md](sessions.md#orchestrator)).
6. **External effects.** A resumed leaf is told the effects its result report recorded, so it does not create a second key or resource ([task-execution.md](task-execution.md#report); archived accounts-and-budget.md).

<a id="scheduling"></a>
## Scheduling

- **Engine and account choice** follows [sessions.md](sessions.md#selection).
- **Accounts are shared** by every project on the PC. An account's usage limit counts for all of them (Q11).
- **Implementation concurrency** is per project: `concurrency.implementation`, default 2 (Q14). Starts are staggered across accounts ([task-execution.md](task-execution.md#lanes)).

<a id="stop"></a>
## Stop and resume

Stop halts the whole run of one project at once, from Slack or from the PC view (Q10, Q10-2). The steps (Q10-2):

1. Mark the run stopped. Start no new session, and never restart one while the run is stopped.
2. Interrupt every running turn:
   - **Claude:** `interrupt()`, which sends ESC (`step2step/claude/session.py:511-515`).
   - **Codex:**
     - `interrupt()`, which sends `turn/interrupt` (`step2step/codex/session.py:441-462`).
     - Then request `thread/backgroundTerminals/clean`.
     - Today only `stop(force=False)` sends that request (`step2step/codex/session.py:580-582`); `stop(force=True)` skips it. So the launcher sends it before any forced stop.
3. Close the sessions. A session that has not stopped within 15 seconds is killed with `stop(force=True)` (`step2step/claude/session.py:186-196`, `step2step/terminal/pty_session.py:201-236`).
4. Record "stopped" and the interrupted leaves in run state, and announce it in Slack and on the PC view.

While stopped:
- File changes stay as they are.
- Question reminders and the three-hour snapshot pause.
- Answers and instructions that arrive are recorded and applied on resume (Q10-2).

Resume:
- A new orchestrator starts from the memory and the run state.
- Interrupted leaves run again in new sessions on top of the leftover changes ([task-execution.md](task-execution.md#stop)) (Q10-2).

Ways to stop and resume:

| Where | Stop | Resume |
| --- | --- | --- |
| Slack button | [작업 중지] on a snapshot, with Slack's confirm dialog (Q10-2 default) | [재개] on the "stopped" message (Q10-2) |
| Slack word | "중지", no confirmation (Q10-2 default) | "재개" (Q10-2) |
| PC view | [중지], confirmed once (Q10; the confirmation is AI) | [재개] (Q10-2) |

Only the registered user can stop or resume (Q10-2 default). This stop replaces the unit loop's stop file, which only takes effect between units, attempts and turns (`barrel/core/unitloop.py:464-469`, checked at `:536`, `:607`, `:676`).

<a id="reuse"></a>
## Reuse and gaps in the existing code

Line numbers are on main at `ceb5a73`. Status values:
- **reuse:** works as is
- **extend:** works and needs additions
- **gap:** missing
- **replace:** current behavior contradicts a decision

| Need | Existing code | Status | Change |
| --- | --- | --- | --- |
| Fresh interactive Claude session | `SessionHandle.start` (`step2step/claude/session.py:100-147`); argv (`step2step/claude/runner.py:362-381`), with `extra_args` appended at `:381` | reuse | Add a per-session environment for the account and the role markers. Per-session MCP config goes through `extra_args` |
| Fresh Codex session | `step2step/codex/session.py:43-48`; `thread/start` (`:105-119`); app-server (`step2step/codex/transport.py:75-89`) | extend | Point `app_dir` at run state; the default is `<workdir>/.step2step` inside the repo (`step2step/codex/session.py:61-64`). Pass more `config` overrides on `thread/start`: the hook-trust bypass and MCP servers ([research.md](research.md#vendors)) |
| Account per session | Both drivers copy the launcher's own environment and take no per-session values. Claude's `child_env()` also drops every `CLAUDE*` variable (`step2step/claude/runner.py:153-163`). Claude's transcript lookup searches `~/.claude/projects`: `find_transcript` has a `base` parameter that no caller passes (`step2step/claude/transcript.py:25-31`). Codex passes the launcher's `CODEX_HOME` through (`step2step/codex/transport.py:56-62`) | gap | A per-session environment parameter in both drivers, for the account folder and the role markers. Transcript lookup under the session's config folder |
| Plan text before approval | Codex: yes (`step2step/codex/session.py:274-290`). Claude: only from the transcript (`step2step/claude/session.py:358-375`), and the hook keeps no `tool_input` (`step2step/claude/hooks.py:38-43`) | gap (Claude) | Record ExitPlanMode's `tool_input` |
| Approve or reject a plan | `step2step/claude/session.py:486-509`, `step2step/codex/session.py:420-439` | reuse | Claude `reject_plan` was never verified live |
| Intent check before approval | Plans are approved blindly (`barrel/core/unitloop.py:767-783`) | replace | `plan_ready` event, then the orchestrator decides |
| Questions | The fixed default answer (`barrel/core/unitloop.py:82`, `:774-776`) | replace | `task_question` event; only that leaf blocks |
| Multi-question widget (Claude) | Refused (`step2step/claude/session.py:426-429`) | gap | Ask again one question at a time (spike) |
| Inject a turn hours later | Claude `send_prompt` needs an idle screen (`step2step/claude/session.py:199-236`); Codex `send_prompt` (`step2step/codex/session.py:252-268`) | reuse | Verify after a long idle (spike) |
| Interrupt and stop | `step2step/claude/session.py:511-515`, `:186-196`; `step2step/codex/session.py:441-462`, `:575-590` | extend | The stop sequence lives in the launcher. Codex background terminals are cleaned only by a non-forced `stop()` (`step2step/codex/session.py:580-582`), so the launcher cleans them before forcing |
| Health events | Claude watchdog (`step2step/claude/watchdog.py:40-124`) | extend | Codex has none |
| Context measurement | None for Claude. Codex token usage is stored raw (`step2step/codex/events.py:86-87`, `step2step/codex/session.py:327-328`) | gap | Readers for both engines |
| Usage-limit detection | Claude screen markers (`step2step/claude/screen.py:104-110`), not calibrated live, with the reset kept as text such as "7pm" (`:111-114`). Codex turn error (`step2step/codex/session.py:305-308`), with `resetsAt` joined as text (`:504-516`) | extend | Calibrate; parse the reset into a time (nothing parses it today) |
| Task runner | `barrel/core/unitloop.py`: flat roadmap (`:194-239`), file order (`:532`), one session at a time | extend | Tree, ready queue, lanes, read sets and resources |
| Codex in the task runner | Claude-only factory (`barrel/core/unitloop.py:433-442`); Codex `wait_turn` lacks `progress_seconds` (`step2step/codex/session.py:338` vs `barrel/core/unitloop.py:779-782`) | gap | An engine-neutral factory and wait adapter |
| Gates, failures, ladder | `barrel/core/gates.py`, `barrel/core/failures.py` | reuse | Ladder over tiers and engines |
| Whole-run halts | The unit loop halts the whole run on any of these:<br>• a blocked dependency (`barrel/core/unitloop.py:546-547`)<br>• a blocked unit (`:565-571`)<br>• a gate defect, at baseline (`:589-602`, `:623`) or during an attempt (`:738-739`)<br>• an environment failure (`:752`, `:755`)<br>• the run budget (`:541`, `:673`) | replace | None of them stops the run (Q01):<br>• a leaf whose dependency is not done simply waits<br>• each of the other cases sends only that leaf back to the orchestrator<br>• the run budget is dropped<br><br>The whole run stops only for the user's stop and for the usage-limit stop, when nothing can run (Q01, Q10) |
| Budgets | `Budget` requires every field to be finite (`barrel/core/failures.py:262-288`), and the loop checks the run clock (`barrel/core/unitloop.py:540-541`) | extend | Drop the run-wide clock ([task-execution.md](task-execution.md#failures)) |
| Preflight | Runs once and exits with code 3 on a fatal finding (`barrel/core/unitloop.py:516-527`) | extend | Results go to the orchestrator; add the baseline run ([task-execution.md](task-execution.md#preflight)) |
| Environment recovery | One recovery command, then the whole run halts (`barrel/core/unitloop.py:740-755`, halts at `:752`, `:755`) | replace | Only that leaf stops |
| Dependency setup | None | gap | `env.setup` ([sessions.md](sessions.md#engines)) |
| Commit | `_commit` (`barrel/core/unitloop.py:823-845`) uses `commit_all`, which is `git add -A` (`barrel/core/gitops.py:148-216`); the path-scoped `commit` (`:78-134`) is used only by tests | extend | Commit only the write set |
| Worktrees, branches, merges, delivery | `barrel/core/gitops.py` creates neither worktrees nor branches. It only checks a branch (`expect_branch`, `:318`) and pushes (`:333`) | gap | Integration worktree, detached lanes, merges, delivery ([runs.md](runs.md#branches)) |
| Notifications | `Notifier` (`barrel/core/unitloop.py:327-368`) | replace | Event log and Slack bot |
| Run state | `RunState` (`barrel/core/unitloop.py:373-423`) | extend | `run.json` and result reports |
| Stop | Stop file (`barrel/core/unitloop.py:464-469`) | replace | Immediate stop |
| step2step's own hooks | Written at `step2step/claude/runner.py:343-360` from `build_settings` (`step2step/claude/hooks.py:79-107`), passed with `--settings` at `runner.py:367-368` | reuse | Claude's docs say settings hooks and plugin hooks merge (spike item 5) |
| Supervisor and IPC | None in step2step: one handle owns one child, and no other process can command it | gap | The launcher process, its socket, and the [access check](#access) |
| Calibration | Claude verified at 2.1.272 ([docs/step2step.md](../../step2step.md)); 2.1.296 installed. Codex verified at 0.153.4 ([docs/codex-control.md](../../codex-control.md)); 0.155.1 installed | re-check | Spike |
