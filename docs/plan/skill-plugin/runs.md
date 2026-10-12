# Runs, branches and sharing

A run is one execution for a project, from a start input to completion. This document covers:
- how a run starts
- the IDs Barrel gives to runs, task nodes and memory units
- the branches and worktrees a run uses
- how the result is delivered
- how `.barrel/` is shared across runs, PCs and teammates
- what happens after a run

Most of it was filled in during the 2026-10-11 review, where the design was silent. It is tagged `(AI)`. User decisions from the archived app plan are carried over where they fit ([migration.md](migration.md#archived)).

<a id="start"></a>
## Starting a run

- **One active run per project per PC** (AI).
- **One repo per project.** Projects that span several repos are not carried into this version ([open-decisions.md](open-decisions.md#not-carried)).
- **What the skill does** depends on the project's state ([plugin.md](plugin.md#skill)). The skill asks one thing in the CLI: the start input, when it was invoked without one (flow 2). Everything else that needs the user goes to Slack (Q03-3).

| The project | The skill |
| --- | --- |
| Has no run, or its last run is complete | Starts a new run |
| Has an active run | Passes the text it was invoked with to that run's orchestrator as an instruction, the same path as a Slack instruction (`barrel instruct`). Then it opens the PC view (AI; opening the view is the Q10-2 default) |
| Has a stopped run | Passes the text to that run as an instruction. The instruction is recorded and applied on resume, like anything that arrives while a run is stopped (Q10-2). The skill reports that the run is stopped and how to resume it: "재개" in Slack, or [재개] in the PC view. Then it opens the PC view (AI) |

**Before a new run starts** (AI):
1. **The folder.**
   - **A new concept:** the skill creates a folder named after the project in the current folder, runs `git init` and makes an empty first commit. A worktree needs a commit to branch from. The start report gives the path.
   - **A folder to maintain that is not a git repo:** the skill runs `git init` and commits the existing files as they are. The start report says so (archived repositories.md#start: such a folder is analyzed first).
2. **Uncommitted changes** in the user's checkout are not part of the run. The start report says so (archived repositories.md#start keeps the user's changes).

**The launcher then** (AI):
1. Records the base: the branch and the commit the run starts from.
2. Creates the run branch and the integration worktree ([branches](#branches)).
3. Writes the default `.barrel/config.json` on the run branch if the project has none, with the repo folder name as the project name. It also writes `.barrel/.gitignore`, which keeps the generated indexes out of git ([sharing](#sharing)).
   - The launcher needs the config before any orchestrator exists: to pick the orchestrator's engine and to name the Slack channel.
   - From then on, among Barrel's sessions only the orchestrator edits the file. People edit it like any other file in the repo (Q12) ([memory.md](memory.md#rules)).
4. Notes the project's earlier run branches that are not merged into the base, for the orchestrator.
5. Creates or reuses the project's Slack channel ([slack.md](slack.md#setup)), opens the PC view, and starts the orchestrator.

**Earlier runs that are not merged** (AI):
- An earlier run's memory and code reach a new run only through that run's branch ([sharing](#sharing)).
- So in S2 the orchestrator asks in Slack whether to include such a branch, and says what it contains.
- If the user says yes, the launcher merges that branch into the new run branch through its git queue.

<a id="ids"></a>
## IDs

| Kind | Format | Example | Unique within |
| --- | --- | --- | --- |
| Run | `<yyyymmdd>-<4 base36 characters>` | `20261011-a7mz` | The project |
| Task node | `T` and its position in the run's tree | `T1.2.3` | Its run. Written `20261011-a7mz/T1.2.3` from outside the run |
| Memory unit | A kind prefix and a short hash | `REQ-k3f9` | The project, across branches and PCs |

- **Memory unit IDs are hash IDs.**
  - The hash is base36 over the unit's kind, summary, creation time and a random nonce. It is 4 characters long, and longer when the kind folder grows or when a new ID collides with an existing one locally (AI).
  - Sequential IDs would collide: two runs on different branches, or two teammates, would both create `REQ-013`.
  - This follows Beads, an issue tracker for coding agents that keeps its data in git. Beads moved from sequential to hash IDs in 0.20.1 (2025-10-31) to stop collisions between agents and branches ([research.md](research.md#prior-art)).
- **A duplicate after a merge.** `barrel memory index` reports it if one ever appears. The unit created later gets a new ID, and the references to it are updated (AI).
- **Answer units are the exception.** They are never edited or renamed ([memory.md](memory.md#rules)).
  - They get 8-character IDs, so a duplicate is not expected.
  - If one ever appears anyway, the orchestrator asks the user how to proceed.
- **Task IDs stay readable.** Each run has its own tree folder, so hierarchical IDs cannot collide ([sharing](#sharing)).
- **IDs are stable.** An ID never changes once given, except in the duplicate case above.

<a id="branches"></a>
## Branches and worktrees

| Worktree | Where | Checked out at | Used for |
| --- | --- | --- | --- |
| The user's checkout | The repo | Whatever the user has | Nothing. Barrel never touches it (AI) |
| Integration | `~/.barrel/projects/<id>/integration/` | The run branch `barrel/<run>` | Merges, post-merge gates, and the orchestrator's work on `.barrel/` |
| Lanes | `~/.barrel/projects/<id>/lanes/<n>/` | A detached HEAD at the run branch's head | One leaf at a time ([task-execution.md](task-execution.md#lanes)) |

- **Lanes use a detached HEAD**, because git does not let one branch be checked out in two worktrees. A leaf commits on its lane's detached HEAD, and the launcher merges that commit into the run branch in the integration worktree (AI).
- **One git queue.** Every git operation in the integration worktree goes through one queue in the launcher: merges, `.barrel/` commits and delivery (AI).
- **No session changes refs.** Hooks stop every Barrel session from running git commands that move refs or rewrite history ([plugin.md](plugin.md#hooks)).
- **The git author** of Barrel's commits is the one the repo already uses (archived Q-012). If none is set, Barrel sets a repo-local author:
  - the GitHub account's name and noreply address, when `gh` is signed in
  - otherwise "Barrel"

<a id="delivery"></a>
## Delivery

- **When.** At completion, after the acceptance check in S8.
  - Delivery is part of S8's exit: a run is not complete until its result is delivered the way `git.delivery` says (archived D-024; 09-29 draft, S8).
  - `git.delivery` is asked once per project ([interviews.md](interviews.md#stack)).
- **How:**

| `git.delivery` | Barrel |
| --- | --- |
| `local` | Does nothing more. The final report names the run branch |
| `push` | Pushes the run branch |
| `pr` | Pushes the run branch and opens a pull request into the base branch |
| `merge` | Merges the run branch into the base branch ([below](#merge)) |

<a id="merge"></a>
**Merging into the base** (AI). Git does not let one branch be checked out in two worktrees, and Barrel never touches the user's checkout. So:
- **The base is not checked out anywhere:** the launcher checks it out in the integration worktree, merges the run branch, and pushes the base if it has a remote.
- **The base is the branch the user has checked out:**
  - **With a remote**, the launcher merges on a temporary branch made from the remote base and pushes that to the base; the user pulls.
  - **Without a remote**, the orchestrator posts a request with the merge command for the user to run. The run waits for that merge ([below](#waiting)).

**Before delivering** (archived repositories.md; details AI):
1. **Re-check the base.** If it moved since the run started, merge it into the run branch and commit the merge, then run every gate of the run.
   - A failing gate becomes a leaf, and S7 continues.
   - Leaves start from the run branch's head, so they work on top of the merged base.
   - Unlike a leaf's trial merge, this merge is kept even when a gate fails ([task-execution.md](task-execution.md#lanes)). Otherwise no leaf could see the change it has to adapt to.
2. **A conflict with the base** becomes a conflict leaf:
   1. The launcher starts the merge in a lane and leaves the conflicted files there.
   2. A task session resolves them by editing files only. Its write set is the conflicted files.
   3. When the leaf's gates pass, the launcher completes the merge commit.
3. **Never bypass branch protection, required reviews or CI.** A protected base turns `merge` into `pr`, and the run waits for that pull request ([below](#waiting)).

<a id="waiting"></a>
**Waiting for a merge** (archived D-024: a requested merge is not a finished merge; details AI). Two cases make a run wait after its work is done: `merge` into a base that only the user can merge, and `merge` that turned into a pull request.
- The orchestrator posts a request with a mention: review and merge the pull request, or run the given command.
- No session runs while the run waits. The launcher checks now and then whether the base contains the run branch.
- When it does, the launcher emits `delivery_done`. An orchestrator then writes and posts the final report, which completes the run ([task-execution.md](task-execution.md#acceptance)).
- With `git.delivery: pr`, nothing waits: the run is complete once the pull request is open, because a pull request is what the user asked for.

**A project with no remote**, usually a new concept, is delivered `local` unless the user chose otherwise. When the delivery scope is asked for such a project, the options include creating a private GitHub repository with `gh` (archived Q-003).

<a id="sharing"></a>
## Sharing `.barrel/` across runs, PCs and teammates

`.barrel/` is tracked by git and shared with the team (Q07, Q12, Q15). Writers on different branches and PCs therefore meet when branches are merged. The rules (AI):

- **Each run has its own task tree:** `.barrel/tasks/<run>/`. Two runs never write the same task file, and each run's Korean display names stay in its own folder.
- **Memory units have hash IDs** ([IDs](#ids)), so units made on different branches do not collide.
- **Generated files are not committed.**
  - The memory and task indexes are listed in `.barrel/.gitignore`, so they never conflict in any merge: not in Barrel's own merges, not in the user's, and not in a pull request merged on a hosted service. Hosted services ignore merge drivers such as `merge=union` ([research.md](research.md#prior-art)).
  - The launcher regenerates them at run start, after every merge, and after every orchestrator turn that changed a unit.
  - In their own checkout, the user runs `barrel memory index` to see them.
- **`config.json` merges like any other file.** A conflict in it during delivery is asked as a question.
- **Memory travels with the code.**
  - `.barrel/` changes are committed on the run branch.
  - They reach later runs and teammates when the run is delivered.
  - A run that is not merged yet is offered in the next run's S2 ([starting a run](#start)).
- **Two clones of one repo** on one PC are two projects, because the project ID includes the folder path ([memory.md](memory.md#run-state)).
- **Each PC has its own Slack app and channel** ([slack.md](slack.md#setup)).
  - Slack spreads an app's events over all of that app's open connections, so two PCs must never share one app.
  - Q09's "one channel per project" therefore holds per PC: a teammate's Barrel has its own channel for the same project ([open-decisions.md](open-decisions.md#ai-defaults)).
  - If `barrel-<project>` is taken, for example by a teammate's channel, the launcher adds a short suffix.

<a id="after"></a>
## After a run

- **The integration worktree is removed**, so the user can check out the run branch (archived D-062; AI).
- **The lanes stay**, with their installed dependencies, for the project's next run (archived D-062; AI).
- **Leftovers are deleted after delivery:** session snapshots, transcript copies and downloaded Slack attachments. The result reports and the event log stay (archived D-062; AI).
- **`barrel project remove`** deletes a project's worktrees and run state. It never deletes branches or the repo (AI).
- **A post when no run is active.** The launcher answers with a fixed message that says how to start one: run the `barrel` skill with the request (AI).
  - Runs start from the skill ([Q03-3](../interview/q03-3-launcher-and-slack.md)).
  - The orchestrator that would have taken the post no longer exists.
