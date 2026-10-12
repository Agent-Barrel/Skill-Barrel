# Projects, runs and delivery

A project is a planning repo and the repos it lists. A run is one execution for one request, from its start input to completion. This document covers:
- what a project is, and how the skill finds it
- how a run starts, and where it starts from
- the IDs Barrel gives to runs, task nodes and memory units
- the branches and worktrees a run uses
- how the result is delivered
- how `.barrel/` is shared across runs, PCs and teammates
- cancelling a run, and what happens after a run
- archiving a project or removing its records

Much of it was filled in where the decisions were silent. That part is tagged `(AI)`. User decisions from the archived app plan are carried over where they fit ([migration.md](migration.md#archived)).

<a id="projects"></a>
## Projects and their repos

A project is a planning repo plus the repos it lists, side by side in one parent folder (archived Q-014, Q-015; Q17, Q17-2).

- **The planning repo** holds `.barrel/`: the memory, task trees, reviews, designs, config, and the list of repos in `repos.json` ([memory.md](memory.md#repos)).
- **The parent folder** is the folder that holds the planning repo. Every repo of the project sits in it, in the folder `repos.json` names (archived Q-014).
- **One repo is the common case.**
  - A single-repo project lists only itself (Q17-2).
  - Its planning repo also holds the code. A small project is never given a separate planning repo (archived Q-015).
- **Several repos** are split by function, such as a frontend and a backend, so each can be deployed and tested on its own. They are not split finer than needed (archived Q-014).
- **No monorepo** unless the user asks for one (archived Q-014).
- **What belongs to one repo** stays in that repo, such as an API's full specification. The planning repo points to it ([memory.md](memory.md#kinds)) (archived Q-015).
- **The repo list changes only with the user's confirmation**, in S5 or S6. Adding or removing a repo is a structural decision (Q17-2).
- **Existing structure is kept.** Barrel never moves, splits or merges repos on its own (archived Q-014, Q-015).

<a id="find"></a>
**Finding the project.** The skill looks at the folder it runs in (AI, from Q17-2; this replaces the `git init` rule that would have broken a parent folder of repos):

| The folder | The project |
| --- | --- |
| A repo with `.barrel/` | That repo is the planning repo |
| A repo without `.barrel/` that a sibling planning repo lists in its `repos.json` | The sibling's project |
| A repo without `.barrel/` that no sibling lists | A single-repo project. The repo becomes its own planning repo |
| A folder that holds a planning repo | That planning repo's project |
| A folder that holds several repos, none of them a planning repo | An existing project of several repos that has never used Barrel. Together with the start input, the skill asks where `.barrel/` should live: in one of these repos, or in a new planning repo in this folder. The new planning repo is the recommendation, because it is the default for projects of several repos (archived Q-015). No repo is added without that answer (archived Q-015: the existing structure is respected; Q17-2) |
| A folder that is neither a repo nor holds one, for a maintenance request | It becomes a repo: `git init`, and the existing files are committed as they are. The start report says so (archived repositories.md#start: such a folder is analyzed first) |
| Any folder, for a new concept | A new project inside it ([below](#new-concept)) |

<a id="new-concept"></a>
**A new concept** (Q17-2: "Barrel creates the planning repo first"; layout AI):
1. The skill creates the parent folder `<current folder>/<project>/` and the planning repo inside it, `<project>/<project>/`, with `git init` and an empty first commit. A worktree needs a commit to branch from.
2. If S5 or S6 settles on several repos, the orchestrator adds them to `repos.json` in its memory turn, after the user confirmed the list. Names such as `<project>-web` and `<project>-api` are an example.
   - When the launcher commits that turn, it creates each new repo in the parent folder, with an empty first commit.
   - The code goes into those repos, and the planning repo keeps only the planning documents (archived Q-015).
3. If one repo is enough, the planning repo also holds the code (archived Q-015).

The start report gives the paths.

<a id="clones"></a>
**Clones** (Q17-2; details AI):
- **What.** At the start of every run, the launcher clones each repo in `repos.json` whose folder is missing from the parent folder. A teammate or a new PC therefore needs only the planning repo.
- **Repos already there** are used as they are. The launcher fetches their remotes and never changes the user's checkout.
- **Credentials.** Clones use the user's own git credentials. If a clone needs a login, a request asks the user to log in (flow 10), and only the work that needs that repo waits (Q01). The invoking session never handles it, because its job ends at the start (Q03-3).

<a id="start"></a>
## Starting a run

- **Each request starts its own run** (Q18; this replaces AI default 35, one active run per project).
  - The skill always starts a new run, even while other runs of the project are active or stopped.
  - The runs go on side by side and are delivered separately. Each has its own run branches, task tree and orchestrator.
- **Changing a run in progress.** The user instructs that run in Slack ([slack.md](slack.md#routing)) (Q18). The skill has no path that passes a request to an existing run.
- **A stopped run** waits for its resume or its cancel. A new request never joins it (Q18 analysis).
- **Shared resources.** The runs of a project share its concurrency and its lanes. The launcher gives their leaves lanes in turn ([task-execution.md](task-execution.md#lanes)) (Q18).
- **The request name** (Q18; AI).
  - The invoking session names the request in a few English words taken from the start input.
  - In Korean mode the Korean writer makes its Korean display name before the run's first post ([task-tree.md](task-tree.md#names)).
  - Every Slack message and the PC view show it.
- **What the skill asks.** Only the start input, when it was invoked without one, and where `.barrel/` should live when [finding the project](#find) needs it. Everything else that needs the user goes to Slack (flow 2, Q03-3).
- **Uncommitted changes** in the user's checkout are not part of the run unless the user says so ([start state](#start-state)). The start report says so (archived repositories.md#start keeps the user's changes).

**The launcher then** (AI):
1. Clones the missing repos ([clones](#clones)).
2. Records the base of each repo: the branch and the commit the run starts from ([start state](#start-state)).
3. Creates the run branch and the integration worktree in each repo ([branches](#branches)).
4. Writes, on the planning repo's run branch, whatever is missing of these files:
   - the default `.barrel/config.json`, with the planning repo's folder name as the project name (Q10-2 default)
   - `.barrel/.gitignore`, which keeps the generated indexes out of git ([sharing](#sharing))
   - `.barrel/repos.json`, which lists the planning repo itself

   The launcher needs the config before any orchestrator exists: to pick the orchestrator's engine and to name the Slack channel. From then on people edit these files like any other, and among Barrel's sessions only the orchestrator changes them (Q12) ([memory.md](memory.md#rules)).
5. Records the start input verbatim as an `answer` unit ([interviews.md](interviews.md#recording)).
6. Gets the request's Korean name, creates or reuses the project's Slack channel ([slack.md](slack.md#setup)), opens the PC view and starts the orchestrator.

**Earlier runs** (Q18; this replaces the S2 question of AI default 36):
- **A run that finished earlier** reaches a later run when the later one is delivered. The later run merges the earlier run's result ([delivery](#delivery)), and conflicting decisions are asked (Q18: "나중에 전달하는 실행은 먼저 끝난 실행의 결과를 합쳐서 맞춘다").
- **A cancelled run whose changes were kept** is never merged automatically. A later run includes it only when the user instructs it to (archived Q-009).
- **A stopped run** is not merged. It goes on when it is resumed.

<a id="start-state"></a>
## Where a run starts from

From archived D-039 and Q-018, which Q17 restored.

- **The default.** A run starts from each repo's current HEAD, and uncommitted changes in the user's checkout are not part of it (AI).
- **The user's work is safe.** The user's own changes and existing policies are always kept. The user's checkout is never touched (archived D-039).

**Developers choose** (archived D-039):
- **When Barrel asks.** In S2 the orchestrator asks in Slack only when the start is unclear: a checkout has uncommitted changes, its HEAD is not on the default branch, or it is behind its remote. Otherwise the run starts from HEAD without a question (AI).
- **Including the uncommitted changes.** The launcher copies them onto the run branch as the run's first commit. The checkout keeps them as they are (AI).
- **Another branch.** The launcher creates the run branch again from the chosen branch, before S3 (AI).

**Non-developers are asked about git first** (archived Q-018):
- **The question.** In plain words: do they know git, and do they follow a git policy for this project?
- **No assumptions.** Being a non-developer is not taken to mean having no git knowledge or policy. A missing answer is not taken as "none" either (archived D-039, Q-018).
- **No policy.** Barrel manages git and decides the start itself. It asks only for the intent behind a choice, in plain words, and keeps the user's own changes untouched.
- **A policy.** Barrel follows it. The answer is recorded, and the project's later runs reuse it.

<a id="ids"></a>
## IDs

| Kind | Format | Example | Unique within |
| --- | --- | --- | --- |
| Run | `<yyyymmdd>-<4 base36 characters>` | `20261013-a7mz` | The project |
| Task node | `T` and its position in the run's tree | `T1.2.3` | Its run. Written `20261013-a7mz/T1.2.3` from outside the run |
| Memory unit | A kind prefix and a short hash | `REQ-k3f9` | The project, across branches and PCs |
| Shared entry | `PREF-` or `EXP-` and a short hash | `PREF-3kd8` | The PC ([memory.md](memory.md#shared)) |

- **Memory unit IDs are hash IDs.**
  - The hash is base36 over the unit's kind, summary, creation time and a random nonce. It is 4 characters long, and longer when the kind folder grows or when a new ID collides with an existing one locally (AI).
  - Sequential IDs would collide. Two runs on different branches, or two teammates, would both create `REQ-013`.
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
| The user's checkouts | The repos in the parent folder | Whatever the user has | Nothing. Barrel never touches them; it only fetches (AI) |
| Integration | `~/.barrel/projects/<id>/runs/<run>/integration/<repo>/` | The run branch `barrel/<run>` of that repo | Merges, post-merge gates, and the `.barrel/` changes in the planning repo |
| Lanes | `~/.barrel/projects/<id>/lanes/<n>/<repo>/` | A detached HEAD at the head of the run branch of the leaf's run | One leaf at a time, with every repo of the project ([task-execution.md](task-execution.md#lanes)) |

- **Each run has its own integration worktrees**, because each run has its own run branches (Q18; AI).
- **Lanes use a detached HEAD**, because git does not let one branch be checked out in two worktrees. A leaf commits on its lane's detached HEAD, and the launcher merges that commit into the run branch in the integration worktree (AI).
- **The memory queue does the git work.** Every git operation in the integration worktrees goes through the project's memory queue ([memory.md](memory.md#queue)): merges, `.barrel/` commits and delivery (Q24; AI).
- **No session changes refs.** Hooks stop every Barrel session from running git commands that move refs or rewrite history ([plugin.md](plugin.md#hooks)).
- **The git author** of Barrel's commits is the one each repo already uses (archived Q-012). If none is set, Barrel sets a repo-local author:
  - the GitHub account's name and noreply address, when `gh` is signed in
  - otherwise "Barrel", replaced by the GitHub identity in new commits once GitHub is connected

  It never changes the global git config or past commits (archived Q-012).
- **Every Barrel commit carries a `Barrel-Run: <run>` trailer** (AI). It tells Barrel's commits from the user's, which is how direct edits are found ([workflow.md](workflow.md#edits)).

<a id="delivery"></a>
## Delivery

- **When.** At completion, after the acceptance check in S8.
  - A run is complete only when every repo it changed is delivered the way `git.delivery` says (archived D-024; 09-29 draft, S8).
  - A delivery that succeeded in some repos only is not completion (archived D-024).
- **The delivery scope** (archived Q-001; Q17):
  - A developer chooses it once per project ([interviews.md](interviews.md#stack)).
  - A non-developer is not asked. Barrel merges into the base automatically, unless the user named a git policy of their own ([start state](#start-state)) (archived Q-001, Q-018).
- **How:**

| `git.delivery` | Barrel, in each repo the run changed |
| --- | --- |
| `local` | Does nothing more. The final report names the run branches |
| `push` | Pushes the run branch |
| `pr` | Pushes the run branch and opens a pull request into the base branch |
| `merge` | Merges the run branch into the base branch ([below](#merge)) |

- **Hosts** (archived Q-017; Q17).
  - Pull requests, new remote repositories and remote merges are automated for GitHub, through `gh`.
  - With another host, Barrel clones and pushes with the user's existing credentials. The user opens and merges requests there: `pr` and a remote `merge` become `push` plus a request to the user (AI).
  - Barrel never moves a repo to GitHub.
- **GitHub not connected** (archived Q-002).
  - Barrel works on the Mac, with local commits and merges.
  - When a delivery needs a remote, Barrel offers the GitHub connection again (`gh auth login`), and the user may still skip it.
  - If skipped, the delivery stays local, and the final report says so (AI).

<a id="merge"></a>
**Merging into the base** (AI). Git does not let one branch be checked out in two worktrees, and Barrel never touches the user's checkout. So, in each repo:
- **The base is not checked out anywhere:** the launcher checks it out in the integration worktree, merges the run branch, and pushes the base if it has a remote.
- **The base is the branch the user has checked out:**
  - **With a remote**, the launcher merges on a temporary branch made from the remote base and pushes that to the base; the user pulls.
  - **Without a remote**, the orchestrator posts a request with the merge command for the user to run. The run waits for that merge ([below](#waiting)).

**Before delivering** (archived repositories.md; details AI):
1. **Re-check the base** in every repo. It may have moved since the run started, for example because another run of the project was delivered (Q18). If it moved, merge it into the run branch, commit the merge, then run every gate of the run.
   - A failing gate becomes a leaf, and S7 continues.
   - Leaves start from the run branch's head, so they work on top of the merged base.
   - Unlike a leaf's trial merge, this merge is kept even when a gate fails ([task-execution.md](task-execution.md#lanes)). Otherwise no leaf could see the change it has to adapt to.
2. **Merge earlier runs' results** (Q18). Some earlier runs of the project may be complete but not in the base, because they were delivered as `local`, `push` or `pr`. Their run branches are merged too, so the later run carries the earlier result. Gates run as in step 1. Cancelled runs are left out ([start](#start)).
3. **Check the decisions that came with the merges** (Q18; AI). Decisions from the base or from earlier runs are compared with the run's own. A conflict is asked as a question with its cascade ([workflow.md](workflow.md#cascade)).
4. **A conflict with the base** becomes a conflict leaf:
   1. The launcher starts the merge in a lane and leaves the conflicted files there.
   2. A task session resolves them by editing files only. Its write set is the conflicted files.
   3. When the leaf's gates pass, the launcher completes the merge commit.
5. **Never bypass branch protection, required reviews or CI.** A protected base turns `merge` into `pr`, and the run waits for that pull request ([below](#waiting)).

<a id="waiting"></a>
**Waiting for a merge** (archived D-024: a requested merge is not a finished merge; details AI). Two cases make a run wait after its work is done:
- `merge` into a base that only the user can merge
- `merge` that turned into a pull request

While waiting:
- **The request.** The orchestrator posts a request with a mention: review and merge the pull request, or run the given command.
- **No sessions.** No session runs while the run waits. The launcher checks now and then:
  - **A pull request** is judged by its state, through `gh`:
    - Merged: the delivery is done.
    - Closed without a merge: the user is asked whether to reopen it, deliver another way, or leave the run undelivered.
    - Whether the base contains the run branch is not used, because squash and rebase merges leave the branch out of the base's history.
  - **A merge the user runs** is judged by the base containing the run branch.
- **The end.** The launcher emits `delivery_done`. An orchestrator then writes and posts the final report, which completes the run ([task-execution.md](task-execution.md#acceptance)).

With `git.delivery: pr`, nothing waits: the run is complete once the pull requests are open, because a pull request is what the user asked for.

**A repo with no remote** is delivered `local` unless the user chose otherwise, which is the usual case for a new concept (archived Q-003).
- A developer is offered a new private GitHub repository, created with `gh`, when the delivery scope is asked.
- A non-developer chooses once, when connecting GitHub at setup, whether new projects are saved to private GitHub repositories automatically ([plugin.md](plugin.md#setup)). That can be turned off per project in `.barrel/config.json`.

<a id="sharing"></a>
## Sharing `.barrel/` across runs, PCs and teammates

`.barrel/` is tracked by git and shared with the team (Q07, Q12, Q15). Writers on different branches and PCs therefore meet when branches are merged. The rules (AI):

- **Each run has its own task tree:** `.barrel/tasks/<run>/`. Two runs never write the same task file, and each run's Korean display names stay in its own folder.
- **Memory units have hash IDs** ([IDs](#ids)), so units made on different branches do not collide.
- **Generated files are not committed.**
  - The memory and task indexes are listed in `.barrel/.gitignore`, so they never conflict in any merge: not in Barrel's own merges, not in the user's, and not in a pull request merged on a hosted service. Hosted services ignore merge drivers such as `merge=union` ([research.md](research.md#prior-art)).
  - The launcher regenerates them at run start and after every commit of the memory queue.
  - In their own checkout, the user runs `barrel memory index` to see them.
- **`config.json` and `repos.json` merge like any other file.** A conflict in them during delivery is asked as a question.
- **Memory travels with the code.**
  - `.barrel/` changes are committed on the run branch of the planning repo.
  - They reach later runs and teammates when the run is delivered.
  - A later run merges the result of an earlier run that is complete but not delivered to the base ([delivery](#delivery)) (Q18).
- **Two clones of one planning repo** on one PC are two projects, because the project ID includes the folder path ([memory.md](memory.md#run-state)).
- **Each PC has its own Slack app and channel** ([slack.md](slack.md#setup)).
  - Slack spreads an app's events over all of that app's open connections, so two PCs must never share one app.
  - Q09's "one channel per project" therefore holds per PC: a teammate's Barrel has its own channel for the same project ([open-decisions.md](open-decisions.md#ai-defaults)).
  - If `barrel-<project>` is taken, for example by a teammate's channel, the launcher adds a short suffix.

<a id="cancel"></a>
## Cancelling a run

From archived Q-009, which Q17 restored. The previous design had dropped it by misreading Q10-2, whose option C was about how stop works. Details AI.

- **Where.** In Slack only:
  - the word "취소" in one of the run's threads
  - or "취소" in the channel, with buttons to pick the run ([slack.md](slack.md#commands))

  The PC view keeps only stop and resume (Q10-2).
- **What happens** (archived Q-009):
  1. **The run stops at once,** like a stop of that run alone: no new session, running turns interrupted, sessions closed ([launcher.md](launcher.md#stop)). The project's other runs go on.
  2. **A short summary** shows what the run changed and has not delivered: for each repo, the commits and files on the run branch that are not in the base. The post carries [보관] (keep) and [폐기] (discard) buttons.
  3. **Nothing is deleted** until the user picks.
  4. **Keep.**
     - The run branches stay, with their memory changes, and the run is marked cancelled.
     - It is never completed, merged or resumed on its own. A later run includes it only when the user instructs it to (archived Q-009).
  5. **Discard.** The run branches and the run's worktrees are deleted. The run state keeps the run's records until the project's records are removed.
- **Never undone by a cancel** (archived Q-009): the user's own changes, code already delivered, deployments, and tools installed on the PC.

<a id="after"></a>
## After a run

- **The integration worktrees are removed**, so the user can check out the run branch (archived D-062; AI).
- **The lanes stay**, with their installed dependencies, for the project's next leaves (archived D-062; AI).
- **Leftovers are deleted after delivery:** session snapshots and transcript copies. Downloaded Slack attachments are deleted once the last work that needs them is done (archived D-062, D-063). The result reports and the event log stay.
- **A post when no run is active.** The launcher answers with a fixed message that says how to start one: run the `barrel` skill with the request (Q22-2).
  - Runs start from the skill only; Slack never starts one (Q03-3, Q22-2).
  - The orchestrator that would have taken the post no longer exists.

<a id="archive"></a>
## Archiving a project or removing its records

From archived Q-020 and Q-021, added after the second readiness check. Commands AI.

- **Archive** (`barrel project archive`).
  - Hides the project from Barrel.app's list and from the PC views.
  - Its run state stays, and it can be opened again (archived Q-020).
- **Remove its records** (`barrel project remove`). Deletes the project's run state and worktrees (archived Q-020):
  - Runs in progress are stopped first, and their unmerged run branches stay in the repos.
  - It never touches the repos, their `.barrel/`, remotes or deployments.
  - Shared memory is cleaned as archived Q-021 says ([memory.md](memory.md#shared)).
- **How the user asks.** Both work through the skill, by asking for them in plain words, and through the `barrel` command.
