# Task execution

Leaves are executed by the launcher's task runner. The task runner is the unit loop (`barrel/core/unitloop.py`) extended for the task tree, for both engines, and for parallel lanes. [launcher.md](launcher.md#reuse) lists what is reused and what changes.

<a id="preflight"></a>
## Before the first leaf: preflight and baseline

At the start of S7, before any leaf runs (09-29 draft, S5; AI):

1. **Preflight.** The unit loop's checks from `task_runner.preflight`: tools, free disk space, and the configured commands (`barrel/core/preflight.py`, run at `barrel/core/unitloop.py:516-527`).
2. **Environment.** `env.setup` runs in the integration worktree ([sessions.md](sessions.md#engines)).
3. **Baseline.** The project's existing checks in `task_runner.baseline` run once on the head of the run branch, and their results are kept in run state. A check that fails here is pre-existing ([below](#pre-existing)). This is what makes "unrelated to the request" provable (archived Q-005; archived orchestration.md).

A preflight or environment failure does not end the run, as it does in the unit loop (exit code 3, `barrel/core/unitloop.py:516-527`). It goes to the orchestrator. The orchestrator fixes it with a setup leaf, or asks the user, for example to approve installing a tool ([user-only](#user-only)) (AI).

<a id="lifecycle"></a>
## One leaf, start to finish

1. **Ready.**
   - Every node in `depends_on` is done (the unit loop rule, `unitloop.py:542-548`).
   - The parallel rule allows it ([lanes](#lanes)).
   - A lane is free.
2. **Prepare the lane** (Q14, AI).
   - **A new leaf:** reset the lane's worktree to the head of the run branch, as a detached HEAD ([runs.md](runs.md#branches)).
   - **A leaf that was interrupted or moved to another account:** keep its lane as it is, leftover changes included ([stop](#stop)).
   - **A leaf with a parked patch:** reset the lane, then apply the patch ([questions](#questions)).
   - **Dependencies:** run `env.setup` if a dependency manifest changed since the lane's last leaf.
3. **Baseline.** The leaf's gates must fail before work starts. This is the unit loop's must-fail-first rule (`gates.py:188-197`, used at `unitloop.py:589-602`).
   - A gate that already passes is a gate defect, and the leaf goes back to the orchestrator.
   - Three exceptions, because their gates may already pass:
     - a leaf with `expect_baseline_fail: false` ([task-tree.md](task-tree.md#fields))
     - a resumed leaf ([stop](#stop))
     - a leaf that runs again with its parked patch ([questions](#questions))
4. **Start a fresh session.**
   - Engine and account come from the leaf's difficulty ([sessions.md](sessions.md#difficulty)). Permission modes are in [sessions.md](sessions.md#modes).
   - Working directory: the lane. Mode: plan mode. `BARREL_TASK` and `BARREL_LANE` are set.
   - A leaf with `browser: true` also gets the browser-automation server ([user-only](#user-only)).
   - The first prompt holds the contract, the units in `memory_units`, and a pointer to the task playbook (insight).
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
8. **Check the write set.** Every changed file must be in `write_set`. A change outside it fails the attempt and goes back to the orchestrator. A session never widens its own scope (09-29 draft).
9. **Review.** Only if `review: true`. The launcher emits `review_needed`; the orchestrator runs a review subagent ([review](#review)) and calls `barrel task review <id> --pass` or `--findings <file>` (Q02).
10. **Commit in the lane.**
    - Only the leaf's paths are committed, with `gitops.commit` (`barrel/core/gitops.py:78-134`) instead of `commit_all`.
    - The commit goes on the lane's detached HEAD.
    - The message keeps the unit loop's format, `T1.2.3: <title>` (`unitloop.py:823-845`), with a `Barrel-Run: <run>` trailer (AI).
11. **Merge.**
    - The launcher's git queue makes a trial merge of the leaf's commit into the run branch in the integration worktree ([lanes](#lanes)).
    - The leaf's gates run again on the merged tree (Q14).
    - The merge is committed only if they pass.
    - Conflicts are handled in [lanes](#lanes).
12. **Report.**
    - The result report goes to run state ([report](#report)).
    - The launcher emits `task_done`, which goes into the medium topic's Slack thread ([slack.md](slack.md#what)).
    - The orchestrator sets the task file to `status: done` with its commit (Q15; [task-tree.md](task-tree.md#status)).

<a id="questions"></a>
## Questions from a task session

- **No guessing.** A task session's question is never answered with a guess. This replaces the unit loop's fixed answer, "Use your best judgement and continue; do not ask again." (`unitloop.py:82`, `:774-776`) (Q01).
- **The path.** The launcher reads the question (`PendingInteraction.questions`, `step2step/contracts.py:63-74`) and emits `task_question`. The orchestrator then takes one of two paths:
  - **The memory answers it.**
    - The orchestrator records a `decision` unit and calls `barrel task answer`.
    - The launcher types the answer into the waiting session: Claude through `answer_menu` / `answer_menu_text` (`step2step/claude/session.py:449-484`), Codex through `answer_questions` (`step2step/codex/session.py:366-389`) (Q01).
  - **The memory does not answer it.**
    - The orchestrator asks in Slack ([interviews.md](interviews.md)), and the leaf is blocked. Its session closes.
    - **The leaf gives up its lane** (AI), so blocked leaves never hold every lane while unrelated work waits (Q01).
      - Its changes so far are saved as a patch in the run state's `parked/`.
      - After the answer, the orchestrator updates the contract. The leaf then runs again in a new session, in a free lane, with the patch applied on top of the run branch's head (09-29 draft, AI).
      - If the updated contract makes the patch obsolete, the orchestrator drops it.
    - Unrelated leaves keep running (Q01).
- **Multi-question widgets.** Claude multi-question widgets are not supported by step2step (`step2step/claude/session.py:426-429`). The launcher interrupts the session and asks it to put one question at a time (AI, spike).
- **Decisions found late.** A task question can show a decision that S3–S5 should have found. The orchestrator then records which discovery method missed it in the decision unit, so the method can be fixed ([interviews.md](interviews.md#discovery)) (09-29 draft).

<a id="failures"></a>
## Failures

- **Classification.** Failures are classified and fingerprinted (`barrel/core/failures.py:26-33`, `:88-128`, `:180-184`).
- **Within one attempt.** The session gets gate feedback.
  - When the same fingerprint repeats `task_runner.repeat_limit` times, the leaf climbs the ladder (`unitloop.py:756-757`).
  - The ladder raises effort, then changes model, then moves to the next engine option or tier ([sessions.md](sessions.md#escalation)).
- **Environment failures.**
  - The recovery command `task_runner.gates.env_recover` runs once (`unitloop.py:740-755`).
  - If that does not help, only this leaf stops and goes to the orchestrator.
  - The unit loop halts the whole run at this point (`unitloop.py:752`, `:755`); Barrel does not (Q01: only the blocked work stops).
- **Gate defects** send the leaf back to the orchestrator, which fixes the contract's gates. This applies whether the gate passes before any work or breaks during an attempt. The unit loop halts the whole run on a gate defect (`unitloop.py:623`, `:738-739`); Barrel does not ([launcher.md](launcher.md#reuse)) (Q01).
- **The run as a whole stops in only two cases:**
  - the user's stop (Q10-2)
  - the usage-limit stop, when no account and no engine can run, which resumes on its own at the reset (Q01, Q10)
- **Harness problems** (stalls, unconfirmed submits, dead sessions, unresolved dialogs): the session is replaced (`unitloop.py:709-724`).
- **Usage limit.** The leaf moves to the next account or engine and keeps its lane changes (Q05, Q12; [sessions.md](sessions.md#accounts)). This replaces the unit loop's fixed sleep (`usage_wait_seconds`, 900 s) on the same session (`unitloop.py:703-708`).
- **Budgets.** These come from `task_runner.budget`, which is the unit loop's `Budget` (`barrel/core/failures.py:262-271`).
  - Per turn and per leaf, as in the unit loop: 3,600 s per turn, 12 turns and 4 hours per leaf, plus the stall and progress limits.
  - A leaf that runs out of its budget counts as a failed attempt and climbs the ladder. It does not wait for the user (AI).
  - There is no run-wide clock. The unit loop stops a whole run after 24 hours (`run_wall_seconds`, `failures.py:269`, checked at `unitloop.py:540-541`), while a Barrel run lasts as long as its work (Q01; AI).
- **No endless retries on the same evidence** (archived D-040). When the alternatives run out, the leaf is abandoned with its attempts and the remaining options. The orchestrator then does one of these:
  - re-splits the work
  - changes the method within the approved requirements, stack and cost (archived D-041)
  - asks the user, if the change touches one of these:
    - requirements, the stack, cost, or a method the user mandated (archived D-041)
    - scope or permissions (AI, from Q01: what only the user can decide)

  Abandoned leaves are posted to the channel (Q10).

<a id="review"></a>
## Independent review

- **Which leaves.** When splitting, the orchestrator marks a leaf `review: true` if it touches core logic, auth, data integrity or external effects (archived Q-004).
- **How.** After the gates pass, the launcher emits `review_needed`. The orchestrator runs a review subagent (Q02: independent review by someone other than the worker). The subagent gets four things, and never the task session's conversation:
  - the contract
  - the units
  - the diff
  - the gate output
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
- A failure counts as pre-existing only if the S7 baseline shows it ([preflight](#preflight)).
- A check that did not run, is flaky, or failed for an unknown reason never counts as pre-existing.

<a id="lanes"></a>
## Parallel lanes

- **How many:** up to `concurrency.implementation` leaves run at once, default 2 (Q14).
- **Which leaves** (archived D-032, as written). Two leaves run together only if all of these hold:
  - neither depends on the other
  - neither one's write set overlaps the other's write set or read set
  - they share no entry in `resources`: a port, a database, a real path outside the repo, a shared environment such as a staging deployment, an external service, or an account with its budget

  When independence is unclear, they run one at a time. A read-only investigation leaf writes only its report in run state, so it never conflicts.
- **Lanes** are git worktrees under `~/.barrel/projects/<id>/lanes/`, one per slot, each on a detached HEAD ([runs.md](runs.md#branches)).
  - They are reused, and each one is reset to the head of the run branch before a new leaf.
  - Reuse keeps installed dependencies, and `env.setup` runs when a manifest changed (Q14, AI).
- **Lane numbers.** Each lane gets `BARREL_LANE`. Gates that start a server derive its port from that number (AI).
- **Integration worktree:** `~/.barrel/projects/<id>/integration/`, checked out on the run branch. Merges and post-merge gates run there, and the orchestrator works on `.barrel/` there (AI).
- **Trial merge:** when a leaf passes in its lane, the launcher merges its commit into the run branch without committing, and the leaf's gates run again on the merged tree (Q14).
  - If they pass, the merge is committed.
  - If they fail, the merge is aborted. So the run branch never holds a failing leaf merge, and other lanes never reset onto one (AI).
  - The one exception is a merge of a base that moved: it is kept, so that leaves can fix it on top ([runs.md](runs.md#delivery)).
- **Conflict, or a failure after the merge:** the leaf runs again in a new session from the head of the run branch. Its prompt describes the change it collided with (Q14). Telling an agent about the concurrent change recovered most broken merges in the STALE study ([research.md](research.md#prior-art)).
- **Start-up:** sessions are spread across accounts and started one at a time with a short gap, to avoid burst throttling (Q14, AI).
- **Not counted:** auxiliary sessions do not count against the concurrency. Subagents run inside the orchestrator, and the Korean writer writes no product code (Q14, AI).

<a id="regression"></a>
## Regression checks

The leaf's own gates on the merged tree cannot see a later merge that breaks an earlier leaf. So the gates run again at three points:

1. **After each merge:** the merged leaf's gates (Q14).
2. **When a medium topic's last leaf is merged:** every gate of that topic's done leaves, on the run branch's head (Q14 "합친 결과로 게이트를 다시 돌린다"; scope AI).
3. **At S8, before acceptance:** every gate of the run (archived D-024).

A failure becomes a new leaf in its topic (AI).

<a id="branch"></a>
## The run branch and the user's checkout

Moved to [runs.md](runs.md): branches and worktrees in [runs.md#branches](runs.md#branches), delivery in [runs.md#delivery](runs.md#delivery).

<a id="stop"></a>
## Stop and resume

- **Stop** interrupts every running leaf. The changes they made so far stay in their lanes (Q10-2).
- **Resume:** an interrupted leaf runs in a new session on top of those leftover changes (Q10-2).
  - Must-fail-first is skipped for it, because the leftover changes may already make its gates pass.
  - It is judged by its gates as usual (AI, needed by Q10-2).
- **A leaf that moved** to another account at a usage limit follows the same rule ([failures](#failures)).

The stop sequence itself is in [launcher.md](launcher.md#stop).

<a id="user-only"></a>
## Things only the user can do

- **The request.** A leaf that needs a login, a credential, a payment or a permission asks for it like any other question ([questions](#questions)). The orchestrator posts the request (`barrel post --kind request`) with a mention, and only that leaf blocks (Q01, Q10).
- **Inside the delegated scope** (archived D-013). The S6 confirmation records which environments, actions and costs the user delegated. Setup inside that scope goes ahead without asking again; anything beyond it is asked ([interviews.md](interviews.md#stack)).
- **Browser automation** (flow 10).
  - A leaf with `browser: true` gets the Playwright MCP server through per-session configuration (AI; spike):
    - Claude: an `--mcp-config` file in the session's extra arguments.
    - Codex: `mcp_servers` overrides in the thread's `config`.

    The user's own config folders stay untouched.
  - The server uses a browser profile kept per project in run state, so a sign-in outlasts the session that asked for it (AI).
    - Only one browser can use a profile at a time, so the profile counts as a `resources` entry: two leaves that need the browser never run together.
  - **When a step needs the user's own sign-in** (flow 10):
    1. The launcher opens that profile's browser on the Mac at the sign-in page.
    2. The request asks the user to sign in there and reply in the thread.
    3. After the reply, the launcher closes that browser, so the profile is free.
    4. The leaf runs again in a new session, finds the profile signed in, and finishes the setup itself.

    Example: the user signs in to AWS, and the leaf creates the IAM key and configures the AWS CLI with it.
- **Computer use** (Claude Code, research preview, macOS only). It is used only after the user agrees in the request's thread, and only while that step runs (AI; archived accounts-and-budget.md: work on the user's screen only in agreed windows).
- **Secrets** (flow 10: "AWS 계정정보를 받고"; AI details). The request offers two ways to give one:
  - a reply in its thread
  - `barrel secret set <name>` on the Mac, which keeps the value out of Slack

  Either way the value goes to the Keychain, and the leaf reads it with `barrel secret get <name>` ([memory.md](memory.md#secrets)).
- **Tools** (archived Q-008).
  - Tools in the confirmed stack, or in the project's existing setup, may be installed through `env.setup`. Installing anything else (Homebrew packages, global npm or pip packages, Docker images) is asked first.
  - Compatible tools already on the PC are reused.
  - Personal settings, other projects and the user's own AI CLIs are left alone.
  - A hook stops task sessions from running system package installs ([plugin.md](plugin.md#hooks)) (AI).

<a id="acceptance"></a>
## Acceptance

1. **Start.** S8 starts when every leaf is done or abandoned. An abandoned leaf's requirement is covered either by leaves that replaced it or listed as open (AI).
2. **Gates.** Every gate of the run runs on the head ([regression](#regression)).
3. **Review.** Review subagents, one per large topic, check the result against the units this run created or changed, plus the `constraint` units it must preserve. At full depth they check every `requirement` and `feature` unit (Q01; Q02; scope AI).
   - Each unit needs evidence from gates, verification or review (AI).
4. **Mismatches.** A mismatch becomes new leaves, and S7 continues.
5. **Delivery.** The run is delivered ([runs.md](runs.md#delivery)). If the delivery has to wait for a merge that only the user can make, the run waits, with a request posted ([runs.md](runs.md#waiting)).
6. **Final report.** When delivery is done, the launcher emits `delivery_done`, and the orchestrator writes the final report. Its contents are an AI choice:
   - what was built, and where it was delivered
   - how it was verified
   - which decisions the AI made without asking
   - what is left open

   The orchestrator posts it with `barrel post --kind report`: through the Korean writer in Korean mode (Q08, Q10), and with a mention (Q10 default). That post marks the run complete.

There is no final human approval gate. The AI judges intent from the specs (Q01; archived D-024).

<a id="report"></a>
## Result report

Each leaf leaves a report in run state (09-29 draft):
- the contract revision
- the sessions: engine, account, model, and the effort requested and actually used ([sessions.md](sessions.md#selection))
- the plan and the intent-check result
- turns, tools used, the final response and the transcript path (09-29 draft)
- gate results with their output paths
- review findings
- the write-set check
- effects outside the repo, such as cloud resources or keys, so a resumed leaf knows what already exists ([launcher.md](launcher.md#recovery)) (AI; archived accounts-and-budget.md: receipts for external effects)
- the commit and the merge result

Today's `RunState` stores neither the response nor the commit (`unitloop.py:373-423`); the report fills that gap.
