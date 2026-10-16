# Facts this design relies on

These facts change over time, so check them again before relying on them. Each section says when it was checked.
- **Official sources:** official docs, source code, man pages and local checks are linked or named.
- **Unofficial sources:** blogs, issues and forum posts are marked (unofficial).

This file replaces the vendor section that was in [session-context.md](../session-context.md) (§7, checked 2026-10-06 and 2026-10-07). Its contents moved here and were updated on 2026-10-08, 2026-10-11 and 2026-10-13 to 2026-10-16.

<a id="environment"></a>
## This Mac (checked 2026-10-07, 2026-10-08, 2026-10-11 and 2026-10-16)

- **Versions:**
  - Claude Code 2.1.301 on 2026-10-16. It was 2.1.296 on 2026-10-11 and 2.1.292 on 2026-10-08, because it updates itself in the background.
  - codex-cli 0.162.1 on 2026-10-13 and 2026-10-16. It was 0.155.1 on 2026-10-11.
  - uv 0.11.19.
  - macOS 15.7.5 (Darwin 24.6).
- **Python:** the system `python3` is 3.9, but the repo needs 3.12 or later. Python 3.13 is at `/opt/anaconda3/bin/python3.13`, and there is no `.venv`.
- **Accounts:** Claude config folders `~/.claude` and `~/.claude-wook`; one Codex home, `~/.codex` (Q12).
- **Plugins** (2026-10-08, not checked since): Claude had only `swift-lsp` installed in `~/.claude`. Skill-Techblog was not installed.
- **Plugin commands** (checked 2026-10-13 with `--help`):
  - Claude Code: `claude plugin install|update|uninstall|enable|disable|list|…`, with `--json` output. `claude plugin update <plugin>` updates a plugin to the latest version, and its help says "restart required to apply". `claude plugin marketplace add|list|remove|update`; `update` refreshes marketplaces from their source.
  - Codex: `codex plugin add|list|marketplace|remove`, and `codex plugin marketplace add|list|upgrade|remove`. `upgrade` refreshes the configured Git marketplace snapshots.
- **Tests:** expected result 506 passed, 2 skipped, 8 deselected.

  ```bash
  uv run --no-project --python 3.13 --with pytest --with pyte --with ptyprocess --with pyyaml \
    python -m pytest tests barrel/tests -m 'not live' -q
  ```

<a id="code"></a>
## The existing code (main at `5c15481`; checked 2026-10-13)

