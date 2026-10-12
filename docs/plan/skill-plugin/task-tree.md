# Task tree

<a id="levels"></a>
## Levels

- **The tree.** Work is split into a tree: large topic, then medium topic, then leaf (small topic). The tree is executed from the top down, recursively (insight).
- **Depth varies.** A project may need more or fewer levels; the orchestrator adapts the depth to the project (insight).
- **One tree per run.** Each run has its own tree, in `.barrel/tasks/<run>/` ([runs.md](runs.md#sharing)).
- **Node IDs** are hierarchical within the run: `T1` for a large topic, `T1.2` for a medium topic, `T1.2.3` for a leaf. From outside the run, a node is written `<run>/T1.2.3`. An ID never changes once given (AI).

<a id="split"></a>
## When nodes are split

| Nodes | Split when | Reviewed by the user |
| --- | --- | --- |
| Large and medium topics | After the functional spec, in S5 (Q06) | Together with the intent summary (Q01, Q06), as deep as the impact level asks ([workflow.md](workflow.md#depth), Q13):<br>• full: every large and medium topic<br>• extended: the affected topics<br>• local: only the short intent summary |
| Leaves | When their medium topic's turn comes, following the planning loop in [memory.md](memory.md#loop) (Q06) | No. Each leaf's plan passes the intent check instead ([task-execution.md](task-execution.md#lifecycle)) |

- Splitting may show that something has to differ from the first direction. Barrel asks about it only under the rules in [workflow.md](workflow.md#asking) (Q06).
- Medium topics run in tree order. When the current medium topic's leaves are all blocked or running and a lane is free, the orchestrator may split and start the next medium topic that does not depend on the blocked work (Q01, AI).

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

<a id="files"></a>
## Files

Each node is one file in `.barrel/tasks/<run>/`, tracked by git (Q15). The contract body is in English (Q08). The header looks like this:

```markdown
---
id: T1.2.3
level: leaf                 # large | medium | leaf
parent: T1.2
title: Add the Google sign-in button to the login page
depends_on: [T1.2.1]
status: planned             # planned | done | abandoned  (durable only, Q15)
commit: null                # set when done
difficulty: normal          # light | normal | hard (sessions.md)
write_set: [src/auth/login.tsx, src/auth/login.test.tsx]
read_set: [src/auth/session.ts]
resources: []               # ports, databases, paths outside the repo, shared environments, services, accounts (archived D-032)
memory_units: [REQ-k3f9, FEAT-2m7q, DEC-x81c, CON-p4tz]
secrets: []                 # Keychain names this leaf may read (memory.md#secrets)
browser: false              # gets the browser-automation server (task-execution.md#user-only)
review: false               # independent review after gates (archived Q-004)
expect_baseline_fail: true  # false when the leaf must keep existing behavior
gates:
  unit: {spec: {shell: "npm test -- login"}, every_turn: true}
---
```

A leaf's body is its contract (archived orchestration.md#task-input, 09-29 draft):

- **Intent:** the one result, and why it is wanted. Links point to the units.
- **Scope:** what to change, what must not change, and the behavior to preserve.
- **Behavior:** inputs, outputs, errors, edge cases.
- **Verification:** the gate commands and the expected results.
- **When something is missing:** the last rule is always the same: "If you need a decision that is not in this contract or its units, do not guess. Ask."

Large and medium nodes hold a short description and their children; they have no contract (AI).

<a id="fields"></a>
## Contract fields

| Field | Origin | Source |
| --- | --- | --- |
| `id`, `title`, `depends_on`, `expect_baseline_fail`, `expected_gate_seconds`, `artifacts`, `budget` | The unit loop's `Unit` (`barrel/core/unitloop.py:178-191`) | Reused |
| `gates` | The roadmap key that `load_roadmap` parses into `Unit.layers` (`barrel/core/unitloop.py:183`, `:216`) | Reused |
| Body (the contract) | Was `prompt` / `prompt_file` | Reused |
| `memory_units` | Was `references`; now the units read in the planning loop | Q07 default |
| `difficulty` | Replaces `model` and `effort`, which now come from `.barrel/config.json` | Q12, Q16 |
| `write_set` | New. Checked before commit, and used to decide what may run in parallel | 09-29 draft, Q14 |
| `read_set`, `resources` | New. Used to decide what may run in parallel ([task-execution.md](task-execution.md#lanes)) | archived D-032 |
| `secrets`, `browser` | New. What the leaf may use for things only the user can grant ([task-execution.md](task-execution.md#user-only)) | AI |
| `level`, `parent` | New. The tree | Q06 |
| `review` | New | archived Q-004 |
| `status`, `commit` | New. Durable status only | Q15 |

- **Gate layers** stay as the unit loop defines them: `exists`, `build`, `unit`, `behavior`, `integration`, `perf` (`barrel/core/gates.py:25`, parsed at `:45-68`).
- **`expect_baseline_fail`** is on by default: a leaf's gates must fail before work starts ([task-execution.md](task-execution.md#lifecycle)). A leaf whose job is to keep behavior unchanged, such as a refactor, has gates that already pass, so it sets the field to false (unit loop field, `barrel/core/unitloop.py:187`; use AI).

<a id="status"></a>
## Status

- **In the task file:** only durable status. `planned`, `done` (with its commit) or `abandoned` (with the reason, in the body) (Q15).
  - The orchestrator writes it when it handles `task_done`, or when it abandons the leaf.
  - The orchestrator is the only writer of task files (AI; [memory.md](memory.md#rules)).
- **In the run state** (`~/.barrel/projects/<id>/runs/<run>/run.json`): running, blocked, waiting for an answer, attempts, sessions and lanes (Q15). The launcher writes it.

<a id="names"></a>
## Korean display names

In Korean mode, every node gets a Korean display name for Slack and the PC view (Q10, option 10-c K).

The names stay out of the task files, because contracts are English only (Q08). They live in `.barrel/tasks/<run>/display-names.ko.json`, a map from node ID to name (AI):
- The Korean-writer session writes them in batches, and the launcher stores them.
- Large and medium topics get theirs when the S5 review document is written.
- Leaves get theirs when their medium topic is split.

If the Slack language is switched from English back to Korean, the missing names are written in one batch then (Q10-2 default).
