# 근거 (2026-09-29 확인)

시점에 따라 바뀌는 사실이다. 인용하기 전에 다시 확인한다. 공식 문서·소스·로컬 확인은 출처를 링크했고, 블로그·이슈는 **[비공식]**으로 표시했다. 이 내용을 정본에 반영하게 되면 [research.csv](../app-plan/research.csv)에 새 RES 행으로 옮긴다.

<a id="current"></a>
## 현재 방식의 상태

- **규모** (2026-09-29, HEAD `b045f50`, 테스트 코드 포함)
  - 첫 커밋 2026-08-11 이후 120커밋
  - Rust 291,273줄 (`crates/` 5개 + `apps/desktop`)
  - TS/TSX 13,178줄, Python 32,367줄
- **2026-09-27 감사 결과** (`d1fed1f` 기준, 이후 커밋 2개는 Jev 보조와 checkout 정리)
  - 81개 FEAT 중 검수기준을 충족한 기능은 0개다.
  - V-01~V-14는 모두 미실험이다.
  - native 검증 DB의 provider 실행 기록은 모두 합성이었다(실제 CLI 미실행).
- **보존 브랜치의 `docs/implementation/work-state.md` 2026-09-27 기록:** "실제 계정·모델·외부 서비스와 새 GUI/앱 번들 검증은 수행하지 않았다."
- **2026-09-29 HEAD에서 다시 확인한 차단 요인:**
  - 구독 과금 판정(`verify_billing_candidate`)은 테스트에서만 호출된다.
  - helper 등록 함수는 심볼 연결 테스트에서만 참조된다.
  - updater의 `pubkey`와 `endpoints`가 비어 있다.
  - 콘솔 소스에 `/api/pairing` 호출이 없다.
  - PTY 의존성이 없다.

<a id="existing"></a>
## 이 레포의 기존 구현

2026-09-29에 코드에서 확인했다. 줄 번호는 HEAD `b045f50` 기준이다.

**`step2step.claude`: 작업마다 새 대화형 Claude Code 세션**

- **세션 생성:** `SessionHandle.start(workdir, model, effort, mode, system_prompt_append, extra_args, turn_timeout)`는 호출할 때마다 새 세션을 띄운다(`step2step/claude/session.py:101-147`).
  - 실행 인자: `claude --session-id <uuid> --settings <훅 설정> --dangerously-skip-permissions [--model] [--effort]`
  - PTY 안에서 대화형으로 돌며, `-p`는 쓰지 않는다(`step2step/claude/runner.py:362-395`).
- **완료 감지:** 주입한 Stop 훅의 신호 파일로 감지한다. 교착·무진척·마감 초과·사용량 한도·제출 실패를 서로 다른 결과로 구분한다(README "How it works").
- **plan 처리:** `approve_plan()`, `reject_plan(feedback)`이 있다(`session.py:486-509`).
  - 승인 대기 중인 계획 본문(`pending.plan`)은 transcript에 ExitPlanMode 기록이 있을 때만 채워진다(`session.py:358-375`).
  - 훅 스크립트는 이벤트 이름·세션·도구 이름만 기록하고, 도구 입력은 버린다(`hooks.py:30-50`).
- **질문:** `answer_menu` 등 검증된 폐쇄 루프로 응답한다. 다중 질문 위젯은 거부한다.
- **자식 세션 환경:** 인증 변수와 `CLAUDE*` 변수를 지운다(`runner.py:153-163`).
- **실측:** 2.1.195~2.1.272(README, `docs/substrate/`). 2.1.272에서는 신뢰 메뉴·`answer_menu`·`approve_plan`을 확인했다.

**`step2step.codex`: Codex app-server 세션**

- **시작:** `codex app-server --listen stdio://`를 띄우고 ChatGPT 로그인을 확인한다. 그다음 `thread/start`에 model·`model_reasoning_effort`·developer instructions를 넘긴다(`step2step/codex/session.py:85-135`).
- **계획 처리:** 승인 대기 중에 계획 본문을 돌려준다(`session.py:270-285`).
  - 승인하면 "Implement the approved plan" turn을 실행한다.
  - 거절하면 피드백을 담아 계획을 고치는 turn을 실행한다(`session.py:415-440`).
- **실측:** 2026-09-10 codex-cli 0.153.4, live 테스트 5개 통과(`docs/codex-control.md:176-195`).
  - 확인한 동작: 파일 생성·연속 수정, 모델·effort 변경, 재개, 질문 응답, 계획 거절·재계획·승인·실행, 명령 승인, 중단.
  - 같은 날 Claude live 테스트는 로그인 만료로 완료하지 못했다.

