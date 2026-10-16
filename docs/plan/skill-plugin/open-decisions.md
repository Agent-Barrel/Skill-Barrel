# Decisions: status and what is left

Updated 2026-10-16, with the decisions of 2026-10-12 (Q17–Q24).

<a id="od"></a>
## OD-1 to OD-10 from the 2026-09-29 draft

All ten are settled. The draft's text is archived in [docs/archive/skill-plugin-2026-09-29/open-decisions.md](../../archive/skill-plugin-2026-09-29/open-decisions.md).

| ID | Topic | Status | Decided by |
| --- | --- | --- | --- |
| OD-1 | What runs the task sessions | A per-PC launcher built on `step2step`. The unit loop's gates, failure handling and ladder are reused and extended ([launcher.md](launcher.md#reuse)) | Q04-2, Q11 |
| OD-2 | The orchestrator's default CLI | There is none. Engines are interchangeable. Each session goes to the least busy usable engine option and account; the order in `.barrel/config.json` only breaks ties ([sessions.md](sessions.md#selection)) | Q04, Q04-2, Q12, Q16; the spreading rule is AI default 20 |
| OD-3 | The existing code | Rust/Tauri, the console, the relay and the old web app are kept on `archive/tauri-desktop-app` in the previous repository and removed from main | 2026-10-06 request |
| OD-4 | Approval scope by request size | The AI sets each stage's depth from the impact. The intent review is never skipped. Only hard-to-reverse choices need the stack confirmation | Q13, Q19 |
| OD-5 | Whether roadmap and contract files are in git | `.barrel/tasks/`, tracked by git; durable status only | Q15 |
| OD-6 | Cross-model research | No split by provider. Research is followed by an independent verification pass | Q16 |
| OD-7 | User surfaces | A Slack bot for reports and all interaction, including cancelling a run, plus a light PC view that can stop and resume | Q09, Q10, Q10-2; archived Q-009, Q17 |
| OD-8 | Parallel execution | Worktree lanes, default 2, only for independent leaves whose reads, writes, shared resources and memory units do not collide | Q14, Q24; archived D-032 |
| OD-9 | What happens when a task is blocked | Only that task waits; unrelated work continues | Q01 |
| OD-10 | Document format | One memory unit per file with indexes, in English; JSON config. The indexes are generated and kept out of git, unlike the units (AI default 8) | Q07, Q08; JSON and the uncommitted indexes are AI (defaults 5 and 8) |

The questions [session-context.md](../session-context.md) listed as not asked yet were all asked on 2026-10-07 and 2026-10-08 (Q11–Q16). The two readiness checks of 2026-10-12 asked Q17–Q23, and the user gave Q24.

<a id="ai-defaults"></a>
## AI defaults to review

The user did not decide these. The AI filled them in to make the design complete.
- Items 1–22 date from 2026-10-08, items 23–40 from the 2026-10-11 review, items 41–59 from the 2026-10-13 revision, and items 60 on from its independent review on 2026-10-16.
- Interview records cite the numbers, so they do not change. An item that a later answer replaced or changed says so.
- Each one can change without touching any interview answer. The ones with the most effect are in bold.

