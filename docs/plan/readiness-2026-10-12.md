# Readiness check, 2026-10-12

Status: applied. [skill-plugin/](skill-plugin/README.md) was revised with everything below from 2026-10-13 to 2026-10-16, at the user's request; [migration.md](skill-plugin/migration.md#readiness) maps each item to its place. Line numbers of `skill-plugin/` files cited in this file and in the Q17–Q24 records refer to the docs before that revision, at `5c15481`. This file is in English because it is a session-to-session document ([Q08](interview/q08-korean-docs.md)).

## Why this file exists

On 2026-10-12 the user asked two things:
- whether the design in `skill-plugin/` and the interview records are enough to build the skill they intended
- to be asked, one question at a time, about anything still undecided

A similar audit on 2026-10-11 was never written down, so it had to be done again. This file keeps the result until `skill-plugin/` is revised.

What was checked:
- `docs/plan/`: README, session-context, 00-original-flow, insight
- the 16 docs in `skill-plugin/` and the 22 interview records
- the 93 decisions in [docs/archive/app-plan/decisions.csv](../archive/app-plan/decisions.csv), with their verbatim answers in [archive/2026-09-18-follow-up/](../archive/app-plan/archive/2026-09-18-follow-up/README.md)
- the code on main at `6a48c4d`, a commit of the previous repository

## Verdict

