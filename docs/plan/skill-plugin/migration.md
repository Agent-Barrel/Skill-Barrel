# Where everything came from

This document maps the inputs to this design:
- the original flow
- the interview
- the 2026-09-29 draft
- the archived app plan
- the existing code

Use it to check that nothing was dropped by accident. The 2026-10-11 review added the rows marked "(10-11)".

<a id="original-flow"></a>
## The original flow

[00-original-flow.md](../00-original-flow.md), item by item.

| # | Original flow | Where it is now | Notes |
| --- | --- | --- | --- |
| 0 | A skill for both CLIs; Fable or Astra advise on hard questions; Opus 5.5 implements; research combines both CLIs' findings; mixed use | [README](README.md#principles) principle 6, [sessions.md](sessions.md#engines) | Q04 and Q04-2: both CLIs, including as orchestrator. Q16: engines are interchangeable. The model examples became defaults in `.barrel/config.json` (Q12). Research is cross-checked by a separate verification pass, not by splitting it across providers (Q16) |
| 1 | Find the CLIs on the PC; use every subscription through per-account folders (config dir, `CODEX_HOME`); ask for account names | [workflow.md](workflow.md#stages) S0, [sessions.md](sessions.md#accounts), [plugin.md](plugin.md#setup) | Q05, Q12. (10-11) Setup now asks once for other subscriptions, not only when a CLI has none |
| 1-1 | Shared memory that depends on no CLI, account or session; understand the whole context before working | [memory.md](memory.md) | Q07 |
| 1-2 | Start from the coarse picture; minimal linked units; refine the plan by following links | [memory.md](memory.md#loop), [task-tree.md](task-tree.md#split) | Q06, Q07 |
| 1-3 | Give each split task only the context it needs | [memory.md](memory.md#context), [task-execution.md](task-execution.md#lifecycle) | insight |
| 1-4 | Settle conflicts between contexts before the work | [memory.md](memory.md#loop), README principle 5 | insight. (10-11) Each settlement is recorded as a `decision` unit |
| 2 | Start from a product concept or a maintenance request | [workflow.md](workflow.md#stages) S1, [runs.md](runs.md#start) | Q13 decides how deep the later stages go. (10-11) An existing repo is onboarded first ([workflow.md](workflow.md#onboarding)) |
| 3 | Requirements derivation and spec through interviews | S3, [interviews.md](interviews.md) | (10-11) The spec is rendered from the units and attached to the S5 review, as Q08's chosen option lists ([interviews.md](interviews.md#review)) |
| 4 | Functional spec through interviews | S4 | Same as 3 |
| 5 | Before each question, research similar services and competitors; explain the context; show the research if wanted | [interviews.md](interviews.md#before), [#format](interviews.md#format) | A verification pass was added (Q16). (10-11) The full research is posted in the thread on request, because a link to an unpushed commit breaks |
| 6 | Enter implementation prep | S6 | |
| 7 | Technical research with current information: pros, cons, constraints such as licensing | S6, [interviews.md](interviews.md#stack) | |
| 8 | Confirm the stack with the user | S6 | Q13: only when new technology enters, at every depth. A new concept always brings new technology |
| 9 | Implement on the confirmed information | S7, [task-execution.md](task-execution.md) | Q14 parallel lanes |
| 10 | Ask for what is needed, then set it up with computer use or Playwright | [workflow.md](workflow.md#asking), [task-execution.md](task-execution.md#user-only) | (10-11) Playwright MCP is given to sessions per session; computer use only after the user agrees; credentials are given in the request's thread or with `barrel secret set` on the Mac, and kept in the Keychain; the delegated scope from S6 (archived D-013) ([open-decisions.md](open-decisions.md#ai-defaults)) |
| 11 | Questions and requests over Slack | [slack.md](slack.md) | Q09, Q10 |
| 12 | A desktop view of the current state, with extra communication | [pc-view.md](pc-view.md) and Slack | Q10, Q10-2: the PC view shows state and can stop and resume; communication goes through Slack |

<a id="interview"></a>
## The interview

| Question | Decided | Where it is now |
| --- | --- | --- |
| [Q01](../interview/q01-keep-working-scope.md) | Keep working; ask only when the documents cannot answer; block only that task; the AI judges the result against the specs; intent review before implementation; cascades go to the user | [workflow.md](workflow.md#asking), [#blocked](workflow.md#blocked), [#cascade](workflow.md#cascade), [task-execution.md](task-execution.md#acceptance) |
| [Q02](../interview/q02-subagent-vs-session.md) | Fresh sessions for implementation, plan approval and work that must survive a restart; subagents for short read-only work: context, research, independent review | [sessions.md](sessions.md#roles). (10-11) The 10-08 rewrite ran research, verification and review as fresh sessions, against option A; they are subagents again. The provider wording is replaced by Q16 |
| [Q03](../interview/q03-orchestrator-restart.md), [Q03-2](../interview/q03-2-bootloader-session.md), [Q03-3](../interview/q03-3-launcher-and-slack.md) | The invoking session launches the orchestrator and ends; questions go to Slack; orchestrators replace themselves | [workflow.md](workflow.md#stages), [sessions.md](sessions.md#orchestrator) |
| [Q04](../interview/q04-target-cli.md), [Q04-2](../interview/q04-2-orchestrator-on-both-cli.md) | Both CLIs from the start, orchestrators included; one launcher built on step2step | [launcher.md](launcher.md), [plugin.md](plugin.md) |
| [Q05](../interview/q05-accounts.md) | Use the registered accounts, set them up if missing, move to the next account | [sessions.md](sessions.md#accounts) |
| [Q06](../interview/q06-task-tree.md) | Two levels reviewed, leaves split when their turn comes; ask only when the specs cannot settle it | [task-tree.md](task-tree.md) |
| [Q07](../interview/q07-shared-memory.md) | Memory in the repo, one unit per file, indexes, verbatim answers as units | [memory.md](memory.md). (10-11) Answer units are written by the launcher |
| [Q08](../interview/q08-korean-docs.md) | English canonical; Korean for people through Skill-Techblog | [interviews.md](interviews.md#language), [slack.md](slack.md#language) |
| [Q09](../interview/q09-slack-and-dashboard.md) | A dedicated bot plus the official MCP for reading; renamed Barrel | [slack.md](slack.md#setup) |
| [Q10](../interview/q10-slack-progress-reports.md), [Q10-2](../interview/q10-2-pc-view-stop-language.md), [confirmed](../interview/q10-confirmed.md) | Slack reports, snapshots, questions, reminders, language; the PC view; stop and resume | [slack.md](slack.md), [pc-view.md](pc-view.md), [launcher.md](launcher.md#stop) |
| [Q11](../interview/q11-launcher-topology.md) | One launcher per PC | [launcher.md](launcher.md) |
| [Q12](../interview/q12-model-config-and-cli-fallback.md) | Model assignment in `.barrel/` for the team; use every CLI and account; moving to another CLI is already decided | [sessions.md](sessions.md#engines), [#accounts](sessions.md#accounts) |
| [Q13](../interview/q13-depth-by-impact.md) | The AI sets each stage's depth from the impact | [workflow.md](workflow.md#depth) |
| [Q14](../interview/q14-parallel-sessions.md) | Parallel worktree lanes, default 2 | [task-execution.md](task-execution.md#lanes), [#regression](task-execution.md#regression) |
| [Q15](../interview/q15-task-files-in-repo.md) | The tree and contracts in `.barrel/tasks/`, tracked by git | [task-tree.md](task-tree.md#files). (10-11) One folder per run ([runs.md](runs.md#sharing)) |
| [Q16](../interview/q16-engines-and-verification.md) | No split by provider; verify research; model and effort by difficulty; the Korean writer as a fresh session | [sessions.md](sessions.md), [interviews.md](interviews.md#before) |

<a id="draft"></a>
## The 2026-09-29 draft

The draft is archived in [docs/archive/skill-plugin-2026-09-29](../../archive/skill-plugin-2026-09-29/README.md).

| Draft item | Now |
| --- | --- |
| Principle 1: decide first | Kept. Intent first (README principle 1) |
| Principle 2: small tasks | Kept (Q06) |
| Principle 3: a fresh session per task | Kept, and subagents now take short read-only work (Q02) |
| Principle 4: check the plan against the intent before running it | Kept ([task-execution.md](task-execution.md#lifecycle) step 6) |
| Principle 5: code gives the verdicts, and approval records and evidence come from code | Kept (README principle 8). (10-11) The launcher now writes answer units, and approvals are tied to a revision ([interviews.md](interviews.md#recording)) |
| Non-goal "does not keep running until done" | Dropped by Q01 |
| Non-goals "no unattended running, no restart after reboot, no multi-project scheduler" | Dropped: Q01 keeps working, Q11 runs every project from one launcher, and auto-resume follows archived Q-007 (AI) |
| Non-goal "no rotating accounts" | Dropped by Q05 and Q12 |
| Non-goal "no Slack, no relay, no dashboard" | Dropped by Q09 and Q10 |
| `workflow.md` S1–S8 and the three tracks | S0–S8 ([workflow.md](workflow.md#stages)); the tracks became impact levels (Q13) |
| `workflow.md` S5: preflight, prompt preview, fail-first for every gate | (10-11) Kept as the S7 preflight and baseline ([task-execution.md](task-execution.md#preflight)); per-leaf fail-first stays |
| `workflow.md` S8 passes only when the Git policy is met | (10-11) Kept: delivery is part of S8's exit ([runs.md](runs.md#delivery)) |
| `workflow.md` approval of a specific revision | (10-11) Kept ([interviews.md](interviews.md#recording)) |
| `clarification.md` ledger | Memory units: `decision` and `answer` (Q07). Open questions are in run state |
| `clarification.md` five discovery methods | Kept in [interviews.md](interviews.md#discovery) |
| `clarification.md` closure and items found late | Stage exits ([interviews.md](interviews.md#exits)), which now include the gap review (10-11); questions from task sessions ([task-execution.md](task-execution.md#questions)); the method that missed a late decision is recorded (10-11) |
| `task-sessions.md` size, contract, execution, plan check, questions, failures | Kept and extended ([task-tree.md](task-tree.md), [task-execution.md](task-execution.md)) |
| `task-sessions.md` read-only investigation leaf | (10-11) A context subagent investigates first (Q02); a read-only leaf only when the investigation is long ([task-tree.md](task-tree.md#size)) |
| `task-sessions.md` result report: response, tools, transcript path, gate output | Kept ([task-execution.md](task-execution.md#report)); (10-11) the response and transcript path were restored |
| `task-sessions.md` "no subagents" | Replaced by Q02 |
| `task-sessions.md` order: `on_unit_blocked: halt` | Replaced: unrelated tasks continue (Q01); parallel lanes (Q14) |
| `task-sessions.md` roles by RTE and provider | Replaced by engine tiers (Q16) |
| `plugin-architecture.md` coordination in the user's session | Replaced by the launcher-owned orchestrator (Q03-3, Q04-2, Q11) |
| `plugin-architecture.md` six skills | One skill plus role playbooks (AI, [plugin.md](plugin.md#playbooks)) |
| `plugin-architecture.md` hooks keyed on `BARREL_TASK` | Kept as role markers ([plugin.md](plugin.md#markers)) |
| `plugin-architecture.md` hook that records approvals and denies model-written approval files | (10-11) Kept in a different form: the launcher writes answer units, and the orchestrator's hook denies writes to `answer/` ([plugin.md](plugin.md#hooks)) |
| `plugin-architecture.md` hook that denies git bypasses such as `--no-verify` | (10-11) Kept, widened to every ref-changing git command in every Barrel session ([plugin.md](plugin.md#hooks)) |
| `plugin-architecture.md` gap list | [launcher.md](launcher.md#reuse) |
| `plugin-architecture.md` and `migration.md`: `~/.barrel/memory` for preferences shared across projects | Not carried. Q07 chose memory in the repo and turned down a PC-local folder. A preference the user states becomes a decision unit in the project. Listed for the user in [open-decisions.md](open-decisions.md#not-carried) (10-11) |
| `migration.md` spec-handling table, including branch and worktree cleanup | (10-11) Cleanup kept ([runs.md](runs.md#after)); the rest of the table is covered by the archived-plan rows below |
| `migration.md` classification of the archived 81 features | Not carried over. This folder replaces the archived plan's CSVs as the design (AI) |
| `validation.md` | Rewritten ([validation.md](validation.md)). H1 (the skill turns itself on) is dropped, because the skill is invoked explicitly. (10-11) The build order before the spike and the false-denial count in H7 are back |
| `open-decisions.md` OD-1…OD-10 | Statuses in [open-decisions.md](open-decisions.md#od) |
| `research.md` | Refreshed in [research.md](research.md) |

<a id="archived"></a>
## Rules carried over from the archived app plan

Some rules from [docs/archive/app-plan](../../archive/app-plan/README.md) are the user's earlier decisions and still fit. In the "Fit" column:
- **P:** the rule applies as written.
- **A:** the rule assumed the desktop app and was adapted.

| Rule | Source | Fit | Where it is now |
| --- | --- | --- | --- |
| Starting with only one of the two CLIs is allowed | D-004 | P | [sessions.md](sessions.md#engines) (10-11) |
| Preferences are shared across projects; explicit ones are recorded, inferred ones stay candidates; project decisions win | D-007, D-030 | Not carried | Q07 put memory in the repo and turned down a PC-local folder. Listed in [open-decisions.md](open-decisions.md#not-carried) (10-11) |
| Research per decision topic, reused for follow-ups unless conditions changed | D-011 | P | [interviews.md](interviews.md#before) (10-11) |
| The environment, action and cost scope is delegated per project; only an expansion is asked | D-013 | A | [interviews.md](interviews.md#stack), [task-execution.md](task-execution.md#user-only) (10-11) |
| The review scope is judged from impact, not file count | `specs/workflow.md#assessment`, D-026, D-034 | P | [workflow.md](workflow.md#depth), [#onboarding](workflow.md#onboarding) |
| Research before asking; one decision per question; record after each answer | `specs/workflow.md#research`, D-065 | P | [interviews.md](interviews.md) |
| Three approval bundles (requirements, features plus wireframes, stack plus design) | D-010 | Not carried | Approvals now follow Q01, Q06 and Q13: the intent review and the stack confirmation |
| The task contract's contents | `specs/orchestration.md#task-input` | P | [task-tree.md](task-tree.md#files) |
| Check the plan against the intent; plan mode is not the check | P-001, RTE-013 | P | [task-execution.md](task-execution.md#lifecycle) |
| Self-reports are not evidence; gates and verification decide; completion includes delivery | `specs/orchestration.md#verification`, D-024 | P | [task-execution.md](task-execution.md), [runs.md](runs.md#delivery) |
| Applying a changed decision: from the next task, or stop the affected tasks now | D-031 | A | [workflow.md](workflow.md#cascade) (10-11). Its configurable default answer is not carried ([open-decisions.md](open-decisions.md#not-carried)) |
| Independent review by risk | Q-004 | P | [task-execution.md](task-execution.md#review) |
| Ask about pre-existing failures each time | Q-005 | P | [task-execution.md](task-execution.md#pre-existing); (10-11) a baseline makes them provable |
| Re-examine and try alternatives; no fixed retry count; ask before changing what the user mandated | D-040, D-041 | P | [task-execution.md](task-execution.md#failures) |
| Parallel only when reads and writes are disjoint, and when shared resources do not collide; one at a time when unclear | D-032 | P | [task-execution.md](task-execution.md#lanes); (10-11) read sets and resources were added so the rule holds as written |
| Sleep policy: follow the OS, prevent sleep on power, or prevent it on battery too | D-047 | A | [launcher.md](launcher.md#sleep) (10-11). Changing it from Slack is not carried; the default is AI |
| Clean up leftovers after every job | D-062 | A | [runs.md](runs.md#after) (10-11) |
| Resume automatically after a crash or OS restart; a user stop stays stopped | `specs/memory-and-lifecycle.md#recovery`, Q-007 | A | [launcher.md](launcher.md#process), [#recovery](launcher.md#recovery) |
| A new project may be saved to a private GitHub repository if the user opts in | Q-003 | A | [runs.md](runs.md#delivery) (10-11) |
| Needed tools are installed after approval; existing ones are reused; personal settings are left alone | Q-008 | A | [task-execution.md](task-execution.md#user-only) (10-11) |
| Cancelling a job offers keep or discard for unmerged changes | Q-009 | Not carried | Barrel has stop and resume instead of cancel (Q10-2 chose option A, not C, which ended the run). A request given to a stopped run waits for the resume ([runs.md](runs.md#start)) (10-11) |
| Git author: reuse the existing one, else a project-scoped one (GitHub noreply or the app's name) | Q-012 | P | [runs.md](runs.md#branches) (10-11) |
| Planning documents live in git with the code; full conversations, common memory and credentials stay out | Q-013 | P | [memory.md](memory.md) (10-11) |
| Git delivery scope; keep the user's changes | `specs/repositories.md#delivery`, `#start` | P | [runs.md](runs.md#delivery), [interviews.md](interviews.md#stack) |
| Only the registered user's Slack account is obeyed, confirmed from the Mac and not by an install alone | D-043 | A | [slack.md](slack.md#setup), [#security](slack.md#security). (10-11) The check from the Mac is the install's OAuth redirect to this Mac, or the one-time code |
| Small, clear tasks may use a cheaper model; the clarity criteria | D-068, `specs/accounts-and-budget.md#model-policy` | P | [sessions.md](sessions.md#difficulty) |
| One project spanning several repos; a separate docs repo for shared planning | Q-014, Q-015 | Not carried in this version | A project is one repo (Q07, Q15 speak of the target repo). Listed for the user in [open-decisions.md](open-decisions.md#not-carried) (10-11) |
| Model roles split by provider (RTE-004/005) | `model-routing.csv` | Not carried | Q16 |

<a id="code"></a>
## The existing code

[launcher.md](launcher.md#reuse) lists, with line references, what is reused, extended, missing or replaced.

New components, which have no existing code:
- the launcher process, its socket and its access check
- the `barrel` command
- the event log
- the Slack bot
- the PC view
- the memory tools (index, render) and answer recording
- the task-tree runner, its lanes and regression checks
- worktrees, merges and delivery
- engine and account selection
- crash recovery, the sleep policy and version checks
- the hooks and the playbooks
- the `barrel` skill
