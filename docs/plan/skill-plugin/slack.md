# Slack

Slack is where Barrel talks to people (flow 11, Q03-3, Q09, Q10).
- **It sends:** progress reports, snapshots, questions, review requests, and requests for things only the user can do.
- **It takes back:** answers, button presses, instructions and commands.

The settled rules come from [q10-confirmed.md](../interview/q10-confirmed.md). This document restates them in English with their sources, and adds what later answers decided: runs per request (Q18), approval and option buttons (archived D-045; Q17), cancelling a run (archived Q-009; Q17), and no credentials through Slack (Q20).

Q10 defaults that the Q10 answer or Q10-2 changed are noted where they apply. Defaults proposed in Q10-2 are tagged `(Q10-2 default)`.

<a id="setup"></a>
## Connection

- **A dedicated Slack bot** posts every question and report, so its messages notify the user (Q09, option 9-a X). The official Slack MCP sends as the user's own account, and the user gets no notification for those messages ([research.md](research.md#vendors)).
- **Only the launcher drives the bot.** Orchestrators and task sessions never post. They leave events through launcher commands (Q10 default). A hook denies the Slack MCP's write tools in every Barrel session ([plugin.md](plugin.md#hooks)) (AI). A leaf's own integrations with outside services do not change this (archived D-069; [task-execution.md](task-execution.md#user-only)).
- **Agents read Slack through the official Slack MCP**, for example to look up an earlier thread. They never post with it (Q09; Q10 default).
  - In Claude Code it comes with the `slack@claude-plugins-official` plugin.
  - Codex has no ready-made setup: the Slack MCP server needs OAuth with a Slack app's client ID. Setup tries `codex mcp add` with this PC's Barrel app's client ID, then `codex mcp login` (AI; [validation.md](validation.md) checks this).
  - If that OAuth does not work, Codex sessions read Slack through `barrel slack read`. It uses the launcher's bot token, so it can read only the channels the bot is in, which are Barrel's own (spike fallback; [launcher.md](launcher.md#commands)).
- **One Slack app and one Socket Mode connection per PC**, held by the launcher (Q11).
  - Slack delivers each event to only one of an app's open connections, so a single connection keeps events from going astray.
  - For the same reason, two PCs never share an app. Each PC's setup creates its own app, for example "Barrel (wook-mbp)" (AI).
  - The launcher routes each event to its project by channel, and to its run as [below](#routing).
- **Incoming messages are never lost** (AI). The launcher records a message before it acknowledges it, and catches up from the channel's history after downtime or a reconnect ([launcher.md](launcher.md#recovery)).
- **One private channel per project on each PC.** The bot creates it at the project's first run and invites the registered user, and nobody else (Q09, Q10 default; archived D-043; creation by the bot is AI).
  - The name is `barrel-<project>`, lowercased and limited to letters, digits, hyphens and underscores, at most 80 characters. These are Slack's rules.
  - If the name is taken, for example by a teammate's channel for the same project, the bot adds a short suffix (AI; [runs.md](runs.md#sharing)).
  - All runs of the project share the channel (Q18).
- **One thread per question** (Q09).
- **Setup** happens in first-run setup ([plugin.md](plugin.md#setup)). Q09's chosen option sets the target: the skill prepares the app up to its manifest, and the user only approves the install and enters the tokens (Q09, option 9-a X; details AI).
  1. The skill writes the app manifest and creates the app from it. Whether this works through the browser or through Slack's manifest API is a spike item.
     - If automation fails, the user creates the app from the generated manifest, with guided steps (spike fallback).
  2. The user approves the install and pastes the app token (`xapp-`), plus the bot token (`xoxb-`) unless the install hands it to Barrel. Both go into the Keychain.
  3. Barrel learns which Slack account is the user's, because only that account is obeyed (archived D-043).
     - The target is to take it from the install itself, so the user does nothing more (spike).
     - The install's OAuth redirect then lands on this Mac, and the launcher exchanges the code. That ties the installing account to this Mac, which is the local check D-043 asks for: an install alone, with nothing on the Mac, would not count.
     - Slack requires an HTTPS redirect URL, so this needs an HTTPS endpoint on the Mac that the browser accepts. The spike checks whether that is practical ([validation.md](validation.md) item 19).
     - If the install cannot report it, the fallback is a one-time code shown in the CLI, which the user types into the bot's DM. The code also proves that the Slack account belongs to the person at this Mac.
     - The bot token alone cannot tell who installed the app.

<a id="manifest"></a>
**The manifest** (AI; [research.md](research.md#vendors)):

| Need | Scopes and events |
| --- | --- |
| Post, and create and join the private channel | `chat:write`, `groups:write`, `groups:write.invites` |
| Read thread replies and channel posts | `groups:history`, event `message.groups` |
| Receive bot mentions | `app_mentions:read`, event `app_mention` |
| Receive the fallback registration code in the bot's DM | `im:history`, event `message.im`, the App Home Messages tab |
| Upload and download files in threads | `files:write`, `files:read` |
| Buttons | Interactivity on. Socket Mode on, with an app-level token that has `connections:write` |

<a id="what"></a>
## What goes where

The event catalog in [launcher.md](launcher.md#events) lists every event with its destination. Messages are built from fixed templates and values; free text from sessions never goes to Slack ([launcher.md](launcher.md#events)). The rules behind it:

- **Every report is a new message.** Barrel never edits a message (Q10).
- **Every message names its run.** It carries the run's request name, because the runs of a project share one channel (Q18).
- **The channel itself** gets the big events (Q10, option 10-a A):
  - a run's start, and its stage changes
  - the start and end of each large and medium topic
  - questions, review requests, and requests for things only the user can do
  - leaves abandoned after retries
  - a whole-run stop for usage limits, and the resume
  - completion of the run: the final report
  - snapshots (Q10 default), the "stopped" and "resumed" messages (Q10-2), and a run's cancellation (archived Q-009)
- **Threads** get the details (Q10, option 10-a A):
  - A leaf's start, plan approval, completion and retries go into the thread of its medium topic's start message.
  - Interview-stage details, such as research starting and ending, go into the thread of that stage's start message.
  - Reminders and the orchestrator's replies to follow-ups go into the question's own thread.

<a id="notify"></a>
## Notifications (Q10 default)

- **Mentions.** Barrel mentions the user only when they have to act: questions, review requests, things only the user can do, a cancel waiting for keep or discard, and completion of the run.
- **A push for every report.** The user sets the channel to "all new posts" to get one; the bot cannot change that setting.
- **The `text` field.** Every message's `text` carries its summary, because phone notifications show only `text`.
- **The progress line.** Each channel message ends with a progress line, so the latest message always shows the current state.
  - From S7 on, the line reads like "말단 34/80 완료 · 진행 3 · 막힘 1 · 답 대기 1". Leaves are split one medium topic at a time, so the total is the number of leaves split so far (AI).
  - Before S7, the line shows the stage and the open questions instead, for example "요구사항 인터뷰 · 답 대기 1" (AI).
  - With several runs, the line covers the run the message belongs to, and a snapshot covers them all (Q18; AI).

<a id="rules"></a>
## Sending rules

- **Send only on change** (Q10 default). Send only when something changes. An error that is being retried is reported only when it resolves.
- **Batching** (Q10 default). Thread details that pile up within one minute go out as one message.
- **Rate** (Q10 default). No more than one message per second per channel.
- **Restart** (Q10 default). When the launcher restarts, it says so. An update's restart is the exception: updates are never announced (Q21).
- **Queue** (AI; [research.md](research.md#vendors)):
  - Messages go out in order through a per-channel queue in `slack.json`.
  - On HTTP 429 the queue waits for `Retry-After`.
  - Every message carries its event ID in its metadata, so a restart never posts it twice ([launcher.md](launcher.md#recovery)).
- **Message format** (AI; [research.md](research.md#vendors)). Text is posted as a `markdown` block, which renders standard Markdown, up to 12,000 characters per message. Anything longer is attached as a file in the thread.

<a id="snapshot"></a>
## Snapshots

- A snapshot is a new message (Q10, option 10-b X). It is sent:
  - when the user writes "상태" in the channel or mentions the bot
  - when a stage changes or a large topic ends
  - when work is running and the channel has been quiet for three hours. This doubles as a sign that Barrel is alive.
    - "Work is running" means at least one session is active.
    - While everything waits on the user, the question reminders take the snapshot's place (AI).
- It contains, for each run of the project, under its request name (Q18):
  - the large and medium topics with their status
  - the running sessions, with engine and model
  - leaves that are blocked or waiting for an answer, and why, from the fixed set of reasons ([launcher.md](launcher.md#events))
  - questions waiting for an answer, with thread links, and posts not sent yet
- It carries a [작업 중지] button, which stops every run of the project (Q10-2 default; Q18).

<a id="questions"></a>
## Questions and requests

- **Header and reply line.**
  - A question starts with `[{project}-질문]`, followed by the run's request name, and asks for the reply in its thread (Q10, Q18).
  - The exact reply line is "이 스레드에 답해 주세요" (Q10-2 default).
  - The launcher adds both, so no model writes them ([interviews.md](interviews.md#posting)) (AI).
  - The project name is the name set at the project's first run, by default the planning repo's folder name (Q10-2 default).
  - In English mode the header is `[{project}-Question]` (Q10-2 default).
- **Content** follows [interviews.md](interviews.md#format).
- **Buttons.**
  - **Options.** A question with options carries one button per option. A reply in the thread still counts as an answer (AI).
  - **Approvals.** A review carries [승인 rN], or [Approve rN] in English mode, and only that button approves (archived D-045; Q17). A reply in a review thread is a change request or a question. A button on an older revision is refused with a link to the current one ([interviews.md](interviews.md#approvals)).
  - **Who may press.** Only the registered user's presses count ([security](#security)).
- **Reminders.** A question that must be answered and has no reply is mentioned again 1, 2, 4 and 8 hours after it was posted, then every 8 hours (Q10).
  - Each reminder is a reply in the question's thread that mentions the user (Q10-2 default).
  - The clock starts when the question actually reaches Slack (Q10-2 default).
  - "Must be answered" covers every question and request Barrel posts (Q10-2 default, from Q01 and Q06). Barrel asks only what the AI cannot decide, so each one holds up some work: an interview stage, a review, or a leaf.
  - Reminders pause while the run is stopped (Q10-2).
- **A reply in a question's thread is the answer** to that question (Q10 default).
  - The launcher records it as an answer unit ([interviews.md](interviews.md#recording)).
  - Edits, deletions, late replies and attachments follow [interviews.md](interviews.md#replies).
- **Credentials are never asked for in Slack** (Q20). A request for one says what is needed and that a dialog is open on the Mac ([memory.md](memory.md#secrets)).
- **Long content goes by attachment or path** (Q10 default 8: "긴 내용은 레포 문서 경로나 커밋·PR 링크로 대신한다"). A link to a commit or a pull request is used only once it has been pushed (AI).

<a id="launcher-requests"></a>
**Requests the launcher raises itself** (AI). Some requests come from the launcher, not from an orchestrator, so no model writes them. Each has a fixed template, written in English and turned into Korean once with Skill-Techblog, like the progress reports (Q10, option 10-c K). Each is a `request` post with a mention:

| Request | When | Asks the user to |
| --- | --- | --- |
| Log in again | An account's login expired ([sessions.md](sessions.md#accounts)) | Run the given login command for that account; the account comes back once it passes |
| Log in to clone | A repo in `repos.json` could not be cloned ([runs.md](runs.md#clones)) | Sign in to the git host; the clone is tried again |
| Calibration failed | A CLI update broke step2step's screen reading, and no Barrel update fixed it ([launcher.md](launcher.md#versions)) | Nothing at once: that CLI is left out until a fix arrives. The request says so and names the CLI and its version |
| Enter a credential | An orchestrator asked for one with `barrel secret ask` | Type it into the dialog open on the Mac ([memory.md](memory.md#secrets)) |
| Save the sudo password | A command needs administrator rights, and no password is saved yet, or the saved one stopped working ([task-execution.md](task-execution.md#sudo)) | Type it once into the dialog open on the Mac |
| Run the skill again | An account folder could not be repaired after a version mismatch ([launcher.md](launcher.md#versions)) | Run the `barrel` skill, which repeats setup |

<a id="routing"></a>
## Which run a message belongs to

A project can have several runs at once (Q18), so the launcher decides which run each message from the user belongs to (Q18; details AI):

- **A reply in a thread** belongs to the run that owns the thread: a question's thread, a review's thread, a medium topic's thread or a run's start message.
- **A post in the channel itself**, outside any thread:
  - **Command words** for the whole project: "상태", "중지", "재개", "화면", and language and sleep changes ([commands](#commands)).
  - **"취소"** asks which run to cancel, with a button per run, unless only one run is active.
  - **Anything else** is an instruction. With one active or stopped run, it goes to that run. With several, the launcher asks with a button per run, under their request names, and routes the post once the user presses one.
- **No run at all.** A post gets the fixed reply that says how to start one: run the `barrel` skill with the request ([runs.md](runs.md#after)). Slack never starts a run (Q22-2).

<a id="commands"></a>
## Commands and instructions

A post that consists of one of these words is a command:

| Word | English mode also accepts | Does | Source |
| --- | --- | --- | --- |
| "상태", or a bot mention | `status` | Posts a snapshot of every run of the project | Q10 |
| "중지" | `stop` | Stops every run of the project at once, without confirmation | Q10-2 default; Q18 |
| "재개" | `resume` | Resumes the runs that were stopped | Q10-2; Q18 |
| "취소" | `cancel` | Cancels one run, then asks keep or discard ([runs.md](runs.md#cancel)) | archived Q-009; Q17 |
| "언어 영어", "language korean" and similar | the same | Switches the Slack language | Q10-2 default |
| "절전 os", "절전 ac", "절전 always" | `sleep os` and so on | Sets the sleep policy ([launcher.md](launcher.md#sleep)) | archived D-047; Q17 |
| "화면" | `view` | Opens the project's PC view on this Mac | Q10-2, the method is AI |

The English command words, the cancel word and the sleep words are AI.

- **Instructions.** Any other post in the channel, and any reply in a report thread, is passed to its run's orchestrator as an instruction ([routing](#routing)) (Q10 default; Q18).
  - The launcher records every instruction verbatim as an answer unit before passing it on ([interviews.md](interviews.md#recording)).
  - An instruction may change settings in `.barrel/config.json`, such as the model assignment or the cascade default. The orchestrator then edits the file, and the change applies from the next session ([sessions.md](sessions.md#engines)) (Q12 analysis; AI).
  - If an instruction changes something decided earlier, the conflicting decisions are asked as well ([workflow.md](workflow.md#cascade); Q10 default, Q01).
- **A stopped run.** Instructions are recorded and applied on resume (Q10-2).
- **Cancel** (archived Q-009; Q17):
  - The run stops at once ([launcher.md](launcher.md#stop)).
  - A post in the run's thread shows what the run changed and has not delivered, with [보관] (keep) and [폐기] (discard) buttons and a mention.
  - Nothing is deleted until the user picks ([runs.md](runs.md#cancel)).

<a id="language"></a>
## Language

- **The choice.** Slack messages go out in Korean or English. Korean is the default, and the language stays as set until changed (Q10).
- **One setting for the PC**, in `~/.barrel/settings.json`, used by every project (Q10-2 default).
  - It changes with the words above, from the next message on.
  - The PC view follows it too.
- **In Korean** (Q10, option 10-c K):
  - Progress reports are fixed templates that the launcher fills in. No model is called per report.
  - The templates are written in English at development time and turned into Korean once with Skill-Techblog.
  - Task names and request names use the Korean display names made when the tree is split and when the run starts ([task-tree.md](task-tree.md#names)).
  - Text that differs every time is written by the Korean-writer session with Skill-Techblog ([interviews.md](interviews.md#language)). That covers questions, review documents, the final report, and replies. Reports link to it.
  - If the Korean writer fails, the post waits as unsent; English is not sent instead ([interviews.md](interviews.md#posting)) (Q10; AI).
- **In English** (Q10-2 default):
  - The English templates and the English sources go out as they are, without Skill-Techblog.
  - The question header is `[{project}-Question]`.
- **Corrections:** when the user asks to correct Korean text, the English source is corrected first, and the Korean is written again from it (Q08, option A).

<a id="security"></a>
## Permissions and content (Q10 default)

- The channel is private.
- Only the registered user's replies, instructions, commands and button presses are accepted (archived D-043). Every event is checked against the stored team and user IDs.
- Credentials, tokens and keys are masked before anything is sent.
- Credentials are never asked for in Slack (Q20). One the user pastes by mistake is masked before it is recorded, and moved to the Keychain ([memory.md](memory.md#secrets)).
- The PC view's address contains its token, so it is never sent to Slack (Q10-2).

<a id="outage"></a>
## When Slack is unreachable

- **Barrel waits** until the connection is back (Q10).
  - It then sends one snapshot and the questions that piled up, all at once.
  - It does not replay what happened in the meantime.
- **Work continues; only sending waits** (Q10-2 default).
  - A leaf whose question has not been sent yet waits alone, as with any blocked leaf (Q01).
  - Reminder clocks start when each question actually reaches Slack (Q10-2 default).
- **No macOS notification and no terminal status command.** Instead, the PC view shows the Slack connection state and the number of unsent posts (Q10-2 default).

<a id="canonical"></a>
## Slack is not the source of truth

Slack messages are reports. The truth is the memory in the repo and the run state (Q10 default). If the workspace's free-plan history limit hides old messages, nothing is lost.

The launcher also keeps which event belongs to which thread in `slack.json`. After a restart it keeps posting into the same threads (Q10 default).