- **The structure holds.** Q01–Q16 and flow items 0–12 are all in the design, and the execution base (`step2step`, the unit loop) exists.
- **It was not complete.** Several of the user's decisions from the archived app plan still fit the skill, but they had been dropped without asking. Q17 restored them.
- **Three decisions were new.** Q18–Q20 settled them.
- **Follow-ups.** The user then adjusted three restored groups (Q17-2) and settled how updates are applied (Q21).
- **Nothing else needs the user.** What remains is for the AI: 18 gaps, 9 spike items without a fallback, and 7 doc errors.
- **A second check the same day** ([below](#second)) found two more questions. The user answered both by keeping the current design (Q22, Q22-2), and gave the spike inputs (Q23).

## Decisions made on 2026-10-12

| Q | Decision | Record |
| --- | --- | --- |
| Q17 | Restore all 13 groups of archived decisions that the design had dropped, adapted to the skill | [q17](interview/q17-restore-archived-decisions.md) |
| Q18 | Each new request starts its own run, even while another run of the same project is in progress | [q18](interview/q18-one-run-per-request.md) |
| Q19 | The stack confirmation covers only choices that are hard to reverse | [q19](interview/q19-new-technology-threshold.md) |
| Q20 | Credentials come through a native macOS dialog on the Mac. sudo goes through a dedicated tool that uses a password the user saves once | [q20](interview/q20-credentials-and-sudo-tool.md) |
| Q17-2 | Group 1: the planning repo lists the project's repos, and work starts by cloning them. Group 5 must be in the skill. Group 8: Barrel auto-updates from the remote instead of pinning a CLI. The previous product name appears in no file of the repo | [q17-2](interview/q17-2-repo-list-config-and-updates.md) |
| Q21 | Updates need no consent and no Slack notice. Like Claude Code, Barrel compares its version with the remote's latest when it runs, and updates itself | [q21](interview/q21-auto-update-consent.md) |
| Q22 | Asked whether Slack may start new runs. The user asked back whether the bot can work without the skill, so the question was asked again as Q22-2 | [q22](interview/q22-slack-new-requests.md) |
| Q22-2 | Barrel stays a skill. No login item, no resident launcher, and Slack never starts a run: "that would be a separate app". The current design stands | [q22-2](interview/q22-2-launcher-residency.md) |
| Q23 | Spike inputs: a Slack workspace with only the user and only new channels; new test projects under `~/Desktop/Projects/`; none of the user's ongoing projects | [q23](interview/q23-spike-inputs.md) |
| Q24 | The user's own instruction: memory is updated whenever a session ends, through a queue that lets one writer at a time, and work is announced when it starts. The user then chose the AI's four additions ([below](#q24)) | [q24](interview/q24-memory-update-queue.md) |

<a id="restored"></a>
## Restored archived decisions (Q17)

| # | Decision | Archived source | In the skill design | Docs to change |
| --- | --- | --- | --- | --- |
| 1 | One project can span several repos, from the first version | Q-014, Q-015; Q17-2 | Repos sit side by side under a parent folder. One shared planning repo holds `.barrel/`, with `.barrel/repos.json` listing every repo (name, clone URL, folder, role, default branch). Starting work clones the repos missing from the parent folder, so a teammate or a new PC needs only the planning repo. Adding or removing a repo is confirmed in S5 or S6. No monorepo unless the user asks | runs.md, memory.md, task-tree.md, task-execution.md, launcher.md, plugin.md#skill, validation.md (a multi-repo real task) |
| 2 | Projects with screens: wireframes first, then detailed design | Q-010, Q-011, Q-019, P-002 | Wireframes made from the functional spec go into the S5 intent review. Detailed design goes into the S6 stack confirmation. Images come from any generation service; modern references keep the result from looking like AI slop. Not forced on projects without screens or on small UI fixes | workflow.md, interviews.md#review, interviews.md#stack, memory.md, task-execution.md#review, validation.md |
| 3 | Developers and non-developers | D-001, Q-001, Q-018, D-039 | First-run setup records a user profile. Non-developers are asked first whether they know git and have a git policy; if not, Barrel manages git and merges automatically. Questions are in plain words | plugin.md#setup, interviews.md#format, runs.md#start, runs.md#delivery |
| 4 | Preferences and verified experience shared across projects | D-007, D-030, D-008, D-009, D-046, Q-021 | Kept in `~/.barrel/` on the PC (the AI proposed the location; the user did not object). Explicit preferences accumulate; inferred ones stay candidates. Project decisions win. Each item can be edited or deleted. Project knowledge stays in the repo (Q07) | memory.md, sessions.md, open-decisions.md |
| 5 | A Barrel-managed CLI environment; personal settings imported by choice | D-048; Q17-2 (must be in the skill) | Every account's login is used (Q12), but sessions start from a Barrel-managed config folder per account. Personal instructions, memory, MCP servers, skills and hooks load only if the user picks them from a list at setup. Each session records the configuration and versions it actually loaded. Spike: the login keeps working from the Barrel-managed folder (Claude keeps one Keychain item per config folder; Codex keeps `auth.json`) | sessions.md#accounts, plugin.md#setup, plugin.md#install, launcher.md#reuse, validation.md |
| 6 | Approvals by a revision button | D-045 | S5 and S6 reviews carry an [승인 rN] button. A thread reply is a change request or a question, never an approval | interviews.md#recording, slack.md#questions, validation.md item 27 |
| 7 | Cancelling a run, with keep or discard | Q-009 | A Slack command cancels one run. Its unmerged changes (the run branch) are kept or discarded. The PC view keeps only stop and resume (Q10-2) | launcher.md#commands, launcher.md#stop, slack.md#commands, runs.md#after |
| 8 | ~~A verified official CLI kept separately~~ replaced: Barrel updates itself from the remote | D-049, replaced by Q17-2 and Q21 | CLI updates cannot be stopped, so Barrel keeps itself current instead of pinning a CLI. See Q21 below | launcher.md#versions, plugin.md#install |
| 9 | No paid usage beyond subscriptions without permission | D-012, D-033, D-056 | Off by default. Never a silent switch to API billing. Only subscription logins are used, as step2step already does | sessions.md#accounts |
| 10 | Minimal experiments before approval | D-042 | In S6, in a separate space. The user's repo and live environments stay untouched | workflow.md#stages, interviews.md#stack |
| 11 | Direct edits to the specs | D-020 | Edits the user makes in `.barrel/` are checked for conflicts. A resolution is asked before it is applied | memory.md#rules, workflow.md#cascade |
| 12 | In-house and tester distribution | D-051; D-058's consent replaced by Q21 | The public repo [Agent-Barrel/Skill-Barrel](https://github.com/Agent-Barrel/Skill-Barrel) is the marketplace and ships only the plugin folder. Because it is public, anyone can install Barrel; repo access no longer limits the audience to in-house users and testers. Updates follow Q21: no consent and no notice | plugin.md#layout, plugin.md#install, launcher.md#versions |
| 13 | Small ones | D-025, D-047, D-031, Q-006, Q-016, Q-017, D-002, D-054, D-003, D-055, D-044, D-063, D-069 | Includes agreed time windows for screen control, the sleep policy settable from Slack, a configurable default for cascades, and macOS 15+ on Apple Silicon | task-execution.md#user-only, launcher.md#sleep, workflow.md#cascade, README.md |

**Left out.** These go into the not-carried list of [open-decisions.md](skill-plugin/open-decisions.md#not-carried), each with its reason:
- D-014 (Slack is optional): Q10 moved all interaction to Slack.
- D-019 (specs as CSV): Q07 chose one file per unit.
- D-023 and D-061 (Slack layout): Q09 chose a channel per project and a thread per question.
- D-036 (Rust/Tauri app): the 2026-10-06 request.
- The central server and console (D-018, D-027, D-028, D-038, D-052, D-053, D-057) and the installer and updater (D-060, D-064, D-066): they belong to the desktop app.
- D-059 (a privileged helper process): replaced by the sudo tool from Q20.
- The rest are already covered by Q11, Q12 and Q16.

<a id="changes"></a>
## What Q18–Q21 change

**Q18: a run per request**
- **Replace:** "one active run per project per PC" (runs.md:16) and the skill's instruction path (runs.md:22-24, plugin.md#skill, AI default 35).
- **The skill** always starts a new run. Instructions to an existing run come through Slack.
- **Concurrency:** the runs of a project share its concurrency and lanes. The launcher schedules their leaves fairly.
- **Slack:**
  - Every message carries the request's name. The header `[{project}-질문]` stays, and the name follows it.
  - A channel instruction is routed by its thread. When that is unclear, the launcher asks with buttons.
- **Delivery:** the run delivered later merges the earlier one's result. Conflicting decisions are asked.
- **Stop and cancel:** stop and resume cover every run of the project (Q10-2). Cancel works per run.
- **Status views:** the snapshot, the progress line and the PC view show each run.

**Q19: what counts as new technology**
- **Replace** the definition at workflow.md:80, and align interviews.md#stack with it.
- **Confirmed by the user:**
  - languages and runtimes
  - frameworks
  - databases and storage
  - external services and APIs
  - anything that costs money
  - licenses that restrict use, such as copyleft or commercial ones
  - tools installed on the PC
- **Chosen by the AI:** ordinary libraries within the confirmed stack. Each choice is recorded as a decision unit and listed in the final report.
- **Checked, not asked:** every new package must exist, be maintained, and have an acceptable license and no known vulnerability. A library that brings a restricted license or a cost moves into the confirmed group.
- **Non-developers** get these questions in plain words, with a recommendation.
- **A source correction:** one source quoted in the question could not be verified. The Q19 record says which.

**Q20: credentials and sudo**
- **Credentials:**
  - They come through a native macOS dialog with hidden input, on the Mac. The value goes to the Keychain, and the model gets only its name.
  - They are not taken through Slack. A credential pasted into Slack by mistake is still masked and moved to the Keychain.
  - `barrel secret set` stays as an option for developers.
- **sudo:**
  - A dedicated tool, `barrel-sudo -- <command>` (the name is the AI's). The user saves the password once, through the dialog.
  - The tool runs the command with sudo and supplies the password (`sudo -S`, and `SUDO_ASKPASS` for a nested sudo).
  - The password never leaves the tool. Only the tool may read the Keychain item, so the tool is a compiled binary; Rust is considered first.
  - A hook denies a raw `sudo` in Barrel sessions and points to the tool.
  - Every command is logged in the event log and in the leaf's result report.
  - Installing tools still needs the S6 confirmation (Q19, archived Q-008).
- **Platforms:** the command format is the same on Windows, and the macOS implementation comes first. On Windows elevation goes through UAC, so a saved password needs another path, such as a scheduled task that runs with the highest privileges (spike).
- **Docs to change:** task-execution.md#user-only, memory.md#secrets, plugin.md#hooks, plugin.md#install, plugin.md#setup, launcher.md#commands, launcher.md#access, validation.md.

**Q21: updates from the remote**
- **Replace:** the pinned CLI of restored group 8 (archived D-049) and the consent of restored group 12 (archived D-058).
- **When Barrel checks** (AI, following "when it runs, like Claude Code"):
  - when the skill runs
  - when the launcher starts
  - periodically while the launcher runs
  - right after a CLI update breaks screen calibration
- **What it updates:** the Barrel plugin in every account folder (Claude Code and Codex) and the launcher (`barrel`), together, so their versions never differ.
- **When it applies:** it downloads at once, and swaps at a point with no running turn. After the launcher restarts, sessions continue from files (the resume path).
- **No notice:** nothing goes to Slack. The launcher log and the event log record the update, as an event that is not routed to Slack.
- **Marketplace address:** the repo moved to Agent-Barrel/Skill-Barrel on 2026-10-12, before anything was installed, so installs use that address from the start. If the repo moves again, the update check registers the new address in each account folder.
- **Docs to change:** launcher.md#versions, launcher.md#events, plugin.md#install, plugin.md#setup, validation.md.

**The previous product name (Q17-2)**
- No file on the main line contains it any more. Never write it again. Quotes that contained it show `[이전 이름]`.
- By the user's choice, the `archive/tauri-desktop-app` branch and past commits keep it. Both are in the previous repository only. Archived docs now give paths with the current package name, so paths on that branch can differ.
- Docs name the previous repository's branches instead of linking its URLs.

<a id="gaps"></a>
## Gaps the AI fills

**Execution and sessions**
1. **Who writes the tests the gates run.** Must-fail-first runs before the session starts. So a contract's acceptance tests are written by an earlier leaf, and the implementing leaf may not edit them (archived D-024, P-001). Docs: task-tree.md#size, task-tree.md#fields, task-execution.md#lifecycle.
2. **Who starts a leaf.** The launcher starts ready leaves from its queue. `barrel task start` is only for the orchestrator to force one. Docs: launcher.md#commands, task-execution.md#lifecycle.
3. **Task sessions can read all of memory in their lane.** A hook denies reads of `.barrel/memory/` in task sessions, and the needed units come in the prompt. This is a guard rail. Docs: plugin.md#hooks, memory.md#context.
4. **Trial merges and `.barrel/` edits share the integration worktree.** The git queue commits the orchestrator's `.barrel/` changes before it starts a merge. Docs: task-execution.md#lanes, runs.md#branches.
5. **A credential that a leaf creates, such as an IAM key, has nowhere to go,** because `barrel secret set` is for the user only. Task sessions may store the names listed in their contract's `secrets`. Docs: launcher.md#access, memory.md#secrets.
6. **Stop does not cover gate commands and merges.** The stop sequence also ends gate processes and aborts a merge in progress. Docs: launcher.md#stop.
7. **Product secrets such as `.env` files.** They are written from the Keychain into git-ignored files when a lane is prepared, and a hook blocks committing them. Docs: memory.md#secrets, task-execution.md#lifecycle.

**Records**

8. **The start input and Slack instructions** are recorded verbatim by the launcher, like answers. Docs: interviews.md#recording, memory.md#kinds.
9. **Open questions and the interview item ledger** need a format in run state. Docs: memory.md#run-state, interviews.md#discovery.

**Merges and delivery**

10. **Decisions that arrive through a merge,** from an earlier run, the base or a parallel run (Q18), are checked against the run's own. A conflict is asked. Docs: runs.md#sharing, runs.md#delivery, workflow.md#cascade.
11. **Squash merges and closed pull requests.** A waiting delivery is judged by the pull request's state, not by whether the base contains the run branch. A closed pull request is asked. Docs: runs.md#waiting.
12. **An abandoned requirement is delivered as "open"** (task-execution.md:230), against Q01 and archived D-041. Dropping a requirement is asked. Docs: task-execution.md#acceptance, task-execution.md#failures.
13. **`git init` in a new concept's folder or a non-git folder** (runs.md:28-29) would break a parent folder of repos. The skill detects such a folder first (Q17 #1). Docs: runs.md#start.

**Slack and flow**

14. **Requests the launcher raises itself,** such as "log in again" or "calibration failed", need fixed templates in both languages. Docs: slack.md#questions, launcher.md#versions, sessions.md#accounts.
15. **Going back from S7 to S2.** Pause the affected leaves, rerun the needed stages, and post a new revision if a review is needed. Docs: workflow.md#depth, workflow.md#cascade.
16. **A question with options** also gets a button per option. A thread reply still counts. Docs: slack.md#questions, interviews.md#format.
17. **Visual review of UI work** (Q17 #2). A review subagent compares screenshots with the references. Docs: task-execution.md#review.

**Accounts**

18. **Login method.** sessions.md:179 says every account is used "whatever its login method". But step2step accepts subscription logins only (`step2step/claude/runner.py:72-83`, `step2step/codex/session.py:98-99`). Use subscription logins only (Q17 #9). Docs: sessions.md#accounts.

<a id="fallbacks"></a>
## Spike items that had no fallback

All of these go into [validation.md](skill-plugin/validation.md).

1. **Questions from a Codex task session.** If `request_user_input` does not work in default mode, the playbook has the session emit `barrel event --type question` and end its turn.
2. **Interactive logins during setup.** If the invoking agent cannot run them, the skill shows the command. The user runs it with `!`, and the skill checks again.
3. **Setup from a sandboxed Codex session.** If it is blocked, the skill asks for escalation, or tells the user to run `barrel setup` in a terminal.
4. **Hooks that do not load.** That account or engine is not used. If no engine is left, setup stops and says why.
5. **The Codex marketplace format.** If it does not fit, the skill and hooks are installed directly into each Codex home.
6. **Computer use.** If it is unavailable, Playwright is used. A step that still fails becomes a request to the user.
7. **Signing in through the automation browser profile.** If that fails, the user is sent the steps to do, or the credential is taken through the Q20 dialog.
8. **Slack setup.**
   - Creating the app: if automation fails, the user creates the app from the generated manifest, with guided steps.
   - The Codex Slack MCP's OAuth: if it fails, Codex sessions read Slack through a `barrel` command that uses the launcher's bot token.
9. **Per-call subagent models.** If a call cannot set its model, that role runs as a fresh session.

<a id="errors"></a>
## Doc errors

1. sessions.md:179, "whatever its login method", contradicts step2step's subscription-only code.
2. task-execution.md:230 delivers an abandoned requirement as open, against Q01 and archived D-041.
3. open-decisions.md:84 and migration.md:130 justify dropping Q-009 with Q10-2's option C. That option was about how stop works, not about cancelling.
4. interviews.md:174 approves through a thread reply, against archived D-045.
5. open-decisions.md:83 and migration.md:111 justify dropping D-007 and D-030 with Q07. Q07 asked where project memory lives, not about preferences shared across projects.
6. The not-carried list is incomplete: 63 of the 93 archived decision IDs appear nowhere in `skill-plugin/` (exact ID match, 2026-10-12).
7. runs.md:28-29's `git init` conflicts with Q-014's parent-folder layout.

<a id="second"></a>
## Second check (same day)

After the morning check, the user asked the same two things again. The check was repeated against the same sources, plus a scan of all 93 archived decision IDs against every file in `docs/plan/`.

**Verdict.** Unchanged: the design and the interview records are enough to build the skill. Two questions were asked, and both kept the current design.

**What Q22 and Q22-2 settle**
- Barrel stays a skill. The launcher is not registered as a login item and does not stay resident on its own. The user: if it worked like that, a separate app would be the cleaner design (Q22-2).
- Slack never starts a run. As before, it takes instructions for active runs only, and new requests start from the skill (Q18).
- After a reboot or a launcher crash, the remaining runs resume when the skill, Barrel.app or a `barrel` command starts the launcher again (AI default 1, archived Q-007).
- **Revision:** launcher.md#process says a launchd agent starts the launcher again "at login (`RunAtLoad`)". launchd stays only as the fallback for a detached launcher that does not survive (Q11). It never starts the launcher at login.

**Added without asking (AI)**
1. **Archived decisions that no file in `docs/plan/` mentioned.** They fit the skill, so they go in:
   - **D-016, Barrel runs on the user's everyday Mac.** Sessions and gate commands run at a lower scheduling priority, so the user's own work stays responsive. Docs: launcher.md#process, task-execution.md#lifecycle.
   - **Q-002, connecting GitHub is recommended but can be skipped.** The setup profile step offers `gh auth login` and allows skipping. It is offered again when a delivery needs a remote. Docs: plugin.md#setup, runs.md#delivery.
   - **Q-020, archiving a project, or deleting Barrel's records of it.**
     - Archiving hides the project from Barrel.app and the PC view and keeps its run state.
     - Deleting removes the run state and the worktrees (`barrel project remove`). It never touches the repo, its `.barrel/`, remotes or deployments, and shared experience is generalized as Q-021 says.
     - Both run through the skill or the `barrel` command.

     Docs: runs.md#after, launcher.md#commands, memory.md.
   - **The rest:** D-035 (no product accounts or billing) holds trivially. D-050 (monthly accounting of paid credits) does not apply while paid usage is off (restored decision 9). D-000 and D-021 are records about documents and history.
2. **A fallback for restored decision 5** (spike). If a Barrel-managed config folder cannot reuse the account's existing login, setup signs in each Barrel folder once. The user said decision 5 must be in the skill (Q17-2), so isolation comes first. Docs: sessions.md#accounts, plugin.md#setup, validation.md.
3. **Wireframes and detailed design (restored decision 2).**
   - The format and the tools are implementation choices (archived P-002).
   - Codex's built-in image generation (`$imagegen`, `gpt-image-2`) needs no API key. It counts toward the Codex plan's limits, so images need no paid API use ([docs](https://learn.chatgpt.com/docs/image-generation), checked 2026-10-12).
   - Other services go through browser automation with the user's own sign-ins (archived Q-019).

   Docs: workflow.md#stages, task-execution.md#review.
4. **Not a design item:** the public repo has no LICENSE file.

<a id="q24"></a>
## What Q24 changes

The user stressed that Barrel works as intended only if its memory is brought up to date after every piece of work. In the current design only the orchestrator writes memory units. A leaf's results stay in its result report in run state, and the parallel rule does not look at memory units. Q24 replaces that.

**The queue**
- One memory queue per project, inside the launcher. Every write to `.barrel/` memory units and task files goes through it, one writer at a time: task sessions, auxiliary sessions, the orchestrator, and the launcher when it records answers.
- The launcher is the one process every session already talks to (Q11), so the queue needs no file locks. The existing code has no lock between processes; step2step has only thread locks.

**End of a leaf.** A session that has finished queues up and ends only after its memory update, in finishing order. Its turn runs in this order:
1. Merge the leaf's code into the run branch (Q14: the gates run again on the merged tree).
2. Show the session the latest memory, including the units others changed while it waited.
3. The session writes the memory for its own work: what it built, what it learned, choices it made inside its contract, the units it implemented.
4. The launcher checks the update (format, links, the kinds this session may change) and commits it.
5. Close the session.

Memory updated before the merge would describe code that is not on the run branch if the merge failed. A session that ends without a merge (blocked on a question, abandoned) still records what it learned, such as a failed approach and why (archived D-040).

**Consolidation.** At the end of each medium topic, the orchestrator reviews the units changed in that topic and removes duplicates and contradictions. This is already a handoff and regression-check point.

**Announcing work**
- The contract, committed when the medium topic is split, gains a list of the memory units the leaf may change.
- "In progress" stays in run state (Q15) and is shown to every session together with the memory indexes. A lane is fixed to the commit it started from, so a note committed later would not reach sessions that are already running.

**Parallel rule.** Two leaves never run together if one may change a memory unit that the other reads or may change. This is archived D-032 applied to memory units ("참조 문서 변경을 먼저 끝낸 뒤 이를 읽는 구현을 시작한다"), and it matches the user's words: dependent leaves, and leaves that could drift from the intent, run one at a time.

**Details (AI; the user did not object)**
- A task session writes only what it built and learned. It cannot change what the user wants: intent, requirements, features, the user's decisions, answers. If one of those must change, the orchestrator handles it as a question with its cascade (Q01).
- The orchestrator checks each leaf's memory update against the contract in its next turn.
- The user's stop does not wait for memory updates; it still halts within 15 s. Interrupted leaves update memory when they finish after resume.
- If a session dies before its update, the next session for that leaf writes it from the leftover changes and the result report. Until then the leaf does not count as done.
- A session that stalls during its turn loses the turn after a time limit, and its update is redone.

**Replaces** AI defaults 8 and 22, under which task and auxiliary sessions never wrote `.barrel/`.

**Docs to change:** memory.md#rules, task-execution.md#lifecycle, task-execution.md#lanes, task-tree.md#files, launcher.md#commands, launcher.md#events, launcher.md#recovery, plugin.md#hooks, sessions.md#orchestrator, validation.md.

## Before the spike

Answered in [Q23](interview/q23-spike-inputs.md):
- **Slack:** the workspace named in Q23.
  - Only the user takes part in tests. No other member is invited or mentioned.
  - Existing channels are not used, neither posted to nor read. Tests use only the private channels Barrel creates.
  - Whether the app installs without an admin is unknown. Spike item 19 finds out.
- **Test projects:** all new, all under `~/Desktop/Projects/`, made by the AI:
  - for the maintenance task, a light repo that looks lived-in: code, tests, build and test commands, a few commits
  - for the multi-repo task, a parent folder with a planning repo and two code repos
  - new concepts, created by running the skill from `~/Desktop/Projects/`
- **Not used:** the user's ongoing projects and existing repos.
- **No GitHub remotes** for the test repos unless the user agrees first.
- **Public repo:** the Q23 record held the workspace name and a person's name verbatim. Before its first commit, on 2026-10-13, the user chose to mask both ([Q23](interview/q23-spike-inputs.md#mask)). The real values are kept outside the repo.

## Next step

1. ~~When the user asks, revise `skill-plugin/` with everything above:~~ Done from 2026-10-13 to 2026-10-16:
   - the restored decisions, Q17-2, Q18–Q21, the gaps, the fallbacks, and the doc errors
   - Q22-2 and the additions from the [second check](#second)
   - [Q24](#q24): the memory queue and memory updates at the end of every session
   - open-decisions.md (AI defaults and not-carried) and migration.md, updated to match
2. Then run the spike in [validation.md](skill-plugin/validation.md). Q17 makes it larger:
   - a multi-repo real task
   - a UI task with wireframes
   - the sudo tool
