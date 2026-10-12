# Sessions, roles and engines

<a id="roles"></a>
## Roles

| Role | Does | Runs as | Default tier and effort | Source |
| --- | --- | --- | --- | --- |
| Invoking session | First-run setup and start, then it ends | The user's own session | none | Q03-3 |
| Orchestrator | Assesses impact, interviews, splits the tree, writes contracts, checks plans, decides, reports | A fresh session started by the launcher | strong, max | Q03-3, Q04-2 |
| Task session | Implements one leaf | A fresh session | By the leaf's difficulty ([below](#difficulty)) | Q02, flow 0 |
| Advice | A second opinion on a hard decision | A subagent of the orchestrator\* | frontier, max | flow 0, Q02, Q16 |
| Intent check | Checks a leaf's plan against its contract and units | A subagent of the orchestrator\* | strong, medium | Q02; archived P-001 |
| Context gathering | Follows memory links; surveys code before a split or at onboarding | A subagent of the orchestrator\* | standard, medium | Q02 |
| Research | Researches a question with current sources | A subagent of the orchestrator\* | strong, max | flow 5, flow 7, Q02, Q16 |
| Verification | Checks the research's claims against their sources | A subagent of the orchestrator\* | strong, high | Q02, Q16 |
| Review | Reviews a high-risk leaf after its gates pass, and checks one large topic in the S8 acceptance | A subagent of the orchestrator\* | strong, max | Q02; archived Q-004; Q01 |
| Korean writer | Writes Korean text from an English source with Skill-Techblog | A fresh session | strong, high | Q08, Q16 default |

