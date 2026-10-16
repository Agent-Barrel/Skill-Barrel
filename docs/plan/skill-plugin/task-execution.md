# Task execution

Leaves are executed by the launcher's task runner. The task runner is the unit loop (`barrel/core/unitloop.py`) extended for the task tree, for both engines, for parallel lanes over several repos, and for the memory queue. [launcher.md](launcher.md#reuse) lists what is reused and what changes.

<a id="preflight"></a>
## Before the first leaf: preflight and baseline

At the start of S7, before any leaf runs (09-29 draft, S5; AI):

1. **Preflight.** The unit loop's checks from `task_runner.preflight`: tools, free disk space, and the configured commands (`barrel/core/preflight.py`, run at `barrel/core/unitloop.py:516-527`).
2. **Environment.** `env.setup` runs in the integration worktrees ([sessions.md](sessions.md#engines)). Product secret files, such as `.env`, are written there from the Keychain ([memory.md](memory.md#secrets)).
3. **Baseline.** The project's existing checks in `task_runner.baseline` run once on the head of the run branches, and their results are kept in run state, down to each failing test or error. A failure seen here is pre-existing ([below](#pre-existing)). This is what makes "unrelated to the request" provable (archived Q-005; archived orchestration.md).

A preflight or environment failure does not end the run, as it does in the unit loop (exit code 3, `barrel/core/unitloop.py:516-527`). It goes to the orchestrator. The orchestrator fixes it with a setup leaf, or asks the user, for example to approve installing a tool ([user-only](#user-only)) (AI).

<a id="lifecycle"></a>
## One leaf, start to finish

1. **Ready.**
   - Every node in `depends_on` is done (the unit loop rule, `unitloop.py:542-548`).
   - The parallel rule allows it ([lanes](#lanes)).
   - A lane is free.

   The launcher starts ready leaves from its queue on its own. `barrel task start` exists only for the orchestrator to force one (AI).
2. **Prepare the lane** (Q14, AI).
   - **A new leaf:** reset the lane's worktree of every repo to the head of the leaf's run branch, as a detached HEAD ([runs.md](runs.md#branches)).
   - **A leaf that was interrupted or moved to another account:** keep its lane as it is, leftover changes included ([stop](#stop)).
   - **A leaf with a parked patch:** reset the lane, then apply the patch ([questions](#questions)).
   - **Dependencies:** run `env.setup` if a dependency manifest changed since the lane's last leaf.
   - **Product secret files:** written from the Keychain into git-ignored files ([memory.md](memory.md#secrets)).
3. **Baseline.** The leaf's gates must fail before work starts. This is the unit loop's must-fail-first rule (`gates.py:188-197`, used at `unitloop.py:589-602`). The tests come from an earlier test leaf, so they exist at this point ([task-tree.md](task-tree.md#tests)).
   - A gate that already passes is a gate defect, and the leaf goes back to the orchestrator.
   - Three exceptions, because their gates may already pass:
     - a leaf with `expect_baseline_fail: false` ([task-tree.md](task-tree.md#fields))
     - a resumed leaf ([stop](#stop))
     - a leaf that runs again with its parked patch ([questions](#questions))
4. **Start a fresh session.**
   - Engine and account come from the leaf's difficulty ([sessions.md](sessions.md#difficulty)). The session runs from that account's Barrel-managed config folder ([sessions.md](sessions.md#accounts)). Permission modes are in [sessions.md](sessions.md#modes).
   - **Working directory:** the lane's folder of the repo the leaf writes. A leaf that writes several repos works from the lane's root, which holds them all (AI).
   - **Mode and markers:** plan mode, with `BARREL_TASK` and `BARREL_LANE` set.
   - A leaf with `browser: true` also gets the browser-automation server ([user-only](#user-only)).
   - **The first prompt** holds the contract, the units in `memory_units`, the memory indexes and the in-progress list ([memory.md](memory.md#queue)), and a pointer to the task playbook (insight; Q24).
5. **Capture the plan.**
   - Codex returns the plan text before approval (`step2step/codex/session.py:274-290`).
   - Claude does not, yet:
     - `pending.plan` is filled only when the transcript already holds the ExitPlanMode call (`step2step/claude/session.py:358-375`).
     - The step2step hook drops the tool input (`step2step/claude/hooks.py:38-43`).

     A hook that records ExitPlanMode's `tool_input` closes this gap ([plugin.md](plugin.md#hooks)).
6. **Intent check.**
   - The launcher emits `plan_ready`.
   - The orchestrator checks the plan against the contract and its units, with an intent-check subagent (Q02; archived P-001: "plan mode is not the check").
   - It then calls `barrel task approve`, or `barrel task reject --feedback …`. These map to `approve_plan()` and `reject_plan(feedback)` (`step2step/claude/session.py:486-509`, `step2step/codex/session.py:420-439`).
   - If the contract itself is wrong, the orchestrator fixes the contract and starts a new attempt.
7. **Implement.**
   - Gates run after turns: every-turn layers first, then the final layers (`_judge`, `unitloop.py:792-820`).
   - A failure goes back to the same session as feedback (`render_feedback_prompt`, `unitloop.py:302-322`).
   - A suspiciously cheap pass is re-run (checked at `gates.py:202-210`, re-run at `unitloop.py:803-811`).
   - Stale artifacts count as failures (checked at `gates.py:213-225`, applied at `unitloop.py:812-818`).
8. **Check the write set and the packages.**
   - Every changed file must be in `write_set`. A change outside it fails the attempt and goes back to the orchestrator. A session never widens its own scope (09-29 draft).
   - Every package added to a dependency manifest must be in `packages` ([packages](#packages)).
9. **Review.** Only if `review` lists `code` or `visual`. The launcher emits `review_needed`; the orchestrator runs a review subagent ([review](#review)) and calls `barrel task review <id> --pass` or `--findings <file>` (Q02).
10. **Commit in the lane.**
    - In each repo the leaf changed, only the leaf's paths are committed, with `gitops.commit` (`barrel/core/gitops.py:78-134`) instead of `commit_all`. Product secret files are never committed ([memory.md](memory.md#secrets)).
    - The commits go on the lane's detached HEADs.
    - The message keeps the unit loop's format, `T1.2.3: <title>` (`unitloop.py:823-845`), with a `Barrel-Run: <run>` trailer (AI).
11. **The finishing turn** (Q24; [memory.md](memory.md#finish)). The session queues for the project's memory queue and, in its turn:
    1. **Merge.** The launcher makes a trial merge of the leaf's commits into the run branch of each repo, in the integration worktrees ([lanes](#lanes)). The leaf's gates run again on the merged tree (Q14), and the merge is committed only if they pass. A leaf that changed several repos is merged in all of them or in none (AI).
    2. **Show.** The session is shown the latest memory, including the units others changed while it waited.
    3. **Write.** The session records what it built, what it learned and the choices it made inside its contract.
    4. **Check and commit.** The launcher checks the update and commits it with the leaf's `done` status and commits.
    5. **Close.** The session ends.

    If the merge fails, the session still records what it learned, and the leaf runs again ([lanes](#lanes)).
12. **Report.**
    - The result report goes to run state ([report](#report)).
    - The launcher emits `task_done`, which goes into the medium topic's Slack thread ([slack.md](slack.md#what)).
    - In its next turn, the orchestrator checks the leaf's memory update against the contract (Q24 default).

<a id="packages"></a>
## New packages

From [Q19](../interview/q19-new-technology-threshold.md); the mechanism is AI.

- **Listed in advance.** When the orchestrator writes a contract, it lists in `packages` the packages the leaf may add.
- **Checked before the contract is committed.** For each package, a context subagent checks:
  - that it exists in its registry, which catches invented package names
  - that it is maintained, with a recent release and a live repository
  - that its license is acceptable
  - that the chosen version has no known vulnerability, from a public vulnerability database such as OSV ([research.md](research.md#vendors))
- **Restricted licenses and costs.** A package whose license restricts use, or that costs money, is not an ordinary library. It goes to the user as a hard-to-reverse choice (Q19; [workflow.md](workflow.md#new-technology)).
- **Checked after the leaf.** The launcher compares the changes to the dependency manifests with `packages`. A package that is not listed fails the attempt and returns to the orchestrator. The orchestrator checks it as above, then allows it in a new contract revision or rejects it.
- **Reported.** The final report lists the ordinary libraries Barrel chose ([acceptance](#acceptance)) (Q19).

<a id="questions"></a>
## Questions from a task session

- **No guessing.** A task session's question is never answered with a guess. This replaces the unit loop's fixed answer, "Use your best judgement and continue; do not ask again." (`unitloop.py:82`, `:774-776`) (Q01).
- **The path.** The launcher reads the question (`PendingInteraction.questions`, `step2step/contracts.py:63-74`) and emits `task_question`. The orchestrator then takes one of two paths:
  - **The memory answers it.**
    - The orchestrator records a `decision` unit and calls `barrel task answer`.
    - The launcher types the answer into the waiting session: Claude through `answer_menu` / `answer_menu_text` (`step2step/claude/session.py:449-484`), Codex through `answer_questions` (`step2step/codex/session.py:366-389`) (Q01).
  - **The memory does not answer it.**
    - The orchestrator asks in Slack ([interviews.md](interviews.md)), and the leaf is blocked.
    - **The session records what it learned** in a memory turn, then closes (Q24).
    - **The leaf gives up its lane** (AI), so blocked leaves never hold every lane while unrelated work waits (Q01).
      - Its changes so far are saved as a patch in the run state's `parked/`.
      - After the answer, the orchestrator updates the contract. The leaf then runs again in a new session, in a free lane, with the patch applied on top of the run branch's head (09-29 draft, AI).
      - If the updated contract makes the patch obsolete, the orchestrator drops it.
    - Unrelated leaves keep running (Q01).
- **Codex task sessions** (spike fallback). If Codex's `request_user_input` does not work in its default mode, the task playbook has the session emit `barrel event --type question` with its question and end its turn. The launcher then handles it as `task_question`.
- **Multi-question widgets.** Claude multi-question widgets are not supported by step2step (`step2step/claude/session.py:426-429`). The launcher interrupts the session and asks it to put one question at a time (AI, spike).
- **Decisions found late.** A task question can show a decision that S3–S5 should have found. The orchestrator then records which discovery method missed it in the decision unit, so the method can be fixed ([interviews.md](interviews.md#discovery)) (09-29 draft).

<a id="failures"></a>
## Failures

- **Classification.** Failures are classified and fingerprinted (`barrel/core/failures.py:26-33`, `:88-128`, `:180-184`).
- **Within one attempt.** The session gets gate feedback.
  - When the same fingerprint repeats `task_runner.repeat_limit` times, the leaf climbs the ladder (`unitloop.py:756-757`).
  - The ladder raises effort, then changes model, then moves to the next engine option or tier ([sessions.md](sessions.md#escalation)).
  - A refusal is the exception: it never climbs the ladder to another model or engine, and goes to the orchestrator instead (archived D-041; [sessions.md](sessions.md#escalation)).
- **Environment failures.**
  - The recovery command `task_runner.gates.env_recover` runs once (`unitloop.py:740-755`).
  - If that does not help, only this leaf stops and goes to the orchestrator.
  - The unit loop halts the whole run at this point (`unitloop.py:752`, `:755`); Barrel does not (Q01: only the blocked work stops).
- **Gate defects** send the leaf back to the orchestrator, which fixes the contract's gates. This applies whether the gate passes before any work or breaks during an attempt. The unit loop halts the whole run on a gate defect (at baseline `unitloop.py:565-566`, during an attempt `:738-739` through `:623`); Barrel does not ([launcher.md](launcher.md#reuse)) (Q01).
- **The run as a whole stops in only two cases:**
  - the user's stop (Q10-2)
  - the usage-limit stop, when no account and no engine can run, which resumes on its own at the reset (Q01, Q10)

  A user's cancel ends one run ([runs.md](runs.md#cancel)).
- **Harness problems** (stalls, unconfirmed submits, dead sessions, unresolved dialogs): the session is replaced (`unitloop.py:709-724`).
- **Usage limit.** The leaf moves to the next account or engine and keeps its lane changes (Q05, Q12; [sessions.md](sessions.md#accounts)). This replaces the unit loop's wait on the same session (`unitloop.py:703-708`), which sleeps `min(usage_wait_seconds, the remaining run budget)` (`:704`; 900 s by default, `:81`).
- **Budgets.** These come from `task_runner.budget`, which is the unit loop's `Budget` (`barrel/core/failures.py:262-271`).
  - Per turn and per leaf, as in the unit loop: 3,600 s per turn, 12 turns and 4 hours per leaf, plus the stall and progress limits.
  - A leaf that runs out of its budget counts as a failed attempt and climbs the ladder. It does not wait for the user (AI).
  - There is no run-wide clock. The unit loop stops a whole run after 24 hours (`run_wall_seconds`, `failures.py:269`, checked at `unitloop.py:540-541` and before every turn at `:671-673`), while a Barrel run lasts as long as its work (Q01; AI).
- **No endless retries on the same evidence** (archived D-040). When the alternatives run out, the leaf is abandoned with its attempts and the remaining options. Its session records what it learned first (Q24). The orchestrator then does one of these:
  - re-splits the work
  - changes the method within the approved requirements, stack and cost (archived D-041)
  - asks the user, if the change touches one of these:
    - requirements, the stack, cost, or a method the user mandated (archived D-041)
    - scope or permissions (AI, from Q01: what only the user can decide)

  **Dropping a requirement is always asked** (Q01; archived D-041). The user decides whether it is dropped, changed, or kept with another approach. The AI never delivers it as "left open" on its own.

  Abandoned leaves are posted to the channel (Q10).

<a id="review"></a>
## Independent review

- **Which leaves.** When splitting, the orchestrator marks a leaf for review:
  - `code`, if it touches core logic, auth, data integrity or external effects (archived Q-004)
  - `visual`, if it builds or changes a screen that has an approved design (Q17; [workflow.md](workflow.md#design))
- **How.** After the gates pass, the launcher emits `review_needed`. The orchestrator runs a review subagent (Q02: independent review by someone other than the worker). The subagent never gets the task session's conversation.
  - A **code review** gets the contract, the units, the diff and the gate output.
  - A **visual review** gets screenshots of the affected screens, captured by the leaf's gates (for example with Playwright), and the approved design with its references. It checks the screens against them, including how the references' techniques were applied (archived Q-019; AI).
- **Findings.** The subagent splits its findings into mandatory and optional.
  - Mandatory findings go back to the leaf (`barrel task review <id> --findings <file>`).
  - The leaf re-verifies and is reviewed again (archived orchestration.md#verification).

<a id="pre-existing"></a>
## Pre-existing failures

When a check fails for a reason unrelated to the request, the orchestrator explains the cause and the impact, and asks the user one of two things:
- split the failure off as separate work
- widen the fix to include it

Rules:
- Work whose completion depends on the answer waits (archived Q-005).
- A failure counts as pre-existing only if the S7 baseline shows it ([preflight](#preflight)). The comparison is per failure, not per check: in a check that already failed, a new failing test, or one that got worse, is the run's to fix (archived Q-005).
- A check that did not run, is flaky, or failed for an unknown reason never counts as pre-existing.

<a id="lanes"></a>
## Parallel lanes

- **How many:** up to `concurrency.implementation` leaves run at once, default 2 (Q14). The limit is per project, and all runs of the project share it (Q18).
- **Which leaves** (archived D-032, as written, and Q24). Two leaves of a run run together only if all of these hold:
  - neither depends on the other
  - neither one's write set overlaps the other's write set or read set
  - they share no entry in `resources`: a port, a database, a real path outside the repo, a shared environment such as a staging deployment, an external service, or an account with its budget
  - neither may change a memory unit that the other reads or may change: one leaf's `memory_writes` against the other's `memory_units` and `memory_writes` (Q24)

  The last rule applies archived D-032, "참조 문서 변경을 먼저 끝낸 뒤 이를 읽는 구현을 시작한다", to memory units. When independence is unclear, the leaves run one at a time. A read-only investigation leaf writes only its report in run state, so it never conflicts.
- **Across runs** (Q18; AI).
  - The launcher gives free lanes to the ready leaves of the project's runs in turn, oldest waiting first, so no run starves.
  - Leaves of different runs commit to different run branches. Between them, the `resources` rule and the memory-unit rule apply, because the in-progress list covers every run of the project (Q24). Overlaps in files are settled when the later run merges the earlier one ([runs.md](runs.md#delivery)).
- **Across projects** (archived D-032: by dependencies, not by project boundaries; AI). The `resources` rule also applies between projects on the PC, for example two leaves that need the same port, database or account budget.
- **Lanes** are git worktrees under `~/.barrel/projects/<id>/lanes/<n>/<repo>/`, one per repo of the project, each on a detached HEAD ([runs.md](runs.md#branches)).
  - They are reused, and each one is reset to the head of the leaf's run branch before a new leaf.
  - Reuse keeps installed dependencies, and `env.setup` runs when a manifest changed (Q14, AI).
- **Lane numbers and ports.** Each lane gets `BARREL_LANE` for its paths. Each running leaf also gets `BARREL_PORT`, a port range that is unique on the PC, so gates that start a server never collide across projects (AI).
- **Integration worktrees:** `~/.barrel/projects/<id>/runs/<run>/integration/<repo>/`, each checked out on the run branch of its repo. Merges and post-merge gates run there, and the planning repo's `.barrel/` changes are made there, all through the memory queue (AI; Q24).
- **Trial merge:** when a leaf passes in its lane, its finishing turn merges its commits into the run branches without committing. The leaf's gates then run again on the merged tree (Q14).
  - If they pass, the merges are committed.
  - If they fail, the merges are aborted. So a run branch never holds a failing leaf merge, and other lanes never reset onto one (AI).
  - The one exception is a merge of a base that moved: it is kept, so that leaves can fix it on top ([runs.md](runs.md#delivery)).
- **Conflict, or a failure after the merge:** the leaf runs again in a new session from the head of the run branch. Its prompt describes the change it collided with (Q14). Telling an agent about the concurrent change recovered most broken merges in the STALE study ([research.md](research.md#prior-art)).
- **Start-up:** sessions are spread across accounts and started one at a time with a short gap, to avoid burst throttling (Q14, AI).
- **Priority:** sessions and gate commands run at a lower scheduling priority, so the user's own work on the Mac stays responsive (archived D-016; [launcher.md](launcher.md#process)).
- **Not counted:** auxiliary sessions do not count against the concurrency (Q14, AI):
  - subagents run inside the orchestrator
  - designer, experiment and Korean-writer sessions write no product code in a lane

<a id="regression"></a>
## Regression checks

The leaf's own gates on the merged tree cannot see a later merge that breaks an earlier leaf. So the gates run again at three points:

1. **After each merge:** the merged leaf's gates (Q14).
2. **When a medium topic's last leaf is merged:** every gate of that topic's done leaves, on the head of the run branches (Q14 "합친 결과로 게이트를 다시 돌린다"; scope AI). The memory consolidation of the topic happens at the same point ([memory.md](memory.md#queue)) (Q24).
3. **At S8, before acceptance:** every gate of the run (archived D-024).

A failure becomes a new leaf in its topic (AI).

<a id="branch"></a>
## The run branch and the user's checkout

Moved to [runs.md](runs.md): branches and worktrees in [runs.md#branches](runs.md#branches), delivery in [runs.md#delivery](runs.md#delivery).

<a id="stop"></a>
## Stop and resume

- **Stop** interrupts every running leaf. The changes they made so far stay in their lanes (Q10-2).
  - The stop sequence, which also ends gate processes and aborts a merge in progress, is in [launcher.md](launcher.md#stop).
  - Memory turns are not awaited. A turn cut short is discarded, and an interrupted leaf updates memory when it finishes after the resume (Q24 default).
- **Resume:** an interrupted leaf runs in a new session on top of those leftover changes (Q10-2).
  - Must-fail-first is skipped for it, because the leftover changes may already make its gates pass.
  - It is judged by its gates as usual (AI, needed by Q10-2).
  - It keeps its contract revision, its approvals and its scopes. A decision changed meanwhile reaches it only through a new contract revision (archived D-031: a resumed task, or one moved to another account, keeps its existing approval, permission and cost policy).
- **A leaf that moved** to another account at a usage limit follows the same rule ([failures](#failures)).

<a id="user-only"></a>
## Things only the user can do

- **The request.** A leaf that needs a login, a payment or a permission asks for it like any other question ([questions](#questions)). The orchestrator posts the request (`barrel post --kind request`) with a mention, and only that leaf blocks (Q01, Q10). A credential goes through `barrel secret ask` instead, below.
- **Inside the delegated scope** (archived D-013). The S6 confirmation records which environments, actions and costs the user delegated. Setup inside that scope goes ahead without asking again; anything beyond it is asked ([interviews.md](interviews.md#stack)).
- **Credentials** (Q20; [memory.md](memory.md#secrets)).
  - The orchestrator calls `barrel secret ask <name>`. The launcher posts the request, which says what is needed, and opens a native macOS dialog with hidden input on the Mac at the same time.
  - The value goes to the Keychain. The leaf uses it by name through `barrel secret run`, which hands it to one command's environment, and never sees it (Q20: the model gets only the name).
  - A credential the leaf creates is stored through `barrel secret capture` ([memory.md](memory.md#secrets)).
  - Nothing secret is taken through Slack. A developer may use `barrel secret set <name>` instead.
  - Example from flow 10: the user enters the AWS account details, or signs in, and the leaf creates the IAM key and configures the AWS CLI with it.

<a id="sudo"></a>
- **Administrator rights** (Q20; details from the Q20 analysis and AI):
  - **The tool.** Barrel has its own tool for this: `barrel-sudo -- <command>`; the name is the AI's.
    - The user saves the password once, through the same macOS dialog, the first time a command needs it (AI).
    - The tool runs the command with sudo and supplies the password: `sudo -S`, and `SUDO_ASKPASS` for a sudo that the command itself starts, as some Homebrew installs do.
  - **The password stays in the tool.** The model and the sessions never receive it.
    - Only the tool may read its Keychain item, so the tool is a compiled binary.
    - Rust is considered first, because one code base can serve macOS and Windows.
  - **No raw sudo.** A hook denies a raw `sudo` in Barrel sessions and points to the tool, so no session hangs on a password prompt it cannot answer ([plugin.md](plugin.md#hooks)).
  - **Logged.** Every command run through the tool goes into the event log, as a `sudo_command` event that is never sent to Slack, and into the leaf's result report, among its effects outside the repo.
  - **What it does not change.** It does not widen what may be installed. A tool installed on the PC still needs the S6 confirmation (Q19; archived Q-008), and the hook that stops system package installs also checks the command given to `barrel-sudo`.
  - **A password that stopped working**, for example after the user changed it, becomes a request to save it again, with the dialog open on the Mac ([slack.md](slack.md#launcher-requests)).
  - **Who does the work.** Barrel does the administrator work. The user only saves the password (archived D-059, adapted by Q20).
  - **Windows.** The command is the same there, and macOS comes first. On Windows, elevation goes through UAC, so a saved password needs another path, such as a scheduled task that runs with the highest privileges (spike).
- **Browser automation** (flow 10).
  - A leaf with `browser: true` gets the Playwright MCP server through per-session configuration (AI; spike):
    - Claude: an `--mcp-config` file in the session's extra arguments.
    - Codex: `mcp_servers` overrides in the thread's `config`.

    The account folders stay untouched.
  - The server uses a browser profile kept per project in run state, so a sign-in outlasts the session that asked for it (AI).
    - Only one browser can use a profile at a time, so the profile counts as a `resources` entry: two leaves that need the browser never run together.
  - **When a step needs the user's own sign-in** (flow 10):
    1. The launcher opens that profile's browser on the Mac at the sign-in page.
    2. The request asks the user to sign in there and reply in the thread.
    3. After the reply, the launcher closes that browser, so the profile is free.
    4. The leaf runs again in a new session, finds the profile signed in, and finishes the setup itself.

    If signing in through the automation profile fails, the request gives the user the steps to do it themselves, or the credential is taken through the dialog instead (spike fallback).
- **Computer use** (Claude Code, research preview, macOS only) (archived D-025; Q17):
  - CLIs, APIs and the automation browser come first. The screen is the last resort.
  - The request explains the work and its scope, and asks for a time window. Computer use runs only after the user agrees to one in the thread, and only within it.
  - The user can end the window at any time from the thread. It also ends when the agreed time is over, or when the user starts using the Mac again (archived D-025: the user can take the screen back). How the launcher notices that is AI and a spike check.
  - If computer use is not available, Playwright is used. A step that still fails becomes a request to the user (spike fallback).
- **External services** (archived D-069; Q17).
  - A leaf's work with outside services goes through the tools and MCP servers chosen for that leaf. They are passed per session like the browser server, within the delegated scope.
  - Barrel's own messages to the user still go only through the launcher's bot (`barrel post`; Q09, Q10 default). The Slack MCP stays read-only in Barrel sessions ([plugin.md](plugin.md#hooks)).
- **Tools** (archived Q-008; Q19).
  - Tools confirmed in S6 are installed by the launcher, not by a task session. It runs the confirmed install commands, through `barrel-sudo` when they need administrator rights, before the first leaf that needs the tool (Q19, Q20; AI). They are kept in `env.tools` in `.barrel/config.json`.
  - The project's own dependencies come through `env.setup` ([sessions.md](sessions.md#engines)).
  - Installing anything else, such as Homebrew packages, global npm or pip packages, or Docker images, is asked first.
  - Compatible tools already on the PC are reused.
  - Personal settings, other projects and the user's own AI CLIs are left alone.
  - A hook stops task sessions from running system package installs, with or without `barrel-sudo` ([plugin.md](plugin.md#hooks)) (AI).

<a id="acceptance"></a>
## Acceptance

1. **Start.** S8 starts when every leaf is done or abandoned. An abandoned leaf's requirement is either covered by leaves that replaced it, or the user decided to drop or change it ([failures](#failures)) (Q01; archived D-041).
2. **Gates.** Every gate of the run runs on the head ([regression](#regression)).
3. **Review.** Review subagents, one per large topic, check the result against the units this run created or changed, plus the `constraint` units it must preserve. At full depth they check every `requirement` and `feature` unit (Q01; Q02; scope AI).
   - Each unit needs evidence from gates, verification or review (AI).
   - The verification includes what the project needs to count as done: installation, deployment, tests and real-use checks (archived D-003; [workflow.md](workflow.md#stages)).
4. **Mismatches.** A mismatch becomes new leaves, and S7 continues.
5. **Delivery.** The run is delivered to every repo it changed ([runs.md](runs.md#delivery)). If the delivery has to wait for a merge that only the user can make, the run waits, with a request posted ([runs.md](runs.md#waiting)).
6. **Final report.** When delivery is done, the launcher emits `delivery_done`, and the orchestrator writes the final report. Its contents are an AI choice:
   - what was built, and where it was delivered, per repo
   - how it was verified
   - which decisions the AI made without asking, including the ordinary libraries it chose (Q19)
   - what the user decided to leave open

   The orchestrator posts it with `barrel post --kind report`: through the Korean writer in Korean mode (Q08, Q10), and with a mention (Q10 default). That post marks the run complete.

There is no final human approval gate. The AI judges intent from the specs (Q01; archived D-024).

<a id="report"></a>
## Result report

Each leaf leaves a report in run state (09-29 draft):
- the contract revision
- the sessions: engine and CLI version, account, model, the effort requested and the effort actually used ([sessions.md](sessions.md#selection))
- the configuration each session actually loaded: its Barrel-managed config folder and the personal settings imported into it (archived D-048; Q17-2)
- the plan and the intent-check result
- turns, tools used, the final response and the transcript path (09-29 draft)
- gate results with their output paths
- review findings
- the write-set and package checks
- effects outside the repo, such as cloud resources, keys, and commands run through `barrel-sudo`, so a resumed leaf knows what already exists ([launcher.md](launcher.md#recovery)) (AI; archived accounts-and-budget.md: receipts for external effects)
- the commits and the merge result, per repo
- the memory update and its commit (Q24)

Today's `RunState` stores neither the response nor the commit (`unitloop.py:373-423`); the report fills that gap.
