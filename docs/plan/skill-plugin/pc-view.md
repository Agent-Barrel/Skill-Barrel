# PC view

The PC view is a small local web page, served by the launcher, that shows how a project's work is going and lets the user stop and resume it. It has to be very light (Q10, Q10-2 option 10-e W). Answers and instructions go through Slack, not here (Q10-2). The settled rules are in [q10-confirmed.md](../interview/q10-confirmed.md) §4.

<a id="build"></a>
## How it is built (Q10-2)

- Python standard-library HTTP server plus Server-Sent Events for live updates. No third-party package and no Node build.
- The page is about 6 KB, or about 15 KB with styles.
- Measured on this Mac on 2026-10-07 with a process similar to the launcher:
  - +1.2 to 2.4 MiB memory
  - under 1 ms of CPU while idle
  - 4 wakeups per minute after raising `serve_forever`'s poll interval
  - The browser tab itself was not measured ([validation.md](validation.md)).
- Each project gets its own port and token. They are picked once and kept in `~/.barrel/projects/<id>/view.json`, readable only by the user (AI, delegated in Q10-2). The one launcher on the PC serves every project's page (Q11).

<a id="content"></a>
## What it shows (Q10-2)

- The large > medium > leaf tree with each node's status.
- Running sessions, with engine and model.
- Leaves that are blocked or waiting for an answer, and why, from the fixed set of reasons. Like Slack, the page is built from templates and values, never from free text ([launcher.md](launcher.md#events)) (AI).
- Questions waiting for an answer, with links to their Slack threads.
- Recent events, from the same event log Slack uses ([launcher.md](launcher.md#events)).
- The Slack connection state and the number of posts not sent yet (Q10-2 default). Posts waiting for the Korean writer count as unsent too ([interviews.md](interviews.md#posting)).

The page follows the Slack language setting (Q10-2 default).

<a id="writes"></a>
## What it can do

- **[중지] and [재개] only** (Q10, Q10-2). [중지] asks for confirmation once (AI); [재개] does not. Both follow the sequence in [launcher.md](launcher.md#stop).

<a id="security"></a>
## Security (Q10-2)

- **Where it listens:** 127.0.0.1 only.
- **Reading.** The page and its live updates (SSE) are plain GET requests with no side effects. Each one is checked for the token in the address and the `Host` header.
- **Acting.** Stop and resume are the only actions. They:
  - accept POST only
  - check the token, the `Host` header and the `Origin` header
  - take no parameters
- **Agent text** is escaped, so it can never render as HTML.

Browsers do not send `Origin` on a same-origin GET, so the `Origin` check applies to the actions only (AI; [research.md](research.md#vendors): no side effects on GET, no parameters on actions).

So the worst a forged request can do is stop the work. It cannot run code. The address contains the token and is never sent to Slack.

<a id="reopen"></a>
## Opening it again after closing it

The user asked for a way to reopen the page whenever they want, and left the method to the AI (Q10-2). Two principles: no extra resident process, and no token-bearing address in Slack.

1. **A fixed address.** The port and token stay the same across launcher restarts, so browser history or a bookmark works. The page also opens in the default browser when a run starts.
2. **"Barrel" in Spotlight or the Dock.**
   - First-run setup creates `~/Applications/Barrel.app` with macOS's `osacompile` (an AppleScript applet).
   - When run, it calls `barrel view open`, which opens a project's address in the default browser. Then the app quits; it never stays resident.
     - `barrel view open` starts the launcher first if it is not running ([launcher.md](launcher.md#process)) (AI).
     - It reads the addresses from run state each time.
   - With several projects running, it asks which one. With none, it says so.
   - It holds no token.
   - Tested on this Mac: 192 KB, ad-hoc signed, passed `codesign --verify --deep --strict`, ran without a Gatekeeper prompt.
3. **"화면" in the Slack channel.** The launcher opens that project's page on this Mac. Typing it on a phone opens the page on the PC.
4. **Running the skill again.** In a project whose run is active, the skill opens the page instead of starting another orchestrator. If it was invoked with a request, it passes that text to the running orchestrator first ([runs.md](runs.md#start)).

<a id="checks"></a>
## Still to check

These are spike items in [validation.md](validation.md):
- Re-measure memory and CPU in the real launcher, including the browser tab.
- Open the page in Chrome and in Safari. Safari 26.4 on this Mac predates WebKit's 2026-06-04 fix: before that fix, localhost was blocked while the "warn on non-secure sites" setting was on.
- Spotlight finds the app in `~/Applications`, and it runs without warnings on other Macs and macOS versions.