All 186 code references in these documents were checked against the code on 2026-10-13. The full reuse and gap map with line references is in [launcher.md](launcher.md#reuse). The main points:

- **One child per handle.** step2step drives one session per handle and has no supervisor and no command channel for other processes.
- **No lock between processes.** No code uses `fcntl`, `flock` or a lock file. step2step has thread locks only (`step2step/codex/transport.py:20`, `:70`; `step2step/codex/session.py:70`; `step2step/terminal/pty_session.py:59`; `step2step/terminal/screen.py:16`). The files that processes share today are the stop files, the state file saved by an atomic rename, and the hook's signal file; none of them is a lock.
- **Codex threads.** Codex handles must be driven from the thread that created them (`step2step/codex/session.py:167-171`).
- **Claude's flags.**
  - Every Claude session gets `--session-id`, `--settings` and `--dangerously-skip-permissions` (`step2step/claude/runner.py:363-370`).
  - `model`, `effort` and `system_prompt_append` have their own parameters. Anything else goes through `extra_args`, appended as is (`:381`).
  - Plan mode is entered with Shift+Tab before each prompt (`step2step/claude/session.py:222-223`).
  - `approve_plan()` picks option 1 of the plan menu (`step2step/claude/runner.py:1287-1310`), so the session returns to bypass (`step2step/claude/session.py:107-110`). On the verified 2.1.272 its label reads "Yes, and switch to bypass permissions" (`step2step/claude/screen.py:68`).
- **Codex's parameters.**
  - `thread/start` always boots read-only (`step2step/codex/session.py:105-119`).
  - Each turn's sandbox is set per turn (`:183-188`): planning turns are read-only, then the session's mode applies. `workspace-write` allows only the workdir.
  - The defaults are approval `never` and sandbox `danger-full-access` (`:44-54`).
  - Nothing sets network access or extra writable roots.
- **Logins.**
  - Codex accepts only a ChatGPT login: `step2step/codex/session.py:97-99` rejects any other account type, and `step2step/codex/transport.py:76` forces `forced_login_method="chatgpt"`.
  - Claude only removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and the `CLAUDE*` variables from the child's environment (`step2step/claude/runner.py:72-83`, `:153-163`). Nothing checks how a Claude config folder is logged in; `Runner.preflight` checks the executable, the runtime folder and disk space only (`:245-278`).
- **Config folders.**
  - `CLAUDE_CONFIG_DIR` appears nowhere in the code. `child_env()` would strip it (`step2step/claude/runner.py:160`), and `tests/test_env_scrub.py:6-13` asserts that no `CLAUDE*` variable survives.
  - `~/.claude` is hard-coded in the transcript lookup (`step2step/claude/transcript.py:27`; `find_transcript`'s `base` parameter, `:25-31`, is never passed), in the settings path (`step2step/claude/calibrate_model.py:37`) and in `tests/test_live.py:22`.
  - A test asserts that Codex passes `CODEX_HOME` through (`tests/codex/test_transport.py:78-84`).
- **The unit loop.**
  - It runs a flat list in file order, one session at a time.
  - It runs in bypass mode (`barrel/core/unitloop.py:439`) and approves any plan menu blindly (`:767-783`). It answers questions with a fixed default (`:82`).
  - It only creates Claude sessions (`:433-442`), one per attempt (`:650`).
  - Its run configuration is one JSON file merged over `DEFAULT_CONFIG` (`:47-83`): preflight, gates (`before`, `after_timeout`, `env_recover`), budget, ladder, `repeat_limit`. There is no setup or install command.
  - On a usage limit it sleeps `min(usage_wait_seconds, the remaining run budget)` and retries the same session (`:703-708`, at `:704`). `usage_wait_seconds` is 900 by default (`:81`).
  - A failed recovery halts the whole run (`:752`, `:755`). A gate defect halts it too: at baseline through `:565-566`, during an attempt through `:738-739` and `:623`.
- **Budgets.** `Budget` (`barrel/core/failures.py:262-288`) requires every field to be finite and positive. Its defaults:
  - 3,600 s per turn
  - 12 turns and 4 hours per unit
  - 24 hours per run, checked at `unitloop.py:540-541` and before every turn at `:671-673`
- **Git.**
  - `barrel/core/gitops.py` works on one repo, creates no worktrees and no branches; it checks a branch and pushes.
  - The path-scoped `commit` (`:78-134`) is used only by tests; the unit loop uses `commit_all` (`unitloop.py:829`).
- **Usage resets** are kept as text: Claude's "7pm" (`step2step/claude/screen.py:111-114`), Codex's `resetsAt` values (`step2step/codex/session.py:504-516`). Nothing converts them into a time.
- **Context use.** No code reads token usage for Claude. Codex token usage is kept raw (`step2step/codex/events.py:86-87`).
- **Tests.**
  - `barrel/tests/` has 84 test functions, none of them live. The unit loop's 24 (`barrel/tests/test_unitloop.py`) use fake sessions; the rest test gates, failures, git, preflight and verification without sessions.
  - `tests/` has 397 more.
  - The 8 live tests are opt-in: `tests/test_live.py` (Claude, `STEP2STEP_LIVE=1`) and `tests/codex/test_live.py` (Codex, `STEP2STEP_CODEX_LIVE=1`).
- **Calibration.** Claude Code was last calibrated at 2.1.272 ([docs/step2step.md](../../step2step.md)) and Codex verified at 0.153.4 ([docs/codex-control.md](../../codex-control.md)).
- **Doc errors found and fixed:**
  - The analysis in [Q04-2](../interview/q04-2-orchestrator-on-both-cli.md), and session-context.md §8.4 before it was corrected on 2026-10-08, mention `SessionHandle.send`. No such method exists; the API is `send_prompt`, `wait_turn` and `run_turn`.
  - [q10-confirmed.md](../interview/q10-confirmed.md) §5 cites `Notifier` at `:326` and `RunState` at `:370`, one to three lines early; they start at `:327` and `:373`. Its "`:575`" for the Codex cleanup is the `def stop` line; the request is at `:580-582`. The interview record is left as it is.

<a id="vendors"></a>
## Vendors

**Claude Code** (checked 2026-10-06 to 2026-10-13)
- **Hooks** ([docs](https://code.claude.com/docs/en/hooks)):
  - `SessionStart` matchers: `startup`, `resume`, `clear`, `compact`, `fork`.
  - `additionalContext` works on `SessionStart`, `UserPromptSubmit` and `PostToolUse`. Injected text is limited to 10,000 characters (09-29 draft).
  - `PreCompact` can block compaction with exit code 2.
  - Every hook input carries `transcript_path`.
  - Plugins ship hooks in `hooks/hooks.json`.
  - Hooks fire for tool calls inside subagents; the input then carries `agent_id` and `agent_type`.
  - Hook processes inherit the claude process's environment, apart from a few scrubbed variables.
  - Hooks from settings files, including `--settings`, and from plugins merge, and all matching hooks run ([settings reference](https://code.claude.com/docs/en/settings-reference)).
- **Skills:** a skill body can use `${CLAUDE_SKILL_DIR}`, and in plugin skills `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}`. These are substituted into the text; they are not environment variables in Bash commands ([docs](https://code.claude.com/docs/en/skills)). Plugin skills are listed as `plugin:skill`.
- **Login check:** `claude auth status` prints JSON and exits 0 when logged in and 1 when not. Its `configDirectory` field follows `CLAUDE_CONFIG_DIR` ([CLI reference](https://code.claude.com/docs/en/cli-reference)). Which field tells a subscription login from an API key is a spike check.
- **Context size:** each assistant entry in the transcript JSONL records `message.usage`. Context size is input plus cache-creation plus cache-read tokens. The status line also receives `context_window.used_percentage` ([docs](https://code.claude.com/docs/en/statusline)).
- **Background sessions** (`claude --bg`, research preview since 2.1.139) ([docs](https://code.claude.com/docs/en/agent-view)):
  - One supervisor service per user runs every background session, each as its own process (`claude daemon status`). It starts when needed, not at login (checked for Q22-2).
  - Flags: `--model`, `--permission-mode`, `--name`, `--settings`, `--plugin-dir`.
  - A session that is finished or waiting, and unattached for about an hour, has its process stopped.
  - The docs do not say whether a background session can start another one.
  - "Running ten agents in parallel uses quota roughly ten times as fast as running one."
  - Barrel does not depend on `--bg` (Q04-2).
- **Cross-session messaging** (2.1.224 and later) ([docs](https://code.claude.com/docs/en/cross-session-messaging)):
  - `ListAgents` and `SendMessage` work between local sessions.
  - `notify_when_idle` works only from the main conversation.
  - Barrel does not use this; the launcher injects turns instead.
- **Subagents** ([docs](https://code.claude.com/docs/en/sub-agents)):
  - Each starts with a fresh context, and the parent gets only a summary.
  - `AskUserQuestion` is removed. `EnterPlanMode` and `ExitPlanMode` are removed unless the subagent's `permissionMode` is `plan`.
  - Limits: 3 levels of nesting, 20 running at once.
  - The Agent tool takes `model` and, since 2.1.292, `effort` on every call. The `CLAUDE_CODE_EFFORT_LEVEL` variable overrides the per-call effort, so the launcher does not set it.
- **Agent teams** ([docs](https://code.claude.com/docs/en/agent-teams)):
  - Experimental.
  - The lead approves teammate plans automatically.
  - Teammates share one checkout; the docs suggest 3–5 teammates.
- **Auto memory** ([docs](https://code.claude.com/docs/en/memory)):
  - Kept per machine and per config folder.
  - Off in background sessions and in sessions started by another session.
  - Barrel does not rely on it (Q07).
- **Accounts:** `CLAUDE_CONFIG_DIR` separates both the config and the login. On macOS each config folder gets its own Keychain item ([aq.dev](https://aq.dev/guides/run-multiple-claude-code-accounts/), unofficial). Plugins are installed per config folder (Q05). Whether a Barrel-managed folder can reuse an account's Keychain item is a spike check.
- **MCP servers:** `claude mcp add <name> …`; local and user scopes are stored per config folder ([docs](https://code.claude.com/docs/en/mcp)).
  - Playwright: `claude mcp add playwright npx @playwright/mcp@latest` ([microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)). For one session only, `--mcp-config <file>` works.
- **Computer use** in the CLI ([docs](https://code.claude.com/docs/en/computer-use)):
  - A research preview, macOS only, on Pro and Max plans, in interactive sessions only.
  - Turned on per project in `/mcp`.
  - Needs the Accessibility and Screen Recording permissions, and an approval for each app in each session.
- **Chrome:** `claude --chrome` needs the Claude in Chrome extension and a claude.ai login ([docs](https://code.claude.com/docs/en/chrome)).
- **Updates:** Claude Code updates itself in the background. `DISABLE_AUTOUPDATER=1` stops that; `claude update` still works ([docs](https://code.claude.com/docs/en/setup)). Marketplaces can update installed plugins in the background, per marketplace ([plugin security docs](https://code.claude.com/docs/en/plugins/security)); Barrel's own version check covers a folder whose plugin moved on by itself ([launcher.md](launcher.md#versions)).
- **Plugins:**
  - Chat and Cowork refuse a plugin that has a top-level `bin/` (09-29 draft).
  - Skill descriptions are limited to about 1,536 characters each in the skill listing (09-29 draft, re-check).

**Codex (0.155.1 checked 2026-10-08 and 2026-10-11; 0.162.1 installed since)**
- **Hooks** ([docs](https://learn.chatgpt.com/docs/hooks)):
  - 12 events: `SessionStart`, `SessionEnd`, `SubagentStart`, `SubagentStop`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `Stop`, `Interrupt`.
  - Every hook input has `session_id`, `transcript_path`, `cwd`, `hook_event_name` and `model`.
  - `PreToolUse` matching:
    - Shell commands match `Bash`.
    - `apply_patch` matches `apply_patch`, `Edit` or `Write`.
    - MCP tools match by name (`mcp__server__tool`).
    - Hosted tools such as web search fire no hook.

    The aliases are in `codex-rs/core/src/tools/hook_names.rs` at `rust-v0.155.1`.
  - `hookSpecificOutput.additionalContext` works on `SessionStart`, `SubagentStart`, `PreToolUse`, `PostToolUse` and `UserPromptSubmit` ([#45999](https://github.com/openai/codex/issues/45999)).
  - `PreCompact` can block compaction, with `"continue": false` or exit code 2 (checked 2026-10-08).
  - A `Stop` hook returning `decision: "block"` continues the turn, using its reason as a new prompt.
  - Hooks time out after 600 s by default.
  - **Trust:**
    - Recorded per hook, by content hash. New or changed hooks are skipped until trusted in `/hooks`, and plugin hooks go through the same review.
    - `--dangerously-bypass-hook-trust` runs them without that review.
    - Hooks from `requirements.toml`, the system or MDM are managed and trusted by policy.
  - **Environment:** hooks get a snapshot of the codex process's environment, minus five internal credential variables. They also get `PLUGIN_ROOT` and `PLUGIN_DATA`. This comes from `codex-rs/hooks/src/registry.rs` at `rust-v0.155.1`; the docs do not say.
- **app-server** ([docs](https://developers.openai.com/codex/app-server)):
  - `thread/start` takes a sandbox mode and a `config` map that works like `-c key=value`. The map is the place for writable roots, network access, `model_reasoning_effort` and the hook-trust bypass.
  - `turn/start` takes a full `sandboxPolicy`, with `writableRoots` and `networkAccess`.
  - The docs' examples write enum values in camelCase while 0.155.1 serializes them in kebab-case. `codex app-server generate-json-schema` settles it.
- **Context size:** the rollout JSONL has `token_count` events with `last_token_usage` and `model_context_window` (one local file showed 258,400). app-server sends `thread/tokenUsage/updated`.
- **Waking an idle session:** there is no built-in way ([#29922](https://github.com/openai/codex/issues/29922), [#32188](https://github.com/openai/codex/issues/32188), [#51272](https://github.com/openai/codex/issues/51272) open; [#29865](https://github.com/openai/codex/issues/29865) closed as not planned). The launcher solves this by starting a new turn on the thread.
- **Subagents** ([docs](https://developers.openai.com/codex/subagents)):
  - They spawn only when asked.
  - `spawn_agent` takes `model` and `reasoning_effort` on every call.
  - The cap is `agents.max_concurrent_threads_per_session`; the legacy `max_threads` default was 6 ([#13964](https://github.com/openai/codex/issues/13964), unofficial).
  - The depth limit is not enforced in 0.155.1 ([#46704](https://github.com/openai/codex/issues/46704)).
- **Login check:** `codex login status` exits 0 when logged in. It follows `CODEX_HOME` ([docs](https://developers.openai.com/codex/auth)). The login is kept in `$CODEX_HOME/auth.json`.
- **Plugins** ([docs](https://developers.openai.com/codex/plugins/build)): `.codex-plugin/plugin.json`, `skills/`, `hooks/hooks.json`. Marketplaces are added with `codex plugin marketplace add` and refreshed with `codex plugin marketplace upgrade`.
- **Skills** ([docs](https://learn.chatgpt.com/docs/build-skills)):
  - Discovered from `.agents/skills` (from the current folder up to the repo root), `~/.agents/skills`, `/etc/codex/skills` and plugins.
  - The parser reads only `name`, `description` and `metadata.short-description`. The bundled validator rejects other keys such as `compatibility`.
  - There is no variable substitution. Codex resolves relative paths in `SKILL.md` against that file's folder.
- **MCP servers:** `codex mcp add <name> -- <command>` or `--url <URL>`, then `codex mcp login <name>` for OAuth. They are stored in `$CODEX_HOME/config.toml` ([docs](https://developers.openai.com/codex/mcp)).
- **Image generation** (checked 2026-10-12 and 2026-10-16; [docs](https://learn.chatgpt.com/docs/image-generation)):
  - Invoked by describing the image, or explicitly with `$imagegen` in the prompt.
  - "Built-in image generation uses `gpt-image-2` and counts toward your general Codex usage limits." No API key is needed. Image turns use those limits three to five times faster on average.
  - Barrel's designer may use it when it runs on Codex; it is one option, not a requirement ([workflow.md](workflow.md#design)).
- **`/goal`:** since 0.128.0. Goals persist across restarts and are stored in `~/.codex`, outside the repo.

**Slack** (checked 2026-10-06 to 2026-10-11; Q10 and Q10-2 sources are in [Q10](../interview/q10-slack-progress-reports.md) and [Q10-2](../interview/q10-2-pc-view-stop-language.md))
- **Official MCP:**
  - Hosted at `mcp.slack.com/mcp`, generally available since 2026-02-17.
  - It uses the user's own token, so the messages it sends come from the user, and the user is not notified.
  - In Claude Code the `slack@claude-plugins-official` plugin configures it. The Codex plugin ships skills only ([slackapi/slack-skills-plugin](https://github.com/slackapi/slack-skills-plugin)).
  - Clients need OAuth with a Slack app's client ID; there is no dynamic client registration. Only Marketplace or internal apps may use it ([docs](https://docs.slack.dev/ai/slack-mcp-server)).
- **Socket Mode** ([docs](https://docs.slack.dev/apis/events-api/using-socket-mode/)):
  - It needs an app token (`xapp-`, `connections:write`) and a bot token (`xoxb-`).
  - Up to 10 connections per app. "When multiple connections are active, each payload may be sent to _any_ of the connections" (checked 2026-10-07; the reason for Q11).
  - Each event must be acknowledged so Slack knows whether to retry. Expect `refresh_requested` disconnects.
  - **Retries** (checked 2026-10-11; [Events API](https://docs.slack.dev/apis/events-api/), [Socket Mode](https://api.slack.com/apis/connections/socket-implement)):
    - An event not acknowledged within 3 seconds is retried three times: at once, after 1 minute, and after 5 minutes.
    - Unless the opt-in Delayed Events feature is on, nothing more than two hours late is delivered. The docs do not say how this applies to Socket Mode.
    - So Barrel catches up from history instead of relying on retries ([launcher.md](launcher.md#recovery)).
  - The Python SDK's built-in Socket Mode client needs no third-party package ([docs](https://docs.slack.dev/tools/python-slack-sdk/socket-mode/)).
- **Scopes and events** ([conversations.create](https://docs.slack.dev/reference/methods/conversations.create)):
  - A private channel: create it with `groups:write`, invite with `groups:write.invites`, read its messages and thread replies with `groups:history` and `message.groups`.
  - Mentions: `app_mentions:read` and `app_mention`. DMs to the bot: `im:history`, `message.im`, and the App Home Messages tab.
  - Channel names: lowercase letters, digits, hyphens and underscores, at most 80 characters.
- **Who gets notified:**
  - By default only DMs, mentions, keywords and replies in followed threads.
  - A plain channel post notifies only if the user sets the channel to all new posts; a bot cannot change that.
  - A mention notifies only channel members.
  - Mobile push waits until one minute after the desktop locks, or ten idle minutes, and shows only the message's `text`.
- **Rate and size:**
  - `chat.postMessage` allows 1 message per second per channel. Bursts may be dropped; going over returns 429 with `Retry-After`.
  - A message holds up to 50 blocks. A section holds up to 3,000 characters.
  - The `markdown` block renders standard Markdown, up to 12,000 characters per message ([docs](https://docs.slack.dev/reference/block-kit/blocks/markdown-block)).
- **Message metadata:** `chat.postMessage` takes `metadata` with an `event_type` and an `event_payload`. `conversations.history` with `include_all_metadata=true` returns it. Every workspace member can see it, so Barrel puts only event IDs there ([docs](https://docs.slack.dev/messaging/message-metadata/)).
- **Thread replies** are not part of channel history. They are read with `conversations.replies`.
- **Free plan:**
  - 90 days of visible history.
  - The bot counts toward the 10-app limit.
  - Heavy posting can hit `message_limit_exceeded`.
- **Interactivity:**
  - Socket Mode carries buttons, modals, slash commands and App Home.
  - Acknowledge within 3 s.
  - Block Kit `confirm` works on buttons.
  - Slash commands cannot run in threads.
- **Agent features:**
  - Streaming, task cards and agent sessions all update one message in place, so Barrel does not use them (Q10).
  - The native Stop button exists only for apps declared as agents.
- **Files:**
  - `files.upload` was retired on 2025-11-12.
  - Use `files.getUploadURLExternal`, then `files.completeUploadExternal` with the channel and `thread_ts`. This needs `files:write`, and the bot must be a channel member ([docs](https://docs.slack.dev/reference/methods/files.completeUploadExternal)).

**macOS** (checked on 15.7.5; man pages read on 2026-10-16)
- **Sleep** (`man caffeinate`, `IOPMLib.h`; checked 2026-10-11):
  - `caffeinate -i -w <pid>` prevents idle sleep until that process exits.
  - `-s` prevents system sleep, but only on AC power.
  - Neither prevents sleep when a laptop's lid closes. The header says "the system may still sleep for lid close, Apple menu, low battery, or other sleep reasons."
- **The input dialog** ([Mac Automation Scripting Guide: Prompting for Text](https://developer.apple.com/library/mac/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/PromptforText.html)): AppleScript's `display dialog "…" default answer "" with hidden answer` asks for text with the input hidden, and returns what was typed. Whether a background launcher can show it is spike item 55.
- **Keychain** (`man security`): `security add-generic-password … -T <appPath>` names an application that may access the item; several `-T` options are allowed, and `-T ""` allows none. Keychain access lists identify an application by its code signature (spike item 57).
- **sudo** (`man sudo`):
  - `-S` reads the password from standard input instead of the terminal.
  - `SUDO_ASKPASS` names a helper program that sudo runs to read the password when no terminal is available, or when `-A` is given.
- **launchd** (`man launchd.plist`, `man launchctl`):
  - `KeepAlive.SuccessfulExit` "implies that RunAtLoad is set to true, since the job needs to run at least once before an exit status can be determined".
  - `KeepAlive.Crashed` restarts a job that exited on a crash signal.
  - `launchctl bootstrap` loads a service definition into a domain, and `launchctl kickstart` "instructs launchd to run the specified service immediately, regardless of its configured launch conditions".
  - Agents in `~/Library/LaunchAgents` are loaded at every login, and macOS 13 and later lists background items under Login Items ([Eclectic Light](https://eclecticlight.co/2023/02/15/controlling-login-and-background-items-in-ventura/), unofficial; from Q22-2).
- **Priority** (`man taskpolicy`): `taskpolicy` runs a program with a lower scheduling or I/O policy, for example `-c utility` or `-c background`, and its children inherit it. `nice` lowers the scheduling priority.

**Local PC view** (measured on this Mac on 2026-10-07)
- **Cost:**
  - A stdlib `ThreadingHTTPServer` with one SSE client added 1.2–2.4 MiB to a launcher-like process.
  - Idle CPU was under 1 ms, with 4 wakeups per minute after raising `serve_forever`'s poll interval. The 0.5 s default gives about 120.
  - A plain `EventSource` page is 5.7 KB.
- **Security:**
  - A localhost endpoint that acts on requests is a known drive-by target (CVE-2025-49596 in MCP Inspector, CVE-2025-52882 in the Claude Code IDE extensions).
  - The fixes converge on five things: bind to 127.0.0.1, require a secret token, allowlist Host and Origin, no side effects on GET, no parameters on actions.
- **Safari:** Safari 26.4 on this Mac predates WebKit's 2026-06-04 fix, which unblocked localhost when "warn on non-secure sites" is on.
- **Barrel.app:** an `osacompile` applet on macOS 15.7.5 was 192 KB, ad-hoc signed, passed `codesign --verify --deep --strict`, carried no quarantine attribute and opened without a Gatekeeper prompt.

**Packages** (checked 2026-10-16)
- **OSV** ([API docs](https://google.github.io/osv.dev/post-v1-query/)): `POST https://api.osv.dev/v1/query` with `{"package": {"name": …, "ecosystem": …}, "version": …}` returns the known vulnerabilities of that version. The docs name no API key and say "Currently there are no limits on the API".
- **Registries** report whether a package exists, its latest release and its declared license; each ecosystem has its own API. The check runs in a context subagent ([task-execution.md](task-execution.md#packages)).

**Skill-Techblog** ([repo](https://github.com/KANG-YEONWOOK/Skill-Techblog), MIT; checked 2026-10-08)
- **v0.5.0** (commit `5895109`, "fix: codex plugin", 2026-10-07):
  - It removed `compatibility: Claude Code` and supports Codex.
  - `dev/codex/REPORT.md` records 9 passing runs on Codex CLI 0.155.1.
  - `references/runtime.md` maps each tool it uses to its Codex equivalent.
- **Flow:**
  1. Read the source.
  2. Write a fact sheet.
  3. Outline.
  4. Draft.
  5. Check with `lint_ko.py`, a rubric and the fact sheet.
  6. Revise in a separate subagent with fresh context (`revise_ko.py`).
  7. Optionally convert the tone (`tone_check.py`).

  The scripts need Python 3.8 or later and only the standard library. It asks the user nothing.
- **Install (Claude):** `claude plugin marketplace add KANG-YEONWOOK/Skill-Techblog`, then `claude plugin install techblog@skill-techblog`. In Codex it is invoked as `$techblog`.

<a id="models"></a>
## Models

The source is [the model tier doc](../../claude-gpt-모델-티어-매핑-가격비교.md), updated 2026-10-07. It is based on Artificial Analysis Intelligence Index v4.3.2 and Coding Agent Index v1.5.

- **New since 2026-09-11:**
  - Claude Opus 5.5 (09-22, $4/$20)
  - GPT-6 Sol and GPT-6 Luna (09-22)
  - Claude Sonnet 5.5 (09-28)
  - GPT-6.1 Sol (09-29, $2/$10)

  GPT-6 has three tiers: Astra, Sol, Luna. There is no Terra successor.
- **Tiers:**

  | Tier | Claude | GPT |
  | --- | --- | --- |
  | Frontier | Fable 5.1 | GPT-6 Astra |
  | Flagship | Opus 5.5 | GPT-6.1 Sol |
  | Mid | Sonnet 5.5 | GPT-6.1 Sol |
  | Light | Haiku 4.5 | GPT-6 Luna |

- **In `.barrel/config.json`** these tiers are named `frontier`, `strong` (flagship) and `standard` (mid). There is no light tier by default ([sessions.md](sessions.md#engines)).
- **Scores at max effort:** Opus 5.5 (58) > Sonnet 5.5 (56) > Fable 5.1 = Astra (53) > GPT-6.1 Sol (52). Opus 5.5 at high effort (54) already beats Fable and Astra at max.
- **The doc's routing pattern:**
  - Everyday work: Opus 5.5 at medium.
  - Harder work: Opus 5.5 at high to max (or GPT-6.1 Sol at xhigh).
  - When failure loops cost more than tokens: Fable 5.1 or Astra.
  - Bulk simple work: GPT-6 Luna.

  Anthropic's own guidance is to start with Opus 5.5 and move to Fable 5.1 when Opus at high effort is not enough. The defaults in [sessions.md](sessions.md#engines) follow this pattern (AI).
- **Model IDs to validate:**
  - Claude: `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5-20251001`.
  - GPT, in `sessions.md`: `gpt-6-astra`, `gpt-6.1-sol`. Not confirmed; the tier doc gives display names only.

  The launcher checks every ID against the CLI at run start ([validation.md](validation.md) item 41).
- **Effort:** effort matters more than the tier.
  - OpenAI efforts: low, medium, high, xhigh, max (Luna adds none).
  - Claude efforts: low to max.
  - Default efforts differ by model.

<a id="prior-art"></a>
## Prior art behind the interview answers

Full lists with links are in the interview records. The points the design uses:

- **Q11, one launcher:**
  - Claude Code runs every background session under one supervisor per user.
  - Slack Socket Mode spreads events across all of an app's connections.
- **Q13, depth by impact:**
  - Kiro (Feature, Bugfix, Quick Spec) and BMAD let the user choose a path by size.
  - BMAD Build (2026-09) decides "how much ceremony a change needs after investigating it".
  - One flow for every size bloats small changes: Böckeler on Kiro ([martinfowler.com](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html), unofficial); Spec Kit [#1174](https://github.com/github/spec-kit/issues/1174), unofficial.
  - A confirmation before coding survives almost everywhere.
- **Q14, parallel lanes:**
  - A worktree per session is the norm (Cursor 2.0, the Codex app, Conductor, Kiro Crew with 3); defaults are small.
  - Merge conflicts appear in 28–42% of agent PRs ([2604.03551](https://arxiv.org/abs/2604.03551), [2607.04697](https://arxiv.org/abs/2607.04697)).
  - In Anthropic's 16-agent C-compiler run, agents duplicated and overwrote each other's work ([post](https://www.anthropic.com/engineering/building-c-compiler)).
  - Telling an agent about the concurrent change recovered 82% of broken merges ([STALE](https://arxiv.org/abs/2609.25396)).
- **Q15, tasks in the repo:**
  - Kiro (`.kiro/specs`, "you should commit these specification files"), Spec Kit (`specs/`) and Taskmaster (`.taskmaster/tasks`) keep their task files in git.
  - Built-in CLI features (Claude Code tasks, Codex `/goal`) keep theirs in the home folder.
- **Q16, verification instead of a provider split:**
  - No product runs two vendors on every question by default.
  - Picking from independent answers helps, while merging them did not beat the baseline in any of 42 tasks ([2603.20324](https://arxiv.org/abs/2603.20324)).
  - In debate, models flip to agree with each other ([2509.05396](https://arxiv.org/abs/2509.05396)).
  - When both models are wrong, they give the same wrong answer about 60% of the time, even across vendors ([2506.07962](https://arxiv.org/abs/2506.07962)).
  - Checking claims against sources ([Verify when Uncertain](https://arxiv.org/abs/2502.15845)) fits Q16's "research, then review and cross-check".
- **Q18, a run per request** (checked 2026-10-12; links in [Q18](../interview/q18-one-run-per-request.md)):
  - GitHub's Copilot coding agent opens a branch and a pull request per assigned issue, and takes changes as comments on that pull request.
  - Devin runs a VM per session and takes messages for a running session. Cursor runs each parallel agent in its own worktree and branch. Codex cloud runs each task in its own sandbox.
  - In all of them, a new request is a new task with its own branch; only instructions for a running task go to it.
- **Q19, what to confirm** (checked 2026-10-12; links in [Q19](../interview/q19-new-technology-threshold.md)):
  - Architecture decision records cover only decisions that are expensive to reverse: languages, frameworks, storage, communication, authentication, deployment.
  - AGENTS.md guides commonly say to ask before adding a production dependency (verified in three guides). A second rule quoted in the question could not be verified; the Q19 record says so.
  - GitHub's dependency review action blocks forbidden licenses and vulnerable dependencies without asking per package.
  - In LLM-written code, nonexistent package names appeared 5.2% of the time for commercial models and 21.7% for open models ([2406.10279](https://arxiv.org/abs/2406.10279)), so every new package is checked.
- **Q20, credentials and sudo** (checked 2026-10-12; links in [Q20](../interview/q20-credentials-and-sudo-tool.md)):
  - Devin and GitHub's Copilot agent take secrets in a settings store, not in the conversation, and pass them to the agent as environment variables.
  - Claude Code's Bash tool has no terminal, so a sudo that asks for a password fails. Community hooks show a GUI password prompt through `SUDO_ASKPASS`, or keep the password away from the model through an MCP server (unofficial).
  - Apple's TN2065: `do shell script … with administrator privileges` asks for authentication, and the same script does not ask again for five minutes.
- **Q21, updates** (checked 2026-10-12; links in [Q21](../interview/q21-auto-update-consent.md)):
  - Claude Code updates itself in the background unless `DISABLE_AUTOUPDATER=1` is set, and its marketplaces can update plugins in the background.
  - VS Code checks for updates in the background by default.
- **Q22-2, residency** (checked 2026-10-12; links in [Q22-2](../interview/q22-2-launcher-residency.md)):
  - Claude Code's background supervisor starts when needed, not at login.
  - Docker Desktop has a "start at login" setting that is off by default.
- **Hash IDs (2026-10-11 review, [runs.md](runs.md#ids)):**
  - **Beads**, an issue tracker for coding agents stored in git (now `gastownhall/beads`):
    - It made hash IDs opt-in in 0.20.0 (2025-10-30) and the default in 0.20.1 (2025-10-31), to stop collisions between agents and branches.
    - IDs are base36 hashes that grow from 4 to 6 characters ([CHANGELOG](https://github.com/gastownhall/beads/blob/main/CHANGELOG.md)).
  - **git-bug** uses the hash of an issue's first operation ([data model](https://github.com/git-bug/git-bug/blob/master/doc/design/data-model.md)).
  - **Backlog.md** keeps sequential IDs by scanning other branches, which does not cover unpushed concurrent branches ([repo](https://github.com/MrLesk/Backlog.md), reading of `src/core/backlog.ts`).
- **Generated files and hosted merges (2026-10-11 review, [runs.md](runs.md#sharing)):** pull requests merged on a hosting service ignore `.gitattributes` merge drivers such as `merge=union` ([GitLab #17325](https://gitlab.com/gitlab-org/gitlab-foss/-/issues/17325), [Bitbucket BCLOUD-21337](https://jira.atlassian.com/browse/BCLOUD-21337), [BCLOUD-20234](https://jira.atlassian.com/browse/BCLOUD-20234), [rubocop#3594](https://github.com/rubocop-hq/rubocop/pull/3594); unofficial). So Barrel keeps its generated indexes out of git.