The Source column covers each role and how it runs. The default tiers and efforts are AI choices ([engines](#engines)), except two:
- frontier for advice comes from flow 0
- medium for the intent check comes from archived D-067

**How Q02 splits the work.** The user chose option A:
- **Fresh sessions:** implementation, anything that needs plan approval, and anything that must survive an orchestrator restart.
- **Subagents:** short read-only work whose result can come back as a summary. That covers gathering context, research (자료 조사), and independent review by someone other than the worker (작업자가 아닌 쪽의 독립 검토).
- A task session may use subagents of its own.

**Notes on the table:**
- \* **Subagent or fresh session.**
  - A role marked \* runs as a subagent of the orchestrator when the engine chosen for it ([selection](#selection)) is on the orchestrator's CLI.
  - Otherwise it runs as a fresh session started with `barrel session start`, because a subagent can only use its parent's CLI.
  - This is a limit of the engines, not a policy about providers (Q16).
- **Subagents and files** (AI).
  - Subagents never write the project.
  - A research, verification or review subagent writes its full report into the orchestrator's run-state folder and returns only the path and a short summary. The report then stays out of the orchestrator's context.
  - Enforcement: a subagent inherits the orchestrator's markers, but Claude's hook input marks subagent calls (`agent_id`), so the hook limits them to that folder ([plugin.md](plugin.md#hooks)). Whether Codex hooks can tell a subagent's calls apart is a spike check.
- **Independence** (Q16).
  - The verification subagent gets the research report and its sources, never the research conversation.
  - A review subagent gets the contract, the units, the diff and the gate output, never the task session's conversation.
- **No subagent across a handoff** (AI). The orchestrator hands off only when none of its subagents is running ([lifecycle](#orchestrator)), so subagent work never has to survive a restart.
- **The Korean writer is always a fresh session** (Q16 default). It writes files, and Skill-Techblog starts a subagent of its own.
- **Model and effort per subagent.**
  - Claude's Agent tool takes `model` and `effort` on every call; per-call `effort` arrived in 2.1.292.
  - Codex's `spawn_agent` takes `model` and `reasoning_effort` ([research.md](research.md#vendors)).

<a id="modes"></a>
## Permission modes

Barrel sessions run unattended, so no session may wait on a permission prompt. Three guards take the place of permission prompts:
- hooks ([plugin.md](plugin.md#hooks))
- the write-set check ([task-execution.md](task-execution.md#lifecycle))
- the command access check ([launcher.md](launcher.md#access))

These modes are what the existing drivers already do (AI to keep them):

| Engine | Every session starts with | Plan mode, for task sessions |
| --- | --- | --- |
| Claude Code | `--dangerously-skip-permissions` (`step2step/claude/runner.py:363-370`) | Entered with Shift+Tab before the prompt (`step2step/claude/session.py:222-223`). Approval picks option 1, "Yes, and bypass permissions", which puts the session back in bypass (`step2step/claude/screen.py:58-62`) |
| Codex | Approval `never` and sandbox `danger-full-access`, the defaults (`step2step/codex/session.py:44-54`) | The planning turn runs read-only. Execution turns use the session's sandbox (`step2step/codex/session.py:183-188`) |

- The orchestrator and the auxiliary sessions run in the same modes. Their hooks limit where they may write.
- A PreToolUse deny is expected to block a call in bypass mode too. The spike checks this on both engines ([validation.md](validation.md) item 5).

<a id="engines"></a>
## Engines and `.barrel/config.json`

- **Engines.** Claude Code and Codex are engines that run Barrel, and any role can run on either one (Q16).
- **One engine is enough.** A CLI that is not installed drops out of every tier (archived D-004).
- **Where models are set.** Model assignment lives in `.barrel/config.json` in the project, so the team can share and edit it (Q12).
- **Model and effort follow the difficulty of the work** (Q16). The file's shape expresses that (AI):
  - **Tiers:** each tier is a list of engine options `{cli, model}` at a similar level.
  - **Roles and leaf difficulties:** each maps to a tier and an effort.
- **Defaults.** The defaults below are AI choices. They come from:
  - flow 0: Opus 5.5 implements, and Fable or Astra advises on hard questions
  - the routing pattern in [the model tier doc](../../claude-gpt-모델-티어-매핑-가격비교.md) (2026-10-07): everyday work on Opus 5.5, harder work on Opus 5.5 at higher effort, and Fable 5.1 or Astra when failure loops cost more than tokens
- **Format.** JSON is also an AI choice ([Q12](../interview/q12-model-config-and-cli-fallback.md)).

```json
{
  "project": "my-app",
  "tiers": {
    "frontier": [{"cli": "claude", "model": "claude-fable-5-1"}, {"cli": "codex", "model": "gpt-6-astra"}],
    "strong":   [{"cli": "claude", "model": "claude-opus-5-5"},  {"cli": "codex", "model": "gpt-6.1-sol"}],
    "standard": [{"cli": "claude", "model": "claude-sonnet-5-5"}, {"cli": "codex", "model": "gpt-6.1-sol"}]
  },
  "roles": {
    "orchestrator":  {"tier": "strong",   "effort": "max"},
    "advice":        {"tier": "frontier", "effort": "max"},
    "intent_check":  {"tier": "strong",   "effort": "medium"},
    "context":       {"tier": "standard", "effort": "medium"},
    "research":      {"tier": "strong",   "effort": "max"},
    "verification":  {"tier": "strong",   "effort": "high"},
    "review":        {"tier": "strong",   "effort": "max"},
    "ko_writer":     {"tier": "strong",   "effort": "high"}
  },
  "leaves": {
    "light":  {"tier": "standard", "effort": "medium"},
    "normal": {"tier": "strong",   "effort": "high"},
    "hard":   {"tier": "strong",   "effort": "max"}
  },
  "concurrency": {"implementation": 2},
  "orchestrator": {"handoff_at_context": 0.6},
  "git": {"delivery": null},
  "env": {"setup": []},
  "task_runner": {
    "preflight": {"tools": ["git"], "min_free_mb": 1024, "commands": []},
    "baseline": [],
    "gates": {"timeout_seconds": 3600, "before": [], "after_timeout": [], "env_recover": []},
    "budget": {"turn_seconds": 3600, "unit_turns": 12, "unit_wall_seconds": 14400, "stall_seconds": 180, "progress_seconds": 1800},
    "repeat_limit": 2,
    "harness_retries": 2
  }
}
```

The sections after `concurrency` (AI):
- **`git.delivery`:** how a finished run is delivered ([runs.md](runs.md#delivery)).
- **`env.setup`:** commands that install the project's dependencies in a worktree. They run when a lane or the integration worktree is prepared and a dependency manifest changed since that worktree's last use. The unit loop has no such command today.
- **`task_runner`:** the unit loop's run configuration, reused as is (`barrel/core/unitloop.py:47-83`; budget fields at `barrel/core/failures.py:262-271`). One field is new: `baseline`, the project's existing check commands, run once at the start of S7 ([task-execution.md](task-execution.md#preflight)).
- **Not carried from the unit loop's configuration**, because a decision replaces each of them:

  | Unit-loop key | Replaced by |
  | --- | --- |
  | `ladder` | the tiers |
  | `notify` | the event log |
  | `on_unit_blocked` | Q01 |
  | `usage_wait_seconds` | moving to another account |
  | `menu_default_answer` | Q01 |
  | `prompt` | contracts and playbooks |
  | `git.push` | delivery |
  | `run_wall_seconds`, the run-wide clock | a run lasts as long as its work ([task-execution.md](task-execution.md#failures)) |

- **Who fills the project values.** The orchestrator fills `env`, `task_runner.preflight` and `task_runner.baseline`: in S2 for an existing repo, in S6 for a new one.
- **Who writes the file.** The launcher writes the default file once, at a project's first run, before any orchestrator exists. After that, among Barrel's sessions only the orchestrator edits it, and people edit it like any file in the repo (Q12; [memory.md](memory.md#rules)).
- **Where the file is read.** The launcher reads `config.json` from the run branch every time it starts a session.
  - A change made through a Slack instruction is made by the orchestrator, and applies from the next session.
  - A change in the user's own checkout applies from the next run, or once it is merged into the run branch.

<a id="selection"></a>
### Choosing an engine and an account (AI)

Barrel uses every CLI and account it can (Q12) and treats the engines in a tier as interchangeable (Q16), so it spreads sessions over all of them instead of always taking the first.

1. **Collect the usable pairs.** For each option in the tier, take each account of that option's CLI. Keep only the pairs that can run now.
   - Drop an option whose CLI is missing on this PC, or whose model or effort is not available. Model IDs and efforts are checked at run start, and whenever `config.json` changes:
     - Codex: against `model/list` (`step2step/codex/session.py:190-197`, validated at `:199-207`).
     - Claude: by a start check (spike).
   - Drop accounts that are marked unusable ([accounts](#accounts)).
2. **Pick the least busy pair.** Take the pair whose account runs the fewest Barrel sessions right now. Ties go to the option listed first, then to the account listed first (Q14: "세션은 계정에 나눠 띄운다").
3. **Subagent roles prefer the orchestrator's CLI.** The pairs on that CLI come first, and the role becomes a fresh session only when the tier has no usable option on that CLI. This follows Q02, which gives short read-only work to subagents ([roles](#roles)).
4. **Nothing usable.** If no pair is usable, the role waits for the earliest reset. The launcher posts a usage-limit stop if the run cannot go on.

Notes:
- **Teammates** with different subscriptions can share one `config.json`. Options this PC cannot run are simply dropped (Q16).
- **Efforts.** The effort names are `low`, `medium`, `high`, `xhigh` and `max`, as in the unit loop (`barrel/core/unitloop.py:43`).
  - On Codex, the launcher uses the nearest effort the model supports.
  - It records the effort actually used in the session list and the result report, so the change is never silent (AI; archived accounts-and-budget.md: no silent effort reduction).
- **Model IDs.** The model IDs above are defaults, checked against each CLI at run start. An ID the CLI does not know is dropped with a notice ([research.md](research.md#models)).

<a id="difficulty"></a>
### Leaf difficulty

When the orchestrator splits a medium topic, it gives each leaf a difficulty. Model and effort then follow the difficulty (Q16). The levels and their criteria are AI choices.

| Difficulty | When | Default |
| --- | --- | --- |
| `light` | Small and fully clear: exact inputs and outputs, error behavior, steps, a fixed verification, no open decision, limited risk (archived D-068) | `standard`, medium |
| `normal` | The default | `strong`, high |
| `hard` | Complex judgment, or code that is hard to verify | `strong`, max |

- Every leaf above `light` stays on the `strong` tier, which holds Opus 5.5, the implementation model in flow 0.
- The frontier tier comes in only through escalation, when failures repeat ([below](#escalation)).
- Size alone never makes a leaf `light` (AI, from archived D-068: clarity, not size).
- Auth, permissions, security, data integrity and external effects never go below `normal` (archived accounts-and-budget.md#model-policy).

<a id="accounts"></a>
## Accounts

- **Every registered and logged-in account is used**, whatever its login method (Q05, Q12):
  - Claude config folders: `~/.claude`, `~/.claude-<name>`, and any folder set in `CLAUDE_CONFIG_DIR`.
  - Codex homes: `~/.codex`, `~/.codex-<name>`, and `CODEX_HOME`.
  - On this Mac: `~/.claude`, `~/.claude-wook` and `~/.codex` (Q12).
- **Setup asks once for more** (flow 1: "유저에게 구독의 계정명을 입력받고"; Q05: "안되어있으면 그렇게 설정까지").
  - First-run setup lists the registered folders and asks whether the user has other subscriptions to add.
  - For each name given, it creates `~/.claude-<name>` or `~/.codex-<name>` and runs that CLI's login with the folder set.
  - `barrel setup --add-account` adds one later (AI).
- **Login check.** `claude auth status` and `codex login status` both exit 0 when the folder is logged in. They honor `CLAUDE_CONFIG_DIR` and `CODEX_HOME` ([research.md](research.md#vendors)).
- **Order.** The order kept in `~/.barrel/settings.json` breaks ties when sessions are spread ([selection](#selection)) (AI).
- **An account becomes unusable.** Either way, new sessions go to the other accounts (Q05), and the affected session is restarted from files on another account or engine (Q05, Q12). A task session's leaf keeps its lane changes, and the new session continues on top of them, as on resume ([task-execution.md](task-execution.md#stop)) (AI).
  - **A usage limit.** The launcher marks the account with its reset time.
  - **An expired login.** This never resets on its own (AI):
    - The account is marked as needing a login.
    - A request asks the user to log in again in that folder (Q01: logins are for the user).
    - The account comes back once `auth status` passes.
  - **A whole CLI.** When every account of a CLI is unusable, that CLI's options drop out of every tier until a reset or a login (Q12).
- **Reset times** come from the limit message: Claude's footer text, such as "7pm", and Codex's `resetsAt` values.
  - Today both are kept as raw text (`step2step/claude/screen.py:111-114`, `step2step/codex/session.py:504-516`); the launcher parses them.
  - When no time can be read, the launcher tries the account again every 30 minutes (AI).
- **Nothing is usable.** The run posts a usage-limit stop to the channel and resumes on its own at the earliest reset (Q01, option 1-a A; Q10). Login requests stay open meanwhile, and a login that is done first ends the stop sooner (AI).
- **Account per session.** The launcher starts each session with that account's `CLAUDE_CONFIG_DIR` or `CODEX_HOME`. Neither driver can do this yet: both build the child's environment from the launcher's own and take no per-session values.
  - Claude also drops every `CLAUDE*` variable (`step2step/claude/runner.py:153-163`).
  - Codex passes the launcher's `CODEX_HOME` through (`step2step/codex/transport.py:56-62`).

  Both need a per-session environment parameter ([launcher.md](launcher.md#reuse)).
- **Plugins** are installed per config folder, so setup installs Barrel's plugin into every account folder ([plugin.md](plugin.md#setup)).

<a id="escalation"></a>
## Escalation on repeated failure

Escalation reuses the unit loop's ladder (`barrel/core/failures.py:224-257`):
- When the same failure fingerprint repeats, effort goes up first, then the model changes.
- With tiers, the ladder moves to another option of the same tier, then to the next tier up, ending at `frontier` (AI). This matches the model tier doc's advice: go to Fable 5.1 or Astra when failure loops cost more than tokens.
- A refusal jumps straight to a different model (`failures.py:246-257`).

<a id="orchestrator"></a>
## Orchestrator lifecycle

- **Start.** The launcher starts the orchestrator with four things: its playbook, the project, the run, and either the start input or the latest handoff note (Q03-3, AI).
- **Turns.** The orchestrator works in turns that events trigger (AI, from the Q04-2 analysis).
  - It ends a turn after issuing launcher commands.
  - The launcher injects the next turn when something happens. The triggers are listed in the event catalog ([launcher.md](launcher.md#events)).
  - Events that arrive during a turn are queued and delivered together in the next turn.
  - Events that arrive while no orchestrator runs, during a handoff or after a crash, wait in the event log and go to the successor's first turn. An event counts as handled only when the turn that received it ends (AI).
- **Handoff triggers:**
  - The end of a stage (Q03-3, Q04-2).
  - During implementation, the end of each medium topic (Q03, option A: the orchestrator ends after one topic).
  - Context use above the threshold. The launcher measures it after every turn (Q03 analysis):
    - Claude: from `message.usage` in the transcript.
    - Codex: from `thread/tokenUsage/updated` events.

    When use passes `orchestrator.handoff_at_context` of the model's window (default 0.6, AI), the next turn asks for a handoff at the next safe point.
- **Safe point** (AI). A handoff happens only between turns, when none of the orchestrator's subagents is running. Leaves of other medium topics keep running in their lanes, and their events wait for the successor.
- **Handoff:**
  1. Every decision and status is already in units and task files. Nothing may live only in the conversation (Q03).
  2. The orchestrator writes a short handoff note in its run-state folder `~/.barrel/projects/<id>/runs/<run>/orchestrator/`: where things stand, what comes next, which threads are open (AI).
  3. It calls `barrel handoff`.
  4. After the turn ends, the launcher commits `.barrel/`, closes the session and starts the successor with the note.
  5. The successor may run on another engine (Q04-2, Q16).
- **Compaction.** In orchestrators, a PreCompact hook blocks automatic compaction and asks the launcher for a handoff instead. Claude blocks with exit code 2, Codex with `continue: false` ([research.md](research.md#vendors), AI).
- **Crash or stall** (AI). The launcher watches the orchestrator like any other session: the Claude watchdog (`step2step/claude/watchdog.py`), and app-server events for Codex. If the orchestrator dies, or stalls past the budget's stall and progress limits, the launcher closes it and starts a successor from the memory, the run state and the last handoff note. This is the same path as resume.

<a id="markers"></a>
## What every Barrel session carries

- **Role markers.** These are environment variables; hooks branch on them ([plugin.md](plugin.md#markers); 09-29 draft; spike):
  - `BARREL_ROLE`, `BARREL_PROJECT`, `BARREL_RUN`
  - `BARREL_TASK` and `BARREL_LANE`, in task sessions only

  Subagents inherit their parent's markers.
- **A playbook.** The first prompt names the role's playbook, a plain file shipped with the plugin ([plugin.md](plugin.md#playbooks)).
- **Its input files.** Only those ([memory.md](memory.md#context)).
