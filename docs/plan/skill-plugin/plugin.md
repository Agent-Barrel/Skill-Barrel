# Plugin, hooks and setup

Barrel ships as one plugin for both Claude Code and Codex (Q04). The design's starting point is the user's own words: the user runs the skill in any session, that session launches the orchestrator, and its role ends (Q03-3). The parts that must run for hours are Python programs, not skill text: the launcher, the task runner, the Slack bot and the PC view.

<a id="layout"></a>
## Repository layout

This repo becomes the plugin, and also its marketplace (AI). Top level:

| Path | Contents | Source |
| --- | --- | --- |
| `.claude-plugin/plugin.json` | Claude Code plugin manifest | Q04 |
| `.claude-plugin/marketplace.json` | Lets `claude plugin marketplace add` use this repo | AI |
| `.codex-plugin/plugin.json` | Codex plugin manifest. Whether one repo can carry both manifests and share skills and hooks is spike item 16 | Q04 |
| `skills/barrel/SKILL.md` | The one user-invoked skill; same file for both CLIs | Q03-3 |
| `skills/barrel/references/` | Setup and start procedures the skill reads on demand | AI |
| `playbooks/` | Role playbooks for launcher-started sessions (plain markdown) | AI |
| `hooks/hooks.json` | Hook registrations | 09-29 draft |
| `hooks/barrel_hook.py` | One hook entry point that branches on the role marker | AI |
| `barrel/` | Python package: launcher, task runner, Slack bot, PC view, memory tools, the `barrel` CLI | Q03-3, Q04-2, Q10 |
| `step2step/` | Session drivers for both engines | Q04-2 |
| `pyproject.toml` | Installs the `barrel` command | AI |

