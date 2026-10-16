# Where everything came from

This document maps the inputs to this design:
- the original flow
- the interview, Q01–Q24
- the 2026-10-12 readiness checks
- the 2026-09-29 draft
- all 93 decisions of the archived app plan
- the existing code

Use it to check that nothing was dropped by accident. The 2026-10-11 review added the rows marked "(10-11)"; the 2026-10-13 revision added or changed the rows marked "(10-13)".

<a id="original-flow"></a>
## The original flow

[00-original-flow.md](../00-original-flow.md), item by item.

| # | Original flow | Where it is now | Notes |
| --- | --- | --- | --- |
| 0 | A skill for both CLIs; Fable or Astra advise on hard questions; Opus 5.5 implements; research combines both CLIs' findings; mixed use | [README](README.md#principles) principle 7, [sessions.md](sessions.md#engines) | Q04 and Q04-2: both CLIs, including as orchestrator. Q16: engines are interchangeable. The model examples became defaults in `.barrel/config.json` (Q12). Research is cross-checked by a separate verification pass, not by splitting it across providers (Q16) |
| 1 | Find the CLIs on the PC; use every subscription through per-account folders (config dir, `CODEX_HOME`); ask for account names | [workflow.md](workflow.md#stages) S0, [sessions.md](sessions.md#accounts), [plugin.md](plugin.md#setup) | Q05, Q12. (10-11) Setup asks once for other subscriptions. (10-13) Sessions run from Barrel-managed config folders named by the account, which reuse each account's login (archived D-048; Q17-2) |
| 1-1 | Shared memory that depends on no CLI, account or session; understand the whole context before working | [memory.md](memory.md) | Q07. (10-13) Every session updates the memory before it ends, through a queue (Q24). Personal instructions and memory the user picks load into Barrel's sessions on both engines, so no engine knows more than another, and project instructions such as `CLAUDE.md` become units ([workflow.md](workflow.md#onboarding)) |
| 1-2 | Start from the coarse picture; minimal linked units; refine the plan by following links | [memory.md](memory.md#loop), [task-tree.md](task-tree.md#split) | Q06, Q07 |
| 1-3 | Give each split task only the context it needs | [memory.md](memory.md#context), [task-execution.md](task-execution.md#lifecycle) | insight. (10-13) A hook keeps task sessions from reading the rest of memory outside their memory turn |
| 1-4 | Settle conflicts between contexts before the work | [memory.md](memory.md#loop), README principle 6 | insight. (10-11) Each settlement is recorded as a `decision` unit |
| 2 | Start from a product concept or a maintenance request | [workflow.md](workflow.md#stages) S1, [runs.md](runs.md#start) | Q13 decides how deep the later stages go. (10-11) An existing project is onboarded first. (10-13) A project may span several repos, and each request is its own run (Q17-2, Q18) |
| 3 | Requirements derivation and spec through interviews | S3, [interviews.md](interviews.md) | (10-11) The spec is rendered from the units and attached to the S5 review, as Q08's chosen option lists |
| 4 | Functional spec through interviews | S4 | Same as 3. (10-13) Wireframes and API rules follow it where they apply (archived Q-010, Q-011; [workflow.md](workflow.md#design)) |
| 5 | Before each question, research similar services and competitors; explain the context; show the research if wanted | [interviews.md](interviews.md#before), [#format](interviews.md#format) | A verification pass was added (Q16). (10-11) The full research is posted in the thread on request. (10-13) Options come with buttons, and non-developers get plain words |
| 6 | Enter implementation prep | S6 | |
| 7 | Technical research with current information: pros, cons, constraints such as licensing | S6, [interviews.md](interviews.md#stack) | (10-13) Modern UI references for projects with screens (archived Q-010); minimal experiments before approval (archived D-042) |
| 8 | Confirm the stack with the user | S6 | Q13: only when new technology enters. (10-13) Q19 defines it as the hard-to-reverse choices; the detailed design is confirmed in the same review; approval is by button (archived D-045) |
| 9 | Implement on the confirmed information | S7, [task-execution.md](task-execution.md) | Q14 parallel lanes. (10-13) Each leaf ends with its memory update (Q24) |
| 10 | Ask for what is needed, then set it up with computer use or Playwright | [workflow.md](workflow.md#asking), [task-execution.md](task-execution.md#user-only) | (10-11) Playwright MCP per session; the delegated scope from S6 (archived D-013). (10-13) Credentials through a macOS dialog, sudo through Barrel's own tool (Q20); computer use within agreed time windows (archived D-025); outside services through per-leaf MCP servers (archived D-069) |
| 11 | Questions and requests over Slack | [slack.md](slack.md) | Q09, Q10. (10-13) Messages of several runs routed by thread and buttons (Q18); cancelling a run (archived Q-009) |
| 12 | A desktop view of the current state, with extra communication | [pc-view.md](pc-view.md) and Slack | Q10, Q10-2: the PC view shows state and can stop and resume; communication goes through Slack |

<a id="interview"></a>
## The interview

| Question | Decided | Where it is now |
| --- | --- | --- |
| [Q01](../interview/q01-keep-working-scope.md) | Keep working; ask only when the documents cannot answer; block only that task; the AI judges the result against the specs; intent review before implementation; cascades go to the user | [workflow.md](workflow.md#asking), [#blocked](workflow.md#blocked), [#cascade](workflow.md#cascade), [task-execution.md](task-execution.md#acceptance) |
| [Q02](../interview/q02-subagent-vs-session.md) | Fresh sessions for implementation, plan approval and work that must survive a restart; subagents for short read-only work: context, research, independent review | [sessions.md](sessions.md#roles). (10-11) Research, verification and review are subagents again. The provider wording is replaced by Q16 |
| [Q03](../interview/q03-orchestrator-restart.md), [Q03-2](../interview/q03-2-bootloader-session.md), [Q03-3](../interview/q03-3-launcher-and-slack.md) | The invoking session launches the orchestrator and ends; questions go to Slack; orchestrators replace themselves | [workflow.md](workflow.md#stages), [sessions.md](sessions.md#orchestrator). (10-13) Clones and their logins also stay out of the invoking session ([runs.md](runs.md#clones)) |
| [Q04](../interview/q04-target-cli.md), [Q04-2](../interview/q04-2-orchestrator-on-both-cli.md) | Both CLIs from the start, orchestrators included; one launcher built on step2step | [launcher.md](launcher.md), [plugin.md](plugin.md) |
| [Q05](../interview/q05-accounts.md) | Use the registered accounts, set them up if missing, move to the next account | [sessions.md](sessions.md#accounts) |
| [Q06](../interview/q06-task-tree.md) | Two levels reviewed, leaves split when their turn comes; ask only when the specs cannot settle it | [task-tree.md](task-tree.md) |
| [Q07](../interview/q07-shared-memory.md) | Memory in the repo, one unit per file, indexes, verbatim answers as units | [memory.md](memory.md). (10-11) Answer units are written by the launcher. The indexes are generated from the units and kept out of git, so merges never conflict; the units themselves are tracked (AI default 8). (10-13) In a project of several repos, "the repo" is the planning repo (Q17) |
| [Q08](../interview/q08-korean-docs.md) | English canonical; Korean for people through Skill-Techblog | [interviews.md](interviews.md#language), [slack.md](slack.md#language) |
| [Q09](../interview/q09-slack-and-dashboard.md) | A dedicated bot plus the official MCP for reading; renamed Barrel | [slack.md](slack.md#setup) |
| [Q10](../interview/q10-slack-progress-reports.md), [Q10-2](../interview/q10-2-pc-view-stop-language.md), [confirmed](../interview/q10-confirmed.md) | Slack reports, snapshots, questions, reminders, language; the PC view; stop and resume | [slack.md](slack.md), [pc-view.md](pc-view.md), [launcher.md](launcher.md#stop) |
| [Q11](../interview/q11-launcher-topology.md) | One launcher per PC | [launcher.md](launcher.md) |
| [Q12](../interview/q12-model-config-and-cli-fallback.md) | Model assignment in `.barrel/` for the team; use every CLI and account; moving to another CLI is already decided | [sessions.md](sessions.md#engines), [#accounts](sessions.md#accounts). (10-13) "Use every config folder" means every account's login; personal settings come only by choice (Q17) |
| [Q13](../interview/q13-depth-by-impact.md) | The AI sets each stage's depth from the impact | [workflow.md](workflow.md#depth) |
| [Q14](../interview/q14-parallel-sessions.md) | Parallel worktree lanes, default 2 | [task-execution.md](task-execution.md#lanes), [#regression](task-execution.md#regression) |
| [Q15](../interview/q15-task-files-in-repo.md) | The tree and contracts in `.barrel/tasks/`, tracked by git | [task-tree.md](task-tree.md#files). (10-11) One folder per run ([runs.md](runs.md#sharing)) |
| [Q16](../interview/q16-engines-and-verification.md) | No split by provider; verify research; model and effort by difficulty; the Korean writer as a fresh session | [sessions.md](sessions.md), [interviews.md](interviews.md#before) |
| [Q17](../interview/q17-restore-archived-decisions.md) | Restore all 13 groups of archived decisions that the design had dropped, adapted to the skill | (10-13) Every group, as the [readiness table](#readiness) maps |
| [Q17-2](../interview/q17-2-repo-list-config-and-updates.md) | The planning repo lists the repos and work starts by cloning them; the Barrel-managed CLI environment must be in the skill; self-update replaces the pinned CLI; no previous product name in the repo | (10-13) [runs.md](runs.md#projects), [memory.md](memory.md#repos), [sessions.md](sessions.md#barrel-folders), [launcher.md](launcher.md#versions) |
| [Q18](../interview/q18-one-run-per-request.md) | A new run per request, with its own branches, tree and orchestrator; Slack messages carry the request name; the later delivery merges the earlier result | (10-13) [runs.md](runs.md#start), [slack.md](slack.md#routing), [task-execution.md](task-execution.md#lanes) |
| [Q19](../interview/q19-new-technology-threshold.md) | Only hard-to-reverse choices are confirmed; Barrel picks ordinary libraries and checks every package | (10-13) [workflow.md](workflow.md#new-technology), [task-execution.md](task-execution.md#packages) |
| [Q20](../interview/q20-credentials-and-sudo-tool.md) | Credentials through a native macOS dialog; a dedicated tool runs sudo commands with a password saved once | (10-13) [memory.md](memory.md#secrets), [task-execution.md](task-execution.md#sudo), [plugin.md](plugin.md#hooks) |
| [Q21](../interview/q21-auto-update-consent.md) | Updates with no consent and no notice, checked when Barrel runs, like Claude Code | (10-13) [launcher.md](launcher.md#versions) |
| [Q22](../interview/q22-slack-new-requests.md), [Q22-2](../interview/q22-2-launcher-residency.md) | Barrel stays a skill: no resident launcher, no login item, no runs started from Slack | (10-13) [launcher.md](launcher.md#process), [README](README.md#non-goals), [runs.md](runs.md#after) |
| [Q23](../interview/q23-spike-inputs.md) | Spike inputs: only the user and only new channels in the named workspace; new test projects under `~/Desktop/Projects/`; none of the user's ongoing projects | (10-13) [validation.md](validation.md#tasks) |
| [Q24](../interview/q24-memory-update-queue.md) | Memory updated whenever a session ends, through a queue with one writer at a time, in finishing order; work announced at its start; the AI's four additions | (10-13) [memory.md](memory.md#queue), [task-execution.md](task-execution.md#lifecycle), [sessions.md](sessions.md#orchestrator) |

<a id="readiness"></a>
## The 2026-10-12 readiness checks

Every item of [readiness-2026-10-12.md](../readiness-2026-10-12.md) and where it went (10-13).

| Item | Where it is now |
| --- | --- |
| Restored 1: several repos | [runs.md](runs.md#projects), [memory.md](memory.md#repos), [task-tree.md](task-tree.md#files), [task-execution.md](task-execution.md#lanes), [plugin.md](plugin.md#skill), [validation.md](validation.md) items 46–47 and the real tasks |
| Restored 2: wireframes and detailed design | [workflow.md](workflow.md#design), [interviews.md](interviews.md#review), [#stack](interviews.md#stack), [memory.md](memory.md#kinds), [task-execution.md](task-execution.md#review), validation item 64 |
| Restored 3: developers and non-developers | [plugin.md](plugin.md#setup), [interviews.md](interviews.md#plain), [runs.md](runs.md#start-state), [#delivery](runs.md#delivery), validation item 63 |
| Restored 4: preferences and experience across projects | [memory.md](memory.md#shared), validation item 61 |
| Restored 5: the Barrel-managed CLI environment | [sessions.md](sessions.md#barrel-folders), [plugin.md](plugin.md#setup), [#install](plugin.md#install), [launcher.md](launcher.md#reuse), validation item 6 |
| Restored 6: approvals by button | [interviews.md](interviews.md#approvals), [slack.md](slack.md#questions), validation item 27 |
| Restored 7: cancelling a run | [runs.md](runs.md#cancel), [launcher.md](launcher.md#stop), [slack.md](slack.md#commands), validation item 49 |
| Restored 8, replaced by self-update | [launcher.md](launcher.md#versions), [plugin.md](plugin.md#install) |
| Restored 9: no paid usage | [sessions.md](sessions.md#paid), validation item 58 |
| Restored 10: experiments | [workflow.md](workflow.md#experiments), [interviews.md](interviews.md#stack), validation item 65 |
| Restored 11: direct edits | [workflow.md](workflow.md#edits), [memory.md](memory.md#rules), validation item 51 |
| Restored 12: distribution | [plugin.md](plugin.md#layout), [#install](plugin.md#install), [launcher.md](launcher.md#versions) |
| Restored 13: the small ones | D-025 [task-execution.md](task-execution.md#user-only); D-047 [launcher.md](launcher.md#sleep); D-031 [workflow.md](workflow.md#cascade); D-002, D-054 [README](README.md#what-barrel-is); Q-006 [sessions.md](sessions.md#roles); Q-016 [plugin.md](plugin.md#hooks); Q-017 [runs.md](runs.md#delivery); D-003 [workflow.md](workflow.md#stages); D-055 [memory.md](memory.md#run-state); D-044 [interviews.md](interviews.md#replies); D-063 [runs.md](runs.md#after); D-069 [task-execution.md](task-execution.md#user-only) |
| Q18 | [runs.md](runs.md#start), [#delivery](runs.md#delivery), [slack.md](slack.md#routing), [#snapshot](slack.md#snapshot), [launcher.md](launcher.md#scheduling), [#stop](launcher.md#stop), [pc-view.md](pc-view.md#content), validation item 48 |
| Q19 | [workflow.md](workflow.md#new-technology), [interviews.md](interviews.md#stack), [task-execution.md](task-execution.md#packages), validation item 52 |
| Q20 | [memory.md](memory.md#secrets), [task-execution.md](task-execution.md#sudo), [plugin.md](plugin.md#hooks), [#install](plugin.md#install), [launcher.md](launcher.md#commands), [#access](launcher.md#access), validation items 55–59 |
| Q21 | [launcher.md](launcher.md#versions), [#events](launcher.md#events), [plugin.md](plugin.md#skill), validation item 60 |
| Gaps 1–4 | 1 tests from an earlier leaf: [task-tree.md](task-tree.md#tests). 2 who starts a leaf: [task-execution.md](task-execution.md#lifecycle). 3 reading memory: [plugin.md](plugin.md#hooks), [memory.md](memory.md#context). 4 merges and `.barrel/` edits: [memory.md](memory.md#queue) |
| Gaps 5–9 | 5 credentials a leaf creates: [memory.md](memory.md#secrets). 6 stop covers gates and merges: [launcher.md](launcher.md#stop). 7 product secrets: [memory.md](memory.md#secrets). 8 start input and instructions recorded: [interviews.md](interviews.md#recording). 9 questions and the ledger: [interviews.md](interviews.md#ledger), [memory.md](memory.md#run-state) |
| Gaps 10–13 | 10 decisions through merges: [runs.md](runs.md#delivery), [workflow.md](workflow.md#cascade). 11 squash merges and closed PRs: [runs.md](runs.md#waiting). 12 dropping a requirement is asked: [task-execution.md](task-execution.md#failures). 13 parent folders and `git init`: [runs.md](runs.md#find) |
| Gaps 14–18 | 14 the launcher's own requests: [slack.md](slack.md#launcher-requests). 15 from S7 back to S2: [workflow.md](workflow.md#back). 16 option buttons: [interviews.md](interviews.md#posting). 17 visual review: [task-execution.md](task-execution.md#review). 18 subscription logins only: [sessions.md](sessions.md#paid) |
| Fallbacks 1–9 | 1 Codex questions: [task-execution.md](task-execution.md#questions), item 67. 2 interactive logins: [plugin.md](plugin.md#setup), item 6. 3 sandboxed setup: [plugin.md](plugin.md#setup), item 17. 4 hooks that do not load: [plugin.md](plugin.md#trust), item 18. 5 the Codex marketplace: [plugin.md](plugin.md#install), item 16. 6 computer use: [task-execution.md](task-execution.md#user-only), item 68. 7 browser sign-in: [task-execution.md](task-execution.md#user-only), item 20. 8 the Slack app and the Codex Slack MCP: [slack.md](slack.md#setup), items 19 and 26. 9 per-call subagent models: [sessions.md](sessions.md#roles), item 14 |
| Doc errors 1–7 | 1 "whatever its login method": [sessions.md](sessions.md#paid). 2 an abandoned requirement delivered as open: [task-execution.md](task-execution.md#acceptance). 3 and 5 the reasons given for dropping Q-009, D-007 and D-030: [open-decisions.md](open-decisions.md#not-carried) and the [table below](#archived). 4 approval by reply: [interviews.md](interviews.md#approvals). 6 the incomplete not-carried list: the [table below](#archived). 7 `git init` in a parent folder: [runs.md](runs.md#find) |
| Second check | Q22-2: [launcher.md](launcher.md#process), items 1 and 54. D-016: [launcher.md](launcher.md#process), item 62. Q-002: [plugin.md](plugin.md#setup), [runs.md](runs.md#delivery). Q-020: [runs.md](runs.md#archive), item 53. The login fallback of restored 5: [sessions.md](sessions.md#barrel-folders). Image tools: [workflow.md](workflow.md#design). The missing LICENSE file is not a design item |
| Q24 | [memory.md](memory.md#queue), [#finish](memory.md#finish), [task-execution.md](task-execution.md#lifecycle), [#lanes](task-execution.md#lanes), [task-tree.md](task-tree.md#fields), [launcher.md](launcher.md#commands), [#events](launcher.md#events), [#recovery](launcher.md#recovery), [plugin.md](plugin.md#hooks), [sessions.md](sessions.md#orchestrator), items 43–45, H20 |

<a id="draft"></a>
## The 2026-09-29 draft

The draft is archived in [docs/archive/skill-plugin-2026-09-29](../../archive/skill-plugin-2026-09-29/README.md).

| Draft item | Now |
| --- | --- |
| Principle 1: decide first | Kept. Intent first (README principle 1) |
| Principle 2: small tasks | Kept (Q06) |
| Principle 3: a fresh session per task | Kept, and subagents now take short read-only work (Q02) |
| Principle 4: check the plan against the intent before running it | Kept ([task-execution.md](task-execution.md#lifecycle) step 6) |
| Principle 5: code gives the verdicts, and approval records and evidence come from code | Kept (README principle 9). (10-11) The launcher writes answer units. (10-13) Approvals come only from buttons |
| Non-goal "does not keep running until done" | Dropped by Q01 |
| Non-goals "no unattended running, no restart after reboot, no multi-project scheduler" | Dropped: Q01 keeps working, Q11 runs every project from one launcher, and auto-resume follows archived Q-007. (10-13) Q22-2: the resume happens when the skill, Barrel.app or a `barrel` command starts the launcher, never at login |
| Non-goal "no rotating accounts" | Dropped by Q05 and Q12 |
| Non-goal "no Slack, no relay, no dashboard" | Dropped by Q09 and Q10 |
| `workflow.md` S1–S8 and the three tracks | S0–S8 ([workflow.md](workflow.md#stages)); the tracks became impact levels (Q13) |
| `workflow.md` S5: preflight, prompt preview, fail-first for every gate | (10-11) Kept as the S7 preflight and baseline ([task-execution.md](task-execution.md#preflight)); per-leaf fail-first stays |
| `workflow.md` S8 passes only when the Git policy is met | (10-11) Kept: delivery is part of S8's exit ([runs.md](runs.md#delivery)) |
| `workflow.md` approval of a specific revision | (10-11) Kept. (10-13) By button ([interviews.md](interviews.md#approvals)) |
| `clarification.md` ledger | Memory units: `decision` and `answer` (Q07). (10-13) The item ledger is in run state ([interviews.md](interviews.md#ledger)) |
| `clarification.md` five discovery methods | Kept in [interviews.md](interviews.md#discovery) |
| `clarification.md` closure and items found late | Stage exits ([interviews.md](interviews.md#exits)), which include the gap review (10-11); questions from task sessions ([task-execution.md](task-execution.md#questions)); the method that missed a late decision is recorded (10-11) |
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
| `plugin-architecture.md` and `migration.md`: `~/.barrel/memory` for preferences shared across projects | (10-13) Brought back by Q17 as shared memory in `~/.barrel/shared/` ([memory.md](memory.md#shared)). The 2026-10-11 reason for dropping it, Q07, was about project memory |
| `migration.md` spec-handling table, including branch and worktree cleanup | (10-11) Cleanup kept ([runs.md](runs.md#after)); the rest of the table is covered by the archived-plan rows below |
| `migration.md` classification of the archived 81 features | Not carried over. This folder replaces the archived plan's CSVs as the design (AI) |
| `validation.md` | Rewritten ([validation.md](validation.md)). H1 (the skill turns itself on) is dropped, because the skill is invoked explicitly. (10-11) The build order before the spike and the false-denial count in H7 are back |
| `open-decisions.md` OD-1…OD-10 | Statuses in [open-decisions.md](open-decisions.md#od) |
| `research.md` | Refreshed in [research.md](research.md) |

<a id="archived"></a>
## All 93 decisions of the archived app plan

The user's decisions in [docs/archive/app-plan](../../archive/app-plan/README.md) still count wherever they fit the skill ([session-context.md](../session-context.md) §2). Every ID of [decisions.csv](../../archive/app-plan/decisions.csv) appears below. In the "Fit" column:
- **P:** applies as written.
- **A:** assumed the desktop app, adapted to the skill.
- **Part:** applies in part; the rest is in [open-decisions.md](open-decisions.md#not-carried).
- **Replaced:** a later answer replaces it.
- **Not carried:** belongs to the desktop app or was decided otherwise; reasons in [open-decisions.md](open-decisions.md#not-carried).
- **Record:** a record about documents or history, not a product rule.

Decisions that Q17 restored, or that the second readiness check added, are tagged Q17 or "2nd check".

| ID | Decision | Fit | Where it is now |
| --- | --- | --- | --- |
| D-000 | 00-original-flow.md is kept verbatim | Record | This repo's own document rule |
| D-001 | Developers and non-developers are both served | A | [plugin.md](plugin.md#setup), [interviews.md](interviews.md#plain), [runs.md](runs.md#delivery) (Q17) |
| D-002 | macOS first | P | [README](README.md#what-barrel-is) (Q17) |
| D-003 | General software, finished through installation, deployment, tests and real use | P | [workflow.md](workflow.md#stages), [task-execution.md](task-execution.md#acceptance) (Q17) |
| D-004 | One CLI is enough to start | P | [sessions.md](sessions.md#engines), [plugin.md](plugin.md#setup) |
| D-005 | A recommended mix of subscriptions | Not carried | Q16 |
| D-006 | Several projects at once | P | [launcher.md](launcher.md) (Q11) |
| D-007 | Shared memory for every CLI, account and session; preferences shared across projects | A | [memory.md](memory.md) (Q07), [#shared](memory.md#shared) (Q17) |
| D-008 | Successful experience shared, judged again for each situation | A | [memory.md](memory.md#shared) (Q17) |
| D-009 | Shared items can be edited and deleted | A | [memory.md](memory.md#shared) (Q17) |
| D-010 | Three approval bundles | Replaced | The S5 and S6 reviews (Q01, Q06, Q13); its wireframes and design are in [workflow.md](workflow.md#design) (Q17) |
| D-011 | Research per decision topic, reused for follow-ups | P | [interviews.md](interviews.md#before) |
| D-012 | Paid usage only with explicit permission and a monthly budget | A | Off by default; only the user turns it on ([sessions.md](sessions.md#paid)) (Q17) |
| D-013 | The environment, action and cost scope is delegated per project | A | [interviews.md](interviews.md#stack), [task-execution.md](task-execution.md#user-only) |
| D-014 | Slack is optional | Not carried | Q10 |
| D-015 | Role presets whose model and effort the user can change | P | `.barrel/config.json` ([sessions.md](sessions.md#engines)) (Q12) |
| D-016 | Barrel shares the user's everyday Mac | A | [launcher.md](launcher.md#process) (2nd check) |
| D-017 | When a provider's usage runs out, another provider's model takes over | P | [sessions.md](sessions.md#selection), [#accounts](sessions.md#accounts) (Q12) |
| D-018 | A product server relays Slack | Not carried | Desktop app |
| D-019 | Specs as CSV | Not carried | Q07 |
| D-020 | Direct edits are reviewed, and a resolution is asked | A | [workflow.md](workflow.md#edits) (Q17) |
| D-021 | The 2026-09-18 requirements baseline was approved | Record | History |
| D-022 | Quality-first roles and efforts | Part | Max effort for coordination, planning and synthesis ([sessions.md](sessions.md#roles)); the provider picks are replaced by Q16's tiers |
| D-023 | A Slack thread per request, with the project shown | Part | The request name on every message ([slack.md](slack.md#what)) (Q18); the layout follows Q09 |
| D-024 | Automatic completion after verified acceptance; completion includes delivery | P | [task-execution.md](task-execution.md#acceptance), [runs.md](runs.md#delivery) |
| D-025 | Screen control only with an explained scope and an agreed time window | A | [task-execution.md](task-execution.md#user-only) (Q17) |
| D-026 | The review scope is judged from size, complexity and risk, not file count | P | [workflow.md](workflow.md#depth), [#onboarding](workflow.md#onboarding) |
| D-027 | The central console's offline scope | Not carried | Desktop app |
| D-028 | A built-in console and a central console | Not carried | Desktop app |
| D-029 | One Mac runs every project; other devices view through the console | Part | One launcher per PC ([launcher.md](launcher.md)) (Q11); the console is not carried |
| D-030 | Explicit preferences and verified successes accumulate; inferred ones stay candidates; project decisions win | A | [memory.md](memory.md#shared) (Q17) |
| D-031 | A change applies from the next task or stops the affected work now; a default can be set; a resumed or moved task keeps its approvals, permissions and costs | A | [workflow.md](workflow.md#cascade), [task-execution.md](task-execution.md#stop) (Q17) |
| D-032 | Parallel only when reads and writes are disjoint; reference changes before the work that reads them; judged by dependencies, not by project boundaries | P | [task-execution.md](task-execution.md#lanes), with memory units (Q24) and resources across projects |
| D-033 | Strict or estimate budget modes; extra spending off by default | A | [sessions.md](sessions.md#paid) (Q17) |
| D-034 | A pre-assessment of size, complexity, impact and context, at medium effort | Part | [workflow.md](workflow.md#stages) S2 and [#depth](workflow.md#depth), with the survey at medium effort; its model pick is replaced by Q16 |
| D-035 | No product accounts or billing | P | Holds: the skill has no accounts of its own |
| D-036 | Rust/Tauri with React | Not carried | 2026-10-06 request |
| D-037 | Reuse what has general value; keep the existing data; analyze existing repos as maintenance input | A | [launcher.md](launcher.md#reuse), [workflow.md](workflow.md#onboarding) |
| D-038 | The relay keeps undelivered Slack messages for seven days | Not carried | Desktop app; the launcher catches up on the channel instead ([launcher.md](launcher.md#recovery)) |
| D-039 | Maintenance keeps the user's changes; developers choose the start | A | [runs.md](runs.md#start-state) (Q17) |
| D-040 | Re-examine and try alternatives; no fixed retry count | P | [task-execution.md](task-execution.md#failures); lessons recorded (Q24) |
| D-041 | Method changes within the approved scope; ask before changing a mandated method; never route around a refusal or a permission limit | P | [task-execution.md](task-execution.md#failures), [workflow.md](workflow.md#new-technology), [sessions.md](sessions.md#escalation) |
| D-042 | Minimal experiments before approval | A | [workflow.md](workflow.md#experiments) (Q17) |
| D-043 | Only the registered user's Slack account, confirmed from the Mac | A | [slack.md](slack.md#setup), [#security](slack.md#security) |
| D-044 | Slack edits and deletions, before and after acceptance | A | [interviews.md](interviews.md#replies) (Q17) |
| D-045 | Approvals by a button that shows the revision | A | [interviews.md](interviews.md#approvals), [slack.md](slack.md#questions) (Q17) |
| D-046 | Disabling and permanently deleting shared memory | A | [memory.md](memory.md#shared) (Q17) |
| D-047 | The sleep policy, changeable from Slack | A | [launcher.md](launcher.md#sleep), [slack.md](slack.md#commands) (Q17) |
| D-048 | A Barrel-managed CLI environment; personal settings picked from a list; project instructions in the assessment; the loaded configuration recorded | A | [sessions.md](sessions.md#barrel-folders), [plugin.md](plugin.md#setup), [workflow.md](workflow.md#onboarding) (Q17, Q17-2) |
| D-049 | A verified official CLI kept separately | Replaced | Self-update ([launcher.md](launcher.md#versions)) (Q17-2, Q21) |
| D-050 | Monthly accounting of paid credits | A | Applies when the user turns paid usage on ([sessions.md](sessions.md#paid)) (Q17) |
| D-051 | In-house and tester distribution | A | The public repo as the marketplace ([plugin.md](plugin.md#layout)) (Q17, Q17-2) |
| D-052 | Deploying the central service | Not carried | Desktop app |
| D-053 | An EC2 machine for that deployment | Not carried | Desktop app |
| D-054 | Apple Silicon, macOS 15 or later | P | [README](README.md#what-barrel-is) (Q17) |
| D-055 | Backups are left to the OS | P | [memory.md](memory.md#run-state) (Q17) |
| D-056 | Claude through stream-json first; never a silent switch to the API | Part | No silent switch: [sessions.md](sessions.md#paid) (Q17); stream-json is replaced by step2step's interactive sessions |
| D-057 | Remote console access over HTTPS | Not carried | Desktop app |
| D-058 | Updates with consent | Replaced | Q21 ([launcher.md](launcher.md#versions)) |
| D-059 | A privileged helper does administrator work | Replaced | The sudo tool ([task-execution.md](task-execution.md#sudo)) (Q20) |
| D-060 | DMG install with a root helper | Not carried | Desktop app |
| D-061 | Slack DM by default, project channels optional | Not carried | Q09 |
| D-062 | Leftovers of every job are cleaned up | A | [runs.md](runs.md#after) |
| D-063 | Attachment copies are deleted after their last use | A | [runs.md](runs.md#after), [interviews.md](interviews.md#replies) (Q17) |
| D-064 | The Tauri updater | Not carried | Desktop app; Q21 covers updates |
| D-065 | Documents are updated after each answer | P | [interviews.md](interviews.md#recording) |
| D-066 | One plan for the updater | Not carried | Desktop app |
| D-067 | Tier corrections; max effort for high-quality coordination; medium effort for the intent check | Part | Both efforts ([sessions.md](sessions.md#roles)); the provider tiers are replaced by Q16 |
| D-068 | Efficient models for small, clear tasks; an optional routing aid | Part | [sessions.md](sessions.md#difficulty); the optional Jev aid is not carried ([open-decisions.md](open-decisions.md#not-carried)) |
| D-069 | Flexible outside integrations through MCP and delegation | Part | [task-execution.md](task-execution.md#user-only) (Q17); sending Barrel's Slack messages through the MCP is replaced by Q09 and Q10 |
| P-001 | Small tasks, accurate source documents, a plan check before execution | P | [task-tree.md](task-tree.md), [task-execution.md](task-execution.md#lifecycle) |
| P-002 | The wireframe workflow; formats and tools are implementation choices | A | [workflow.md](workflow.md#design) (Q17) |
| Q-001 | The Git delivery scope per project; non-developers merge automatically | A | [runs.md](runs.md#delivery), [#merge](runs.md#merge), [interviews.md](interviews.md#stack) (Q17) |
| Q-002 | Connecting GitHub is recommended and can be skipped | A | [plugin.md](plugin.md#setup), [runs.md](runs.md#delivery) (2nd check) |
| Q-003 | Non-developers' new projects saved to private GitHub repositories, chosen once | A | [plugin.md](plugin.md#setup), [runs.md](runs.md#delivery) |
| Q-004 | Independent review by risk | P | [task-execution.md](task-execution.md#review) |
| Q-005 | Pre-existing failures are asked each time; new or worse failures are fixed | P | [task-execution.md](task-execution.md#pre-existing), compared per failure |
| Q-006 | A CLI's own subagents are left to it | P | [sessions.md](sessions.md#roles) (Q17) |
| Q-007 | Resume after a crash or an OS restart; a user stop stays stopped | A | [launcher.md](launcher.md#process), [#recovery](launcher.md#recovery); never at login (Q22-2) |
| Q-008 | Barrel prepares git and gh; other needed tools are installed after approval; existing ones are reused | A | [plugin.md](plugin.md#setup), [task-execution.md](task-execution.md#user-only), [interviews.md](interviews.md#stack) |
| Q-009 | Cancelling a job offers keep or discard | A | [runs.md](runs.md#cancel) (Q17) |
| Q-010 | Wireframes from the functional spec before the UI design; images in the design | A | [workflow.md](workflow.md#design) (Q17) |
| Q-011 | Wireframes and design inside the existing approvals; API rules after the wireframes | A | [workflow.md](workflow.md#design), [interviews.md](interviews.md#review), [#stack](interviews.md#stack) (Q17) |
| Q-012 | The git author: reuse the existing one, else a project-scoped one | P | [runs.md](runs.md#branches) |
| Q-013 | Planning documents in git with the code; conversations, shared memory and credentials stay out | P | [memory.md](memory.md), [#layout](memory.md#layout) |
| Q-014 | One project, several repos in one parent folder; no monorepo unless asked | A | [runs.md](runs.md#projects) (Q17, Q17-2) |
| Q-015 | A separate planning repo for new projects of several repos; repo-specific documents stay in their repo | A | [runs.md](runs.md#projects), [memory.md](memory.md#kinds) (Q17) |
| Q-016 | After an unexpected compaction, judge by the result | P | [plugin.md](plugin.md#hooks), [launcher.md](launcher.md#events) (Q17) |
| Q-017 | GitHub automation first; other hosts through existing credentials | A | [runs.md](runs.md#delivery) (Q17) |
| Q-018 | Non-developers are asked about git knowledge and policy first | A | [runs.md](runs.md#start-state), [interviews.md](interviews.md#plain) (Q17) |
| Q-019 | Any image service; modern references against AI slop | A | [workflow.md](workflow.md#design), [task-execution.md](task-execution.md#review) (Q17) |
| Q-020 | Archiving a project, or deleting its records | A | [runs.md](runs.md#archive) (2nd check) |
| Q-021 | Deleting a project's records keeps only generalized experience | A | [memory.md](memory.md#shared) (Q17) |

The archived plan's routing table (`model-routing.csv`, with RTE-004 and RTE-005 splitting research by provider) is replaced by Q16.

<a id="code"></a>
## The existing code

[launcher.md](launcher.md#reuse) lists, with line references, what is reused, extended, missing or replaced.

New components, which have no existing code:
- the launcher process, its socket and its access check
- the `barrel` command
- the event log
- the memory queue, and the git work it serializes
- shared memory
- the Slack bot
- the PC view
- the memory tools (index, render) and answer recording
- the task-tree runner, its lanes over several repos, and regression checks
- worktrees, merges and delivery per repo, and pull request states
- engine and account selection, and the Barrel-managed config folders
- the credential dialog, the sudo tool, and package checks
- crash recovery, the sleep policy, and self-update
- the hooks and the playbooks
- the `barrel` skill
