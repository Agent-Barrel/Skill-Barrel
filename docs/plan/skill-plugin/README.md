# Barrel design

Updated 2026-10-16. Status: canonical design, not implemented yet. Written in English because English is canonical ([Q08](../interview/q08-korean-docs.md)).

This folder is the design Barrel is built from. It replaces the 2026-09-29 draft, which is archived in [docs/archive/skill-plugin-2026-09-29](../../archive/skill-plugin-2026-09-29/README.md).
- It was rewritten on 2026-10-08 from interview answers Q01–Q16, and checked again on 2026-10-11 against the verbatim answers, the original flow, the archived drafts and the code.
- From 2026-10-13 to 2026-10-16 it was revised with everything decided on 2026-10-12, and then checked by three independent reviews against the verbatim answers, the archived decisions and the code:
  - interview answers Q17–Q24
  - the gaps, spike fallbacks and doc errors that the two readiness checks found ([readiness-2026-10-12.md](../readiness-2026-10-12.md))

  Each of the 93 archived user decisions is now either reflected or listed with the reason it is not ([migration.md](migration.md#archived)).

## What Barrel is

Barrel is a skill for Claude Code and Codex. It changes how a coding agent works.

1. The user runs the `barrel` skill in any Claude Code or Codex session and gives it a product concept or a maintenance request (flow 2).
2. That session makes sure the per-PC launcher is running and has it start a new run with an orchestrator session. Then its own job ends (Q03-3, Q18).
3. Barrel then works without the user attached:
   - It draws out the requirements and the functional spec through interviews over Slack (flow 3–5).
   - For a project with screens, it draws wireframes. For one with an API, it settles the API's inputs, outputs, permissions and errors (archived Q-010, Q-011; Q17).
   - It has the user review an intent summary and, as deep as the request needs, the top two levels of the task tree (Q01, Q06, Q13).
   - It researches the technology. When a choice is hard to reverse, the user confirms it, together with the detailed design of the main screens (flow 6–8, Q13, Q19).
   - It implements the work as small leaf tasks. Each leaf runs in a fresh coding-agent session that gets only the context it needs (insight, Q02, Q06).
   - It checks the result and delivers it to every repo the run changed.
4. Every decision and every piece of context lives in small linked files in the project's planning repo. None of it lives only in a session, an account or a CLI's own memory, so any session or account can be replaced at any point (flow 1, Q07).
5. Every session Barrel starts brings that memory up to date before it ends, one session at a time. So no session works from a stale picture (Q24).
6. Barrel asks the human only what those files cannot answer, and keeps working on unrelated tasks while one task waits. At the end it judges the result against the requirements and the functional spec (Q01).

A project is a planning repo plus the repos it lists, side by side in one parent folder. A small project that one repo serves has only that repo, which is then its planning repo; a project split by function, such as a frontend and a backend, has several (archived Q-014, Q-015; Q17, Q17-2). Each request is its own run, so several runs of one project can go on side by side (Q18).

Barrel runs on macOS 15 or later, on Apple Silicon first (archived D-002, D-054; Q17).

Sources: the [2026-10-06 request](../README.md#source), [00-original-flow.md](../00-original-flow.md), [insight.md](../insight.md), and interview answers [Q01–Q24](../interview/README.md).

## Reading rules

- The verbatim answers in [interview/](../interview/README.md) are the source of truth. If this folder disagrees with one of them, the answer wins and this folder gets fixed.
- Every decision carries a source tag:

| Tag | Meaning |
| --- | --- |
| `(Q07)` | The user's answer to that interview question |
| `(Q07 default)` | A default the AI proposed in that question; the user did not object. `(Q24 default)` covers the details the AI listed in Q24 |
| `(AI)` | A detail the AI decided, because the user delegated it or nothing was said. Open to change; the ones with the most effect are listed in [open-decisions.md](open-decisions.md#ai-defaults) |
| `(09-29 draft)` | A rule carried over from the 2026-09-29 draft, which the AI wrote from the user's 09-29 request. It was not asked in the interview, so it counts as an AI default |
| `(archived D-032)` | A user decision from the archived app plan ([docs/archive/app-plan](../../archive/app-plan/README.md)), carried over because it still fits ([migration.md](migration.md#archived)). The decisions Q17 brought back also carry `Q17`, as in `(archived D-048; Q17)` |
| `(flow 5)` | An item of [00-original-flow.md](../00-original-flow.md) |
| `(insight)` | [insight.md](../insight.md) |
| `(10-06 request)` | The [2026-10-06 request](../README.md#source) |

- Code references are `path:line` on main at `5c15481`. They were checked against the code on 2026-10-13.

## Documents

| Document | Contents |
| --- | --- |
| [workflow.md](workflow.md) | Stages from first run to completion, onboarding, wireframes and design, experiments, depth by impact and what counts as new technology, when Barrel asks the human, change cascades and direct edits |
| [interviews.md](interviews.md) | How every human question is researched, verified, posted, answered and recorded; approval buttons; the S5 review and the S6 confirmation |
| [memory.md](memory.md) | `.barrel/` in the planning repo: memory units, the memory queue, review records, indexes, the planning loop; memory shared across projects; run state outside the repo; secrets |
| [task-tree.md](task-tree.md) | Large > medium > leaf topics, when they are split, leaf size and test leaves, and the task contract |
| [sessions.md](sessions.md) | Roles, permission modes, engines and `.barrel/config.json`, accounts and Barrel-managed config folders, subagents, and the orchestrator lifecycle |
| [task-execution.md](task-execution.md) | How one leaf runs, from plan to its memory update; preflight, questions, failures, packages, parallel lanes, regression checks, things only the user can do, acceptance |
| [runs.md](runs.md) | Projects and their repos, starting a run, IDs, branches and worktrees, delivery, sharing `.barrel/` across runs and teammates, cancelling a run, archiving a project |
| [launcher.md](launcher.md) | The per-PC launcher: process, sleep, updates, commands and access, event catalog, recovery, stop, resume and cancel, and a reuse and gap map of the existing code |
| [slack.md](slack.md) | The Slack bot: manifest, progress reports, snapshots, questions, buttons, routing between runs, commands, language, outages |
| [pc-view.md](pc-view.md) | The local status page with stop and resume, and how to reopen it |
| [plugin.md](plugin.md) | Packaging for both CLIs, the `barrel` skill, hooks and hook trust, role markers, install, the sudo tool, and first-run setup |
| [migration.md](migration.md) | Mappings from the original flow, the interview, the 09-29 draft, all 93 archived decisions and the existing code |
| [validation.md](validation.md) | What the spike builds first, the spike checklist with fallbacks, the real tasks and the pass criteria |
| [open-decisions.md](open-decisions.md) | Status of OD-1…OD-10, the AI defaults waiting for review, and the archived decisions not carried |
| [research.md](research.md) | Dated code, vendor and prior-art facts this design relies on |

## Principles

1. **Intent first.** Before implementation, Barrel draws out the direction, the purpose and the implementation intent through requirements and functional-spec interviews, and writes them down (flow 2–5, Q01).
2. **Sessions are brains, files are memory.** Every session starts fresh and reads its context from files. Nothing lives only in a conversation, in one account, or in a CLI's own memory (10-06 request, flow 1, Q03, Q07).
3. **Memory is current after every session.** A session Barrel started ends only after it has written what it did and learned into memory. A queue lets one writer in at a time, so nothing is overwritten or lost (Q24).
4. **Ask only what the documents cannot answer.**
   - What the AI can decide from the intent and the specs, it decides.
   - It asks only when the direction cannot be inferred or a genuinely new decision is needed (Q01, Q06).
   - Separately, it requests what only the user can do, such as a login (Q01; flow 10).
   - A blocked task stops alone, and unrelated tasks continue.
5. **Small tasks, fresh sessions, only the needed context.** Each leaf goes to a new session that receives only the context units that leaf needs (insight, Q02, Q06).
6. **Conflicts are settled before the work.** When two pieces of context bear on a task, the direction and the trade-offs between them are decided before the task starts (insight, flow 1).
7. **Engines are interchangeable.** Claude Code and Codex are engines that run Barrel. No role is tied to a provider. Model and effort follow the difficulty of the work, and every usable CLI and account on the PC is used (Q12, Q16).
8. **Findings are verified before they are used.** Research is followed by an independent verification pass that checks each claim against its sources (Q16).
9. **Code gives the verdicts and keeps the records; the AI judges intent.**
   - Gates, which are deterministic commands, decide whether a task passed (archived D-024).
   - The launcher, which is code, records every answer, instruction and approval verbatim (09-29 draft, principle 5).
   - The AI judges whether the final result matches the intent, using the requirements and the functional spec (Q01).
10. **English inside, Korean for people.**
    - Memory, contracts and session-to-session files are English.
    - Human-facing text is written in Korean with Skill-Techblog unless the Slack language is set to English (Q08, Q10).
11. **Slack and the PC view only report.** The files in the repo and the run state are the truth (Q10 default).

## Non-goals

- No `claude -p` or other headless runs. Sessions are interactive and driven by `step2step` (repo rule).
- No resident launcher, no login item, and no run started from Slack. Barrel is a skill: the skill, Barrel.app or a `barrel` command starts the launcher, and Slack only instructs runs that exist (Q22-2).
- No pinned CLI version. CLI updates cannot be stopped, so Barrel keeps itself current instead (Q17-2, Q21).
- No paid usage beyond the subscriptions unless the user turns it on, with a monthly budget (archived D-012, D-033, D-056; Q17).
- No posting through the Slack MCP. Only the launcher's bot posts (Q09, Q10 default).
- No editing of Slack messages. Progress is always a new message (Q10).
- No answering questions or sending instructions from the PC view. That happens in Slack (Q10-2).
- No user-facing stop for a single task. Stop halts every run of the project (Q10-2, Q18). Two related actions remain:
  - Cancelling one run is a separate Slack command (archived Q-009; Q17).
  - The orchestrator can still cancel a leaf whose contract a change replaced ([workflow.md](workflow.md#cascade)).
- No status command in the terminal. Status is in Slack and the PC view (Q10-2 default).
- No auto-answering a task session's questions with a guess (Q01; replaces `menu_default_answer`, `barrel/core/unitloop.py:82`).
- No roles split by provider, such as "Claude-side research" and "Codex-side research" (Q16).

## Glossary

| Term | Meaning |
| --- | --- |
| Invoking session | The Claude Code or Codex session where the user runs the `barrel` skill. It sets things up, starts a run and ends (Q03-3, Q18) |
| Launcher | The one Barrel process per PC (Q11). It owns every session, the Slack connection, the PC views, the event log and every project's memory queue (Q24). It also keeps Barrel up to date (Q21). Built on `step2step` |
| Engine | Claude Code or Codex, as used by Barrel (Q16) |
| Account | One subscription login of an engine (Q05). The user's own config folders, such as `~/.claude-wook`, hold these logins |
| Barrel-managed config folder | The config folder Barrel's sessions run from, one per account and named by the account: `~/.barrel/accounts/<engine>-<account>/`, used as `CLAUDE_CONFIG_DIR` or `CODEX_HOME`. It reuses the account's login and holds Barrel's plugin plus only the personal settings the user picked (archived D-048; Q17-2; [sessions.md](sessions.md#accounts)) |
| Project | A planning repo and the repos listed in its `.barrel/repos.json`, side by side in one parent folder ([runs.md](runs.md#projects)). A small project may have only one repo (archived Q-014, Q-015; Q17, Q17-2) |
| Planning repo | The repo that holds the project's `.barrel/`: memory, task trees, reviews, design and config (archived Q-015; Q17) |
| Run | One execution for one request, from its start input to completion. Each request starts its own run, so a project can have several at once (Q18). Its ID looks like `20261013-a7mz` ([runs.md](runs.md#ids)) |
| Request name | A short name for a run's request. It is shown on every Slack message and in the PC view (Q18) |
| Run branch | `barrel/<run>` in every repo the run changes. The run's work is committed and delivered from it ([runs.md](runs.md#branches)) |
| Orchestrator | The session that plans and directs one run. It is replaced by a successor at stage ends, at medium-topic ends, and before its context fills up (Q03, Q03-3, Q04-2) |
| Task session | A fresh session that implements one leaf task (Q02) |
| Auxiliary role | Advice, intent check, context gathering, research, verification, review, design, experiment, Korean writing or curating shared memory ([sessions.md](sessions.md#roles)). The first six run as subagents of the orchestrator, or as fresh sessions when their engine is on another CLI (Q02, Q16; advice as a subagent is AI). The other four always run as fresh sessions |
| Subagent | A child agent inside a session, used for short read-only work (Q02) |
| Memory unit | One file under `.barrel/memory/` that holds one minimal piece of context (Q07). Its ID is a short hash, such as `REQ-k3f9` ([runs.md](runs.md#ids)) |
| Memory queue | The launcher's queue, one per project, that lets one writer at a time change `.barrel/` and the project's integration worktrees (Q24; [memory.md](memory.md#queue)) |
| Shared memory | Preferences and verified experience shared across projects, in `~/.barrel/shared/` on the PC (archived D-007, D-008, D-030; Q17; [memory.md](memory.md#shared)) |
| Task node, leaf, contract | One file under `.barrel/tasks/<run>/`. A leaf's file is its contract (Q06, Q15) |
| Run state | Files under `~/.barrel/`, outside the repo (Q07): sessions, events, Slack threads, lanes, the queue. Written by the launcher, its hooks and, in their own folders, the sessions ([memory.md](memory.md#run-state)) |
| Gate | A deterministic verification command from the unit loop (`barrel/core/gates.py`) |
| Lane | A reused set of git worktrees, one per repo of the project, in which one leaf task is implemented (Q14). Each worktree sits on a detached HEAD (AI) |

## Status and next step

- Nothing in this folder is implemented yet.
- The execution base that exists on main is `step2step/` and the unit loop (`barrel/core/`, `orchestration/drivers/unit_loop.py`). [launcher.md](launcher.md#reuse) maps what is reused, what is extended and what is new.
- The next step is the spike in [validation.md](validation.md), starting with the thin slices it lists first.
