# Session context for Barrel design work

Updated 2026-10-12 (two readiness checks, Q17–Q24, move to [Agent-Barrel/Skill-Barrel](https://github.com/Agent-Barrel/Skill-Barrel))

This file holds what a fresh Claude Code or Codex session needs, beyond [README.md](README.md), [interview/](interview/README.md) and the canonical design in [skill-plugin/](skill-plugin/README.md), to continue Barrel's work. Before this file existed, most of it lived only in one session's conversation and in that session's CLI memory. CLI memory is per machine and per account, so other sessions can't see it. It is written in English because it is a session-to-session document ([Q08](interview/q08-korean-docs.md)).

If this file and an interview answer disagree, the verbatim interview answer wins.

## 1. Read order

1. [README.md](README.md): the 2026-10-06 request, the conflict table, and a Korean summary of what was decided.
2. [interview/](interview/README.md): the user's answers, verbatim. These are the source of truth for every design decision. [q10-confirmed.md](interview/q10-confirmed.md) gathers Q10 and Q10-2 with per-item sources.
3. This file.
4. [skill-plugin/](skill-plugin/README.md): the canonical design, in English, now 16 docs. Start with its README.
   - It was rewritten on 2026-10-08 from Q01–Q16.
   - It was checked again on 2026-10-11 against the verbatim answers, the original flow, the archived drafts and the code. That pass fixed two contradictions with Q02 and Q05, filled the gaps the flow needs, and added [runs.md](skill-plugin/runs.md).
   - Every statement in it carries a source tag, and the verbatim interview answers win over it.
   - Q17–Q24 (2026-10-12) are not in it yet. Read [readiness-2026-10-12.md](readiness-2026-10-12.md) before relying on it.
5. [00-original-flow.md](00-original-flow.md) and [insight.md](insight.md).
6. [ci-test-redundancy.md](ci-test-redundancy.md) (Korean): when a test or a CI job adds nothing, and how to judge it. Check it before adding tests or CI.

The 2026-09-29 draft is archived in [docs/archive/skill-plugin-2026-09-29](../archive/skill-plugin-2026-09-29/README.md).

## 2. Working with the user

These rules come from the 2026-10-06 session.

- **Language.** Talk to the user in Korean. Documents follow Q08: English is canonical, and Korean text that people read is produced from the English original with the Skill-Techblog skill.
- **Interview protocol.**
  - Ask about one decision topic per question.
  - Before asking, research how similar services and tools solved the same problem (original flow item 5).
  - Each question states why it is asked now, what must be decided, a research summary with sources, and options with one recommendation and its reason.
  - A question may end with defaults that apply unless the user objects. When the user does not object, record that as an AI note, not as the user's answer.
- **Record every answer immediately.** After each answer, before asking the next question, create a new file `interview/qNN-<slug>.md`. It contains:
  - the question as it was asked (context, research, options)
  - the user's answer, verbatim in a text block, typos included
  - a short summary marked "원문이 우선"
  - any AI analysis in its own clearly labeled section

  Add a row to `interview/README.md`. Follow-up answers get their own files (`q03-2`, `q03-3`, `q04-2`). When a later answer supersedes earlier analysis, put a pointer in the older file. Never edit a verbatim answer, except for two masks the user asked for: the previous product name becomes `[이전 이름]` (§6), and the workspace and person names in Q23 become `[워크스페이스 이름]` and `[사용자 이름]` (§5). Don't fold answers into other docs until the user asks.
- **Consolidated record.** When the user asks for the settled result of a topic, write `interview/qNN-confirmed.md`. It gathers the decisions and tags each item with its source: the user's answer, a default the user did not object to, or a detail the AI decided because the user left it to the AI. [q10-confirmed.md](interview/q10-confirmed.md) is the first one.
- **Carry decisions out.** Once the user decides, implement the decision as stated. Don't reopen it or attach caveats. Never put warnings about account switching or terms of service in any doc or code ([Q05](interview/q05-accounts.md)).
  - Don't ask again about something an earlier answer already covers. In Q12 the user objected that moving work to another CLI had already been decided ("그냥 하라고 했잖아").
- **Engines, not providers.** Claude Code and Codex are only engines that run Barrel. Never design roles or research by provider, such as "Claude-side research" and "Codex-side research". Cross-checking means an independent verification step, and model and effort follow the difficulty of the work ([Q16](interview/q16-engines-and-verification.md)). The user reacted sharply when a question assumed a split by provider.
- **Plan mode.** In plan mode only the plan file can be written. Keep answers verbatim in the plan file and write the interview files first thing after approval, as was done for Q11–Q16.
- **Take the user's words literally.** Don't add roles or components the user did not ask for. In Q03-2 the skill-invoking session was turned into a long-lived relay for questions. The user wanted that session only to launch the orchestrator and end, with human questions going to Slack (original flow item 11). See [Q03-3](interview/q03-3-launcher-and-slack.md).
  - **The same goes for questions.** A readiness check asks only about gaps or conflicts in what the user already decided. It never proposes a new capability. In Q22 and Q22-2 the AI asked about starting runs from Slack and about a resident launcher registered as a login item. The user answered that such a design would be a separate app, and that this repo builds a skill ([Q22-2](interview/q22-2-launcher-residency.md)).
- **Archived decisions are the user's.** The user decisions in the archived app plan ([decisions.csv](../archive/app-plan/decisions.csv)) still count wherever they fit the skill. Don't drop one without asking. Q17 restored the ones the 2026-10-08 rewrite had dropped.
- **Map existing code first.** Before proposing a mechanism, map the existing code with file:line references and present the design as reuse or extension of it. On main, that means `step2step/`, `barrel/` and `orchestration/drivers/`. Old code is on the archive branch.
- **No `claude -p`.** Never use `claude -p` for Claude sessions. This repo deliberately drives interactive sessions through `step2step`.
- **Git.** Commit or push only when the user asks.

## 3. Reading the interview records

| Topic | Final answer | Notes |
| --- | --- | --- |
| How far "keep working" goes | [Q01](interview/q01-keep-working-scope.md) | |
| Subagent vs fresh session | [Q02](interview/q02-subagent-vs-session.md) | Q02 assigns roles by the kind of work. Its "other-provider work" wording is superseded by Q16. Option A puts research and independent review on subagents. The 10-08 rewrite had made them fresh sessions; this was fixed on 10-11. |
| Orchestrator launch and restart | [Q03-3](interview/q03-3-launcher-and-slack.md) + [Q04-2](interview/q04-2-orchestrator-on-both-cli.md) | Superseded: the `/clear` handoff in [Q03](interview/q03-orchestrator-restart.md) and the bootloader relay in [Q03-2](interview/q03-2-bootloader-session.md). |
| Target CLIs | [Q04](interview/q04-target-cli.md) + [Q04-2](interview/q04-2-orchestrator-on-both-cli.md) | Orchestrators also run on both CLIs. |
| Subscription accounts | [Q05](interview/q05-accounts.md) + [Q12](interview/q12-model-config-and-cli-fallback.md) | Use every registered account and CLI; move to the next account or CLI. |
| Task tree | [Q06](interview/q06-task-tree.md) | |
| Shared memory | [Q07](interview/q07-shared-memory.md) | |
| Korean documents | [Q08](interview/q08-korean-docs.md) | |
| Slack connection, product name | [Q09](interview/q09-slack-and-dashboard.md) | 9-a (dedicated bot plus the official MCP) stands. Q10 supersedes 9-b (local web dashboard). The product is renamed Barrel. |
| Slack progress reports, stop and resume, PC view, Slack language | [Q10](interview/q10-slack-progress-reports.md) + [Q10-2](interview/q10-2-pc-view-stop-language.md) | Summary with per-item sources: [q10-confirmed.md](interview/q10-confirmed.md). |
| Launcher topology | [Q11](interview/q11-launcher-topology.md) | One launcher per PC. |
| Model assignment | [Q12](interview/q12-model-config-and-cli-fallback.md) + [Q16](interview/q16-engines-and-verification.md) | `.barrel/config.json`, shared by the team; tiers by difficulty, no roles by provider. |
| Depth by request size (OD-4) | [Q13](interview/q13-depth-by-impact.md) | |
| Parallel execution (OD-8) | [Q14](interview/q14-parallel-sessions.md) | Asked before Q13. |
| Task files (OD-5) | [Q15](interview/q15-task-files-in-repo.md) | |
| Cross-checking research (OD-6), Korean text from Codex | [Q16](interview/q16-engines-and-verification.md) | Research plus an independent verification pass; a fresh Korean-writer session on any engine. |
| Archived decisions the design had dropped | [Q17](interview/q17-restore-archived-decisions.md) | All 13 groups restored and adapted to the skill. Among them: multi-repo projects, wireframes, non-developer users, preferences shared across projects, and a Barrel-managed CLI environment. |
| A new request while a run is in progress | [Q18](interview/q18-one-run-per-request.md) | A new run per request. Replaces part of AI default 35. |
| What counts as new technology (Q13) | [Q19](interview/q19-new-technology-threshold.md) | Only choices that are hard to reverse. |
| Credentials and sudo (flow 10) | [Q20](interview/q20-credentials-and-sudo-tool.md) | Credentials through a native macOS dialog; a dedicated sudo tool that uses a password saved once. |
| Follow-ups to the restored decisions | [Q17-2](interview/q17-2-repo-list-config-and-updates.md) | The planning repo lists the project's repos to clone; the Barrel-managed CLI environment must be in the skill; self-update from the remote replaces the pinned CLI. Also: the previous product name appears in no file of the repo. |
| Consent for updates | [Q21](interview/q21-auto-update-consent.md) | None, and no Slack notice. Barrel checks the remote's latest version when it runs, like Claude Code. |
| New runs from Slack; a resident launcher | [Q22-2](interview/q22-2-launcher-residency.md) | Neither. Barrel stays a skill: no login item, and Slack only instructs active runs. [Q22](interview/q22-slack-new-requests.md) was asked again as Q22-2. |
| Spike inputs | [Q23](interview/q23-spike-inputs.md) | Only the user and only new channels in the Slack workspace named there; new test projects under `~/Desktop/Projects/`; none of the user's ongoing projects. Details in [readiness](readiness-2026-10-12.md) "Before the spike". |
| Keeping memory current | [Q24](interview/q24-memory-update-queue.md) | The user's own instruction. One memory queue per project in the launcher. A finished session merges its code, then updates memory and ends, in finishing order. Contracts list the memory units they may change, and "in progress" is shown to every session from run state. Leaves that touch the same memory units never run together. The orchestrator consolidates memory at each medium topic's end. |

The combined picture that used to follow this table is now the canonical design in [skill-plugin/](skill-plugin/README.md).

## 4. The 2026-09-29 draft's open decisions

All of OD-1 to OD-10 are settled. Their status and sources are in [skill-plugin/open-decisions.md](skill-plugin/open-decisions.md#od).

## 5. Questions not asked yet

None.
- Q11–Q16 (2026-10-07 and 2026-10-08) covered the questions this section used to list: launcher topology, model routing, OD-4, OD-6, OD-8, and Korean text from Codex.
- On 2026-10-12 the user asked whether everything needed to build the skill was decided. The check found four decisions for the user, asked as Q17–Q20 (§3). The user's follow-ups became Q17-2 and Q21.
- The user asked again the same day. The second check asked Q22 and Q22-2, and both kept the current design. Q23 collected the spike inputs.
- Then the user gave Q24 unasked: keep memory current after every session, through a queue with one writer at a time. The user chose the AI's four additions.

**Pending revision.** None of the 2026-10-12 results are in `skill-plugin/` yet. [readiness-2026-10-12.md](readiness-2026-10-12.md) lists what the next revision must change:
- the restored decisions, Q17-2 and Q18–Q21
- 18 gaps the AI fills
- fallbacks for 9 spike items
- 7 doc errors
- Q22-2 and the second check's additions: archived D-016, Q-002 and Q-020, and a login fallback for restored decision 5
- Q24: the memory queue, memory updates at the end of every session, and memory units in the parallel rule

**Q23 names:** the Q23 answer named a Slack workspace and a person verbatim. The repository is public, so on 2026-10-13 the user chose to mask both, as `[워크스페이스 이름]` and `[사용자 이름]` ([Q23](interview/q23-spike-inputs.md#mask)). The real values are kept outside the repo, in this Mac's CLI memory. Never write them into a repo file.

The revision happens when the user asks.

The two lists in [skill-plugin/open-decisions.md](skill-plugin/open-decisions.md):
- [AI defaults](skill-plugin/open-decisions.md#ai-defaults): details the AI filled in. Items 1–22 are from 2026-10-08, and the rest from 2026-10-11. They still wait for the user's review. Q18 replaces part of item 35.
- [Not carried](skill-plugin/open-decisions.md#not-carried): Q17 brought back multi-repo projects, preferences shared across projects and cancelling a run. The list is rewritten in the revision.

## 6. Repository facts

- **Repository.** [Agent-Barrel/Skill-Barrel](https://github.com/Agent-Barrel/Skill-Barrel) (public) since 2026-10-12. It started from the previous repository's files without their history, so it has one branch, `main`.
  - Commit hashes in the docs belong to the previous repository.
  - So does the `archive/tauri-desktop-app` branch: the Rust/Tauri app, the React console, the TS relay, the old Python web app (with its interview pipeline) and old run records.
  - The old app's code exists only in the previous repository, on its `archive/tauri-desktop-app` branch. Clones of this repository have neither that branch nor a remote for the previous repository.
- **Contents of main.**
  - `step2step/`
  - `barrel/core/{unitloop,gates,failures,preflight,verify,gitops}.py` with 6 test files in `barrel/tests/`
  - `orchestration/drivers/{unit_loop,run_worker,w0_v3_probe,w1_live_probe}.py`
  - `docs/{plan,archive,substrate,step2step.md,codex-control.md}`
- **Code facts.** The reuse and gap map of `step2step/` and the unit loop, with line references, is in [skill-plugin/launcher.md](skill-plugin/launcher.md#reuse). A summary is in [skill-plugin/research.md](skill-plugin/research.md#code). Corrections to earlier notes:
  - `SessionHandle.send` does not exist; the API is `send_prompt`, `wait_turn` and `run_turn`.
  - Current line numbers: `child_env()` is `step2step/claude/runner.py:153-163`, `Notifier` is `barrel/core/unitloop.py:327-368`, `RunState` is `:373-423`, the stop files are `:464-469`.
- **Name.** The product is Barrel, and the Python package is `barrel/`.
  - The user asked on 2026-10-12 that the previous product name appear in no file of the repo ([Q17-2](interview/q17-2-repo-list-config-and-updates.md)). Never write it, not even in a quote: verbatim answers that contained it show `[이전 이름]` instead.
  - By the user's choice, only the files on the main line were cleaned. The `archive/tauri-desktop-app` branch and past commits, both in the previous repository, still contain the name, so paths on that branch can differ from the paths the archived docs give.
  - Docs name the previous repository's branches and paths instead of linking its URLs.
- **Environment (2026-10-11).**
  - Versions: Claude Code 2.1.296, codex-cli 0.155.1, uv 0.11.19, macOS (Darwin 24.6).
    - Claude Code updates itself; it was 2.1.292 on 2026-10-08.
    - codex-cli 0.162.1 was released on 2026-10-09 but is not installed.
  - Accounts: `~/.claude`, `~/.claude-wook`, `~/.codex`.
  - Python: the system `python3` is 3.9, but the repo needs 3.12 or later. Python 3.13 is at `/opt/anaconda3/bin/python3.13`, and there is no `.venv`.
  - `step2step` screen calibration was last done at Claude Code 2.1.272.
- **Tests.** Run:

  ```bash
  uv run --no-project --python 3.13 --with pytest --with pyte --with ptyprocess --with pyyaml \
    python -m pytest tests barrel/tests -m 'not live' -q
  ```

  Expected result: 506 passed, 2 skipped, 8 deselected.

## 7. Vendor facts

Moved on 2026-10-08 to [skill-plugin/research.md](skill-plugin/research.md#vendors), and updated there:
- Skill-Techblog v0.5.0 supports Codex.
- Codex hooks can block compaction.
- Slack Socket Mode spreads events across connections.
- Facts about the model tiers.

## 8. Spike checklist gathered during the interview

The consolidated checklist, with the items added while writing the canonical design, is [skill-plugin/validation.md](skill-plugin/validation.md#checklist). It cites the numbers below as §8.n.

1. On macOS, the launcher keeps running after the invoking session ends when started detached. If it doesn't, use launchd.
2. `step2step` screen calibration is still valid at the installed versions (Claude Code 2.1.296 and codex-cli 0.155.1 on 2026-10-11; the interview said 2.1.291).
3. A Codex orchestrator can start its successor through the launcher.
4. The launcher can inject a Slack reply as a new turn: `send_prompt` for Claude (corrected 2026-10-08; there is no `SessionHandle.send`), a new app-server turn for Codex.
5. One repo can carry both plugin manifests (`.claude-plugin/`, `.codex-plugin/`) while sharing skills and hooks.
6. Slack bot setup: how much of app creation and workspace install the skill can automate (manifest, browser automation).
7. Barrel's plugin hooks and skills load in sessions the launcher starts, and a role marker (environment variable) reaches the hooks.
8. Only if `claude --bg` is used: whether a background session can start another one, and whether a monitor wakes an idle background session.
9. Socket Mode receives button clicks (with the confirm dialog), channel command words and thread replies, and the launcher checks that the sender is the registered user.
10. Mentions reach the phone under default settings, including mentions inside thread replies (question reminders).
11. Stop halts every Claude and Codex session within 15 s. Nothing respawns afterwards, and no Codex background process is left.
12. Resume hands interrupted leaf tasks to new sessions on top of the leftover changes.
13. After a Slack outage, only one snapshot and the queued questions are sent, and reminder clocks start when each question is actually posted.
14. After a launcher restart, posts continue in the same threads and the PC view URL is unchanged.
15. The PC view is re-measured in the real launcher, including the browser tab, and opens in Chrome and Safari.
16. `~/Applications/Barrel.app` is found by Spotlight and runs without warnings on other Macs and macOS versions.
17. The workspace plan is checked. On a free plan the bot counts toward the 10-app limit, and heavy posting can hit `message_limit_exceeded`.