**unit loop: 작업 목록을 세션 하나씩 실행**

- **입력:** 설정(`barrel/core/unitloop.py:47-83`)과 유닛(`unitloop.py:178-239`: id·title·prompt·gates·depends_on·model·effort·references 등). 로드맵은 대상 레포의 JSON이다.
- **세션:** 시도마다 `SessionHandle.start(..., mode="bypass")`로 새 세션을 띄우고, 끝나면 닫는다(`unitloop.py:433-442`, `645-660`, `759-765`).
- **승인·질문 처리:**
  - 승인 메뉴는 검토 없이 `approve_plan()`한다.
  - 질문 메뉴는 `menu_default_answer`("Use your best judgement and continue; do not ask again.")로 답한다(`unitloop.py:767-783`).
- **결정적 판정:**
  - `gates.py`: 게이트 계층, must-fail-first, 비정상적으로 싼 통과 재실행, 오래된 산출물 검사
  - `failures.py`: 실패 분류와 지문
  - `preflight.py`: 사전 점검
- **실행 제어:** `orchestration/drivers/unit_loop.py --config <run.json> [--only U#] [--dry-run]`. 상태는 `orchestration/results/<name>/state.json`에 남는다. 종료 코드 0/2/3/4, 중지 파일, `on_unit_blocked: halt|skip`을 지원한다.
- **실측:** 2026-08 Starfort 12유닛을 돈 것은 일회성 드라이버였다. 이를 2026-09-16에 일반화한 현재 엔진은 가짜 세션 테스트만 있다(`barrel/tests/test_unitloop.py`).
- **Codex:** barrel과 orchestration 어디에서도 `step2step.codex`를 쓰지 않는다.

**이전 Python 웹 앱: 인터뷰부터 검증까지**

- **흐름:** 인터뷰(프로젝트당 지속 세션) → purpose → requirements → 18열 기능 CSV(`spec_csv.py` 검증) → develop → verify(이전 Python 앱의 `core/service.py`).
- **develop:** 승인된 P0 기능 전체를 한 프롬프트, 한 세션으로 구현한다(`service.py:1085-1093`). 수정 라운드는 새 세션에서 한다. plan 모드는 쓰지 않는다.
- **answerer:** answerer 세션이 정본에서 답을 찾고, 못 찾으면 질문함으로 보낸다. 결정은 `docs/decisions.md`에 D-###로 기록한다(`qa.py`, `decisions.py`). 이 경로는 가짜 실행으로만 검증됐다.
- **실측:** 2026-07-31 신규 프로젝트 E2E 실행, 2026-08-01 오토파일럿 스모크(`orchestration/reports/demo-transcript.md`, `autopilot-smoke.md`).

**Rust 엔진: 전체 흐름은 구현, 실측은 없음**

- **단계:** 사전 평가 → 요구 → 기능+와이어프레임 → 스택+디자인 → 계획(엔진 crate의 `src/coordinator.rs:271-311`).
- **조사:** Codex·Claude 두 세션을 병렬로 돌리며, 서로의 결과를 보지 않게 한다(`research.rs:264-300`).
- **작업:** 의도 확인(별도 읽기 전용 세션) → 구현 → 호스트 검증 → 필요하면 리뷰(별도 세션).
  - 실행 단위마다 새 세션이다(`runner.rs:484-522`, `resume_session_id: None`).
  - 구현이 의도 확인 세션을 재사용하면 거부한다(`execution.rs:1309-1314`).
- **Claude 드라이버:** `--print --input-format stream-json --output-format stream-json …`(런타임 crate의 `src/drivers.rs:563-600`). PTY는 없다.
- **실측:** 인증된 실제 CLI로 돈 기록이 없다(`docs/implementation/validation.md`, `work-state.md`).

<a id="vendors"></a>
## 벤더 기능

**Claude Code 2.1.284** (로컬 `claude --version`)

