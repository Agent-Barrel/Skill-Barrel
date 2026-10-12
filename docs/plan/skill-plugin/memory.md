# Memory and run state

Barrel keeps two kinds of files.

| | Where | Tracked by git | Written by | Holds |
| --- | --- | --- | --- | --- |
| Project files | `.barrel/` in the target repo | Yes, shared with the team (Q07, Q12, Q15) | The orchestrator, and the launcher for answers and generated files ([rules](#rules)) | Config, memory units, review records, task trees and contracts |
| Run state | `~/.barrel/` on the PC | No (Q07) | The launcher and its hooks. Also the orchestrator, in its own folder; fresh auxiliary sessions and investigation leaves, in `outputs/` (AI) | Accounts, sessions, events, Slack threads, lanes, logs |

Neither depends on a CLI's own memory or on one account or session (flow 1, Q07). Claude Code's auto memory is kept per machine and per config folder, and it is off in background sessions and in sessions started by another session. That is one more reason Barrel never relies on it ([research.md](research.md#vendors)).

<a id="layout"></a>
## `.barrel/` in the target repo

```text
.barrel/
  config.json            engines, roles, task runner, Git delivery, project name (Q12, Q14, Q16; sessions.md)
  .gitignore             lists the generated indexes, which are not committed (runs.md#sharing)
  memory/
    intent/      INDEX.md  INT-7q2m.md …
    requirement/ INDEX.md  REQ-k3f9.md …
    feature/     INDEX.md  FEAT-2m7q.md …
    decision/    INDEX.md  DEC-x81c.md …
    constraint/  INDEX.md  CON-p4tz.md …
    answer/      INDEX.md  ANS-9wd3.md …
    research/    INDEX.md  RES-h5vb.md …
  reviews/
    <run>/                           S5 and S6 review documents, per revision: the English source and the text as posted
      S5-intent-r1.md  S5-intent-r1.ko.md  S6-stack-r1.md …
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
  - The facts in a review live in their own units: intent, decisions, task nodes.
  - Approvals point to a record and a hash that covers both files.

<a id="unit"></a>
## A memory unit

One unit is one file that holds one minimal piece of context. Its header carries the ID, the kind, a one-line summary and the related IDs (Q07). Four more fields keep history explicit (AI).

```markdown
---
id: REQ-k3f9
kind: requirement
summary: Members can sign in with their Google account.
related: [INT-7q2m, FEAT-2m7q, DEC-x81c]
sources: [ANS-9wd3]
status: active          # active | superseded
supersedes: []
created: 2026-10-11T09:12:00+09:00
---
Members who already have a Google account can sign in without creating a password.
…
```

<a id="kinds"></a>
## Kinds

These kinds are an AI default. A project may add a kind, for example screen flows or API contracts. Every kind gets its own folder and its own index (Q07).

| Kind | ID | Holds | Usually written in |
| --- | --- | --- | --- |
| intent | `INT-` | The planning intent: the start input, purpose, direction, what the user wants and why (flow 2, Q01). For an existing repo, also the product as inferred at onboarding, until the user confirms it ([workflow.md](workflow.md#onboarding)) | S1–S5 |
| requirement | `REQ-` | One requirement (flow 3) | S3 |
| feature | `FEAT-` | One functional-spec item, linked to the requirements it serves (flow 4) | S4 |
| decision | `DEC-` | One decision (Q01, Q13), of one of these kinds:<br>• the user's own, linked to the `ANS-` it came from<br>• a default the user did not object to<br>• the AI's own, with its reasons<br>• one stack choice from S6<br>• a piece of the existing stack found at onboarding, with source `existing code`<br>• a settled conflict between contexts ([loop](#loop)) | Any stage |
| constraint | `CON-` | Behavior to preserve, invariants, environment limits, things not to change | S2–S4 |
| answer | `ANS-` | One reply from the user, verbatim and in its original language, with the question as posted. Written by the launcher, not by a model (Q07, Q08; [interviews.md](interviews.md#recording)) | Any stage |
| research | `RES-` | A research question; sources with dates; each claim marked verified, unverified or contradicted; the conclusion (flow 5, flow 7, Q16) | Before questions, S6 |

<a id="index"></a>
## Indexes and backlinks

- **One index per kind.** Every kind folder has an `INDEX.md` with one line per unit (Q07).
  - Example line: `- REQ-k3f9 — Members can sign in with their Google account. · related: INT-7q2m, FEAT-2m7q, DEC-x81c · used by: 20261011-a7mz/T1.2.3, DEC-v0c2`
  - Lines are ordered by `created` (AI).
- **Backlinks** (AI). "Used by" lists the backlinks. They are computed from every unit's `related` and `sources` fields and from every task's `memory_units`. Change cascades rely on them ([workflow.md](workflow.md#cascade)).
- **Generated, never edited, not committed** (AI).
  - `barrel memory index` generates the indexes from the headers. Nobody edits them by hand, and a hook denies such edits ([plugin.md](plugin.md#hooks)).
  - They are listed in `.barrel/.gitignore`, so they never conflict in a merge. The launcher regenerates them whenever the units may have changed ([runs.md](runs.md#sharing)).
- **Task indexes.** `.barrel/tasks/<run>/INDEX.md` works the same way for the run's task nodes.

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
- **Who writes `.barrel/`** (AI; one writer per file):
  - **The launcher**, which is code:
    - writes the `answer` units ([interviews.md](interviews.md#recording))
    - generates the indexes
    - stores the Korean display names that the Korean writer returns, and the Korean text of each review record as posted
    - writes the default `config.json` and `.gitignore` once, before the first orchestrator exists ([runs.md](runs.md#start))
  - **The orchestrator** writes every other unit, the review records, the task files with their durable status ([task-tree.md](task-tree.md#status)), and every later change Barrel makes to `config.json`. People may edit `config.json` like any file in the repo (Q12).
  - **Subagents, task sessions and fresh auxiliary sessions** never write `.barrel/`.
  - **Hooks enforce this.** The orchestrator's hook also denies edits to `answer/` and to generated files ([plugin.md](plugin.md#hooks)).
- **Commits.** The launcher commits `.barrel/` on the run branch through its git queue ([runs.md](runs.md#branches)):
  - after each answer unit it writes
  - after each orchestrator turn that changed `.barrel/`
  - at every handoff

  The commit subject is `barrel: memory` (AI).

<a id="loop"></a>
## The planning loop

Every plan, for a medium topic or a leaf, is aligned with the memory this way (flow 1, insight):

1. Start from the coarse picture: the indexes and the intent units.
2. Draft the plan.
3. Read the units the draft needs, and revise the plan.
4. Follow the related links of those units, and revise again. Repeat.
5. Stop when both of these hold (Q07 default):
   - The last reading pass changed nothing in the plan.
   - Every link of every unit read has been either read or dismissed from its index line.
6. Settle every conflict between the contexts before the work starts (insight).
   - Record each settlement as a `decision` unit linked to both contexts, so a later session sees the trade-off instead of the conflict (AI).
   - If settling a conflict needs the user, ask ([workflow.md](workflow.md#asking)).
7. List the units that were read in the node's `memory_units` field (Q07 default).

<a id="context"></a>
## What each session is given

| Session | Given |
| --- | --- |
| Task session | Its contract and the units in `memory_units`. Not the whole memory, and never a conversation (insight, Q07 default) |
| Orchestrator | The indexes, the latest handoff note and its playbook. It reads units when it needs them (AI) |
| Subagent of the orchestrator | The prompt and the files the orchestrator names (AI) |
| Fresh auxiliary session | The input files named in `barrel session start` (AI) |

<a id="run-state"></a>
## Run state outside the repo

Run state lives outside the repo (Q07). The launcher writes it, except for the folders marked otherwise. The layout is an AI default.

```text
~/.barrel/
  settings.json          engines in use, accounts and their order, Slack app and registered Slack user, Slack language, sleep policy
                         (Q05, Q10-2 default, archived D-047)
  launcher.sock          command socket (launcher.md)
  launcher.lock, launcher.log
  projects/<project-id>/
    project.json         repo path, Slack channel
    view.json            PC view port and token, file mode 0600 (AI, for Q10-2's fixed address)
    integration/         worktree on the current run's branch (runs.md#branches)
    lanes/<n>/           reused worktrees for leaf tasks (Q14)
    browser/             the browser profile for browser automation and the user's sign-ins (task-execution.md#user-only)
    runs/<run>/
      run.json           phase, stopped flag, base, transient task status (running, waiting for an answer, blocked, attempts),
                         sessions and their PIDs, lanes
      events.jsonl       event log (Q10 default)
      slack.json         thread map, outbound queue, last handled inbound message, reminder clocks (Q10 default)
      orchestrator/      written by the orchestrator and its subagents: handoff notes, drafts, research and review reports
      outputs/           written by fresh auxiliary sessions and investigation leaves: Korean text, reports
      reports/           leaf result reports (task-execution.md#report)
      parked/            patches of leaves that gave up their lane while waiting (task-execution.md#questions)
      attachments/       files the user attached in Slack (interviews.md#replies)
      sessions/          step2step app dirs, snapshots, transcript copies, plans captured by the ExitPlanMode hook, hook markers
      gates/  logs/      gate output and logs (unit loop layout)
```

- The project ID is the repo folder name plus a short hash of the repo's absolute path (AI).
- What is deleted after a run is listed in [runs.md](runs.md#after).

<a id="secrets"></a>
## Secrets

All of this is AI default, except where a source is named.

- **Storage.** Slack tokens, and every credential the user provides for flow 10, live in the macOS Keychain, through the `security` command.
- **Giving one.** A request that needs a credential offers two ways (flow 10: "AWS 계정정보를 받고"; flow 11: requests go through Slack):
  - **In the request's thread.** The launcher masks the value in the answer unit and stores it in the Keychain under a generated name, which the orchestrator gets. Barrel cannot delete the user's own Slack message, so the value stays in Slack's history.
  - **On the Mac**, with `barrel secret set <name>`, which reads the value without echo. Nothing goes to Slack.
- **Reading one.** A task session reads a credential with `barrel secret get <name>`, for the names listed in its contract's `secrets` field ([launcher.md](launcher.md#access)).
  - This is a guard rail, not a security boundary.
  - Every Barrel session runs with the user's permissions. Any process the user runs can usually read Keychain items that the `security` command created, by running `security` itself (spike).
- **Where credentials never go:**
  - a file in the repo
  - a unit
  - a message Barrel sends, because everything sent is masked first (Q10 default)
