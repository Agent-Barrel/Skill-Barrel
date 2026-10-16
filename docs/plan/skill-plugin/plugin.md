# Plugin, hooks and setup

Barrel ships as one plugin for both Claude Code and Codex (Q04). The design's starting point is the user's own words: the user runs the skill in any session, that session launches the orchestrator, and its role ends (Q03-3). The parts that must run for hours are Python programs, not skill text: the launcher, the task runner, the Slack bot and the PC view. The sudo tool is a small compiled program (Q20).

<a id="layout"></a>
## Repository layout

This repo, the public [Agent-Barrel/Skill-Barrel](https://github.com/Agent-Barrel/Skill-Barrel), is the plugin's marketplace (archived D-051; Q17, Q17-2). Anyone can install Barrel from it, so access to the repo no longer limits who uses it.

It ships only the plugin folder (archived D-051; Q17). Development files, such as `docs/`, the tests and `orchestration/`, stay outside that folder. The folder's name and the paths inside it are AI.

| Path | Contents | Source |
| --- | --- | --- |
| `.claude-plugin/marketplace.json` | Lets `claude plugin marketplace add` use this repo; points to the plugin folder | AI |
| The Codex marketplace manifest | The same for `codex plugin marketplace add`. Whether its format fits is spike item 16 | Q04 |
| `plugin/.claude-plugin/plugin.json` | Claude Code plugin manifest | Q04 |
| `plugin/.codex-plugin/plugin.json` | Codex plugin manifest. Whether one plugin can carry both manifests and share skills and hooks is spike item 16 | Q04 |
| `plugin/skills/barrel/SKILL.md` | The one user-invoked skill; same file for both CLIs | Q03-3 |
| `plugin/skills/barrel/references/` | Setup and start procedures the skill reads on demand | AI |
| `plugin/playbooks/` | Role playbooks for launcher-started sessions (plain markdown) | AI |
| `plugin/hooks/hooks.json` | Hook registrations | 09-29 draft |
| `plugin/hooks/barrel_hook.py` | One hook entry point that branches on the role marker | AI |
| `plugin/barrel/` | Python package: launcher, task runner, Slack bot, PC view, memory tools, the `barrel` CLI | Q03-3, Q04-2, Q10 |
| `plugin/step2step/` | Session drivers for both engines | Q04-2 |
| `plugin/pyproject.toml` | Installs the `barrel` command | AI |
| `plugin/tools/` | Prebuilt `barrel-sudo` binaries, one per platform ([install](#install)) | Q20; AI |

There is no top-level `bin/`, in the repo or in the plugin folder. Claude's Chat and Cowork surfaces refuse to install a plugin that has one ([research.md](research.md#vendors)).

<a id="skill"></a>
## The `barrel` skill

The skill is the only thing the user invokes.

**Invoking it** ([research.md](research.md#vendors)):
- **Claude Code:** `/barrel:barrel <request>`. Plugin skills are namespaced as `plugin:skill`.
- **Codex:** `$barrel <request>`.
- **Either CLI:** by asking for Barrel in plain words.

**Finding its own plugin folder**, to install the launcher (AI):
- **Claude Code:** substitutes `${CLAUDE_PLUGIN_ROOT}` in the skill's body.
- **Codex:** resolves paths relative to the folder of `SKILL.md`.

**What it does.** It runs in the invoking session and does exactly this:
1. **Update.** The first `barrel` command it runs compares Barrel's version with the remote's latest and updates without asking or announcing anything (Q21; [launcher.md](launcher.md#versions)).
2. **First-run setup**, if anything is missing ([below](#setup)).
3. **Find the project** from the folder it runs in ([runs.md](runs.md#find)). For a parent folder of repos with no planning repo, it asks where `.barrel/` should live, together with the start input.
4. **Do what was asked:**
   - **A request:** start a new run (Q18; [runs.md](runs.md#start); [workflow.md](workflow.md#stages) S1).
     - It takes the start input: a product concept, or a project to maintain plus what to change (flow 2). The input comes from the text the skill was invoked with. If that text is missing, the skill asks for it once, in the CLI.
     - It names the request in a few English words.
     - It prepares the folder for a new concept or a folder that is not a repo ([runs.md](runs.md#find)).
     - It calls `barrel run start`, even while other runs of the project are going on. It never passes the request to a running run; that is done in Slack (Q18).
   - **Archiving a project, or removing its records**, when the user asks for that: `barrel project archive` or `barrel project remove` (archived Q-020; [runs.md](runs.md#archive)).
5. **Report and end** (Q03-3): the channel, the request name and the PC view. Nothing else that needs the user is asked here; it goes to Slack (flow 2, Q03-3).

**Keeping it out of everyday sessions** (AI; body length 09-29 draft):
- The description is short and says the skill runs only when the user asks for Barrel. That keeps it from loading by itself in the user's everyday sessions.
- The body stays short; details live in `references/`.

<a id="playbooks"></a>
## Role playbooks

Sessions that the launcher starts get their instructions from a playbook file named in their first prompt. That covers the orchestrator, task sessions, the designer, experiments, the Korean writer, and subagent roles that run as fresh sessions (AI). The orchestrator's subagents get their part of the orchestrator's playbook in the prompt the orchestrator writes for them.

Playbooks are plain files rather than more skills, for two reasons:
- The user's ordinary sessions do not get a longer skill list.
- Neither CLI decides by itself to load a role's rules into the wrong session.

Each playbook states:
- the role's inputs and outputs
- the commands it may use ([launcher.md](launcher.md#commands), [access](launcher.md#access))
- what it records in its memory turn, and what it may not change ([memory.md](memory.md#queue)) (Q24)
- the rules that apply to it, for example:
  - the orchestrator's question rules ([interviews.md](interviews.md))
  - the task session's "do not guess, ask" rule ([task-tree.md](task-tree.md#files))
  - `barrel-sudo` instead of `sudo` ([task-execution.md](task-execution.md#sudo))

<a id="markers"></a>
## Role markers

The launcher starts every session with these environment variables (09-29 draft, AI names):

| Variable | Value |
| --- | --- |
| `BARREL_ROLE` | `orchestrator`, `task`, `designer`, `experiment`, `ko_writer` or `curator`. Also `advice`, `intent_check`, `context`, `research`, `verification` or `review`, when those run as fresh sessions |
| `BARREL_PROJECT` | The project ID |
| `BARREL_RUN` | The run ID |
| `BARREL_TASK`, `BARREL_LANE` | The leaf ID and the lane number, in task sessions only |

**Getting the variables to the hooks:**
- **Both drivers need a per-session parameter.** Each builds the child environment from the launcher's own and takes no per-session values:
  - Claude: `step2step/claude/runner.py:153-163`
  - Codex: `step2step/codex/transport.py:56-62`
- **From there, the docs say the variables reach the hooks** ([research.md](research.md#vendors)). Spike item 5 checks this live.
  - Claude's hook processes inherit the session's environment.
  - Codex's hooks inherit the app-server's environment.
- **Subagents inherit their parent's markers.** Hooks also fire for subagent tool calls, and they apply the subagent rule in the [hooks](#hooks) table, not the orchestrator's own. Claude marks those calls with `agent_id`.
- **No marker, no effect.** Sessions without `BARREL_ROLE` are the user's own, and Barrel's hooks do nothing in them.

**Who holds the memory turn.** Hooks do not trust a variable for this. They ask the launcher, which knows whose turn it is ([memory.md](memory.md#queue)) (AI).

<a id="hooks"></a>
## Hooks

| Event | Role | Behavior | Claude Code | Codex |
| --- | --- | --- | --- | --- |
| SessionStart (startup, resume, compact) | Any Barrel role | Inject the role, the project, the run, the playbook path, where the contract or handoff note is, and the in-progress list (AI; Q24) | `additionalContext` | `hookSpecificOutput.additionalContext` |
| Every Barrel hook event | Any Barrel role | The first time the event fires in a session, write a marker with the plugin version. The launcher checks the markers ([below](#trust)) (AI) | Marker file | Marker file |
| PreToolUse on file writes | Orchestrator | Allow writes only to two places (09-29 draft: the orchestrator does not edit product code; paths AI):<br>• `.barrel/` in its run's integration worktree of the planning repo, while it holds the memory turn (Q24), except the files the launcher writes: `answer/`, the generated indexes, the Korean display names and the posted Korean texts of reviews<br>• the orchestrator's run-state folder | Deny `Write`, `Edit` with a reason | Deny `apply_patch` (matched as `Edit`, `Write`) with a reason |
| PreToolUse on file writes and shell commands | Subagents of the orchestrator | Allow writes only to the orchestrator's run-state folder, for their reports. Deny every `barrel` command, so a subagent cannot approve, post or hand off (AI) | Deny. Calls from a subagent carry `agent_id` | Spike: whether Codex hooks can tell a subagent's calls apart |
| PreToolUse on file writes | Task | Allow writes only inside the leaf's `write_set`. An investigation leaf may also write its report in `outputs/` (09-29 draft). In its memory turn, also the memory units it may write, in the planning repo's integration worktree of its run: new `implementation`, `lesson` and `decision` units, and the units in `memory_writes` (Q24) | Deny | Deny |
| PreToolUse on file reads | Task | Deny reads of `.barrel/memory/` outside the session's memory turn. The units it needs come in its prompt (AI; a guard rail) | Deny `Read`, `Grep`, `Glob` on that path | Deny on that path where Codex's hooks see reads |
| PreToolUse on file writes | Fresh auxiliary sessions | Allow writes only to their own place in run state: their `experiments/<n>/` folder for an experiment, and `outputs/` for every other one: the designer, the Korean writer, the curator, and subagent roles that run as fresh sessions. In their memory turn, also new `lesson` units (AI; Q24) | Deny | Deny |
| PreToolUse on shell commands | Any Barrel role | Deny git commands that move refs or rewrite history (commit, push, reset, rebase, merge, switching branches, deleting branches or tags) and `--no-verify`. The launcher makes every commit and merge (09-29 draft; [runs.md](runs.md#branches)) | Deny `Bash` | Deny `Bash` |
| PreToolUse on shell commands | Any Barrel role | Deny a raw `sudo`, and say to use `barrel-sudo -- <command>` instead. Without a terminal, a raw sudo would wait for a password forever (Q20) | Deny `Bash` | Deny `Bash` |
| PreToolUse on shell commands | Task | Deny system package installs: `brew install`, and global npm or pip installs, whether run directly or through `barrel-sudo`. Approved tools come through `env.setup` (archived Q-008; Q19; AI) | Deny `Bash` | Deny `Bash` |
| PreToolUse on Slack MCP write tools | Any Barrel role | Deny. Only the launcher posts (Q09, Q10 default) | Deny the matching `mcp__` tools | Deny the matching `mcp__` tools |
| PreToolUse on `ExitPlanMode` | Task, Claude only | Save `tool_input.plan` to run state, so the launcher has the plan before approval (09-29 draft) | Records the input | Not needed; app-server returns the plan |
| PreCompact | Orchestrator | Block compaction and ask the launcher for a handoff (AI) | Exit 2 | `continue: false` |
| PreCompact | Task | Allow it, and record `task_compacted` for the size measurement only. Compaction changes nothing in how the leaf is judged: its gates and review decide (archived Q-016) | — | — |

- **One command per event.** `hooks/hooks.json` registers exactly one command for each event, `hooks/barrel_hook.py <event>`. The rows above are branches inside it. So Codex trusts, and the markers report, one hook per event (AI).
- **Hooks are guard rails.** Shell commands can write and read files that the hooks never see, so the final guards are the write-set and package checks before commit, and the launcher's check of every memory update ([task-execution.md](task-execution.md#lifecycle), [memory.md](memory.md#queue)) (09-29 draft; AI).
- **Hooks never keep an agent running against its will.** No Stop hook forces continuation (09-29 draft).
- **Hook sources merge.** step2step injects its own Stop and event hooks through `--settings` (written at `step2step/claude/runner.py:343-360`, passed at `:367-368`). Claude's docs say settings hooks and plugin hooks merge. Spike item 5 checks it.

<a id="trust"></a>
**Hook trust and the marker check** (AI; [research.md](research.md#vendors)):
- **The problem.** Codex skips a non-managed hook until it is trusted in `/hooks`, separately in every `CODEX_HOME`, and again after the hook changes. Hooks that are silently skipped would turn the guards off.
- **The fix.** Launcher-started Codex sessions run with the hook-trust bypass: `--dangerously-bypass-hook-trust`, or the same setting in `thread/start`'s `config`. The user then does not review Barrel's hooks in each Codex home (spike).
- **The safety net, on both engines.** The launcher stops a session when either of these happens. It then repairs the account folder or marks it unusable ([launcher.md](launcher.md#versions)).
  - **No SessionStart marker soon after the session starts.** Its hooks did not run: not loaded, not trusted, or the wrong version.
  - **The session has run a shell command, an edit or an MCP tool, but no PreToolUse marker appeared.**
    - Codex trusts each event's hook separately, so one can be skipped while another runs.
    - Hosted tools such as web search fire no hook, so they do not count here.
- **If the hooks still do not load** after the repair, that account or engine is not used. If no engine is left, setup stops and says why (spike fallback).
- **What the check cannot see.** It covers the two events every session fires: SessionStart and PreToolUse.
  - A skipped PreCompact hook would go unnoticed, because compaction rarely happens.
  - In an orchestrator, that costs a compaction instead of a handoff. It does not turn off a guard.

<a id="install"></a>
## Installing

- **The launcher** is installed once per PC as the `barrel` command, with `uv tool install` from the plugin folder (AI).
  - uv supplies Python 3.12 or later. The system `python3` on this Mac is 3.9 ([research.md](research.md#environment)).
  - Every config folder's copy of the plugin therefore calls the same launcher.
  - Updates replace it together with the plugins ([launcher.md](launcher.md#versions)) (Q21).
- **The sudo tool** (Q20; details AI).
  - The plugin carries prebuilt `barrel-sudo` binaries, one per platform. Setup copies the one for this Mac to `~/.barrel/bin/barrel-sudo`.
  - Setup creates a local code-signing identity on this Mac and signs the tool with it. The Keychain item that holds the password names this signed tool as its only reader, so a later update, signed by the same identity, keeps its access (spike).
  - The password is not asked at setup. It is asked the first time a command needs it ([task-execution.md](task-execution.md#sudo)).
- **The plugin**, in two kinds of account folders (Q05; archived D-048; Q17-2):
  - **The user's own folders** (`~/.claude`, `~/.claude-<name>`, `~/.codex`, …) get only the Barrel plugin, so the skill can be invoked from any of them. Its hooks do nothing in the user's own sessions, which carry no role marker.
  - **The Barrel-managed folders** (`~/.barrel/accounts/<engine>-<account>/`) get the Barrel plugin, Skill-Techblog, the Slack MCP, and the personal settings the user picked ([sessions.md](sessions.md#barrel-folders)).
  - Commands, per folder:
    - Claude: `CLAUDE_CONFIG_DIR=<dir> claude plugin marketplace add Agent-Barrel/Skill-Barrel`, then `claude plugin install barrel@<marketplace>`.
    - Codex: `CODEX_HOME=<dir> codex plugin marketplace add Agent-Barrel/Skill-Barrel`, then `codex plugin add barrel@<marketplace>`.
    - Both commands exist in the installed versions ([research.md](research.md#vendors)).
  - If the Codex marketplace format does not fit, setup installs the skill and the hooks directly into each Codex home (spike fallback).
- **Skill-Techblog**, for Korean text (Q08), in every Barrel-managed folder:
  - Claude: `claude plugin marketplace add KANG-YEONWOOK/Skill-Techblog`, then `claude plugin install techblog@skill-techblog`.
  - Codex: it follows its own v0.5.0 instructions; the skill is invoked as `$techblog` there ([research.md](research.md#vendors)).
- **The official Slack MCP**, for reading (Q09), in every Barrel-managed folder:
  - Claude: the `slack@claude-plugins-official` plugin.
  - Codex: `codex mcp add` with this PC's Barrel Slack app's client ID, then `codex mcp login` (spike). It is set up after the Slack app exists ([setup](#setup)). If its OAuth does not work, Codex sessions read Slack through `barrel slack read` ([slack.md](slack.md#setup)).
- **Browser automation** is not installed into the account folders. The launcher passes the Playwright MCP server to the sessions that need it ([task-execution.md](task-execution.md#user-only)). Setup only checks that `npx` exists (AI).

<a id="setup"></a>
## First-run setup

The skill runs these steps in the invoking session and skips any step that is already done (flow 1, Q05, Q09, Q11, Q12). It reports what it did. These are the only questions the user answers in the CLI, besides the start input.

1. **Python and uv.** Install uv if it is missing, then Python 3.12 or later through uv (AI).
2. **The `barrel` command.** Install it from the plugin folder ([install](#install)). The steps below run through `barrel setup`. Setup works without the launcher: it starts its own short test sessions where it needs them (step 10), and starts the launcher only in its last step (AI).
   - If the invoking session is a sandboxed Codex session and setup is blocked, the skill asks the user to approve an escalation, or tells them to run `barrel setup` in a terminal (spike fallback).
3. **Engines.** Find `claude` and `codex` on PATH. If one is missing, ask the user how to proceed: install it, give its path, or go on with one engine (flow 1; archived D-004). The answer is kept in the settings, so it is not asked again.
4. **User profile** (archived D-001, Q-001; Q17). Ask, in plain words, whether the user is a developer. The answer is kept in `~/.barrel/settings.json`. It decides two things:
   - whether questions use plain words ([interviews.md](interviews.md#plain))
   - whether delivery merges automatically ([runs.md](runs.md#delivery))
5. **Git and GitHub** (archived Q-002, Q-003, Q-008).
   - If `git` or `gh` is missing, setup installs it; a global install is allowed. Compatible versions already on the PC are reused (archived Q-008). Setup says what it installed.
   - Recommend connecting GitHub with `gh auth login`. The user may skip it, and Barrel then works on the Mac alone. It is offered again when a delivery needs a remote.
   - A non-developer who connects chooses once whether Barrel saves each new project to a private GitHub repository automatically. A project can turn that off in its `config.json`.
6. **Accounts** ([sessions.md](sessions.md#accounts)).
   1. List the registered Claude config folders and Codex homes. Check that each is logged in, with `claude auth status` or `codex login status`. Check that each Claude account uses a subscription login; leave out any that does not ([sessions.md](sessions.md#paid)).
   2. Ask once whether the user has other subscriptions to add. For each account name, create `~/.claude-<name>` or `~/.codex-<name>` and run that CLI's login with the folder set (flow 1, Q05).
   3. Every logged-in subscription account is used (Q12).

   An interactive login may need a terminal the invoking agent cannot drive. Then the skill shows the command, the user runs it with `!` in the same CLI, and the skill checks again (spike fallback).
7. **Personal settings** (archived D-048; Q17-2). List what the user's own folders hold: personal instructions, memory, MCP servers, skills and hooks. The user picks what Barrel's sessions should get; nothing is imported without being picked. Then:
   - picked instructions and memory become the user-level instruction files of every Barrel-managed folder, on both engines, so every Barrel session loads them (flow 1)
   - picked MCP servers and skills go into the Barrel-managed folders of both engines, where the engine supports them
   - picked hooks go only to the engine they were written for
8. **Barrel-managed config folders** ([sessions.md](sessions.md#barrel-folders)). Create `~/.barrel/accounts/<engine>-<account>/` for each account, and make it use the account's existing login. If the login cannot be reused, sign in to each Barrel folder once (spike fallback).
9. **Plugins.** Install them as [above](#install).
10. **Codex hooks.** Start a short test session the way the launcher will, and check that Barrel's hooks run with the trust bypass. If they do not, walk the user through `/hooks` in each Codex home ([trust](#trust)).
11. **Slack app**, one for this PC ([slack.md](slack.md#setup)) (Q09, option 9-a X: the skill prepares the app; the user only approves the install and enters the tokens):
    1. The skill writes the manifest ([slack.md](slack.md#manifest)) and creates the app from it. How it creates the app, through the browser or Slack's manifest API, is spike item 19. If that fails, the user creates the app from the manifest, with guided steps (spike fallback).
    2. The user approves the install in the workspace and enters the tokens in the macOS input dialog, not in the CLI: the app token, and the bot token unless the install hands it to Barrel. They go into the Keychain, and no model sees them (Q20; AI).
    3. Barrel learns the user's Slack ID from the install, if the spike shows that works. Otherwise the user types a one-time code into the bot's DM (archived D-043; [slack.md](slack.md#setup)).
12. **Slack MCP for Codex.** `codex mcp add` with the new app's client ID, then `codex mcp login`, in every Codex home of Barrel's ([install](#install)).
13. **The sudo tool.** Install it and sign it ([install](#install)) (Q20).
14. **Barrel.app.** Create `~/Applications/Barrel.app` with `osacompile` ([pc-view.md](pc-view.md#reopen)) (AI, delegated in Q10-2).
15. **Browser automation.** Check that `npx` exists for the Playwright MCP server. If it is missing, a leaf that needs a browser asks for it later (AI).
16. **Settings.** Write `~/.barrel/settings.json`:
    - the engines in use, and the accounts, in order
    - the user profile, and the GitHub auto-save choice of step 5
    - the Slack app and the registered user
    - the language: Korean (Q10)
    - the sleep policy: `ac` (archived D-047; default AI)
    - paid usage: off (archived D-012, D-033; [sessions.md](sessions.md#paid))
17. **Launcher.** Start the launcher detached, or as a bootstrapped launchd job if the spike requires it ([launcher.md](launcher.md#process)) (Q11). It is never registered as a login item (Q22-2).

<a id="budget"></a>
## Context budget

These limits are from the 09-29 draft and must be checked again ([research.md](research.md#vendors)):
- **Skill descriptions:** Claude Code allows about 1,536 characters per skill description in its listing, Codex about 1,024.
- **Hook injections:** Claude Code caps the text a hook injects at 10,000 characters.

So the skill and the playbooks stay short and point to files, and hooks inject paths, not documents (09-29 draft).