| # | Default | Where |
| --- | --- | --- |
| 1 | **After a crash or a reboot, the launcher resumes the runs that were running; runs the user stopped stay stopped (carried over from archived Q-007).**<br>• Settled by Q22-2: the runs resume when the skill, Barrel.app or a `barrel` command starts the launcher again. Nothing starts it at login.<br>• launchd is only a fallback, and even then it never starts the launcher at login | [launcher.md](launcher.md#process) |
| 2 | **Replaced by Q20.** Credentials used to come through the request's thread or `barrel secret set`. Now they come through a macOS dialog on the Mac and never through Slack; `barrel secret set` stays for developers | [memory.md](memory.md#secrets), [task-execution.md](task-execution.md#user-only) |
| 3 | The orchestrator hands off at 60% of its model's context window. The handoffs at each stage end and each medium topic's end come from Q03-3 and Q03 | [sessions.md](sessions.md#orchestrator) |
| 4 | The default tiers, efforts and model IDs, following the 2026-10-07 model tier doc: Opus 5.5 at max for the orchestrator; `normal` and `hard` leaves on the `strong` tier; the frontier tier for advice and for escalation | [sessions.md](sessions.md#engines), [research.md](research.md#models) |
| 5 | `.barrel/config.json` is JSON | [sessions.md](sessions.md#engines) |
| 6 | Branches and worktrees:<br>• the integration worktrees and the lanes live in run state, and lanes use a detached HEAD<br>• the user's checkout is not touched<br>• the integration worktrees are removed after the run<br>**Changed:** they are now per run and per repo (Q17, Q18). The run starts from HEAD, but developers are asked when the start is unclear, and non-developers with no git policy leave it to Barrel (archived D-039, Q-018) | [runs.md](runs.md#branches), [#start-state](runs.md#start-state) |
| 7 | **Delivery:**<br>• the scope is asked once per project<br>• delivery happens at completion, after re-checking the base; a moved base is merged and kept, and failing gates become leaves<br>• a conflict with the base becomes a conflict leaf<br>• `merge` into a base the user has checked out goes through the remote. Without a remote, a developer is asked to merge, and the run waits<br>• a protected base turns `merge` into a pull request<br>**Changed:**<br>• delivery covers every repo (archived D-024)<br>• non-developers are not asked; Barrel merges, in their own checkout too when there is no remote (archived Q-001, Q-002)<br>• pull requests are automated on GitHub only (archived Q-017)<br>• a waiting delivery is judged by the pull request's state<br>• the later run merges an earlier finished run (Q18) | [runs.md](runs.md#delivery) |
| 8 | Memory:<br>• the kinds, and the `status`, `supersedes`, `sources` and `created` fields (no `status` on answers)<br>• indexes generated by code and not committed<br>• review records kept in `.barrel/reviews/`, with the posted Korean text in its own file<br>• Korean display names in their own file<br>**Replaced in part by Q24:** one writer at a time through the memory queue replaces "one writer per file", and commits happen at the end of each turn of the queue. The kinds `implementation`, `lesson`, `screen` and `api` were added | [memory.md](memory.md#rules), [task-tree.md](task-tree.md#names) |
| 9 | **IDs:**<br>• hash IDs for memory units (`REQ-k3f9`, after Beads)<br>• one task tree per run, with hierarchical IDs (`<run>/T1.2.3`)<br>• run IDs `<yyyymmdd>-<4 base36>`<br>• shared entries `PREF-` and `EXP-` (added 2026-10-13) | [runs.md](runs.md#ids) |
| 10 | Event-driven orchestrator turns; the event catalog; Slack and the PC view show only template text. **Updated:** events for memory turns, direct edits, updates and cancels; every message carries its request name | [sessions.md](sessions.md#orchestrator), [launcher.md](launcher.md#events) |
| 11 | One skill, plus role playbooks as plain files. **Updated:** playbooks for the designer and experiments | [plugin.md](plugin.md#playbooks) |
| 12 | The `barrel` command names and the Unix socket. The access check identifies callers by their peer process; it is a guard rail, not a security boundary. **Updated:** `instruct` is gone (Q18). Commands for memory turns, shared memory, the credential dialog, reading Slack and archiving or removing a project were added | [launcher.md](launcher.md#commands), [#access](launcher.md#access) |
| 13 | The full research is posted in the thread on request. The rendered specs come with the S5 review (Q08's chosen option); at extended depth, only the parts this run changed; at local depth, nothing, because the review is one short summary (Q13). **Updated:** the S5 review also carries the wireframes and the API rules (archived Q-011) | [interviews.md](interviews.md#format), [#review](interviews.md#review) |
| 14 | **Slack setup:**<br>• one Slack app per PC, and a private channel per project, with a suffix if the name is taken<br>• the user's Slack ID comes from the install, whose OAuth redirect lands on this Mac. A one-time code is the fallback (archived D-043)<br>• English command words<br>**Updated:** the words "취소" and "절전", and `barrel slack read` as the Codex fallback for reading | [slack.md](slack.md#setup) |
| 15 | A leaf blocked on a human answer closes its session and gives up its lane. Its changes wait as a patch, and it runs again fresh after the answer. **Changed:** the session first records what it learned, in a memory turn (Q24) | [task-execution.md](task-execution.md#questions) |
| 16 | When the current medium topic is blocked, the next independent medium topic may start | [task-tree.md](task-tree.md#split) |
| 17 | Auxiliary sessions do not count toward the concurrency; session starts are staggered | [task-execution.md](task-execution.md#lanes) |
| 18 | The PC view's [중지] asks for confirmation once; [재개] does not | [pc-view.md](pc-view.md#writes) |
| 19 | How subagent roles run. Q02 option A itself puts research and independent review on subagents. What the AI added:<br>• subagent roles prefer the orchestrator's CLI<br>• subagents write only their reports, into the orchestrator's folder<br>• no handoff while a subagent runs<br>• S8 acceptance uses one review subagent per large topic<br>• advice runs as a subagent too: Q02 had it as a fresh session only for the provider reason that Q16 removed | [sessions.md](sessions.md#roles) |
| 20 | Sessions are spread over every usable engine option and account in a tier, least busy first, across every project and run. The listed order only breaks ties | [sessions.md](sessions.md#selection) |
| 21 | Rules tagged `(09-29 draft)`. They come from the AI-written draft, not from the interview:<br>• the five discovery methods<br>• the contract body<br>• the write-set check and hooks<br>• plan capture<br>• re-running a leaf fresh after an answer<br>• the result report<br>• the build order and the validation hypotheses | [interviews.md](interviews.md#discovery), [task-tree.md](task-tree.md#files), [task-execution.md](task-execution.md), [plugin.md](plugin.md#hooks), [validation.md](validation.md) |
| 22 | Write permissions per role. Every Barrel session is denied ref-changing git commands and the Slack MCP's write tools. Task sessions are also denied system package installs. **Replaced in part by Q24:** task and auxiliary sessions now write memory in their turn. **Extended by Q20:** a raw `sudo` is denied, and installs are denied through `barrel-sudo` too | [plugin.md](plugin.md#hooks) |
| 23 | **Onboarding an existing project: the inferred product intent, the existing stack and commands, and the invariants are recorded before the first assessment.** **Updated:** the project's own agent instructions become units (archived D-048), and the main modules become `implementation` units | [workflow.md](workflow.md#onboarding) |
| 24 | **Answers are written by the launcher, verbatim and with the question as posted. Edited, deleted and late replies and attachments follow fixed rules.** **Changed:**<br>• approvals come only from the revision's button, never from a reply (archived D-045)<br>• start inputs, instructions and button presses are recorded the same way<br>• edits before recording follow archived D-044 | [interviews.md](interviews.md#recording), [#replies](interviews.md#replies) |
| 25 | **`barrel post`: the launcher runs the Korean writer and adds the header, the reply line, the mention and the buttons. If the Korean writer fails, the post waits as unsent; English is never sent while Korean is set** | [interviews.md](interviews.md#posting) |
| 26 | Task-runner settings and `env.setup` in `.barrel/config.json`:<br>• read from the run branch at each session start<br>• the default file written once, by the launcher<br>• which unit-loop keys are not carried<br>• `memory.turn_seconds`, `cascade.default` and `git.github_autosave` (added 2026-10-13) | [sessions.md](sessions.md#engines) |
| 27 | Preflight and a baseline of the existing checks at the start of S7; preflight failures go to the orchestrator | [task-execution.md](task-execution.md#preflight) |
| 28 | **No run-wide clock. The whole run stops only for the user's stop and for the usage-limit stop, which Q01 and Q10 set.** A leaf out of budget climbs the ladder. Every other unit-loop halt becomes a return of that leaf to the orchestrator. A cancel ends one run at the user's request (archived Q-009) | [task-execution.md](task-execution.md#failures), [launcher.md](launcher.md#reuse) |
| 29 | Trial merges, so the run branch never holds a failing leaf merge (a moved base's merge is kept on purpose); regression checks at the end of each medium topic and at S8. A leaf that changed several repos is merged in all of them or in none | [task-execution.md](task-execution.md#lanes), [#regression](task-execution.md#regression) |
| 30 | **The sleep policy defaults to `ac`: prevent idle sleep while on power (the policy options, and changing them from Slack, are archived D-047)** | [launcher.md](launcher.md#sleep) |
| 31 | Crash recovery:<br>• end old processes<br>• abort half-done merges and memory turns<br>• finish or record interrupted merges<br>• dedupe Slack posts by message metadata<br>• catch up on Slack messages missed while down<br>• record a message before acknowledging it<br>• keep waiting cancels and pull requests | [launcher.md](launcher.md#recovery) |
| 32 | **Launcher-started Codex sessions use the hook-trust bypass. With one hook command per event, the SessionStart and PreToolUse markers stop any session whose guards did not run** (a skipped PreCompact hook would go unnoticed). An account or engine whose hooks never load is not used | [plugin.md](plugin.md#trust) |
| 33 | **Replaced by Q21.** The plugin version per account folder, the launcher upgrade when idle, and a calibration check after a CLI update are now part of Barrel's self-update, which needs no consent and posts nothing | [launcher.md](launcher.md#versions) |
| 34 | Browser automation through a per-session Playwright MCP server. **Changed:** computer use only within a time window the user agreed to, ending when the user takes the screen back (archived D-025; how that is noticed is AI); outside services through MCP servers chosen per leaf (archived D-069) | [task-execution.md](task-execution.md#user-only) |
| 35 | **Starting a run. Replaced in part by Q18:** a request always starts its own run, and the skill no longer passes a request to a running or stopped run. What stays:<br>• the skill asks only the start input after setup, plus where `.barrel/` should live for a parent folder of repos without a planning repo<br>• posts when no run is active get a fixed reply, and Slack never starts a run (Q22-2) | [runs.md](runs.md#start), [#after](runs.md#after) |
| 36 | Before a run:<br>• the launcher writes a default `config.json`<br>• a new concept gets a folder and a first commit without a question<br>• a non-git folder is initialized<br>**Changed:**<br>• Q18 replaced the S2 question about including an earlier unmerged run: the later delivery merges it<br>• the folder handling now finds projects of several repos (Q17-2), and a new concept gets a parent folder and a planning repo | [runs.md](runs.md#start), [#projects](runs.md#projects) |
| 37 | Reset times are parsed; when none can be read, the account is tried again every 30 minutes. An expired login is not a usage limit: the user is asked to log in again | [sessions.md](sessions.md#accounts) |
| 38 | No three-hour snapshot while everything waits on the user; the progress line before S7, and its denominator. With several runs, the line covers its own run | [slack.md](slack.md#snapshot), [#notify](slack.md#notify) |
| 39 | The run-state layout, and what is deleted after a run. **Changed:** integration worktrees per run and repo, the queue state, shared memory, the accounts folder and experiment folders | [memory.md](memory.md#run-state), [runs.md](runs.md#after) |
| 40 | **Readings of chosen option texts:**<br>• "POST만 받는다" and the Origin check in Q10-2's option W apply to stop and resume. The page and its live updates load by GET, with the token and Host checked: a page cannot be loaded by POST, and browsers send no Origin on a same-origin GET.<br>• Q13's option says both "전체는 모든 단계를 거친다" and "스택은 새 기술이 들어올 때만 확정받는다". The design applies the second at full depth too.<br>• Q09's "프로젝트마다 채널 하나" holds per PC: each teammate's Barrel has its own Slack app and channel | [pc-view.md](pc-view.md#security), [workflow.md](workflow.md#depth), [runs.md](runs.md#sharing) |
| 41 | **Projects and their folders:**<br>• the parent folder is the planning repo's folder<br>• a new concept gets `<project>/<project>/` as its planning repo, and code repos beside it once S5 or S6 confirms them<br>• for a parent folder of repos with no planning repo, the skill asks where `.barrel/` lives, together with the start input, and recommends a new planning repo<br>• the launcher clones missing repos at run start | [runs.md](runs.md#projects) |
| 42 | **The memory queue's mechanism:**<br>• one queue per project in the launcher, which also does the git work of the integration worktrees<br>• `barrel memory begin` and `end`; task sessions are queued by the launcher when they finish<br>• a session may hold its turn for `memory.turn_seconds`, 600 s, counted from the moment it is shown the memory; the launcher's merge and gates before that do not count<br>• answers reach the orchestrator from run state at once; only their units' commits wait<br>• one in-progress list per project, across its runs<br>• hooks ask the launcher who holds the turn | [memory.md](memory.md#queue) |
| 43 | New memory kinds `implementation`, `lesson`, `screen` and `api`; contract fields `memory_writes`, `packages`, the `review` list and paths that name their repo; tests written by an earlier test leaf | [memory.md](memory.md#kinds), [task-tree.md](task-tree.md#tests) |
| 44 | **Shared memory:**<br>• `~/.barrel/shared/`, written by the launcher one at a time for the PC<br>• inferred preferences stay candidates and are never applied as decisions<br>• experience is promoted at a medium topic's consolidation<br>• when a project's records are removed, a fresh `curator` session applies archived Q-021, and the launcher applies its output | [memory.md](memory.md#shared) |
| 45 | **Barrel-managed config folders:**<br>• `~/.barrel/accounts/<engine>-<account>/`, which reuse the account's login, or sign in once if that fails<br>• the user's own folders get only the Barrel plugin<br>• picked instructions and memory become the user-level instruction files of every Barrel folder on both engines; picked MCP servers and skills go to both engines<br>• Claude accounts are checked for a subscription login | [sessions.md](sessions.md#barrel-folders) |
| 46 | Design: wireframes and the detailed design from `designer` sessions, kept per reviewed revision in `.barrel/design/<run>/r<N>/`; images from any available service; visual review from screenshots. Experiments in `experiment` sessions, in a run-state folder | [workflow.md](workflow.md#design), [#experiments](workflow.md#experiments), [sessions.md](sessions.md#roles) |
| 47 | **Several runs in one project:**<br>• the invoking session names the request in English, and the Korean writer makes its Korean name before the first post<br>• a channel post goes to the run whose thread it is in, or is asked with buttons when unclear<br>• lanes go to the runs' leaves in turn, oldest waiting first; across runs the `resources` and memory-unit rules apply, and file overlaps are settled at delivery | [runs.md](runs.md#start), [slack.md](slack.md#routing), [task-execution.md](task-execution.md#lanes) |
| 48 | Cancel: only in Slack; the interrupted leaves' changes are saved as patches first; keep leaves the run branches and patches and marks the run cancelled; discard deletes them with the worktrees | [runs.md](runs.md#cancel) |
| 49 | **Updates:** checked every time the skill runs, at another `barrel` command (at most every ten minutes), at launcher start, every six hours, and after a calibration failure; swapped when no turn runs; the restart is silent | [launcher.md](launcher.md#versions) |
| 50 | **The sudo tool:** named `barrel-sudo`; shipped prebuilt in the plugin's `tools/`; signed with a local identity made at setup so updates keep its Keychain access; the password asked the first time it is needed | [task-execution.md](task-execution.md#sudo), [plugin.md](plugin.md#install) |
| 51 | **Secrets:** `barrel secret ask` posts the request and opens the dialog; a task session uses a value only through `barrel secret run` and stores one it created through `barrel secret capture`, so it never sees either; the Slack tokens go through the dialog too; product secret files are written into git-ignored files and never committed | [memory.md](memory.md#secrets) |
| 52 | The cascade default as `cascade.default` in `config.json`; the Slack words for the sleep policy; a lower scheduling priority for sessions and gates | [workflow.md](workflow.md#cascade), [launcher.md](launcher.md#sleep), [#process](launcher.md#process) |
| 53 | Direct edits are found as `.barrel/` changes in commits without the `Barrel-Run` trailer | [workflow.md](workflow.md#edits) |
| 54 | **The launcher exits when no project has a running, stopped or waiting run, nor a cancel waiting for keep or discard. The launchd fallback is bootstrapped from `~/.barrel/launchd/`, and launchd never restarts it (Q22-2)** | [launcher.md](launcher.md#process) |
| 55 | Where a run starts from: developers are asked only when the start is unclear; chosen uncommitted changes become the run's first commit | [runs.md](runs.md#start-state) |
| 56 | Package checks: packages listed in the contract, checked against the registry and OSV before the contract is committed, and compared with the manifests after the leaf | [task-execution.md](task-execution.md#packages) |
| 57 | Delivery elsewhere: other hosts get a push plus a request; without GitHub, the connection is offered again and the delivery stays local | [runs.md](runs.md#delivery) |
| 58 | The fixed templates of the requests the launcher raises itself | [slack.md](slack.md#launcher-requests) |
| 59 | The commands `barrel project archive` and `remove` | [runs.md](runs.md#archive) |
| 60 | **A refusal goes to the orchestrator and is never retried on another model or engine** (from archived D-041) | [sessions.md](sessions.md#escalation) |
| 61 | The `resources` rule applies across projects, and each running leaf gets a PC-unique `BARREL_PORT` (from archived D-032) | [task-execution.md](task-execution.md#lanes) |
| 62 | Tools confirmed in S6 are kept in `env.tools` and installed by the launcher, not by a task session (from archived Q-008 and Q19) | [task-execution.md](task-execution.md#user-only), [sessions.md](sessions.md#engines) |
| 63 | Tree depth by position: "medium topic" means a node whose children are leaves; levels in between are `group` | [task-tree.md](task-tree.md#levels) |
| 64 | A PC-wide event log for updates and restarts; the events `sudo_command`, `pr_closed`, `reply_deleted` and `model_dropped` | [launcher.md](launcher.md#events) |
| 65 | **Paid usage:** the switch lives in `~/.barrel/settings.json`, off at setup; turning it on needs the user's word in Slack or at setup, with one monthly budget (the conditions are archived D-012, D-033 and D-050) | [sessions.md](sessions.md#paid) |
| 66 | **Local depth means one short confirmation, so a hard-to-reverse choice, a new screen or a redesigned main screen makes a request at least extended.** At extended depth, S6 researches the affected features | [workflow.md](workflow.md#depth) |
| 67 | The calibration failure is a notice without a mention, because the user has nothing to do | [slack.md](slack.md#launcher-requests) |
| 68 | A duplicate answer-unit ID is fixed by the launcher without asking | [runs.md](runs.md#ids) |
| 69 | The fixed parts of a post depend on its kind: header, reply line, mention and reminders for questions, reviews and requests; the request name and a mention for the final report; nothing for a reply | [interviews.md](interviews.md#posting) |

<a id="not-carried"></a>
## Not carried into this version

These archived user decisions, or parts of them, are not in this design. Each has its reason. Every other archived decision is reflected; [migration.md](migration.md#archived) maps all 93.

| Archived decision | Why it is not in this version |
| --- | --- |
| D-005: the recommended mix of one Codex and one Claude subscription, or more | Q16: engines are interchangeable, and people have different subscriptions. One engine is enough (archived D-004) |
| D-014: Slack is optional; the desktop alone can run everything | Q10 moved all interaction to Slack |
| D-018, D-027, D-028, D-038, D-052, D-053, D-057: the central server, its console, the seven-day relay queue, its deployment on EC2, remote console access | They belong to the desktop app. The skill has no server. What the relay queue did for incoming messages, the launcher does by catching up on the channel's history after downtime ([launcher.md](launcher.md#recovery)); for outgoing posts, Q10's outage rule applies |
| D-019: specs as CSV | Q07 chose one file per unit |
| D-023, in part: a Slack thread per request | Q09 chose a channel per project and a thread per question. The request name on every message (Q18) keeps the request visible |
| D-029, in part: other PCs and phones view and control through the console | The console belongs to the desktop app. One Mac running every project is kept (Q11) |
| D-036: Rust/Tauri modules with a React UI | The 2026-10-06 request |
| D-022, D-034 and D-067, in part: the model picks named by provider (Astra, Fable) | Q16: tiers by difficulty, with no roles by provider. What stays: max effort for coordination, planning and synthesis; medium for the intent check (D-067, P-001) and for the survey behind the impact assessment (D-034) |
| D-068, in part: the optional Jev routing aid | It needs its own API key and budget. Routing follows the difficulty tiers (Q16), and paid usage is off by default ([sessions.md](sessions.md#paid)) |
| D-069, in part: an agent asked to send Slack messages through the Slack MCP | Barrel's own Slack posts go only through the launcher's bot (Q09, Q10 default). Outside integrations of a leaf are kept ([task-execution.md](task-execution.md#user-only)) |
| D-056, in part: the stream-json path for Claude | This repo drives interactive sessions through `step2step` and never uses `claude -p` |
| D-060, D-064, D-066: the DMG installer, the root helper's packaging, and the Tauri updater | They belong to the desktop app. Q21's self-update covers updates |
| D-061: DM by default, project channels optional | Q09 chose a channel per project |
| RTE-004, RTE-005: research roles by provider | Q16 |

**Replaced rather than dropped:**
- D-010, three approval bundles: replaced by the S5 and S6 reviews (Q01, Q06, Q13). Their contents, the wireframes and the detailed design, came back with Q17.
- D-049, a verified CLI kept separately: replaced by self-update (Q17-2, Q21).
- D-058, updates with consent: replaced by Q21.
- D-059, a privileged helper process: replaced by the sudo tool (Q20).

**Records, not product rules:**
- D-000: 00-original-flow.md stays verbatim. This repo keeps that rule for its own documents.
- D-021: a record of the 2026-09-18 baseline approval.

<a id="open"></a>
## Still open

Nothing from the interview is open. The spike ([validation.md](validation.md)) may raise new questions. Those go through the same interview protocol and are recorded as Q25 and later.
