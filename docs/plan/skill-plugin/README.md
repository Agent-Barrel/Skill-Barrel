# Barrel design

Updated 2026-10-11. Status: canonical design, not implemented yet. Written in English because English is canonical ([Q08](../interview/q08-korean-docs.md)).

This folder is the design Barrel is built from. It replaces the 2026-09-29 draft, which is archived in [docs/archive/skill-plugin-2026-09-29](../../archive/skill-plugin-2026-09-29/README.md).
- It was rewritten on 2026-10-08 from interview answers Q01–Q16.
- On 2026-10-11 it was checked again against the verbatim answers, the original flow, the archived drafts and the code:
  - Two places that contradicted the answers (Q02, Q05) were fixed.
  - The gaps the flow needs filled were filled. The defaults added are listed for review in [open-decisions.md](open-decisions.md#ai-defaults).

## What Barrel is

Barrel is a skill for Claude Code and Codex. It changes how a coding agent works.

1. The user runs the `barrel` skill in any Claude Code or Codex session and gives it a product concept or a maintenance request.
2. That session makes sure the per-PC launcher is running, has it start an orchestrator session, and its own job ends.
3. Barrel then works without the user attached:
   - It draws out the requirements and the functional spec through interviews over Slack.
   - It has the user review an intent summary and, as deep as the request needs, the top two levels of the task tree.
   - It researches the technology and, when new technology enters, has the user confirm the stack.
   - It implements the work as small leaf tasks. Each leaf runs in a fresh coding-agent session that gets only the context it needs.
   - It checks the result and delivers it to the repo.
4. Every decision and every piece of context lives in small linked files in the repo, never only in a session or in a CLI's memory. Any session or account can therefore be replaced at any point.
5. Barrel asks the human only what those files cannot answer, and keeps working on unrelated tasks while one task waits. At the end it judges the result against the requirements and the functional spec.

Sources: the [2026-10-06 request](../README.md#source), [00-original-flow.md](../00-original-flow.md), [insight.md](../insight.md), and interview answers [Q01–Q16](../interview/README.md).

## Reading rules

- The verbatim answers in [interview/](../interview/README.md) are the source of truth. If this folder disagrees with one of them, the answer wins and this folder gets fixed.
- Every decision carries a source tag:

| Tag | Meaning |
| --- | --- |
| `(Q07)` | The user's answer to that interview question |
| `(Q07 default)` | A default the AI proposed in that question; the user did not object |
| `(AI)` | A detail the AI decided, because the user delegated it or nothing was said. Open to change; the ones with the most effect are listed in [open-decisions.md](open-decisions.md#ai-defaults) |
| `(09-29 draft)` | A rule carried over from the 2026-09-29 draft, which the AI wrote from the user's 09-29 request. It was not asked in the interview, so it counts as an AI default |
| `(archived D-032)` | A user decision from the archived app plan ([docs/archive/app-plan](../../archive/app-plan/README.md)), carried over because it still fits ([migration.md](migration.md#archived)) |
| `(flow 5)` | An item of [00-original-flow.md](../00-original-flow.md) |
| `(insight)` | [insight.md](../insight.md) |
| `(10-06 request)` | The [2026-10-06 request](../README.md#source) |

- Code references are `path:line` on main at `ceb5a73`.

## Documents

| Document | Contents |
| --- | --- |
| [workflow.md](workflow.md) | Stages from first run to completion, onboarding an existing repo, depth by impact, when Barrel asks the human, change cascades |
| [interviews.md](interviews.md) | How every human question is researched, verified, posted, answered and recorded |
| [memory.md](memory.md) | `.barrel/` in the repo: memory units, review records, indexes, the planning loop, who writes what; run state outside the repo; secrets |
| [task-tree.md](task-tree.md) | Large > medium > leaf topics, when they are split, leaf size, and the task contract |
| [sessions.md](sessions.md) | Roles, permission modes, engines and `.barrel/config.json`, accounts, subagents, and the orchestrator lifecycle |
| [task-execution.md](task-execution.md) | How one leaf runs, from plan to commit; preflight, questions, failures, parallel lanes, regression checks, acceptance |
| [runs.md](runs.md) | Starting a run, IDs, branches and worktrees, delivery, sharing `.barrel/` across runs and teammates, after a run |
| [launcher.md](launcher.md) | The per-PC launcher: process, sleep, versions, commands and access, event catalog, recovery, stop and resume, and a reuse and gap map of the existing code |
| [slack.md](slack.md) | The Slack bot: manifest, progress reports, snapshots, questions, reminders, commands, language, outages |
| [pc-view.md](pc-view.md) | The local status page with stop and resume, and how to reopen it |
| [plugin.md](plugin.md) | Packaging for both CLIs, the `barrel` skill, hooks and hook trust, role markers, install and first-run setup |
| [migration.md](migration.md) | Mappings from the original flow, the interview, the 09-29 draft, the archived plan and the existing code |
| [validation.md](validation.md) | What the spike builds first, the spike checklist and its pass criteria |
| [open-decisions.md](open-decisions.md) | Status of OD-1…OD-10, the AI defaults waiting for review, and the archived decisions not carried |
| [research.md](research.md) | Dated code, vendor and prior-art facts this design relies on |

## Principles

1. **Intent first.** Before implementation, Barrel draws out the direction, the purpose and the implementation intent through requirements and functional-spec interviews, and writes them down (flow 2–5, Q01).
2. **Sessions are brains, files are memory.** Every session starts fresh and reads its context from files. Nothing lives only in a conversation, in one account, or in a CLI's own memory (10-06 request, flow 1, Q03, Q07).
3. **Ask only what the documents cannot answer.**
   - What the AI can decide from the intent and the specs, it decides.
   - It asks only when the direction cannot be inferred or a genuinely new decision is needed (Q01, Q06).
   - Separately, it requests what only the user can do, such as a login (Q01; flow 10).
   - A blocked task stops alone, and unrelated tasks continue.
4. **Small tasks, fresh sessions, only the needed context.** Each leaf goes to a new session that receives only the context units that leaf needs (insight, Q02, Q06).
5. **Conflicts are settled before the work.** When two pieces of context bear on a task, the direction and the trade-offs between them are decided before the task starts (insight, flow 1).
6. **Engines are interchangeable.** Claude Code and Codex are engines that run Barrel. No role is tied to a provider. Model and effort follow the difficulty of the work, and every usable CLI and account on the PC is used (Q12, Q16).
7. **Findings are verified before they are used.** Research is followed by an independent verification pass that checks each claim against its sources (Q16).
8. **Code gives the verdicts and keeps the records; the AI judges intent.**
   - Gates, which are deterministic commands, decide whether a task passed (archived D-024).
   - The launcher, which is code, records every answer and approval verbatim (09-29 draft, principle 5).
   - The AI judges whether the final result matches the intent, using the requirements and the functional spec (Q01).
9. **English inside, Korean for people.**
   - Memory, contracts and session-to-session files are English.
   - Human-facing text is written in Korean with Skill-Techblog unless the Slack language is set to English (Q08, Q10).
10. **Slack and the PC view only report.** The files in the repo and the run state are the truth (Q10 default).

## Non-goals

- No `claude -p` or other headless runs. Sessions are interactive and driven by `step2step` (repo rule).
- No posting through the Slack MCP. Only the launcher's bot posts (Q09, Q10 default).
- No editing of Slack messages. Progress is always a new message (Q10).
- No answering questions or sending instructions from the PC view. That happens in Slack (Q10-2).
- No user-facing stop for a single task. Stop halts the whole project run (Q10-2). The orchestrator can still cancel a leaf whose contract a change replaced ([workflow.md](workflow.md#cascade)).
- No status command in the terminal. Status is in Slack and the PC view (Q10-2 default).
- No auto-answering a task session's questions with a guess (Q01; replaces `menu_default_answer`, `barrel/core/unitloop.py:82`).
- No roles split by provider, such as "Claude-side research" and "Codex-side research" (Q16).

## Glossary

| Term | Meaning |
| --- | --- |
| Invoking session | The Claude Code or Codex session where the user runs the `barrel` skill. It sets things up, starts the run and ends (Q03-3) |
| Launcher | The one Barrel process per PC (Q11). It owns every session, the Slack connection, the PC views, the event log and, as an AI detail, the git queue. Built on `step2step` |
| Engine | Claude Code or Codex, as used by Barrel (Q16) |
| Account | One config folder of an engine: a `CLAUDE_CONFIG_DIR` or `CODEX_HOME` with its own login (Q05) |
| Project | A target repo that Barrel works on. Its shared files are in `.barrel/` |
| Run | One execution for a project, from a start input to completion. A project can have many runs over time, one active at a time on a PC. Its ID looks like `20261011-a7mz` ([runs.md](runs.md)) |
| Run branch | `barrel/<run>`, where a run's work is committed and from which it is delivered ([runs.md](runs.md#branches)) |
| Orchestrator | The session that plans and directs a run. It is replaced by a successor at stage ends, at medium-topic ends, and before its context fills up (Q03, Q03-3, Q04-2) |
| Task session | A fresh session that implements one leaf task (Q02) |
| Auxiliary role | Advice, intent check, context gathering, research, verification or review. Each runs as a subagent of the orchestrator, or as a fresh session when its engine is on another CLI (Q02, Q16). The Korean writer is always a fresh session ([sessions.md](sessions.md#roles)) |
| Subagent | A child agent inside a session, used for short read-only work (Q02) |
| Memory unit | One file under `.barrel/memory/` that holds one minimal piece of context (Q07). Its ID is a short hash, such as `REQ-k3f9` ([runs.md](runs.md#ids)) |
| Task node, leaf, contract | One file under `.barrel/tasks/<run>/`. A leaf's file is its contract (Q06, Q15) |
| Run state | Files under `~/.barrel/`, outside the repo (Q07): sessions, events, Slack threads, lanes. Written by the launcher and its hooks. The orchestrator writes its own folder, and fresh auxiliary sessions and investigation leaves write `outputs/` (AI) |
| Gate | A deterministic verification command from the unit loop (`barrel/core/gates.py`) |
| Lane | A reused git worktree in which one leaf task is implemented (Q14). It sits on a detached HEAD (AI) |

## Status and next step

- Nothing in this folder is implemented yet.
- The execution base that exists on main is `step2step/` and the unit loop (`barrel/core/`, `orchestration/drivers/unit_loop.py`). [launcher.md](launcher.md#reuse) maps what is reused, what is extended and what is new.
- The next step is the spike in [validation.md](validation.md), starting with the thin slices it lists first.
