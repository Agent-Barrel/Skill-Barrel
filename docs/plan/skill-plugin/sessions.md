# Sessions, roles and engines

<a id="roles"></a>
## Roles

| Role | Does | Runs as | Default tier and effort | Source |
| --- | --- | --- | --- | --- |
| Invoking session | First-run setup and start, then it ends | The user's own session | none | Q03-3 |
| Orchestrator | Assesses impact, interviews, splits the tree, writes contracts, checks plans and memory updates, decides, reports. One per run | A fresh session started by the launcher | strong, max | Q03-3, Q04-2, Q18 |
| Task session | Implements one leaf | A fresh session | By the leaf's difficulty ([below](#difficulty)) | Q02, flow 0 |
| Advice | A second opinion on a hard decision | A subagent of the orchestrator\* | frontier, max | flow 0, Q02, Q16 |
| Intent check | Checks a leaf's plan against its contract and units | A subagent of the orchestrator\* | strong, medium | Q02; archived P-001 |
| Context gathering | Follows memory links; surveys code before a split or at onboarding; checks new packages | A subagent of the orchestrator\* | standard, medium | Q02; Q19 |
| Research | Researches a question with current sources | A subagent of the orchestrator\* | strong, max | flow 5, flow 7, Q02, Q16 |
| Verification | Checks the research's claims against their sources | A subagent of the orchestrator\* | strong, high | Q02, Q16 |
| Review | Reviews a high-risk leaf, or a UI leaf against its design, after its gates pass; checks one large topic in the S8 acceptance | A subagent of the orchestrator\* | strong, max | Q02; archived Q-004; Q01; Q17 |
| Designer | Draws the wireframes from the functional spec, then the detailed design of the main screens, with images from any service ([workflow.md](workflow.md#design)) | A fresh session | strong, high | archived Q-010, Q-011, Q-019; Q17 |
| Experiment | Runs one minimal experiment for an S6 choice, in its own run-state folder ([workflow.md](workflow.md#experiments)) | A fresh session | strong, high | archived D-042; Q17 |
| Korean writer | Writes Korean text from an English source with Skill-Techblog | A fresh session | strong, high | Q08, Q16 default |

The Source column covers each role and how it runs. The default tiers and efforts are AI choices ([engines](#engines)), except two:
- frontier for advice comes from flow 0
- medium for the intent check comes from archived D-067

**How Q02 splits the work.** The user chose option A:
- **Fresh sessions:** implementation, anything that needs plan approval, and anything that must survive an orchestrator restart. Design and experiments write files and can run long, so they are fresh sessions too (AI).
- **Subagents:** short read-only work whose result can come back as a summary. That covers gathering context, research (자료 조사), and independent review by someone other than the worker (작업자가 아닌 쪽의 독립 검토).
- A task session may use subagents of its own. How it uses them is up to that session. Barrel does not assign, watch or review them one by one; it is responsible for the leaf it assigned and for its result (archived Q-006; Q17).

**Notes on the table:**
- \* **Subagent or fresh session.**
  - A role marked \* runs as a subagent of the orchestrator when the engine chosen for it ([selection](#selection)) is on the orchestrator's CLI.
  - Otherwise it runs as a fresh session started with `barrel session start`, because a subagent can only use its parent's CLI.
  - The same happens when the engine cannot set a subagent's model or effort per call: that role then runs as a fresh session with the tier's model (spike fallback).
  - This is a limit of the engines, not a policy about providers (Q16).
- **Subagents and files** (AI).
  - Subagents never write the project.
  - A research, verification or review subagent writes its full report into the orchestrator's run-state folder and returns only the path and a short summary. The report then stays out of the orchestrator's context.
  - Enforcement: a subagent inherits the orchestrator's markers, but Claude's hook input marks subagent calls (`agent_id`), so the hook limits them to that folder ([plugin.md](plugin.md#hooks)). Whether Codex hooks can tell a subagent's calls apart is a spike check.
- **Independence** (Q16).
  - The verification subagent gets the research report and its sources, never the research conversation.
  - A review subagent gets the contract, the units, the diff or the screenshots, and the gate output, never the task session's conversation.
- **No subagent across a handoff** (AI). The orchestrator hands off only when none of its subagents is running ([lifecycle](#orchestrator)), so subagent work never has to survive a restart.
- **Fresh auxiliary sessions end with a memory turn** (Q24). Designer, experiment and Korean-writer sessions record what they learned before they end ([memory.md](memory.md#queue)).
- **The Korean writer is always a fresh session** (Q16 default). It writes files, and Skill-Techblog starts a subagent of its own.
- **Images are not tied to an engine** (archived Q-019; Q16). The designer uses whatever image service is available: Codex's built-in image generation when it runs on Codex, or any other service through browser automation with the user's sign-ins ([workflow.md](workflow.md#design)).
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
| Claude Code | `--dangerously-skip-permissions` (`step2step/claude/runner.py:363-370`) | Entered with Shift+Tab before the prompt (`step2step/claude/session.py:222-223`). Approval picks option 1 of the plan menu (`step2step/claude/runner.py:1287-1310`), which puts the session back in bypass (`step2step/claude/session.py:107-110`). On the verified 2.1.272 its label reads "Yes, and switch to bypass permissions" (`step2step/claude/screen.py:68`) |
| Codex | Approval `never` and sandbox `danger-full-access`, the defaults (`step2step/codex/session.py:44-54`) | The planning turn runs read-only. Execution turns use the session's sandbox (`step2step/codex/session.py:183-188`) |

- The orchestrator and the auxiliary sessions run in the same modes. Their hooks limit where they may write.
- A PreToolUse deny is expected to block a call in bypass mode too. The spike checks this on both engines ([validation.md](validation.md) item 5).

<a id="engines"></a>
## Engines and `.barrel/config.json`

- **Engines.** Claude Code and Codex are engines that run Barrel, and any role can run on either one (Q16).
- **One engine is enough.** A CLI that is not installed drops out of every tier (archived D-004).
- **Where models are set.** Model assignment lives in `.barrel/config.json` in the planning repo, so the team can share and edit it (Q12).
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
    "designer":      {"tier": "strong",   "effort": "high"},
    "experiment":    {"tier": "strong",   "effort": "high"},
    "ko_writer":     {"tier": "strong",   "effort": "high"}
  },
  "leaves": {
    "light":  {"tier": "standard", "effort": "medium"},
    "normal": {"tier": "strong",   "effort": "high"},
    "hard":   {"tier": "strong",   "effort": "max"}
  },
  "concurrency": {"implementation": 2},
  "orchestrator": {"handoff_at_context": 0.6},
  "memory": {"turn_seconds": 600},
  "cascade": {"default": "ask"},
  "git": {"delivery": null, "github_autosave": null},
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
- **`memory.turn_seconds`:** how long a session may hold its memory turn before it loses it ([memory.md](memory.md#queue)) (Q24 default).
- **`cascade.default`:** what happens when a change affects running leaves: `ask`, `next_task` or `now` ([workflow.md](workflow.md#cascade)) (archived D-031; Q17).
- **`git.delivery`:** how a finished run is delivered ([runs.md](runs.md#delivery)). `git.github_autosave` turns off the automatic private GitHub repository for this project (archived Q-003).
- **`env.setup`:** commands that install the project's dependencies in a worktree. They run when a lane or an integration worktree is prepared and a dependency manifest changed since that worktree's last use. The unit loop has no such command today.
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

- **Who fills the project values.** The orchestrator fills `env`, `task_runner.preflight` and `task_runner.baseline`: in S2 for an existing project, in S6 for a new one.
- **Who writes the file.** The launcher writes the default file once, at a project's first run, before any orchestrator exists. After that, among Barrel's sessions only the orchestrator edits it, in its memory turn, and people edit it like any file in the repo (Q12; [memory.md](memory.md#rules)).
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
2. **Pick the least busy pair.** Take the pair whose account runs the fewest Barrel sessions right now, across every project and run on the PC. Ties go to the option listed first, then to the account listed first (Q14: "세션은 계정에 나눠 띄운다"; Q11).
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

- **Every registered, logged-in subscription account is used** (Q05, Q12):
  - Claude config folders: `~/.claude`, `~/.claude-<name>`, and any folder set in `CLAUDE_CONFIG_DIR`.
  - Codex homes: `~/.codex`, `~/.codex-<name>`, and `CODEX_HOME`.
  - On this Mac: `~/.claude`, `~/.claude-wook` and `~/.codex` (Q12).
- **Setup asks once for more** (flow 1: "유저에게 구독의 계정명을 입력받고"; Q05: "안되어있으면 그렇게 설정까지").
  - First-run setup lists the registered folders and asks whether the user has other subscriptions to add.
  - For each name given, it creates `~/.claude-<name>` or `~/.codex-<name>` and runs that CLI's login with the folder set.
  - `barrel setup --add-account` adds one later (AI).
- **Login check.** `claude auth status` and `codex login status` both exit 0 when the folder is logged in. They honor `CLAUDE_CONFIG_DIR` and `CODEX_HOME` ([research.md](research.md#vendors)).

<a id="barrel-folders"></a>
**Barrel-managed config folders** (archived D-048; Q17, Q17-2: "이건 반영해줘야 해"; layout AI).
- **What they are.** Sessions do not run from the user's own folders. For each account, Barrel keeps its own config folder, named by the account as flow 1 asks:
  - `~/.barrel/accounts/claude-<account>/` as `CLAUDE_CONFIG_DIR`
  - `~/.barrel/accounts/codex-<account>/` as `CODEX_HOME`

  `~/.claude` counts as the account `default`.
- **The login is the account's.**
  - Login and configuration are kept apart (archived D-048).
  - Claude keeps one Keychain item per config folder, and Codex keeps its login in `auth.json`. So setup makes the Barrel folder use the account's existing login: by copying the login item or the file (spike).
  - If the login cannot be reused this way, setup signs in each Barrel folder once. Keeping personal settings out comes first, because the user said this decision must be in the skill (Q17-2; spike fallback).
- **What is in a Barrel folder:**
  - the Barrel plugin, Skill-Techblog and the Slack MCP ([plugin.md](plugin.md#install))
  - only the personal settings the user picked at setup: instructions, memory, MCP servers, skills and hooks (archived D-048)

  Picked instructions and memory become shared preferences ([memory.md](memory.md#shared)), so every engine and account sees the same context (flow 1). Picked MCP servers and skills go into the Barrel folders of both engines where the engine supports them. Hooks go only to the engine they were written for (AI).
- **What it never touches:** the user's own folders, beyond installing the Barrel plugin so the skill can be invoked there, and any managed policy of the organization (archived D-048).
- **Recorded.** Each session records the configuration and the versions it actually loaded, in the session list and the result report (archived D-048; [task-execution.md](task-execution.md#report)).

<a id="paid"></a>
**Subscriptions only** (archived D-012, D-033, D-056; Q17).
- **What Barrel runs on.** Sessions use subscription logins only. Paid usage beyond the subscriptions, such as API keys or extra credits, is off, and Barrel never switches to it silently.
- **How it is enforced.**
  - Codex: step2step accepts only a ChatGPT login (`step2step/codex/session.py:97-99`, `step2step/codex/transport.py:76`).
  - Claude: step2step removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and the `CLAUDE*` variables from the child's environment (`step2step/claude/runner.py:72-83`, `:153-163`). It does not check how a config folder is logged in, so setup checks each Claude account's login method and leaves out any account that is not a subscription login (AI; spike).
- **No path to turn it on.** This version has none. If one is added, archived D-012 and D-033 apply: explicit permission, a monthly budget across all projects, and a strict or estimate mode.
- **An earlier sentence is corrected.** The 2026-10-11 design said every account is used "whatever its login method". That contradicted step2step's Codex check and this decision.

**When an account becomes unusable.** Either way, new sessions go to the other accounts (Q05), and the affected session is restarted from files on another account or engine (Q05, Q12). A task session's leaf keeps its lane changes, and the new session continues on top of them, as on resume ([task-execution.md](task-execution.md#stop)) (AI).
- **A usage limit.** The launcher marks the account with its reset time.
- **An expired login.** This never resets on its own (AI):
  - The account is marked as needing a login.
  - A request asks the user to log in again ([slack.md](slack.md#launcher-requests)) (Q01: logins are for the user).
  - The account comes back once `auth status` passes.
- **A whole CLI.** When every account of a CLI is unusable, that CLI's options drop out of every tier until a reset or a login (Q12).

**Reset times** come from the limit message: Claude's footer text, such as "7pm", and Codex's `resetsAt` values.
- Today both are kept as raw text (`step2step/claude/screen.py:111-114`, `step2step/codex/session.py:504-516`); the launcher parses them.
- When no time can be read, the launcher tries the account again every 30 minutes (AI).

**Nothing is usable.** The run posts a usage-limit stop to the channel and resumes on its own at the earliest reset (Q01, option 1-a A; Q10). Login requests stay open meanwhile, and a login that is done first ends the stop sooner (AI).

**Account per session.** The launcher starts each session with its Barrel-managed `CLAUDE_CONFIG_DIR` or `CODEX_HOME`. Neither driver can do this yet: both build the child's environment from the launcher's own and take no per-session values.
- Claude also drops every `CLAUDE*` variable (`step2step/claude/runner.py:153-163`, at `:160`), and a test asserts that none survives (`tests/test_env_scrub.py:6-13`). A per-session value has to be added after the scrub.
- Codex passes the launcher's `CODEX_HOME` through (`step2step/codex/transport.py:56-62`).

Both need a per-session environment parameter ([launcher.md](launcher.md#reuse)).

<a id="escalation"></a>
## Escalation on repeated failure

Escalation reuses the unit loop's ladder (`barrel/core/failures.py:224-257`):
- When the same failure fingerprint repeats, effort goes up first, then the model changes.
- With tiers, the ladder moves to another option of the same tier, then to the next tier up, ending at `frontier` (AI). This matches the model tier doc's advice: go to Fable 5.1 or Astra when failure loops cost more than tokens.
- A refusal jumps straight to a different model (`failures.py:246-257`).

<a id="orchestrator"></a>
## Orchestrator lifecycle

- **One per run.** Each run has its own orchestrator; several runs of a project have several (Q18).
- **Start.** The launcher starts the orchestrator with four things: its playbook, the project, the run, and either the start input or the latest handoff note (Q03-3, AI).
- **Turns.** The orchestrator works in turns that events trigger (AI, from the Q04-2 analysis).
  - It ends a turn after issuing launcher commands.
  - The launcher injects the next turn when something happens. The triggers are listed in the event catalog ([launcher.md](launcher.md#events)).
  - Events that arrive during a turn are queued and delivered together in the next turn.
  - Events that arrive while no orchestrator runs, during a handoff or after a crash, wait in the event log and go to the successor's first turn. An event counts as handled only when the turn that received it ends (AI).
- **Writes go through the memory queue** (Q24). The orchestrator writes `.barrel/` only inside a memory turn (`barrel memory begin` … `barrel memory end`), like every other writer ([memory.md](memory.md#queue)).
- **Memory duties** (Q24, Q24 default):
  - In the turn after a leaf finishes, it checks the leaf's memory update against the contract.
  - At the end of each medium topic, it consolidates the memory that topic changed, and promotes verified experience to shared memory.
- **Handoff triggers:**
  - The end of a stage (Q03-3, Q04-2).
  - During implementation, the end of each medium topic (Q03, option A: the orchestrator ends after one topic).
  - Context use above the threshold. The launcher measures it after every turn (Q03 analysis):
    - Claude: from `message.usage` in the transcript.
    - Codex: from `thread/tokenUsage/updated` events.

    When use passes `orchestrator.handoff_at_context` of the model's window (default 0.6, AI), the next turn asks for a handoff at the next safe point.
- **Safe point** (AI). A handoff happens only between turns, when none of the orchestrator's subagents is running. Leaves of other medium topics keep running in their lanes, and their events wait for the successor.
- **Handoff:**
  1. Every decision and status is already in units and task files. Nothing may live only in the conversation (Q03). The orchestrator's last memory turn makes sure of it (Q24).
  2. The orchestrator writes a short handoff note in its run-state folder `~/.barrel/projects/<id>/runs/<run>/orchestrator/`: where things stand, what comes next, which threads are open (AI).
  3. It calls `barrel handoff`.
  4. After the turn ends, the launcher closes the session and starts the successor with the note.
  5. The successor may run on another engine (Q04-2, Q16).
- **Compaction.** In orchestrators, a PreCompact hook blocks automatic compaction and asks the launcher for a handoff instead. Claude blocks with exit code 2, Codex with `continue: false` ([research.md](research.md#vendors), AI).
- **Crash or stall** (AI). The launcher watches the orchestrator like any other session: the Claude watchdog (`step2step/claude/watchdog.py`), and app-server events for Codex. If the orchestrator dies, or stalls past the budget's stall and progress limits, the launcher closes it and starts a successor from the memory, the run state and the last handoff note. This is the same path as resume.

<a id="markers"></a>
## What every Barrel session carries

- **Role markers.** These are environment variables; hooks branch on them ([plugin.md](plugin.md#markers); 09-29 draft; spike):
  - `BARREL_ROLE`, `BARREL_PROJECT`, `BARREL_RUN`
  - `BARREL_TASK` and `BARREL_LANE`, in task sessions only

  Subagents inherit their parent's markers.
- **Its Barrel-managed config folder** for its account ([accounts](#barrel-folders)).
- **A playbook.** The first prompt names the role's playbook, a plain file shipped with the plugin ([plugin.md](plugin.md#playbooks)).
- **Its input files.** Only those ([memory.md](memory.md#context)).
