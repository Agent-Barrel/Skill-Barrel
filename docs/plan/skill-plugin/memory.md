# Memory and run state

Barrel keeps three kinds of files.

| | Where | Tracked by git | Written by | Holds |
| --- | --- | --- | --- | --- |
| Project files | `.barrel/` in the project's planning repo ([runs.md](runs.md#projects)) | Yes, shared with the team (Q07, Q12, Q15) | Every Barrel session in its turn of the memory queue, the launcher, and people ([rules](#rules), [queue](#queue)) | Config, the repo list, memory units, review records, designs, task trees and contracts |
| Shared memory | `~/.barrel/shared/` on the PC | No | The launcher, on the orchestrator's request; the user ([shared](#shared)) | Preferences and verified experience used across projects (archived D-007, D-030; Q17) |
| Run state | `~/.barrel/` on the PC | No (Q07) | The launcher and its hooks; sessions in their own folders ([run state](#run-state)) | Accounts, sessions, events, Slack threads, lanes, the queue, logs |

None of them depends on a CLI's own memory or on one account or session (flow 1, Q07). Claude Code's auto memory is kept per machine and per config folder, and it is off in background sessions and in sessions started by another session. That is one more reason Barrel never relies on it ([research.md](research.md#vendors)).

<a id="layout"></a>
## `.barrel/` in the planning repo

A project's shared files live in its planning repo. A small project that one repo serves has only that repo, which is then its planning repo. A project split into several repos has one repo for the shared planning (archived Q-014, Q-015; Q17; [runs.md](runs.md#projects)).

```text
.barrel/
  config.json            engines, roles, task runner, Git delivery, cascade default, project name (Q12, Q14, Q16; sessions.md)
  repos.json             the project's repos (Q17-2; below)
  .gitignore             lists the generated indexes, which are not committed (runs.md#sharing)
  memory/
    intent/          INDEX.md  INT-7q2m.md …
    requirement/     INDEX.md  REQ-k3f9.md …
    feature/         INDEX.md  FEAT-2m7q.md …
    screen/          INDEX.md  SCR-a81k.md …
    api/             INDEX.md  API-4qzt.md …
    decision/        INDEX.md  DEC-x81c.md …
    constraint/      INDEX.md  CON-p4tz.md …
    implementation/  INDEX.md  IMP-b2n7.md …
    lesson/          INDEX.md  LES-8hw3.md …
    answer/          INDEX.md  ANS-9wd3ka2m.md …
    research/        INDEX.md  RES-h5vb.md …
  reviews/
    <run>/                           S5 and S6 review records, per revision: the English source and the text as posted
      S5-intent-r1.md  S5-intent-r1.ko.md  S6-stack-r1.md …
  design/
    <run>/r<N>/                      wireframes and detailed designs, as reviewed in revision N (workflow.md#design)
  tasks/
    <run>/                           one folder per run (runs.md#sharing)
      INDEX.md
      T1.md  T1.2.md  T1.2.3.md …    one file per tree node (Q15, task-tree.md)
      display-names.ko.json          Korean display names for Slack and the PC view (Q10, option 10-c K)
```

- `config.json` is described in [sessions.md](sessions.md#engines).
- Task files are described in [task-tree.md](task-tree.md#files).
- IDs are described in [runs.md](runs.md#ids).
- **Review records** are the S5 intent review and the S6 stack confirmation ([interviews.md](interviews.md#recording)) (AI).
  - Each record is the English source, which the orchestrator writes. In Korean mode it also has a `.ko.md` file next to it, holding the Korean text exactly as posted, which the launcher writes.
  - They are documents, not units: one review holds many facts, and a unit holds one (Q07).
  - The facts in a review live in their own units: intent, decisions, screens, APIs, task nodes.
  - Approvals point to a record and a hash that covers the record, its posted text and the design files of that revision.
- **Designs** are the files the designer sessions made, as the user reviewed them. Like the specs, they are kept in git with the code (archived Q-013). Their format is an implementation choice (archived P-002).

<a id="repos"></a>
**`repos.json`** lists the repos of the project, so that a teammate or a new PC needs only the planning repo to start (Q17-2; fields AI):

```json
{
  "repos": [
    {"name": "shop-docs", "url": "git@github.com:acme/shop-docs.git", "folder": "shop-docs", "role": "planning", "default_branch": "main"},
    {"name": "shop-web",  "url": "git@github.com:acme/shop-web.git",  "folder": "shop-web",  "role": "frontend", "default_branch": "main"},
    {"name": "shop-api",  "url": "git@github.com:acme/shop-api.git",  "folder": "shop-api",  "role": "backend",  "default_branch": "main"}
  ]
}
```

- `folder` is the repo's folder in the project's parent folder, the folder that holds the planning repo ([runs.md](runs.md#projects)).
- `url` is null for a repo that has no remote. Such a repo cannot be cloned on another PC.
- A single-repo project lists only itself (Q17-2).
- The list changes only with the user's confirmation in S5 or S6 (Q17-2).

<a id="unit"></a>
## A memory unit

One unit is one file that holds one minimal piece of context. Its header carries the ID, the kind, a one-line summary and the related IDs (Q07). Four more fields keep history explicit (AI).

```markdown
---
id: REQ-k3f9
kind: requirement
summary: Members can sign in with their Google account.
related: [INT-7q2m, FEAT-2m7q, DEC-x81c]
sources: [ANS-9wd3ka2m]
status: active          # active | superseded
supersedes: []
created: 2026-10-13T09:12:00+09:00
---
Members who already have a Google account can sign in without creating a password.
…
```

<a id="kinds"></a>
## Kinds

These kinds are an AI default, and a project may add more. Every kind gets its own folder and its own index (Q07). The kinds `implementation` and `lesson` exist because Q24 has every session record what it built and learned. The kinds `screen` and `api` exist because Q17 restored wireframes and API rules.

| Kind | ID | Holds | Usually written in |
| --- | --- | --- | --- |
| intent | `INT-` | The planning intent: the start input, purpose, direction, what the user wants and why (flow 2, Q01). For an existing project, also the product as inferred at onboarding, until the user confirms it ([workflow.md](workflow.md#onboarding)) | S1–S5 |
| requirement | `REQ-` | One requirement (flow 3) | S3 |
| feature | `FEAT-` | One functional-spec item, linked to the requirements it serves (flow 4) | S4 |
| screen | `SCR-` | One screen: its purpose, its place in the flow, its wireframe and, once approved, its detailed design in `.barrel/design/`. Linked to the features it serves (archived Q-010, Q-011; Q17) | S4, S6 |
| api | `API-` | One API: a short form of its inputs, outputs, permissions and error rules, and a pointer, with a revision, to the full specification in the code repo that serves it (archived Q-011, Q-015; Q17) | S4 |
| decision | `DEC-` | One decision (Q01, Q13), of one of these kinds:<br>• the user's own, linked to the `ANS-` it came from<br>• a default the user did not object to<br>• the AI's own, with its reasons, including an ordinary library Barrel chose (Q19)<br>• a choice a session made inside its contract or role (Q24)<br>• one stack choice from S6<br>• a piece of the existing stack found at onboarding, with source `existing code`<br>• a settled conflict between contexts ([loop](#loop)) | Any stage |
| constraint | `CON-` | Behavior to preserve, invariants, environment limits, things not to change, the project's own instructions for agents | S2–S4 |
| implementation | `IMP-` | What exists in the code and where: a module, an interface, a behavior. Linked to the features and requirements it implements, so the backlinks show what is built (Q24) | S2, S7 |
| lesson | `LES-` | Something a session learned that later sessions need: a failed approach and why (archived D-040), a quirk of the environment, a convention found in the code (Q24) | S7 |
| answer | `ANS-` | One thing the user sent, verbatim and in its original language: a reply, a button press, an instruction or a start input, with the question it answers if any. Written by the launcher, not by a model (Q07, Q08; [interviews.md](interviews.md#recording)) | Any stage |
| research | `RES-` | A research question; sources with dates; each claim marked verified, unverified or contradicted; experiments and their results; the conclusion (flow 5, flow 7, Q16; archived D-042) | Before questions, S6 |

<a id="index"></a>
## Indexes and backlinks

- **One index per kind.** Every kind folder has an `INDEX.md` with one line per unit (Q07).
  - Example line: `- REQ-k3f9 — Members can sign in with their Google account. · related: INT-7q2m, FEAT-2m7q, DEC-x81c · used by: 20261013-a7mz/T1.2.3, IMP-b2n7`
  - Lines are ordered by `created` (AI).
- **Backlinks** (AI).
  - "Used by" lists the backlinks. They are computed from every unit's `related` and `sources` fields and from every task's `memory_units` and `memory_writes`.
  - Change cascades rely on them ([workflow.md](workflow.md#cascade)), and so does finding which features are implemented, through the `implementation` units.
- **Generated, never edited, not committed** (AI).
  - `barrel memory index` generates the indexes from the headers. Nobody edits them by hand, and a hook denies such edits ([plugin.md](plugin.md#hooks)).
  - They are listed in `.barrel/.gitignore`, so they never conflict in a merge. The launcher regenerates them after every commit of the memory queue ([runs.md](runs.md#sharing)).
- **Task indexes.** `.barrel/tasks/<run>/INDEX.md` works the same way for the run's task nodes.
- **Shared memory** has its own indexes in `~/.barrel/shared/` ([shared](#shared)).

<a id="rules"></a>
## Writing rules

- **Language.** Units are written in English. Only `answer` units keep the user's original language (Q08).
- **One fact per unit.** Link to other units instead of repeating them (flow 1, insight, Q07).
- **Changes** (AI):
  - To change a unit, write a new one with `supersedes` and set the old one to `status: superseded`.
  - `answer` units are never edited, so they carry no `status` field.
    - A later reply, including an edited Slack reply, becomes a new answer unit that lists the earlier one in `supersedes` ([interviews.md](interviews.md#replies)).
    - The index then shows the earlier one as superseded.
- **Secrets never go into units** (AI). A reply or an attachment that contains a credential is masked before its answer unit is written. The credential itself goes into the Keychain ([secrets](#secrets)) (archived Q-013 keeps credentials out of git).
- **Every write goes through the memory queue,** one writer at a time ([queue](#queue)) (Q24).
- **Who may write what:**

| Writer | May write | Source |
| --- | --- | --- |
| The launcher, which is code | `answer` units; the generated indexes; the Korean display names and the Korean text of review records as posted; the default `config.json`, `.gitignore` and `repos.json` at a project's first run; a leaf's `done` status and its commits | Q07, Q24; AI |
| The orchestrator | Every other kind, including intent, requirements and features as the user decides them; review records and design revisions; task files and contracts; later changes to `config.json` and `repos.json` | AI; Q24 |
| Task sessions | In their memory turn only, in the planning repo's integration worktree of their run:<br>• new `implementation`, `lesson` and `decision` units about their own work<br>• changes to the units listed in their contract's `memory_writes` | Q24, Q24 default |
| Fresh auxiliary sessions: the designer, experiments, the Korean writer, the curator, and subagent roles that run as fresh sessions | In their memory turn only: new `lesson` units. Their main output goes to the run state, and the orchestrator or, for the curator, the launcher turns it into units or entries | Q24; AI |
| Subagents | Never `.barrel/`, only their reports in the orchestrator's run-state folder ([sessions.md](sessions.md#roles)) | AI |
| People | Anything, as with any file in the repo. Edits to specs and memory are reviewed ([workflow.md](workflow.md#edits)) | Q12; archived D-020 |

- **Hooks enforce the table.** A session may write `.barrel/` only while it holds the queue, and only what its row allows. The orchestrator's hook also denies edits to `answer/` and to generated files ([plugin.md](plugin.md#hooks)).
- **Commits.** Every turn of the queue that changed `.barrel/` ends in one commit on the run branch of the planning repo, made by the launcher ([runs.md](runs.md#branches)). The subject is `barrel: memory (<writer>)`, and every Barrel commit carries a `Barrel-Run: <run>` trailer (AI).

<a id="queue"></a>
## The memory queue

The user's instruction ([Q24](../interview/q24-memory-update-queue.md)) has five parts:
- Barrel works as intended only if the memory is brought up to date whenever a piece of work ends.
- No two sessions may change memory at once.
- A session ends only after it has updated memory for its own work.
- Sessions update and end in the order they finished.
- Work is announced when it starts.

The user then chose the AI's four additions: update right after the merge, a consolidation at each medium topic's end, "in progress" shown from run state, and memory units in the parallel rule. Mechanism details are AI unless tagged.

**The queue**
- **Where.** One queue per project, inside the launcher (Q24). The launcher is the one process every session already talks to (Q11), so the queue needs no file locks. The existing code has no lock between processes ([research.md](research.md#code)).
- **What goes through it.**
  - Every write to `.barrel/`: memory units, task files, reviews, designs, config.
  - Every git operation in the project's integration worktrees: merges, commits and delivery. This makes it also the git queue of the earlier design.
  - A turn holds the queue from its first write to its commit, so no other writer touches `.barrel/` or an integration worktree meanwhile. Uncommitted `.barrel/` edits therefore never meet a merge.
  - An answer reaches the orchestrator as soon as the launcher records it in run state. Only its unit's commit waits for the queue, so a long merge never delays a question (AI).
- **Who queues** (Q24): task sessions, auxiliary sessions, the orchestrator, and the launcher itself when it records answers or merges.
- **Order.** First come, first served. A session queues when it finishes its work, so sessions update memory and end in the order they finished (Q24).

<a id="finish"></a>
**A leaf's finishing turn** (Q24; the user chose this order):
1. **Merge.** The launcher merges the leaf's commits into the run branch: a trial merge, with the leaf's gates run again on the merged tree (Q14; [task-execution.md](task-execution.md#lanes)).
2. **Show.** The launcher shows the session the latest memory: the indexes, plus every unit changed since the session started, including those that others changed while it waited.
3. **Write.** The session writes the memory of its own work:
   - what it built, as `implementation` units
   - what it learned, as `lesson` units
   - the choices it made inside its contract, as `decision` units
   - links from what it built to the units it implemented
4. **Check and commit.** The launcher checks the update: the format, that every link resolves, and that only allowed kinds and allowed units changed. It then commits the update together with the leaf's `done` status and its commits.
5. **Close.** The session ends.

Why this order (Q24 default): memory updated before the merge would describe code that is not on the run branch if the merge failed. With one turn, the code and the memory move together.
- **If the merge fails** on a conflict or on gates that fail on the merged tree, the session still records what it learned in the same turn and then closes. The leaf runs again ([task-execution.md](task-execution.md#lanes)) (AI).
- **A session that ends without a merge,** because it is blocked on a question or abandoned, still takes a turn and records what it learned, such as a failed approach and why (archived D-040; Q24 default).
- **A session with nothing to record** ends its turn without a change.

**Other turns** (AI):
- **The orchestrator** takes a turn whenever it writes `.barrel/`: `barrel memory begin` waits for the turn, and `barrel memory end` hands the changes to the launcher's check and commit. Its last turn before a handoff makes sure the memory holds everything (Q03, Q24).
- **Designer, experiment and Korean-writer sessions** take one turn when they finish.
- **The launcher** takes a turn for each answer unit it writes, and for each merge that is not part of a leaf's turn.

**Limits** (Q24 default):
- **What a task session may change.** Only what it built and learned. It cannot change what the user wants: intent, requirements, features, constraints, the user's decisions, answers. If one of those has to change, the session says so in its update. The orchestrator then handles it as a question with its cascade (Q01).
- **Checks.** The launcher checks every update before it commits. The orchestrator checks each leaf's update against its contract in its next turn.
- **Stop.** The user's stop does not wait for memory turns; it still halts within 15 s ([launcher.md](launcher.md#stop)). A turn cut short is discarded and done again: an interrupted leaf updates memory when it finishes after the resume.
- **A session that dies** before its turn: the next session for that leaf writes the update from the leftover changes and the result report. Until then the leaf does not count as done.
- **A session that stalls** in its turn loses it after `memory.turn_seconds` (default 600 s, AI). The clock covers the session's own part, from the moment it is shown the memory to its `barrel memory end`; the launcher's merge and gates before it do not count. Its uncommitted `.barrel/` changes are discarded, and its update is done again.

**Consolidation** (Q24). At the end of each medium topic, the orchestrator:
- reviews the units changed in that topic
- removes duplicates and contradictions, by superseding them
- promotes verified experience that would help other projects into [shared memory](#shared) (archived D-008, D-030; AI)

This point is already a handoff and a regression check ([task-execution.md](task-execution.md#regression)). The leaf turns keep memory current; the consolidation keeps it consistent.

**Announcing work** (Q24):
- **The plan is in git.** A contract, committed when its medium topic is split, lists the memory units the leaf may change, in `memory_writes` ([task-tree.md](task-tree.md#fields)).
- **"In progress" is in run state.** One list per project, across all its runs, names the running leaves and the units they may change (Q24; per project, AI).
  - Every session gets this list together with the memory indexes, when it starts and when it takes its turn.
  - A note committed to git would not reach sessions that are already running, because a lane is fixed to the commit it started from.
- **The parallel rule** keeps conflicting work apart. Two leaves never run together if one may change a memory unit that the other reads or may change, even when they belong to different runs of the project (archived D-032; [task-execution.md](task-execution.md#lanes)).

This replaces two parts of earlier AI defaults ([open-decisions.md](open-decisions.md#ai-defaults)):
- one writer per file (default 8)
- task and auxiliary sessions never writing `.barrel/` (default 22)

<a id="loop"></a>
## The planning loop

Every plan, for a medium topic or a leaf, is aligned with the memory this way (flow 1, insight):

1. Start from the coarse picture: the indexes, the intent units and the in-progress list.
2. Draft the plan.
3. Read the units the draft needs, and revise the plan.
4. Follow the related links of those units, and revise again. Repeat.
5. Stop when both of these hold (Q07 default):
   - The last reading pass changed nothing in the plan.
   - Every link of every unit read has been either read or dismissed from its index line.
6. Settle every conflict between the contexts before the work starts (insight).
   - Record each settlement as a `decision` unit linked to both contexts, so a later session sees the trade-off instead of the conflict (AI).
   - If settling a conflict needs the user, ask ([workflow.md](workflow.md#asking)).
7. List the units that were read in the node's `memory_units` field, and the units the leaf may change in `memory_writes` (Q07 default; Q24).

<a id="context"></a>
## What each session is given

| Session | Given |
| --- | --- |
| Task session | Its contract, the units in `memory_units` (shared entries included), the memory indexes and the in-progress list (Q24). Not the other units, and never a conversation (insight, Q07 default). A hook denies it reads of `.barrel/memory/` outside its memory turn; this is a guard rail (AI). A unit it finds missing in the indexes is asked for as a question ([task-execution.md](task-execution.md#questions)) |
| Orchestrator | The indexes, the shared-memory index, the in-progress list, the latest handoff note and its playbook. It reads units when it needs them (AI) |
| Subagent of the orchestrator | The prompt and the files the orchestrator names (AI) |
| Fresh auxiliary session | The input files named in `barrel session start`, and in its memory turn the indexes (AI) |

<a id="shared"></a>
## Memory shared across projects

From archived D-007, D-008, D-009, D-030, D-046 and Q-021, which Q17 restored. The location is the AI's proposal, to which the user did not object (Q17).

Project knowledge stays in the project's repo (Q07). The PC keeps only what belongs to the person and to general know-how:

```text
~/.barrel/shared/
  preference/  INDEX.md  PREF-3kd8.md …
  experience/  INDEX.md  EXP-v72p.md …
  deleted.jsonl          one line per permanently deleted entry: its ID and the date (archived D-046)
```

- **Preferences** (archived D-030):
  - **Explicit.** A general preference the user states, such as "always use pnpm", is recorded as `active`.
  - **Inferred.** A preference the AI infers from the user's choices is recorded as `candidate`. A candidate is never applied as a decision. It may be offered as the recommendation in a question, and the answer confirms or drops it (AI).
- **Experience** (archived D-008):
  - A successful approach that gates and reviews verified, kept with its situation, attempt, result and evidence.
  - The orchestrator promotes it at a medium topic's consolidation ([queue](#queue)). Each entry lists the projects it came from.
  - It is reused only after checking that it fits the current situation. It is never an absolute rule.
- **Priority.** A project's own decisions win. A shared entry never silently overwrites a project decision (archived D-030).
- **Writes.** The launcher writes the files on the orchestrator's request, one at a time for the whole PC (AI). A change applies from the next session (archived D-031).
- **Managing entries** (archived D-009, D-046):
  - **Edit.** The entries are plain files the user may edit. The user may also ask in Slack, and the orchestrator edits them.
  - **Disable.** `status: disabled` excludes the entry from future use and keeps it as past evidence.
  - **Delete permanently.** The file and its index line go, and only the fact of the deletion stays in `deleted.jsonl`. Sessions that already received the entry keep it until they end.
- **Deleting a project's records** (`barrel project remove`; [runs.md](runs.md#archive)) goes through the shared entries whose sources include that project (archived Q-021):
  - the project's name, code and business details are removed
  - generalized know-how stays
  - an entry that cannot be separated from the project is deleted
  - preferences the user set, and experience from other projects, stay

  This takes judgment, so the launcher starts a fresh `curator` session ([sessions.md](sessions.md#roles)). The curator writes the rewritten entries into its output, and the launcher applies them (AI).

<a id="run-state"></a>
## Run state outside the repo

Run state lives outside the repo (Q07). The launcher writes it, except for the folders marked otherwise. The layout is an AI default.

```text
~/.barrel/
  settings.json          engines and accounts in order, the user profile, the GitHub auto-save choice, the Slack app and
                         registered Slack user, Slack language, sleep policy, the paid-usage setting, update state
                         (Q05, Q10-2 default, archived D-001, D-012, D-033, D-047, Q-003; Q21)
  events.jsonl           the PC-wide event log: updates, launcher restarts (launcher.md#events)
  launcher.sock          command socket (launcher.md)
  launcher.lock, launcher.log
  accounts/<engine>-<account>/   Barrel-managed config folders (sessions.md#accounts)
  bin/barrel-sudo        the sudo tool (plugin.md#install)
  launchd/               the launchd job, used only as a fallback (launcher.md#process)
  shared/                memory shared across projects (above)
  projects/<project-id>/
    project.json         planning repo path, parent folder, Slack channel, archived flag
    view.json            PC view port and token, file mode 0600 (AI, for Q10-2's fixed address)
    queue.json           the memory queue: the turn in progress and the writers waiting (Q24)
    in-progress.json     the running leaves of every run of the project, with the units they may change (Q24)
    lanes/<n>/<repo>/    reused worktrees for leaf tasks, one per repo of the project (Q14)
    browser/             the browser profile for browser automation and the user's sign-ins (task-execution.md#user-only)
    runs/<run>/
      run.json           request name, phase, stopped or cancelled flag, base per repo, transient task status
                         (running, waiting for an answer, blocked, attempts), sessions and their PIDs, lanes,
                         open questions, the interview ledger
      integration/<repo>/  worktree on the run branch of each repo the run uses (runs.md#branches)
      events.jsonl       event log (Q10 default)
      slack.json         thread map, outbound queue, last handled inbound message, reminder clocks (Q10 default)
      orchestrator/      written by the orchestrator and its subagents: handoff notes, drafts, research and review reports
      outputs/           written by fresh auxiliary sessions and investigation leaves: Korean text, designs, reports
      experiments/<n>/   written by experiment sessions (workflow.md#experiments)
      reports/           leaf result reports (task-execution.md#report)
      parked/            patches of leaves that gave up their lane while waiting (task-execution.md#questions)
      attachments/       files the user attached in Slack (interviews.md#replies)
      sessions/          step2step app dirs, snapshots, transcript copies, plans captured by the ExitPlanMode hook, hook markers
      gates/  logs/      gate output and logs (unit loop layout)
```

- **The project ID** is the planning repo's folder name plus a short hash of its absolute path (AI).
- **Questions and the ledger** in `run.json` (AI):
  - Each open question records its kind, its thread, when it was posted, its reminder state, its status (`unsent`, `open`, `answered`, `superseded`), what it blocks (a stage or leaves), and its units.
  - Each ledger item records its text, the method that found it, its state and the units that settle it ([interviews.md](interviews.md#ledger)).
- **No backups of its own.** Barrel has no backup or export feature. Run state relies on the OS's backups, and the memory is in git (archived D-055; Q17).
- What is deleted after a run is listed in [runs.md](runs.md#after).

<a id="secrets"></a>
## Secrets

From [Q20](../interview/q20-credentials-and-sudo-tool.md) unless marked; it replaces AI default 2.

- **Storage.** Slack tokens, and every credential the user provides for flow 10, live in the macOS Keychain, through the `security` command (AI).
- **How the user gives a credential** (Q20):
  - The orchestrator names the credential and calls `barrel secret ask <name>` ([launcher.md](launcher.md#commands)). The launcher posts the request in Slack with a mention, saying what is needed, and at the same time opens a native macOS input dialog on the Mac, with the input hidden ([slack.md](slack.md#launcher-requests)).
  - The value goes straight into the Keychain under that name. The orchestrator and the sessions get only the name (Q20: "모델에게는 이름만 넘긴다").
  - Credentials are never taken through Slack. One pasted into Slack by mistake is masked in its answer unit and moved to the Keychain. The message itself stays in Slack's history, because Barrel cannot delete the user's messages.
  - `barrel secret set <name>` in a terminal stays as an option for developers.
  - While the user is away, only the work that needs the credential waits (Q01).
- **Using one** (AI). A task session never sees a value. It runs `barrel secret run --env <VAR>=<name> -- <command>`, which puts the value into that command's environment only, for the names in its contract's `secrets` field ([launcher.md](launcher.md#access)).
- **Storing one a leaf creates** (AI). A leaf that creates a credential, such as an IAM key, runs the creating command through `barrel secret capture <name> [--field <path>] -- <command>`. The tool stores the value it reads from the command's output in the Keychain and prints only what is not secret. The names a leaf may store are listed in its `secrets` field.
- **Slack's own tokens** are entered at setup through the same dialog, never typed into the CLI, so they never reach a model's transcript ([plugin.md](plugin.md#setup)) (AI).
- **Product secrets** (AI). The product may need secret files, such as `.env`.
  - They are written from the Keychain into git-ignored files when a lane or an integration worktree is prepared.
  - The launcher never commits those paths, even when one appears in a write set.
- **The sudo password** (Q20). It is saved once, through the same dialog, into a Keychain item that only the sudo tool may read ([plugin.md](plugin.md#install)).
- **A guard rail, not a security boundary.** Every Barrel session runs with the user's permissions. Any process the user runs can usually read Keychain items that the `security` command created, by running `security` itself (spike). The sudo password's item is the exception, since its access list names only the sudo tool ([validation.md](validation.md#checklist)).
- **Where credentials never go:**
  - a file in the repo
  - a unit
  - a model's prompt, output or transcript, as far as the tools can keep them out
  - a message Barrel sends, because everything sent is masked first (Q10 default)
