# Validation (spike)

The spike checks, with real CLIs and real models, that this design works end to end on both engines. Q04 requires both CLIs in the pass criteria. The spike does not use mocks or fixtures (09-29 draft).

Work order: Claude Code first, then Codex right after (Q04).

<a id="build"></a>
## What the spike builds first

The checklist below needs a working launcher, so the spike first builds thin versions of the parts in this order (09-29 draft; order AI).

**Before anything new is built**, the existing tests pass:
- the fake-session tests of the unit loop
- the step2step suite ([research.md](research.md#environment))

1. **Launcher core.**
   - the process, the lock, the socket and the access check
   - a per-session environment in both drivers, with Barrel-managed config folders
   - session ownership for Claude and Codex
   - the event log, the stop sequence, and the memory queue
2. **One orchestrator loop.**
   - start, event-driven turns, memory turns, a handoff
   - the context readers
3. **A thin task runner.**
   - one lane over a project of two repos
   - plan capture, the intent check through the orchestrator, gates, the write-set check, commit
   - the finishing turn: merge, memory update, close
4. **A thin Slack bot.**
   - posting with a `markdown` block, buttons, and Socket Mode receive
   - answer units written by the launcher
   - reminders
5. **A thin PC view.** The tree, plus stop and resume.

The rest comes after these pass:
- two lanes, two runs of one project, cancel, regression checks
- the Korean writer, the designer, experiments, onboarding
- shared memory, the credential dialog, the sudo tool
- Barrel.app, recovery, sleep, updates and version checks

A dry run with real gates comes before the real tasks:
- preflight
- the baseline
- fail-first for every gate of a small sample roadmap

<a id="checklist"></a>
## Spike checklist

Items marked §8.n come from [session-context.md](../session-context.md) §8. Q10-confirmed §8 overlaps with them; its items are folded in. The numbers of items 1–42 do not change, because other documents cite them. Items added on 2026-10-13 start at 43. Where a check has a plan B, it is given as "If it fails".

**Launcher and sessions**

1. **The launcher survives on its own.**
   - Started detached, the launcher keeps running after the invoking session ends on macOS.
   - Started from a Codex invoking session, it runs outside that session's sandbox, with network access and writes under `~/.barrel/`.

   If either fails, use the launchd fallback (§8.1, Q11). Then check that the job:
   - is bootstrapped from `~/.barrel/launchd/`
   - does not restart on its own after a crash, and waits like a detached launcher
   - is not listed as a login item
   - does not start after a reboot (Q22-2; [launcher.md](launcher.md#process))
2. step2step's screen calibration still holds at the installed versions, Claude Code 2.1.301 and codex-cli 0.162.1 on 2026-10-16 (§8.2). Run `python -m step2step.claude.calibrate_dialogs <dir> --answer`.
3. A Codex orchestrator starts its successor through `barrel handoff` (§8.3).
4. The launcher injects a Slack reply as a new turn into an orchestrator that has been idle for hours: Claude with `send_prompt`, Codex with a new turn (§8.4). §8.4 named `SessionHandle.send` before it was corrected on 2026-10-08; the real API is `send_prompt` / `wait_turn`.
5. **Hooks in launcher-started sessions** (§8.7).
   - Plugin hooks and skills load in sessions the launcher starts.
   - The role markers reach the hook processes, including for subagent tool calls.
   - step2step's `--settings` hooks run alongside the plugin's.
   - A PreToolUse deny blocks a call in bypass mode (Claude) and with approval `never` (Codex).
   - The SessionStart marker appears in every session, and the PreToolUse marker after the first shell, edit or MCP call. A session missing either is stopped. A hosted tool such as web search does not trigger the check.
   - Claude hooks limit an orchestrator subagent's writes by `agent_id`. Check whether Codex hooks can tell a subagent's calls apart.
   - A hook can ask the launcher whose memory turn it is.
6. **Barrel-managed config folders** (archived D-048; Q17-2).
   - With a Barrel-managed `CLAUDE_CONFIG_DIR` or `CODEX_HOME` per session, the reused login, the plugins and the transcript path all follow that folder (Q05, Q12).
   - Personal settings that the user did not pick do not load. The session records what it loaded.
   - If the login cannot be reused, one sign-in per Barrel folder works.
   - If the invoking agent cannot run an interactive login, the skill shows the command, the user runs it with `!`, and the skill checks again.
7. The plan text of every Claude task session is captured from ExitPlanMode before approval (09-29 H4).
8. Claude `reject_plan(feedback)` works live (never recorded before).
9. The context readers report usage for both engines, and an orchestrator above the threshold hands off at the next safe point.
10. The PreCompact hook blocks automatic compaction in orchestrators on both CLIs.
11. Two projects run on one launcher: Slack events reach the right project by channel, and accounts are shared correctly (Q11).
12. **Fallback** (Q12).
    - An account at its usage limit gives way to the next account. When every account of one CLI is limited, the role moves to the other CLI.
    - A leaf that moves keeps its lane changes.
    - The reset time is parsed, or retried every 30 minutes.
13. A Claude multi-question widget is handled by asking again one question at a time.
14. **Subagents per call.** Subagent roles run with the tier's model and effort on both CLIs: Claude's Agent tool `model` and `effort`, Codex `spawn_agent` ([sessions.md](sessions.md#roles)). If a call cannot set its model, that role runs as a fresh session with the tier's model.
15. **Access check.** The command access check identifies the caller by the socket's peer process. A task session's `barrel task approve` is refused, even after the session changes its environment variables ([launcher.md](launcher.md#access)).

**Plugin**

16. The repo's marketplace serves one plugin folder that carries both manifests and shares the skills and hooks (§8.5). If the Codex marketplace format does not fit, setup installs the skill and the hooks directly into each Codex home.
17. **Finding the plugin folder.** The skill finds its plugin folder and installs the launcher: `${CLAUDE_PLUGIN_ROOT}` in Claude, a path relative to `SKILL.md` in Codex. If setup from a sandboxed Codex session is blocked, the skill asks for an escalation, or tells the user to run `barrel setup` in a terminal.
18. **Codex hook trust.** Launcher-started Codex sessions run Barrel's hooks with the hook-trust bypass in the installed codex-cli, without any review in `/hooks`.
    - If not, check that trust is kept per `CODEX_HOME` and asked again after a hook changes ([plugin.md](plugin.md#trust)).
    - If the hooks still do not load, that account or engine is not used, and setup says so when no engine is left.
19. **Slack app setup** (§8.6; Q09 option X).
    - How much of the app's creation and installation the skill can automate: the manifest, Slack's manifest API, browser automation.
    - The target is that the user only approves the install and enters the tokens.
    - Whether the app installs without a workspace admin. Q23 left this open.
    - Whether the install can tell Barrel the user's Slack ID, so the one-time code is not needed. Slack requires an HTTPS redirect URL, so check whether an HTTPS endpoint on the Mac is practical ([slack.md](slack.md#setup)).

    If creating the app automatically fails, the user creates it from the generated manifest, with guided steps.
20. **Per-session browser automation.** A leaf with `browser: true` gets the Playwright MCP server on both engines through per-session configuration, and the account folders stay untouched ([task-execution.md](task-execution.md#user-only)). If signing in through the automation profile fails, the request gives the user the steps instead, or the credential goes through the dialog.

**Slack**

21. Socket Mode receives button clicks with the confirm dialog, the command words and thread replies, and the sender is checked against the registered user (§8.9).
22. Mentions reach the phone under default settings, including the reminder mentions inside threads (§8.10).
23. After a Slack outage, only one snapshot and the queued questions are sent, and reminder clocks start when each question is actually posted (§8.13).
24. After a launcher restart, posts continue in the same threads and the PC view's address is unchanged (§8.14).
25. The workspace plan: on a free plan each PC's Barrel app counts toward the 10-app limit, and heavy posting may hit `message_limit_exceeded` (§8.17).
26. Codex sessions can read Slack through the official MCP, set up with `codex mcp add` using the Barrel app's client ID and `codex mcp login` ([slack.md](slack.md#setup)). If the OAuth does not work, `barrel slack read` serves them with the bot token, reading only Barrel's channels.
27. **Answers and approvals recorded by the launcher.**
    - Every reply, button press, instruction and start input becomes an answer unit written by the launcher, verbatim and, for a reply, with the question as posted.
    - A message is recorded before it is acknowledged.
    - An edited reply becomes a superseding unit. An edit or a deletion made before the launcher recorded the message follows archived D-044.
    - A review is approved only by its [승인 rN] button. A reply in its thread never approves, and a button on an older revision is refused ([interviews.md](interviews.md#approvals)).
    - Each option of a question has a button, and a reply still counts as an answer.
    - A credential pasted into a reply is masked in the unit and moved to the Keychain.
    - In Korean mode, no English free text from a session reaches Slack or the PC view ([launcher.md](launcher.md#events)).

**Stop, resume and recovery**

28. **Stop.** It halts every Claude and Codex session of every run of the project within 15 seconds.
    - Nothing restarts afterwards.
    - No Codex background process is left, even after a forced stop, which skips step2step's background-terminal cleanup (§8.11; [launcher.md](launcher.md#stop)).
    - Gate processes end, and a merge in progress is aborted.
29. Resume hands interrupted leaves to new sessions on top of the leftover changes, skipping must-fail-first for them (§8.12).
30. **Recovery.** Kill the launcher with `kill -9` during a merge, again during a memory turn, and again during a Slack post. Then, with the launcher down, answer a question and write "재개" in the channel. After the restart:
    - nothing is merged or posted twice
    - the interrupted memory turn is done again, and nothing it half-wrote is committed
    - a leaf whose merge was committed just before the kill gets its memory update before its `task_done`
    - no old process keeps running
    - the answer and the command sent during the downtime are processed

    ([launcher.md](launcher.md#recovery)).

**PC view and the Mac**

31. Measure memory and CPU in the real launcher, including the browser tab, and open the page in Chrome and Safari (§8.15). The page and its live updates load by GET; stop and resume refuse a request without the right `Origin`.
32. Spotlight finds `~/Applications/Barrel.app`, and it runs without warnings on other Macs and macOS versions (§8.16).
33. **Sleep.** With the sleep policy `ac`, a run keeps going overnight on power with the display off. With `os`, macOS sleeps as usual. The Slack words "절전 os|ac|always" change the policy ([launcher.md](launcher.md#sleep)).
34. **CLI updates** (Q17-2, Q21). A Claude Code update under a running launcher is handled:
    - If the calibration check fails, Barrel checks for its own update at once.
    - If no update fixes it, that CLI drops out, and the "calibration failed" notice is posted without a mention ([launcher.md](launcher.md#versions)).

**Execution**

35. **Two lanes.**
    - Two lanes on detached HEADs run leaves in parallel.
    - Merging into the run branch re-runs the gates as a trial merge: a failing merge is aborted and never reaches the run branch.
    - A forced conflict makes the leaf run again with the concurrent change described (Q14).
    - The read-set and resource rules keep a leaf that reads a file another leaf writes out of the same batch (archived D-032).
    - A leaf blocked on a question records what it learned, gives up its lane, and gets its patch back when it runs again ([task-execution.md](task-execution.md#questions)).
36. **Regression.** A later leaf that breaks an earlier leaf's behavior is caught by the medium topic's regression check ([task-execution.md](task-execution.md#regression)).
37. The verification pass catches a false claim planted in a research report (Q16).
38. A small fix stays at local depth: no stack step, one short intent summary (Q13).
39. **Onboarding.**
    - On an existing project, onboarding records the stack, the build and test commands, and the project's own agent instructions as units.
    - A later request that adds no technology gets no stack confirmation ([workflow.md](workflow.md#onboarding)).
40. The Korean writer produces Korean text with Skill-Techblog on both engines (Q16 default; Skill-Techblog v0.5.0). When it fails, the post waits as unsent; English is never sent.
41. Model IDs and efforts in `.barrel/config.json` are validated at run start and whenever the file changes: Codex through `model/list`, Claude through a start check. An unknown ID is dropped with a notice ([sessions.md](sessions.md#selection)).
42. **Long runs and delivery.**
    - A run longer than 24 hours keeps going, with no run-wide clock.
    - At the end, delivery happens in every repo the run changed, as `git.delivery` says, and the integration worktrees are removed so the user can check out the run branches ([runs.md](runs.md#after)).
    - `merge` into the base the user has checked out goes through the remote. Without a remote, a developer is asked to merge, and the run completes once the base contains the run branch; a developer's checkout is never touched. For a non-developer, the launcher merges there itself (item 71) ([runs.md](runs.md#merge), [#waiting](runs.md#waiting)).
    - A pull request merged by squash completes the delivery. A pull request closed without a merge is asked about.
    - The final report, with its completion mention, is posted only when delivery is done.
    - A base that moved with a conflicting change produces a conflict leaf. The leaf resolves the conflict by editing files, and the launcher completes the merge.

**Memory** (Q24)

43. **The memory queue.**
    - Two leaves that finish together update memory one after the other, in the order they finished.
    - The second sees the units the first changed.
    - Each session ends only after its update is committed, and the commit carries the leaf's `done` status.
    - A change to a forbidden kind, such as a requirement unit, is refused by the launcher's check.
    - A stalled turn is lost after `memory.turn_seconds`, and the update is done again.
    - A stop does not wait for a turn.
    - A session killed before its turn has its update written by the next session for that leaf.
44. **Memory units in the parallel rule.** A leaf whose `memory_writes` holds a unit that another leaf reads never runs with it ([task-execution.md](task-execution.md#lanes)).
45. **The orchestrator's memory turns.**
    - Its writes to `.barrel/` outside a turn are denied by the hook.
    - It checks each leaf's update against the contract in its next turn.
    - It consolidates a medium topic's memory at the topic's end.

**Projects and runs**

46. **A project of several repos** (Q17, Q17-2).
    - The project: a planning repo with `repos.json`, and two code repos, all made for the test ([tasks](#tasks)).
    - The launcher clones a missing repo at run start, and a clone that needs a login becomes a Slack request.
    - A leaf that writes two repos is merged in both or in neither.
    - Delivery covers every repo, and a delivery that failed in one repo is not completion.
47. **Finding the project.** Each case of [runs.md](runs.md#find) gives the expected project, including the two special ones:
    - a parent folder of repos with no planning repo, which is asked with the start input
    - a folder that is not a repo
48. **Two runs of one project** (Q18).
    - Two requests run side by side, with their own branches, task trees and orchestrators, and share the lanes in turn.
    - The in-progress list covers both runs, and the memory-unit rule keeps a leaf of one run that changes a unit away from a leaf of the other that reads it.
    - Every message carries its request name.
    - A thread reply reaches its run, and a channel post with two runs active is asked with buttons.
    - Stop and resume cover both runs.
    - The later delivery merges the earlier run's result, and a conflicting decision is asked.
49. **Cancel** (archived Q-009).
    - Cancelling one of two runs leaves the other running.
    - The cancelled run's interrupted leaves are saved as patches before any lane is reset, and the keep-or-discard post lists them.
    - Keep leaves the run branches, which are never merged automatically.
    - Discard deletes the branches and the worktrees.
    - The user's own changes stay untouched either way.
50. **Where a run starts from** (archived D-039, Q-018).
    - A developer whose checkout has uncommitted changes is asked. The changes join the run only if chosen, and the checkout keeps them.
    - A non-developer is asked about their git policy first.
51. **Direct edits** (archived D-020). A commit by the user that edits a requirement unit is found when the run merges its base. The orchestrator explains the conflict and asks before it applies a resolution.
52. **Package checks** (Q19).
    - These are caught before the contract is committed: an invented package name, a GPL-licensed package, and a version with a known vulnerability.
    - A package that a leaf adds without the contract listing it fails the attempt.
    - The final report lists the libraries Barrel chose.
53. **Archive and remove** (archived Q-020, Q-021).
    - An archived project disappears from Barrel.app and the PC view, and comes back when reopened.
    - Removal deletes the run state and the worktrees, and leaves the repos, `.barrel/` and the remotes alone.
    - Shared experience loses that project's specifics.
54. **The launcher exits when idle.** When no project has a running, stopped or waiting run, nor a cancel waiting for keep or discard, the launcher exits. The skill, Barrel.app or a `barrel` command starts it again (Q22-2; AI).

**Secrets and administrator rights** (Q20)

55. **The credential dialog.**
    - A launcher running detached, and one running as a launchd job, opens the native macOS dialog on the Mac, with hidden input.
    - The value lands in the Keychain, and the session gets only its name.
    - `barrel secret run` hands a value to one command, and `barrel secret capture` stores a created key, with neither value appearing in the session's transcript.
    - The Slack tokens at setup go through the same dialog.
56. **The sudo tool.**
    - `barrel-sudo -- <command>` runs without a prompt through `sudo -S`, and a nested sudo works through `SUDO_ASKPASS`.
    - The password never appears in a transcript, a log, an event, a unit or a Slack message.
    - A raw `sudo` in a Barrel session is denied by the hook.
    - `barrel-sudo -- brew install <x>` from a task session is denied.
    - Every command run through the tool is logged.
57. **The sudo tool's Keychain access.**
    - Only the tool can read the password's item; another program triggers macOS's prompt.
    - After an update, re-signed with the local identity, the tool still reads it without a prompt.
    - If not, the "save the sudo password" request appears.
58. **Subscriptions only.** A Claude account that is logged in with an API key is left out at setup, and no session ever uses API billing ([sessions.md](sessions.md#paid)). Paid usage stays off until the user turns it on with a monthly budget; in strict mode, a paid step stops before the budget would be exceeded.
59. **Windows** (later, after macOS). The same `barrel-sudo` command works on Windows through a scheduled task that runs with the highest privileges, or the spike finds another path (Q20).

**Updates, people and the Mac**

60. **Self-update** (Q21). With a newer version on the remote:
    - The skill updates before it starts a run.
    - The launcher updates at a point with no running turn: the plugin in every account folder, the user's and Barrel's, and the launcher itself.
    - Sessions continue from files.
    - Nothing is posted to Slack, not even "restarted".
    - A changed marketplace address is followed.
61. **Shared memory** (archived D-007, D-008, D-030, D-046).
    - An explicit preference stated in one project is used in the next, while an inferred one stays a candidate.
    - A project decision wins over a shared preference.
    - Disable and permanent delete work.
62. **Lower priority** (archived D-016). During two parallel leaves with gates running, the user's foreground apps stay responsive.
63. **A non-developer** (archived D-001, Q-001, Q-018).
    - The profile says non-developer, and questions come in plain words with a recommendation.
    - No delivery scope is asked, and the result is merged automatically.
    - GitHub can be skipped at setup, and it is offered again when a delivery needs a remote.
64. **Design** (archived Q-010, Q-011, Q-019).
    - Wireframes made from the functional spec go into the S5 review, and the detailed design into the S6 confirmation.
    - Images come from an available service on either engine.
    - A visual review catches a screen that misses the approved design.
65. **Experiments** (archived D-042). An experiment runs in its run-state folder, never touches a repo, and its result reaches the S6 confirmation.
66. **The launcher's own requests.** Each fixed template posts in both languages ([slack.md](slack.md#launcher-requests)).
67. **Questions from Codex task sessions.** If `request_user_input` does not work in Codex's default mode, the session's `barrel event --type question` reaches the orchestrator as `task_question`.
68. **Computer use** (archived D-025).
    - Computer use runs only inside a time window the user agreed to.
    - It stops when the user ends the window, or when the launcher sees the user using the Mac.
    - If computer use is unavailable, Playwright is used, and a step that still fails becomes a request.

69. **Refusals** (archived D-041). A session's refusal goes to the orchestrator and is never retried on another model or engine.
70. **Across projects** (archived D-032). Two projects' leaves that need the same port or database never run together, and every running leaf gets its own `BARREL_PORT`.
71. **A non-developer's local merge** (archived Q-001, Q-002). Without a remote or GitHub, the launcher merges into the base in the user's checkout itself, and only when that leaves the user's uncommitted changes untouched.
72. **Approved tools** (archived Q-008; Q19). A tool confirmed in S6 is installed by the launcher from `env.tools`, through `barrel-sudo` when needed, and a task session's own install attempt is denied.
73. **New failures in a failing check** (archived Q-005). A test that starts failing inside a check that already failed at baseline is caught as the run's own failure.
74. **Git and gh at setup** (archived Q-008). On a Mac without `git` or `gh`, setup installs them, and reuses compatible versions when they exist.

§8.8 (`claude --bg`) is dropped: the launcher drives Claude through step2step, and `--bg` is optional (Q04-2).

<a id="tasks"></a>
## Real tasks

The tasks come from the 09-29 draft, with two added from Q17:

1. **New concept with screens (full impact):** a small web product in a new project. It covers the wireframes, the detailed design and the visual review (Q17).
2. **Maintenance (extended):** one change request on an existing repo. This is also the first run on that repo, so it covers onboarding.
3. **Small fix (local):** a request that touches one or two files.
4. **A project of several repos (extended):** a change that spans a frontend repo and a backend repo, with an API change between them (Q17, Q17-2).

**Inputs** ([Q23](../interview/q23-spike-inputs.md)):
- **Projects.** Every test project is new, made by the AI under `~/Desktop/Projects/`:
  - for task 2, a light repo that looks lived-in: code, tests, build and test commands, a few commits
  - for task 4, a parent folder with a planning repo and two code repos
  - for tasks 1 and 3, projects created by running the skill from `~/Desktop/Projects/`
- **Not used:** the user's ongoing projects and existing repos.
- **No GitHub remotes** for the test repos, unless the user agrees first. Creating one publishes something outside the Mac.
- **Slack:** the workspace named in Q23.
  - Only the user takes part. No other member is invited or mentioned.
  - Existing channels are not used: neither posted to nor read, not even through the Slack MCP. Tests use only the private channels Barrel creates.
  - Whether the app installs without an admin is unknown; item 19 finds out. The free plan's app limit is item 25.

How they run:
- Each task runs once with a Claude orchestrator and once with a Codex orchestrator (Q04).
- At least one run forces an account switch and a move to the other CLI (Q12).
- At least one run of task 2 shares its project with a second request (Q18).
- Each request is also done once without Barrel, as a baseline (09-29 draft).

<a id="hypotheses"></a>
## Hypotheses and pass criteria

The thresholds are proposals, to be adjusted before the spike.

| ID | Hypothesis | Measured by | Pass |
| --- | --- | --- | --- |
| H2 | Almost every decision is drawn out before implementation | Decisions first found during S7, and the discovery method that missed each one | Each one recorded, and the checklist fixed for its cause |
| H3 | A fresh session finishes a leaf from its contract alone | Per leaf: done, blocked or gate failure; compactions | No compaction in leaves that meet the size rule |
| H4 | The Claude plan text is captured before approval | Capture rate | 100% |
| H5 | The intent check catches plans that drift | `reject_plan` count and reasons; review of the approved plans | Reasons recorded |
| H6 | No guessing | Task questions answered with a guess | 0 |
| H7 | The guards work, and they do not get in the way | Orchestrator writes outside `.barrel/` that got merged; commits with files outside the write set; writes that the hooks denied wrongly | 0, 0, and every wrong denial explained and fixed |
| H8 | The result matches the intent | The user's rating per task (matches, partly, does not), and whether the AI's acceptance agreed | All four "matches", or each miss is explained by a missed decision |
| H9 | The burden is acceptable | Questions asked, the user's time, wall-clock time, tokens, against the baseline | The user decides whether the increase is acceptable |
| H10 | Orchestrators replace themselves without the user | Handoffs that succeeded | 100% |
| H11 | The Slack loop works | Answers that reached the orchestrator; reminders sent on schedule | 100% |
| H12 | Stop is immediate | Time until every session stopped; anything restarted | Within 15 s; 0 restarted |
| H13 | Fallback needs no manual step | Account and engine switches at limits | All automatic |
| H14 | Depth follows impact | The stages each task went through | Matches [workflow.md](workflow.md#depth) |
| H15 | Research is verified | Planted false claims flagged | 100% |
| H16 | Answers are records, not transcriptions | Answer units compared with the Slack replies and button presses | 100% identical, apart from masked credentials |
| H17 | Recovery repeats nothing | Duplicate merges or posts after a forced kill | 0 |
| H18 | Merges do not break finished work silently | Planted regressions caught before acceptance | 100% |
| H19 | No message from the user is lost | Answers and commands sent while the launcher was down or reconnecting, and processed afterwards | 100% |
| H20 | Memory is current after every session (Q24) | Finished sessions whose memory update was committed before they ended, in finishing order; writes lost or overwritten | 100%; 0 |
| H21 | Runs stay apart (Q18) | Leaves of one run merged into another run's branches other than at delivery; messages with the wrong request name | 0; 0 |
| H22 | Approvals come only from buttons (archived D-045) | Approvals recorded from replies; presses on an older revision that were accepted | 0; 0 |
| H23 | Secrets stay out of sight (Q20) | Credentials or the sudo password found in transcripts, logs, events, units or Slack | 0 |
| H24 | Updates are silent and complete (Q21) | Account folders and the launcher on the same version after an update; Slack posts about the update | 100%; 0 |

No leaf may complete without its gates (09-29 draft).

<a id="after"></a>
## After the spike

- **Pass:** build the full design on top of the thin slices. Follow the order [launcher.md](launcher.md#reuse) implies: the launcher process, the memory queue and session ownership first, then the task runner, then Slack and the PC view.
- **Partial pass:** when one engine or one item fails, the spike has not passed, because Q04 puts both CLIs in the pass criteria ("클로드 코덱스 모두 사용 가능한게 목표야", Q04-2). The failing part is fixed and checked again before the full build.
- **Fail:** record the causes and revisit the launcher design. The decisions in the interview stay as they are.
