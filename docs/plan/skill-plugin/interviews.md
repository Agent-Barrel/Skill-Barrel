# Interviews and questions

These rules apply to every question Barrel asks a human:
- requirements and functional-spec interviews (S3, S4)
- the intent review (S5) and the stack confirmation (S6)
- questions that block a task (S7)
- questions about cascading changes ([workflow.md](workflow.md#cascade))

The questions go to Slack ([Q03-3](../interview/q03-3-launcher-and-slack.md), flow 11). How they are posted and reminded is in [slack.md](slack.md#questions).

<a id="discovery"></a>
## Finding everything that needs deciding

The aim of S3 and S4 is to capture, before implementation, everything that shows what the user intends for the project. With that written down, the AI can answer its own later questions from the documents (Q01).

**The test.** Could this choice make the result differ from what the user expects? If it could, and no unit answers it, it must be decided (09-29 draft). Choices that change requirements, the stack, cost, or a method the user mandated are always the user's (archived D-041). So are scope and permissions (AI, from Q01).

| Kind of item | What happens |
| --- | --- |
| A decision only the user can make | Asked, and the answer recorded |
| Already settled by an earlier decision | Linked to that decision, not asked again |
| Delegated by the user ("decide the layout yourself") | Recorded with the limits of the delegation. Anything outside those limits is asked |
| A technical judgment inside the approved scope, such as internal structure | Decided by the AI, with the reasons recorded. Never turned into a question |

These kinds come from the 09-29 draft.

No single method finds everything, so the orchestrator combines five (09-29 draft):

1. **Break down the request.** Purpose, users, core flows, inputs and outputs, boundaries and exceptions, what is out of scope.
2. **Go through a dimension checklist**, as deep as the impact level requires ([workflow.md](workflow.md#depth)):
   - users and permissions; core flows and screens; input validation, errors, empty states
   - the data model; retention, deletion and migration; compatibility with existing data
   - API contracts and their consumers; external services, accounts and costs
   - stack, dependencies and licenses; performance and scale; security and privacy; platform support
   - deployment and operations; Git delivery; acceptance criteria and the verification environment
3. **Research similar services and competitors**, in the same domain and in others. This surfaces decisions the user had not thought of (flow 5).
4. **Compare with what exists**, for maintenance requests: the existing code and units against the request. This covers behavior to keep, invariants, and earlier decisions to reuse ([workflow.md](workflow.md#onboarding)).
5. **Run an independent gap review.** A review subagent reads the units and the draft specs and marks every place where an implementer would have to guess. Each place found becomes an item.
   - It is required for extended and full impact and optional for local (09-29 draft, mapped to Q13's levels). The stage exits check that it ran ([exits](#exits)).
   - The draft wanted the reviewer to be "preferably another provider". That is dropped (Q16).

Splitting a medium topic is the last check: a contract field that cannot be filled from the units is a missing decision (09-29 draft). A decision that still turns up later is recorded with the method that missed it ([task-execution.md](task-execution.md#questions)).

<a id="before"></a>
## Before asking

1. **Check the documents.** The orchestrator looks for the answer first, in the intent, requirement, feature and decision units. It asks only when the direction cannot be inferred or a new decision is needed (Q01, Q06).
2. **Get advice on hard questions.** When the decision is hard, an advice subagent on the frontier tier gives a second opinion. The advice shapes the options and the recommendation (flow 0, Q02, Q16).
3. **Research.** A research subagent looks at (Q02, flow 5, flow 7):
   - how services in the same domain solved the same problem
   - how services in other domains solved it
   - competing products
   - for technical questions, open-source projects and services, with their pros, cons and constraints (licensing and cost, e.g. a paid license like PyQt's)

   Research uses current sources and records the date of each source. It is done per decision topic: follow-up questions on the same topic reuse the existing `research` unit, unless the conditions changed or the information has to be fresher (archived D-011).
4. **Verify.** A separate verification subagent checks the findings against the facts (Q02, Q16). How the check works is an AI choice:
   - It sees the research report and its sources, never the research conversation.
   - It checks every claim against its source and marks it verified, unverified or contradicted.
   - For any claim that drives the decision, it looks for a second independent source.
   - Only verified claims are presented as facts; the others are labeled.

   Which engine researches and which one verifies is decided by `.barrel/config.json` and by the accounts available at that moment ([sessions.md](sessions.md#selection)). Q16 settled that this is not a split by provider.
5. **Record.** The research and its verification status become a `research` unit ([memory.md](memory.md#kinds)).

Quick lookups inside a task, such as checking one API's signature, are done by a subagent of that task session (Q02). Their results are still checked against the facts, as Q16 asks: the task's gates run the code that uses them, which tests them by execution. A finding that a gate cannot test goes to the orchestrator, which verifies it as above (AI).

<a id="posting"></a>
## Posting

The orchestrator never posts to Slack itself (Q10 default). It writes the English text and calls `barrel post` ([launcher.md](launcher.md#commands)):

| Kind | Used for | Mention |
| --- | --- | --- |
| `question` | A decision the user has to make | Yes |
| `review` | The S5 intent review, the S6 stack confirmation | Yes |
| `request` | Something only the user can do ([task-execution.md](task-execution.md#user-only)) | Yes |
| `report` | The final report | Yes (Q10 default: completion) |
| `reply` | The orchestrator's answer to a follow-up in a question's thread ([flow](#flow)) | No |

What the launcher does with it (AI):
1. **Korean writer.** In Korean mode, it has the Korean writer turn the English source into Korean ([language](#language)).
2. **Fixed parts.** It adds the parts that are fixed, so no model writes them:
   - the header `[{project}-질문]`, or `[{project}-Question]` in English mode (Q10, Q10-2 default)
   - the reply line "이 스레드에 답해 주세요" (Q10, Q10-2 default)
   - the mention
3. **Format.** It posts the text as a Slack `markdown` block. Anything over the 12,000-character limit is attached as a file in the thread ([slack.md](slack.md#rules)).
4. **Record.** It records the post's thread and starts the reminder clock ([slack.md](slack.md#questions)).

**If the Korean writer fails:**
- It is retried on the next engine option, then again later.
- Until Korean text exists, the post counts as unsent, as during a Slack outage. The PC view and the snapshot show it as unsent.
- English is never sent while Korean is set (Q10: "한번 정하면 바꿀 때까지 정한 언어로"; AI).

<a id="format"></a>
## Question format

Each question covers one decision topic. Small independent items within the same topic may be grouped (archived workflow.md#research; same rule as this repo's own interview).

The orchestrator writes, in this order:
1. Why this is asked now.
2. What must be decided, and what else to consider together with it.
3. A short research summary with sources.
4. Options, each with its consequences.
5. One recommendation with its reason.
6. Optionally, defaults that apply unless the user objects (AI, after this repo's own interview protocol).

The launcher adds the header before these and the reply line after them ([posting](#posting)).

**The full research on request** (flow 5: the user can get the research if they want it). The question carries the summary. When the user asks for the full research in the thread, three things happen:
1. The orchestrator writes it up from the `research` unit.
2. It posts the write-up as a `reply` in the user's language.
3. Anything over the size limit is attached as a file (AI).

A link to the unit cannot serve, because the run branch is usually not pushed when the question is asked.

Long content always goes by attachment or path, never into the message body (Q10 default).

<a id="flow"></a>
## Order and concurrency

- **Dependent questions.** Interview questions whose answers depend on each other are asked one at a time. The next question is prepared only after the previous answer is recorded (AI, from the recording rule below).
- **Independent questions** may be open at the same time, each in its own thread. Example: questions from two blocked tasks (AI).
- **A reply in a question's thread** is delivered to the orchestrator as the reply to that question (Q10 default).
- **Follow-ups.** If the reply is a follow-up question rather than an answer, the orchestrator answers in the thread with `barrel post --kind reply` and keeps waiting (AI).

<a id="recording"></a>
## Recording answers

Answers are records made by code, not transcriptions by a model (09-29 draft principle 5: approvals and evidence come from code; mechanism AI).

1. **The answer unit.** When a reply arrives, the launcher writes it as an `answer` unit and commits it. The unit holds:
   - the question as it was posted, and its English source
   - the reply, unchanged and in its original language (Q07, Q08)
   - the Slack user, the time and the thread
2. **Event.** The launcher emits `answer_recorded` with the unit's ID.
3. **Updates.** The orchestrator updates the `requirement`, `feature` and `decision` units the answer settles, and links them to the answer (AI, after archived D-065: update the documents right after each answer).
4. **Next question.** Only then does the orchestrator prepare the next question.
5. **Defaults.** A default the user did not object to is recorded as a `decision` marked "default, not objected", linked to the answer. It is never recorded as the user's own answer.
6. **Never edited.** An `answer` unit is never changed. A later answer lists the earlier ones it replaces in its own `supersedes` field ([memory.md](memory.md#rules)). The units it changes are superseded in the usual way.

**Approvals are tied to a revision** (09-29 draft; AI):
- The S5 review document and the S6 confirmation are stored as review records in `.barrel/reviews/<run>/`, one per revision ([memory.md](memory.md#layout)).
  - The orchestrator writes the English source. In Korean mode, the launcher stores the Korean text as posted in a file next to it.
- `barrel post --kind review` carries the record's path. The answer unit records that path and a hash over both files.
- When a requested change produces a new revision, it is a new file, posted as a new message. A reply in the old revision's thread does not approve the new one.

<a id="replies"></a>
## Edited, deleted and late replies, and attachments (AI)

| What arrives | What happens |
| --- | --- |
| An edit to a reply that was already recorded | A new answer unit that supersedes the first. The orchestrator treats it as a change, with a cascade if needed ([workflow.md](workflow.md#cascade)) |
| A deleted reply | The recorded answer stays. The deletion is noted in run state and told to the orchestrator |
| A reply to a question that was already answered or replaced | Passed to the orchestrator as an instruction, with that question's context |
| A file attached to a reply | Downloaded into the run state's `attachments/` and passed along with the answer |
| A credential in a reply or an attachment | Masked in the answer unit and stored in the Keychain ([memory.md](memory.md#secrets)) |

<a id="language"></a>
## Language

- **English first.** The orchestrator writes every post in English first (Q08).
- **In Korean mode** (the default), a fresh Korean-writer session turns the English source into Korean with Skill-Techblog. The orchestrator never writes the Korean itself (Q08, Q16 default).
  - The Korean writer keeps the source's structure and adds nothing to it. Skill-Techblog's fact sheet checks this (AI).
- **In English mode**, the English source is sent as it is (Q10-2 default).
- **Corrections.** When the user asks for a correction to Korean text, the English source is corrected first, and the Korean is written again from it (Q08, option A).

<a id="exits"></a>
## Stage exits

| Stage | Exit condition |
| --- | --- |
| S3 Requirements | Every open requirement question is answered or resolved from documents, and the `requirement` units are written. At extended and full depth, the independent gap review has run and its items are closed ([discovery](#discovery)) |
| S4 Functional spec | The same for features. Every feature links to the requirements it serves |
| S5 Intent review | The user approves the current revision in its review thread. A requested change is applied, and the new revision is posted (Q01, Q06; [recording](#recording)) |
| S6 Implementation prep | When new technology entered, the user approves the current revision of the stack confirmation (flow 8, Q13). Otherwise S6 ends when its research is recorded ([workflow.md](workflow.md#depth)) |

<a id="review"></a>
## The S5 review document

The S5 review document shows what the AI understood the intent to be (Q01, Q06). It is stored as a review record before it is posted ([recording](#recording)). It holds:
- What will be built, what will not be built, and how "done" is judged.
- The impact level from S2 and its reasons (Q13).
- The large and medium topics, as deep as the impact level asks ([task-tree.md](task-tree.md#split)), each with its Korean display name in Korean mode (Q10, option 10-c K).
- The decisions the AI made on its own that the user may want to see (AI).

**The specs come with it.** The requirements spec and the functional spec are rendered from the units with `barrel memory render` and attached to the review post (flow 3–4).
- In Korean mode they go through the Korean writer. Q08's chosen option lists "검토용 요구사항·기능 명세" among the texts sent to the user in their language.
- At local and extended depth, only the requirements and features this run changed are attached (AI).

<a id="stack"></a>
## The S6 stack confirmation

The confirmation runs when new technology enters, which a new concept always does (Q13). It is stored as a review record, and each stack choice in it also becomes a `decision` unit once approved (AI; [memory.md](memory.md#kinds)). For each stack choice, the confirmation lists (flow 7–8):
- the requirement or feature it serves
- the candidates and why one is recommended
- pros, cons, constraints and costs, from current and verified sources

It also records three more things:
- **The delegated scope** (archived D-013): the environments, actions and costs that Barrel may handle without asking again, for example "create AWS resources for the staging environment, up to this monthly cost". Anything beyond that scope is asked.
- **The tools to install on the PC** (archived Q-008). Installing a tool outside this list is asked later.
- **The Git delivery scope**, if the project has none yet ([runs.md](runs.md#delivery)): local commits, push, pull request or merge. A project with no remote is also offered a new private GitHub repository (archived Q-003). The answer is stored in `.barrel/config.json`. When a run has no stack confirmation, the scope is asked before the run's first delivery (archived repositories.md#delivery, AI).