There is no top-level `bin/`. Claude's Chat and Cowork surfaces refuse to install a plugin that has one ([research.md](research.md#vendors)).

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
1. **First-run setup**, if anything is missing ([below](#setup)).
2. **Start**, by the project's state ([runs.md](runs.md#start); [workflow.md](workflow.md#stages) S1):
   - **Take the start input:** a product concept, or a project to maintain plus what to change (flow 2).
     - It comes from the text the skill was invoked with.
     - If that text is missing, the skill asks for it once, in the CLI. This is the only question the skill asks after setup; anything else that needs the user goes to Slack (flow 2, Q03-3).
     - The project to maintain defaults to the repo the session is in (AI).
   - **No run, or the last run is complete:** prepare the folder as [runs.md](runs.md#start) says, then call `barrel run start`.
   - **Active run:** pass the text to that run's orchestrator with `barrel instruct`, then open the PC view (AI; opening the view is the Q10-2 default).
   - **Stopped run:** pass the text to that run with `barrel instruct`, where it waits for the resume (Q10-2). Say how to resume, and open the PC view (AI).
3. **Report the channel and the PC view, then end** (Q03-3).

**Keeping it out of everyday sessions** (AI; body length 09-29 draft):
- The description is short and says the skill runs only when the user asks for Barrel. That keeps it from loading by itself in the user's everyday sessions.
- The body stays short; details live in `references/`.

<a id="playbooks"></a>
## Role playbooks

Sessions that the launcher starts get their instructions from a playbook file named in their first prompt. That covers the orchestrator, task sessions, the Korean writer, and subagent roles that run as fresh sessions (AI). The orchestrator's subagents get their part of the orchestrator's playbook in the prompt the orchestrator writes for them.

Playbooks are plain files rather than more skills, for two reasons:
- The user's ordinary sessions do not get a longer skill list.
- Neither CLI decides by itself to load a role's rules into the wrong session.

Each playbook states:
- the role's inputs and outputs
- the commands it may use ([launcher.md](launcher.md#commands), [access](launcher.md#access))
- the rules that apply to it, for example:
  - the orchestrator's question rules ([interviews.md](interviews.md))
  - the task session's "do not guess, ask" rule ([task-tree.md](task-tree.md#files))

<a id="markers"></a>
## Role markers

The launcher starts every session with these environment variables (09-29 draft, AI names):

| Variable | Value |
| --- | --- |
| `BARREL_ROLE` | `orchestrator`, `task` or `ko_writer`. Also `advice`, `intent_check`, `context`, `research`, `verification` or `review`, when those run as fresh sessions |
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

<a id="hooks"></a>
## Hooks

| Event | Role | Behavior | Claude Code | Codex |
| --- | --- | --- | --- | --- |
| SessionStart (startup, resume, compact) | Any Barrel role | Inject the role, the project, the playbook path, and where the contract or handoff note is (AI) | `additionalContext` | `hookSpecificOutput.additionalContext` |
| Every Barrel hook event | Any Barrel role | The first time the event fires in a session, write a marker with the plugin version. The launcher checks the markers ([below](#trust)) (AI) | Marker file | Marker file |
| PreToolUse on file writes | Orchestrator | Allow writes only to two places (09-29 draft: the orchestrator does not edit product code; paths AI):<br>• `.barrel/` in the integration worktree, except the files the launcher writes: `answer/`, the generated indexes, the Korean display names and the posted Korean texts of reviews<br>• the orchestrator's run-state folder | Deny `Write`, `Edit` with a reason | Deny `apply_patch` (matched as `Edit`, `Write`) with a reason |
| PreToolUse on file writes and shell commands | Subagents of the orchestrator | Allow writes only to the orchestrator's run-state folder, for their reports. Deny every `barrel` command, so a subagent cannot approve, post or hand off (AI) | Deny. Calls from a subagent carry `agent_id` | Spike: whether Codex hooks can tell a subagent's calls apart |
| PreToolUse on file writes | Task | Allow writes only inside the leaf's `write_set`. An investigation leaf may also write its report in `outputs/` (09-29 draft) | Deny | Deny |
| PreToolUse on file writes | Fresh auxiliary sessions | Allow writes only to the run state's `outputs/` (AI) | Deny | Deny |
| PreToolUse on shell commands | Any Barrel role | Deny git commands that move refs or rewrite history (commit, push, reset, rebase, merge, switching branches, deleting branches or tags) and `--no-verify`. The launcher makes every commit and merge (09-29 draft; [runs.md](runs.md#branches)) | Deny `Bash` | Deny `Bash` |
| PreToolUse on shell commands | Task | Deny system package installs: `brew install`, and global npm or pip installs. Approved tools come through `env.setup` (archived Q-008; AI) | Deny `Bash` | Deny `Bash` |
| PreToolUse on Slack MCP write tools | Any Barrel role | Deny. Only the launcher posts (Q09, Q10 default) | Deny the matching `mcp__` tools | Deny the matching `mcp__` tools |
| PreToolUse on `ExitPlanMode` | Task, Claude only | Save `tool_input.plan` to run state, so the launcher has the plan before approval (09-29 draft) | Records the input | Not needed; app-server returns the plan |
| PreCompact | Orchestrator | Block compaction and ask the launcher for a handoff (AI) | Exit 2 | `continue: false` |
| PreCompact | Task | Allow it, and record a `task_compacted` event: the leaf was larger than the size rule allows (AI) | — | — |

- **One command per event.** `hooks/hooks.json` registers exactly one command for each event, `hooks/barrel_hook.py <event>`. The rows above are branches inside it. So Codex trusts, and the markers report, one hook per event (AI).
- **Hooks are guard rails.** Shell commands can write files that the write hooks never see, so the final guard is the write-set check before commit ([task-execution.md](task-execution.md#lifecycle)) (09-29 draft).
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
- **What the check cannot see.** It covers the two events every session fires: SessionStart and PreToolUse.
  - A skipped PreCompact hook would go unnoticed, because compaction rarely happens.
  - In an orchestrator, that costs a compaction instead of a handoff. It does not turn off a guard.

<a id="install"></a>
## Installing

- **The launcher** is installed once per PC as the `barrel` command, with `uv tool install` from the plugin folder (AI).
  - uv supplies Python 3.12 or later. The system `python3` on this Mac is 3.9 ([research.md](research.md#environment)).
  - Every config folder's copy of the plugin therefore calls the same launcher.
  - The skill compares `barrel --version` with its own version. An older launcher is upgraded once no run is active ([launcher.md](launcher.md#versions)).
- **The plugin**, in every account folder, because plugins live per config folder (Q05):
  - Claude: `CLAUDE_CONFIG_DIR=<dir> claude plugin marketplace add <repo>`, then `claude plugin install barrel@<marketplace>`.
  - Codex: `CODEX_HOME=<dir> codex plugin marketplace add <repo>`, then `codex plugin add barrel@<marketplace>`.
  - Both commands exist in the installed versions ([research.md](research.md#vendors)).
- **Skill-Techblog**, for Korean text (Q08):
  - In every Claude account folder: `claude plugin marketplace add KANG-YEONWOOK/Skill-Techblog`, then `claude plugin install techblog@skill-techblog`.
  - For Codex, it follows its own v0.5.0 instructions; the skill is invoked as `$techblog` there ([research.md](research.md#vendors)).
- **The official Slack MCP**, for reading (Q09):
  - Claude: the `slack@claude-plugins-official` plugin.
  - Codex: `codex mcp add` with this PC's Barrel Slack app's client ID, then `codex mcp login` (spike). It is set up after the Slack app exists ([setup](#setup) step 8).
- **Browser automation** is not installed into the account folders. The launcher passes the Playwright MCP server to the sessions that need it ([task-execution.md](task-execution.md#user-only)). Setup only checks that `npx` exists (AI).

<a id="setup"></a>
## First-run setup

The skill runs these steps in the invoking session and skips any step that is already done (flow 1, Q05, Q09, Q11, Q12). It reports what it did.

1. **Python and uv.** Install uv if it is missing, then Python 3.12 or later through uv (AI).
2. **The `barrel` command.** Install it from the plugin folder ([install](#install)). The steps below run through `barrel setup`. Setup works without the launcher: it starts its own short test sessions where it needs them (step 6), and starts the launcher only in step 11 (AI).
3. **Engines.** Find `claude` and `codex` on PATH. If one is missing, ask the user how to proceed: install it, give its path, or go on with one engine (flow 1; archived D-004). The answer is kept in the settings, so it is not asked again.
4. **Accounts** ([sessions.md](sessions.md#accounts)).
   1. List the registered Claude config folders and Codex homes. Check that each is logged in, with `claude auth status` or `codex login status`.
   2. Ask once whether the user has other subscriptions to add. For each account name, create `~/.claude-<name>` or `~/.codex-<name>` and run that CLI's login with the folder set (flow 1, Q05).
   3. Every logged-in account is used (Q12).
5. **Plugins.** Install Barrel and Skill-Techblog into every account folder, and the Slack MCP plugin into every Claude folder ([install](#install)).
6. **Codex hooks.** Start a short test session the way the launcher will, and check that Barrel's hooks run with the trust bypass. If they do not, walk the user through `/hooks` in each Codex home ([trust](#trust)).
7. **Slack app**, one for this PC ([slack.md](slack.md#setup)) (Q09, option 9-a X: the skill prepares the app; the user only approves the install and enters the tokens):
   1. The skill writes the manifest ([slack.md](slack.md#manifest)) and creates the app from it. How it creates the app, through the browser or Slack's manifest API, is spike item 19.
   2. The user approves the install in the workspace and pastes the tokens: the app token, and the bot token unless the install hands it to Barrel. They go into the Keychain.
   3. Barrel learns the user's Slack ID from the install, if the spike shows that works. Otherwise the user types a one-time code into the bot's DM (archived D-043; [slack.md](slack.md#setup)).
8. **Slack MCP for Codex.** `codex mcp add` with the new app's client ID, then `codex mcp login`, in every Codex home ([install](#install)).
9. **Barrel.app.** Create `~/Applications/Barrel.app` with `osacompile` ([pc-view.md](pc-view.md#reopen)) (AI, delegated in Q10-2).
10. **Browser automation.** Check that `npx` exists for the Playwright MCP server. If it is missing, a leaf that needs a browser asks for it later (AI).
11. **Launcher.** Start the launcher: detached, or as a launchd agent ([launcher.md](launcher.md#process)) (Q11).
12. **Settings.** Write `~/.barrel/settings.json`:
    - the engines in use, and the accounts, in order
    - the Slack app and the registered user
    - the language: Korean (Q10)
    - the sleep policy: `ac` (archived D-047; default AI)

<a id="budget"></a>
## Context budget

These limits are from the 09-29 draft and must be checked again ([research.md](research.md#vendors)):
- **Skill descriptions:** Claude Code allows about 1,536 characters per skill description in its listing, Codex about 1,024.
- **Hook injections:** Claude Code caps the text a hook injects at 10,000 characters.

So the skill and the playbooks stay short and point to files, and hooks inject paths, not documents (09-29 draft).
