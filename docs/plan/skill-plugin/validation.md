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
   - a per-session environment in both drivers
   - session ownership for Claude and Codex
   - the event log, and the stop sequence
2. **One orchestrator loop.**
   - start, event-driven turns, a handoff
   - the context readers
3. **A thin task runner.**
   - one lane
   - plan capture, the intent check through the orchestrator, gates, the write-set check, commit, merge
4. **A thin Slack bot.**
   - posting with a `markdown` block, and Socket Mode receive
   - answer units written by the launcher
   - reminders
5. **A thin PC view.** The tree, plus stop and resume.

The rest comes after these pass: two lanes, regression checks, the Korean writer, onboarding, Barrel.app, recovery, sleep and version checks.

A dry run with real gates comes before the real tasks:
- preflight
- the baseline
- fail-first for every gate of a small sample roadmap

<a id="checklist"></a>
## Spike checklist

Items marked §8.n come from [session-context.md](../session-context.md) §8. Q10-confirmed §8 overlaps with them; its items are folded in.

**Launcher and sessions**

1. **The launcher survives on its own.**
   - Started detached, the launcher keeps running after the invoking session ends on macOS.
   - Started from a Codex invoking session, it runs outside that session's sandbox, with network access and writes under `~/.barrel/`.

   If either fails, use a launchd user agent (§8.1, Q11). Also check that the launchd agent restarts it after a crash and at login ([launcher.md](launcher.md#process)).
2. step2step's screen calibration still holds at Claude Code 2.1.296 and codex-cli 0.155.1 (§8.2). Run `python -m step2step.claude.calibrate_dialogs <dir> --answer`.
3. A Codex orchestrator starts its successor through `barrel handoff` (§8.3).
4. The launcher injects a Slack reply as a new turn into an orchestrator that has been idle for hours: Claude with `send_prompt`, Codex with a new turn (§8.4). §8.4 named `SessionHandle.send` before it was corrected on 2026-10-08; the real API is `send_prompt` / `wait_turn`.
5. **Hooks in launcher-started sessions** (§8.7).
   - Plugin hooks and skills load in sessions the launcher starts.
   - The role markers reach the hook processes, including for subagent tool calls.
   - step2step's `--settings` hooks run alongside the plugin's.
   - A PreToolUse deny blocks a call in bypass mode (Claude) and with approval `never` (Codex).
   - The SessionStart marker appears in every session, and the PreToolUse marker after the first shell, edit or MCP call. A session missing either is stopped. A hosted tool such as web search does not trigger the check.
   - Claude hooks limit an orchestrator subagent's writes by `agent_id`. Check whether Codex hooks can tell a subagent's calls apart.
6. With `CLAUDE_CONFIG_DIR` set per session, the login, the plugins and the transcript path all follow that folder (Q05, Q12).
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
14. **Subagents per call.** Subagent roles run with the tier's model and effort on both CLIs: Claude's Agent tool `model` and `effort`, Codex `spawn_agent` ([sessions.md](sessions.md#roles)).
15. **Access check.** The command access check identifies the caller by the socket's peer process. A task session's `barrel task approve` is refused, even after the session changes its environment variables ([launcher.md](launcher.md#access)).

**Plugin**

16. One repo carries both manifests and shares the skills and hooks (§8.5).
17. **Finding the plugin folder.** The skill finds its plugin folder and installs the launcher: `${CLAUDE_PLUGIN_ROOT}` in Claude, a path relative to `SKILL.md` in Codex.
18. **Codex hook trust.** Launcher-started Codex sessions run Barrel's hooks with the hook-trust bypass in 0.155.1, without any review in `/hooks`. If not, check that trust is kept per `CODEX_HOME` and asked again after a hook changes ([plugin.md](plugin.md#trust)).
19. **Slack app setup** (§8.6; Q09 option X).
    - How much of the app's creation and installation the skill can automate: the manifest, Slack's manifest API, browser automation.
    - The target is that the user only approves the install and enters the tokens.
    - Whether the install can tell Barrel the user's Slack ID, so the one-time code is not needed. Slack requires an HTTPS redirect URL, so check whether an HTTPS endpoint on the Mac is practical ([slack.md](slack.md#setup)).
20. **Per-session browser automation.** A leaf with `browser: true` gets the Playwright MCP server on both engines through per-session configuration, and the account folders stay untouched ([task-execution.md](task-execution.md#user-only)).

**Slack**

21. Socket Mode receives button clicks with the confirm dialog, the command words and thread replies, and the sender is checked against the registered user (§8.9).
22. Mentions reach the phone under default settings, including the reminder mentions inside threads (§8.10).
23. After a Slack outage, only one snapshot and the queued questions are sent, and reminder clocks start when each question is actually posted (§8.13).
24. After a launcher restart, posts continue in the same threads and the PC view's address is unchanged (§8.14).
25. The workspace plan: on a free plan each PC's Barrel app counts toward the 10-app limit, and heavy posting may hit `message_limit_exceeded` (§8.17).
26. Codex sessions can read Slack through the official MCP, set up with `codex mcp add` using the Barrel app's client ID and `codex mcp login` ([slack.md](slack.md#setup)).
27. **Answers recorded by the launcher.**
    - Every reply becomes an answer unit written by the launcher, verbatim and with the question as posted.
    - The reply is recorded before it is acknowledged.
    - An edited reply becomes a superseding unit.
    - A reply in an old revision's thread does not approve a newer revision ([interviews.md](interviews.md#recording)).
    - A credential given in a reply is masked in the unit and stored in the Keychain.
    - In Korean mode, no English free text from a session reaches Slack or the PC view ([launcher.md](launcher.md#events)).

**Stop, resume and recovery**

28. **Stop.** It halts every Claude and Codex session within 15 seconds.
    - Nothing restarts afterwards.
    - No Codex background process is left, even after a forced stop, which skips step2step's background-terminal cleanup (§8.11; [launcher.md](launcher.md#stop)).
29. Resume hands interrupted leaves to new sessions on top of the leftover changes, skipping must-fail-first for them (§8.12).
30. **Recovery.** Kill the launcher with `kill -9` during a merge, and again during a Slack post. Then, with the launcher down, answer a question and write "재개" in the channel. After the restart:
    - nothing is merged or posted twice
    - no old process keeps running
    - the answer and the command sent during the downtime are processed

    ([launcher.md](launcher.md#recovery)).

**PC view and the Mac**

31. Measure memory and CPU in the real launcher, including the browser tab, and open the page in Chrome and Safari (§8.15). The page and its live updates load by GET; stop and resume refuse a request without the right `Origin`.
32. Spotlight finds `~/Applications/Barrel.app`, and it runs without warnings on other Macs and macOS versions (§8.16).
33. **Sleep.** With the sleep policy `ac`, a run keeps going overnight on power with the display off. With `os`, macOS sleeps as usual ([launcher.md](launcher.md#sleep)).
34. **CLI updates.** A Claude Code update under a running launcher is handled. If the calibration check fails, that CLI drops out and a request is posted ([launcher.md](launcher.md#versions)).

**Execution**

35. **Two lanes.**
    - Two lanes on detached HEADs run leaves in parallel.
    - Merging into the run branch re-runs the gates as a trial merge: a failing merge is aborted and never reaches the run branch.
    - A forced conflict makes the leaf run again with the concurrent change described (Q14).
    - The read-set and resource rules keep a leaf that reads a file another leaf writes out of the same batch (archived D-032).
    - A leaf blocked on a question gives up its lane. Its patch comes back when it runs again ([task-execution.md](task-execution.md#questions)).
36. **Regression.** A later leaf that breaks an earlier leaf's behavior is caught by the medium topic's regression check ([task-execution.md](task-execution.md#regression)).
37. The verification pass catches a false claim planted in a research report (Q16).
38. A small fix stays at local depth: no stack step, one short intent summary (Q13).
39. **Onboarding.**
    - On an existing repo, onboarding records the stack and the build and test commands.
    - A later request that adds no technology gets no stack confirmation ([workflow.md](workflow.md#onboarding)).
40. The Korean writer produces Korean text with Skill-Techblog on both engines (Q16 default; Skill-Techblog v0.5.0). When it fails, the post waits as unsent; English is never sent.
41. Model IDs and efforts in `.barrel/config.json` are validated at run start and whenever the file changes: Codex through `model/list`, Claude through a start check. An unknown ID is dropped with a notice ([sessions.md](sessions.md#selection)).
42. **Long runs and delivery.**
    - A run longer than 24 hours keeps going, with no run-wide clock.
    - At the end, delivery happens as `git.delivery` says, and the integration worktree is removed so the user can check out the run branch ([runs.md](runs.md#after)).
    - `merge` into the base the user has checked out goes through the remote. Without a remote, the user is asked to merge, and the run completes once the base contains the run branch. The user's checkout is never touched ([runs.md](runs.md#merge), [#waiting](runs.md#waiting)).
    - The final report, with its completion mention, is posted only when delivery is done.
    - A base that moved with a conflicting change produces a conflict leaf. The leaf resolves the conflict by editing files, and the launcher completes the merge.

§8.8 (`claude --bg`) is dropped: the launcher drives Claude through step2step, and `--bg` is optional (Q04-2).

<a id="tasks"></a>
## Real tasks

The tasks come from the 09-29 draft:

1. **New concept (full impact):** build one small web feature in a new repo.
2. **Maintenance (extended):** one real change request on an existing repo the user picks. This is also the first run on that repo, so it covers onboarding.
3. **Small fix (local):** a request that touches one or two files.

How they run:
- Each task runs once with a Claude orchestrator and once with a Codex orchestrator (Q04).
- At least one run forces an account switch and a move to the other CLI (Q12).
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
| H8 | The result matches the intent | The user's rating per task (matches, partly, does not), and whether the AI's acceptance agreed | All three "matches", or each miss is explained by a missed decision |
| H9 | The burden is acceptable | Questions asked, the user's time, wall-clock time, tokens, against the baseline | The user decides whether the increase is acceptable |
| H10 | Orchestrators replace themselves without the user | Handoffs that succeeded | 100% |
| H11 | The Slack loop works | Answers that reached the orchestrator; reminders sent on schedule | 100% |
| H12 | Stop is immediate | Time until every session stopped; anything restarted | Within 15 s; 0 restarted |
| H13 | Fallback needs no manual step | Account and engine switches at limits | All automatic |
| H14 | Depth follows impact | The stages each task went through | Matches [workflow.md](workflow.md#depth) |
| H15 | Research is verified | Planted false claims flagged | 100% |
| H16 | Answers are records, not transcriptions | Answer units compared with the Slack replies | 100% identical, apart from masked credentials |
| H17 | Recovery repeats nothing | Duplicate merges or posts after a forced kill | 0 |
| H18 | Merges do not break finished work silently | Planted regressions caught before acceptance | 100% |
| H19 | No message from the user is lost | Answers and commands sent while the launcher was down or reconnecting, and processed afterwards | 100% |

No leaf may complete without its gates (09-29 draft).

<a id="after"></a>
## After the spike

- **Pass:** build the full design on top of the thin slices. Follow the order [launcher.md](launcher.md#reuse) implies: the launcher process and session ownership first, then the task runner, then Slack and the PC view.
- **Partial pass:** decide with the user what to ship first. Example: if only the Codex orchestrator fails, Claude orchestrators could run while it is fixed.
- **Fail:** record the causes and revisit the launcher design. The decisions in the interview stay as they are.
