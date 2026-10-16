# Task tree

<a id="levels"></a>
## Levels

- **The tree.** Work is split into a tree: large topic, then medium topic, then leaf (small topic). The tree is executed from the top down, recursively (insight).
- **Depth varies** (insight: "프로젝트의 특성에 맞춰 더 세분화된 분류, 덜 세분화된 분류도 가능"). The orchestrator gives the tree as many levels as the project needs, two at least. The rules in these documents name three levels and apply by position (AI):
  - **Large topics** are the top level.
  - **Medium topics** are the nodes whose children are leaves. Every rule that names a medium topic applies to them: the split when its turn comes, its Slack thread, the handoff, the regression check and the memory consolidation at its end.
  - **Leaves** are the nodes without children.
  - In a two-level tree, each large topic is also its own medium topic. In a deeper tree, the levels in between are split in S5 together with the large topics, and the S5 review shows the top two levels (Q06). They are marked `group`.
- **One tree per run.** Each run has its own tree, in `.barrel/tasks/<run>/` of the planning repo ([runs.md](runs.md#sharing)). Several runs of a project each have their own (Q18).
- **Node IDs** are hierarchical within the run: `T1` for a large topic, `T1.2` for a medium topic, `T1.2.3` for a leaf. From outside the run, a node is written `<run>/T1.2.3`. An ID never changes once given (AI).

<a id="split"></a>
## When nodes are split

| Nodes | Split when | Reviewed by the user |
| --- | --- | --- |
| Large and medium topics | After the functional spec, and the wireframes and API rules where they apply, in S5 (Q06; [workflow.md](workflow.md#design)) | Together with the intent summary (Q01, Q06), as deep as the impact level asks ([workflow.md](workflow.md#depth), Q13):<br>• full: every large and medium topic<br>• extended: the affected topics<br>• local: only the short intent summary |
| Leaves | When their medium topic's turn comes, following the planning loop in [memory.md](memory.md#loop) (Q06) | No. Each leaf's plan passes the intent check instead ([task-execution.md](task-execution.md#lifecycle)) |

- Splitting may show that something has to differ from the first direction. Barrel asks about it only under the rules in [workflow.md](workflow.md#asking) (Q06).
- Medium topics run in tree order. When the current medium topic's leaves are all blocked or running and a lane is free, the orchestrator may split and start the next medium topic that does not depend on the blocked work (Q01, AI).
- Design work before S5 and S6, the wireframes and the detailed design, is done by designer sessions, not by leaves. It produces review material, not product code ([workflow.md](workflow.md#design)) (AI).

<a id="size"></a>
## Leaf size

A leaf must meet all four conditions (Q06 default):

1. One fresh session can finish it without context compaction.
2. It has one result.
3. The files it writes can be listed in advance.
   - If they cannot, the orchestrator investigates first with a context-gathering subagent (Q02).
   - Only an investigation too long for a subagent becomes a read-only leaf. It writes a report under the run state's `outputs/`, and an `exists` gate checks for the report (09-29 draft, AI).
4. Its verification is fixed: gate commands with the expected results.

A leaf also carries no open decision. If one remains, it is resolved first, from documents or by a question (09-29 draft, Q01).

<a id="tests"></a>
**Tests come from an earlier leaf** (AI; archived D-024, P-001: self-reports are not evidence, and the worker is not the judge).
- When the tests a leaf must pass do not exist yet, a test leaf writes them first. Its own gates check that the tests exist and run.
- The implementing leaf depends on the test leaf. It lists the tests in its `read_set`, not in its `write_set`, so it cannot change them.
- So the tests exist before the implementing session starts, and the must-fail-first check can run on them ([task-execution.md](task-execution.md#lifecycle)).
- A leaf that keeps existing behavior, such as a refactor, uses the existing tests and sets `expect_baseline_fail: false` ([fields](#fields)).

<a id="files"></a>
## Files

Each node is one file in `.barrel/tasks/<run>/` of the planning repo, tracked by git (Q15). The contract body is in English (Q08). The header looks like this:

```markdown
---
id: T1.2.3
level: leaf                 # large | group | medium | leaf
parent: T1.2
title: Add the Google sign-in button to the login page
depends_on: [T1.2.1]        # T1.2.1 wrote the tests this leaf must pass
status: planned             # planned | done | abandoned  (durable only, Q15)
commit: {}                  # per repo, set when done: {shop-web: 3f2a9c1}
difficulty: normal          # light | normal | hard (sessions.md)
write_set: [shop-web:src/auth/login.tsx]
read_set: [shop-web:src/auth/session.ts, shop-web:src/auth/login.test.tsx, shop-api:docs/api/auth.yaml]
resources: []               # ports, databases, paths outside the repo, shared environments, services, accounts (archived D-032)
memory_units: [REQ-k3f9, FEAT-2m7q, SCR-a81k, API-4qzt, DEC-x81c, CON-p4tz, IMP-b2n7]
memory_writes: [IMP-b2n7]   # existing units this leaf may change (Q24)
packages: []                # new packages this leaf may add, already checked (Q19)
secrets: []                 # Keychain names this leaf may use or store, never see (memory.md#secrets)
browser: false              # gets the browser-automation server (task-execution.md#user-only)
review: [visual]            # code (archived Q-004), visual (Q17)
expect_baseline_fail: true  # false when the leaf must keep existing behavior
gates:
  unit: {spec: {shell: "npm test -- login"}, every_turn: true, repo: shop-web}
---
```

**Paths name their repo** (AI; Q17). A path in `write_set` or `read_set` is written `<repo folder>:<path>`, with the folder from `repos.json` ([memory.md](memory.md#repos)). In a single-repo project the prefix may be left out. A gate runs in the lane's folder for its `repo`.

A leaf's body is its contract (archived orchestration.md#task-input, 09-29 draft):

- **Intent:** the one result, and why it is wanted. Links point to the units.
- **Scope:** what to change, what must not change, and the behavior to preserve.
- **Behavior:** inputs, outputs, errors, edge cases.
- **Verification:** the gate commands and the expected results. For a UI leaf, also the approved design it must match ([task-execution.md](task-execution.md#review)).
- **Memory:** what the leaf should record when it ends, beyond what it builds ([memory.md](memory.md#finish)).
- **When something is missing:** the last rule is always the same: "If you need a decision that is not in this contract or its units, do not guess. Ask."

Large and medium nodes hold a short description and their children; they have no contract (AI).

<a id="fields"></a>
## Contract fields

| Field | Origin | Source |
| --- | --- | --- |
| `id`, `title`, `depends_on`, `expect_baseline_fail`, `expected_gate_seconds`, `artifacts`, `budget` | The unit loop's `Unit` (`barrel/core/unitloop.py:178-191`) | Reused |
| `gates` | The roadmap key that `load_roadmap` parses into `Unit.layers` (`barrel/core/unitloop.py:183`, `:216`) | Reused. The `repo` key is new (AI; Q17) |
| Body (the contract) | Was `prompt` / `prompt_file` | Reused |
| `memory_units` | Was `references`; now the units read in the planning loop | Q07 default |
| `memory_writes` | New. The existing memory units the leaf may change in its memory turn. Also used by the parallel rule | Q24 |
| `packages` | New. The packages the leaf may add, checked before the contract is committed ([task-execution.md](task-execution.md#packages)) | Q19; AI |
| `difficulty` | Replaces `model` and `effort`, which now come from `.barrel/config.json` | Q12, Q16 |
| `write_set` | New. Checked before commit, and used to decide what may run in parallel. Paths name their repo | 09-29 draft, Q14; Q17 |
| `read_set`, `resources` | New. Used to decide what may run in parallel ([task-execution.md](task-execution.md#lanes)) | archived D-032 |
| `secrets`, `browser` | New. What the leaf may use for things only the user can grant ([task-execution.md](task-execution.md#user-only)) | AI; Q20 |
| `level`, `parent` | New. The tree; `group` marks a level between the large and the medium topics | Q06; insight; AI |
| `review` | New. `code` for an independent code review, `visual` for a comparison with the approved design | archived Q-004; Q17 |
| `status`, `commit` | New. Durable status only. `commit` holds one commit per repo | Q15; Q17 |

- **Gate layers** stay as the unit loop defines them: `exists`, `build`, `unit`, `behavior`, `integration`, `perf` (`barrel/core/gates.py:25`, parsed at `:45-68`).
- **`expect_baseline_fail`** is on by default: a leaf's gates must fail before work starts ([task-execution.md](task-execution.md#lifecycle)). A leaf whose job is to keep behavior unchanged, such as a refactor, has gates that already pass, so it sets the field to false (unit loop field, `barrel/core/unitloop.py:187`; use AI).

<a id="status"></a>
## Status

- **In the task file:** only durable status. `planned`, `done` (with its commits) or `abandoned` (with the reason, in the body) (Q15).
  - The orchestrator writes the contract, `planned` and `abandoned`.
  - The launcher writes `done` and the commits in the leaf's finishing turn ([memory.md](memory.md#finish)) (AI).
  - Every write goes through the memory queue (Q24).
- **In the run state**: `run.json` of the run holds running, blocked, waiting for an answer, attempts, sessions and lanes (Q15). The project's `in-progress.json` lists the running leaves of all its runs with their `memory_writes` (Q24). The launcher writes both ([memory.md](memory.md#run-state)).

<a id="names"></a>
## Korean display names

In Korean mode, every node gets a Korean display name for Slack and the PC view (Q10, option 10-c K). So does the run's request name (Q18).

The names stay out of the task files, because contracts are English only (Q08). They live in `.barrel/tasks/<run>/display-names.ko.json`, a map from node ID to name, with the request name under `request` (AI):
- The Korean-writer session writes them in batches, and the launcher stores them.
- The request name gets its Korean name first, before the run's first post ([runs.md](runs.md#start)).
- Large and medium topics get theirs when the S5 review document is written.
- Leaves get theirs when their medium topic is split.

If the Slack language is switched from English back to Korean, the missing names are written in one batch then (Q10-2 default).