- **subagent** (전환안은 작업 세션으로 쓰지 않는다. [이유](task-sessions.md#execution))
  - "Each subagent starts with a fresh, isolated context window. It doesn't see your conversation history."
  - 받는 것: 위임 프롬프트, CLAUDE.md, git 상태, 미리 지정한 스킬
  - `AskUserQuestion`은 subagent에서 거부된다. 부모 세션에는 최종 보고만 돌아간다.
  - transcript는 별도로 저장되고 기본 30일 뒤 삭제된다.
  - frontmatter로 model(전체 ID 가능)·effort·isolation: worktree·permissionMode·hooks를 지정한다.
  - 기본 동시 20개, 중첩 3단
  - 출처: [sub-agents](https://code.claude.com/docs/en/sub-agents)
- **hooks**
  - 이벤트 30여 개. PreToolUse는 사유를 붙여 거부(`permissionDecision: deny`)하거나 입력을 수정(`updatedInput`)할 수 있다. Stop·SubagentStop은 종료를 막을 수 있다.
  - SessionStart·UserPromptSubmit 등은 `additionalContext`를 주입할 수 있으며, 1만 자로 제한된다.
  - subagent 안에서 호출된 도구에도 설정·플러그인 훅이 실행된다. 입력에 `agent_id`·`agent_type`이 포함된다.
  - 출처: [hooks](https://code.claude.com/docs/en/hooks)
- **Stop 훅 한도:** "Claude Code overrides a Stop hook after it blocks eight times in a row without progress." 출처: [hooks-guide](https://code.claude.com/docs/en/hooks-guide)
- **데스크톱 Code 탭**
  - 터미널 없이 플러그인을 설치할 수 있다. CLI와 설정·훅·스킬을 공유한다.
  - 병렬 세션마다 worktree를 격리한다. 다른 세션 조회·메시지와 task chip으로 새 세션을 시작하는 기능이 있다.
  - 출처: [desktop](https://code.claude.com/docs/en/desktop)
- **표면별 플러그인 지원**
  - Chat은 에이전트·훅을 무시하고, Cowork·Claude Code는 불러온다.
  - 최상위 `bin/`이 있으면 Chat·Cowork는 설치를 거부한다.
  - 조직 관리자가 플러그인을 Required로 지정할 수 있다.
  - 출처: [platform-support](https://claude.com/docs/plugins/platform-support)
- **로컬 CLI 확인**
  - `claude plugin eval`은 플러그인 유무 비교(ablation)를 기본으로 한다.
  - `claude` 인자: `--agent`, `--model`, `--effort`, `--permission-mode`, `--allowedTools`, `-n/--name`, `--plugin-dir`, `--session-id`

**Codex 0.155.1** (로컬 확인. 최신 0.159.0, 2026-09-29)

- **hooks:** stable ([#19012](https://github.com/openai/codex/pull/19012), 2026-04-23).
  - 이벤트 12개: SessionStart/End, UserPromptSubmit, PreToolUse, PermissionRequest, PostToolUse, Pre/PostCompact, SubagentStart/Stop, Stop, Interrupt
  - PreToolUse 거부·입력 수정, Stop `decision: block`
  - 훅마다 사용자가 한 번 신뢰해야 한다(내용 hash 고정). 관리형 훅은 자동으로 신뢰된다.
  - 출처: [hooks](https://learn.chatgpt.com/docs/hooks)
- **plugins:** stable ([#15820](https://github.com/openai/codex/pull/15820), 2026-03-26). 스킬·MCP·훅·apps를 묶는다. 소스는 `.claude-plugin/plugin.json`도 인식한다. 출처: [plugins](https://learn.chatgpt.com/docs/plugins)
- **skills**
  - `.agents/skills`, `~/.agents/skills` 등에서 찾는다. 설명이 요청과 맞으면 자동으로 쓴다.
  - 목록은 컨텍스트의 2%, 설명은 1,024자까지다. frontmatter는 name·description만 읽는다.
  - 출처: [build-skills](https://learn.chatgpt.com/docs/build-skills)
- **subagents**
  - 요청이 있거나 "applicable `AGENTS.md` or skill instructions that request delegation"이 있으면 만든다.
  - custom agent TOML에 `model`·`model_reasoning_effort`·`sandbox_mode`를 지정한다. 부모에는 요약이 돌아온다.
  - 컨텍스트 격리 범위와 훅에서 subagent를 구분하는 방법은 문서에 없다.
  - 출처: [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- **exec** (로컬 `codex exec --help`): `-m`, `-c key=value`, `-s/--sandbox`, `-C`, `--json`, `--output-schema`, `-o`, `resume`
- **제거·실험 기능:** `codex mcp-server`는 [#42993](https://github.com/openai/codex/pull/42993)(2026-09-05)에서 제거됐다. `app-server`는 experimental이다.

<a id="policy"></a>
## 정책

- **Anthropic 과금 변경 보류**
  - `claude -p`·Agent SDK·서드파티 앱 사용량을 구독 한도에서 떼어 별도 월 크레딧으로 옮기는 변경이 예고됐다(2026-06-15 시행 예정). 시행 당일 보류됐다.
  - 현재는 모두 구독 한도에서 차감된다. 대화형 터미널·IDE 사용은 변경 대상이 아니었다.
  - 재설계 후 미리 공지하겠다고 했다.
  - 출처: [Help Center](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)(2026-06-16 갱신), [경위 정리](https://www.digitalapplied.com/blog/anthropic-claude-credit-overhaul-june-15-2026) [비공식]
- **Agent SDK 문서:** 사전 승인 없이 서드파티 제품이 claude.ai 로그인이나 구독 한도를 제공하는 것은 허용되지 않는다. 출처: [agent-sdk overview](https://code.claude.com/docs/en/agent-sdk/overview)
- **OpenAI**
  - 제3자 앱이 사용자의 ChatGPT 플랜으로 Codex를 구동하는 것에 대한 명시 정책은 찾지 못했다.
  - 자동화에는 API 키를 권한다.
  - 출처: [auth](https://learn.chatgpt.com/docs/auth), [non-interactive](https://learn.chatgpt.com/docs/non-interactive-mode)
- **다계정 순환:** 플랜 한도는 개인의 일반 사용을 전제로 한다. 계정을 순환하면 약관상 위험이 있다(추론). 출처: [legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance)

<a id="prior-art"></a>
## 선행 사례

- **스킬 발동률**
  - 스킬만 두면 56%의 사례에서 한 번도 호출되지 않았다. 항상 로드되는 AGENTS.md 색인은 100%였다: [Vercel](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) (2026-01-27) [비공식]
  - 도움 없이는 발동률 50~55%, 프롬프트마다 강제 평가 훅을 쓰면 100%: [Scott Spence](https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals) (2026-02-08) [비공식]
- **superpowers** ([저장소](https://github.com/obra/superpowers))
  - 세션 시작 훅으로 부트스트랩하고, 차단 없이 지시만 쓴다.
  - 보고된 문제: 승인 관문 건너뛰기([#2372](https://github.com/obra/superpowers/issues/2372)), 서브에이전트 결과를 "PASS"로 지어냄([#1749](https://github.com/obra/superpowers/issues/1749)) [비공식]
- **BMAD `bmad-loop`** ([저장소](https://github.com/bmad-code-org/bmad-loop), 베타)
  - "No LLM in the control loop"
  - 훅은 이벤트만 기록하고, 파일 확인과 테스트는 코드가 한다. 리뷰는 새 세션에서 한다.
  - 원칙 5와 같은 방향이다.
- **Agent OS v3:** 구현·조율 단계를 없애고 표준 주입만 남겼다. 이유: "frontier models handle this well on their own now". 출처: [CHANGELOG](https://github.com/buildermethods/agent-os/blob/main/CHANGELOG.md)
- **명세 과부하:** Spec Kit으로 기능 하나를 만들 때 markdown 2,577줄, 에이전트 33.5분, 리뷰 3.5시간이 들었다. 반복 방식은 8분이었다: [Scott Logic](https://blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html) (2025-11-26) [비공식]
- **독립 오케스트레이터 정리**
  - Terragon은 2026-02-09에 종료했다.
  - Vibe Kanban은 2026-04-10에 클라우드 기능을 종료했다. 사유: "we couldn't find a business model". 출처: [공지](https://www.vibekanban.com/blog/shutdown)
- **자기 보고의 한계:** 에이전트가 제대로 테스트하지 않고 완료를 선언하는 문제가 있다. Anthropic은 이를 바깥 파일(통과 목록·진행 기록)과 브라우저 테스트로 보완했다. 출처: [Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

<a id="recheck"></a>
## spike에서 다시 확인할 것

- Claude 작업 세션의 계획 본문 확보: 훅이 ExitPlanMode 입력을 저장하는 방식이 승인 대기 중에 항상 동작하는지
- `reject_plan(feedback)`의 Claude 실측. 코드는 있지만 live 기록이 없다
- `step2step`이 띄운 작업 세션에 사용자 범위 플러그인·훅이 적용되는지, `BARREL_TASK` 환경변수가 훅까지 전달되는지
- 현재 Claude Code 버전에서 `step2step` 화면 표시 재보정이 필요한지(`calibrate_dialogs`)
- Claude Code 슬래시 명령이 어느 사용자 입력 훅 이벤트로 들어오는지(승인 기록 방식)
- 한 트리에 두 플러그인 매니페스트를 두고 `hooks/hooks.json`을 공용으로 쓸 수 있는지
- Codex 훅 회귀 보고: 데스크톱 업데이트 후 훅 미실행([#21639](https://github.com/openai/codex/issues/21639)), 0.154.0에서 세션 시작 주입 거부([#45999](https://github.com/openai/codex/issues/45999)) [비공식]
