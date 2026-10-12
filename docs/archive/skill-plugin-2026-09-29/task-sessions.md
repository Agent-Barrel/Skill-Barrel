# 작은 작업과 작업당 새 세션

작업마다 새 코딩 에이전트 세션 하나가 작업을 맡는다. **이 레포에는 이를 실행하는 기반이 이미 있다.**

- `step2step`은 호출할 때마다 실제 Claude Code 대화형 세션을 새로 띄운다.
- unit loop는 작업 목록을 순서대로 새 세션에 맡기고, 게이트로 결과를 판정한다.

이 문서는 그 실행 기반 위에 확정 원칙과 의도 대조 원칙을 얹는 방법을 정한다. 기존 구현의 근거는 [research](research.md#existing)에 있다.

<a id="size"></a>
## 작업 크기

작업 하나는 새 세션 하나가 컨텍스트 압축 없이 의도대로 끝낼 수 있는 크기여야 한다(P-001 1). 고정 토큰 수는 두지 않는다. 대신 아래 조건을 모두 만족하는지 본다.

- **결과가 하나다.** 한 기능 조각(예: 화면 하나의 입력 → 저장 → 검증)이나 한 가지 수정이다.
- **쓰기 범위를 미리 적을 수 있다.** 적을 수 없으면 선행 조사 작업으로 나눈다.
- **검증 방법이 정해져 있다.** 게이트로 실행할 명령과 기대 결과가 있다.
- **미해결 판단이 없다.** 있으면 [확정 항목](clarification.md#late)으로 돌린다.

<a id="contract"></a>
## 작업 계약

unit loop의 유닛 형식을 작업 계약으로 쓴다. 유닛 형식은 `barrel/core/unitloop.py`의 `Unit`이고, 대상 레포의 `roadmap.json`에 들어간다. 여기에 기존 [작업 입력 계약](../app-plan/specs/orchestration.md#task-input)이 요구하는 필드만 더한다.

| 필드 | 기존 유닛 | 전환안 |
| --- | --- | --- |
| `id`, `title`, `depends_on` | 있음 | 그대로 |
| `prompt` / `prompt_file` | 있음 | 계약 본문(의도·범위·동작·완료 조건·막혔을 때)을 담은 파일 |
| `references`, 설정의 `north_star` | 있음 | 정본 문서 경로·절·revision |
| `gates` (exists/build/unit/behavior/integration/perf) | 있음 | 계약의 검증 명령 |
| `model`, `effort` | 있음 | 역할(RTE)에 맞게 지정 |
| `decisions` | 없음 | 추가. 관련 확정 항목 ID |
| `write_set` | 없음 | 추가. 드라이버가 커밋 전에 검사 |
| `provider` | 없음 | 추가. `claude` / `codex` |

```json
{
  "id": "T-003",
  "title": "로그인 화면의 소셜 로그인 버튼",
  "prompt_file": "tasks/T-003.md",
  "depends_on": ["T-001"],
  "decisions": ["C-001", "C-002"],
  "write_set": ["src/auth/login.ts", "src/auth/login.test.ts"],
  "provider": "claude",
  "model": "claude-opus-5-5",
  "effort": "max",
  "references": ["docs/features.csv#FEAT-012"],
  "gates": {"unit": {"spec": {"shell": "npm test -- login"}, "every_turn": true}}
}
```

계약 본문(`tasks/T-003.md`)에는 작업 세션에 필요한 것만 담는다. 전체 대화나 전체 기능표는 넘기지 않는다. 계약 본문의 마지막 규칙은 항상 같다. **"정본에 없는 판단이 필요하면 추측하지 말고 질문한다."**

<a id="execution"></a>
## 새 세션으로 실행하기

| | Claude Code | Codex |
| --- | --- | --- |
| 세션 드라이버 | `step2step.claude.SessionHandle.start(...)`. 호출마다 새 `--session-id`로 실제 대화형 세션을 PTY에서 띄운다. `-p`를 쓰지 않아 대화형 구독 경로로 동작한다 | `step2step.codex`. `codex app-server`로 새 thread를 시작하며 ChatGPT 로그인을 확인한다 |
| 모델·effort | 실행 인자 `--model` / `--effort` | `thread/start`의 model·`model_reasoning_effort` |
| 계획 승인 | plan 모드 → 승인 메뉴 → `approve_plan()` 또는 `reject_plan(feedback)` | 계획 turn → 승인 전에 계획 본문을 받는다 → 승인 또는 피드백 수정 |
| 완료 감지 | Stop 훅 신호 파일 | `turn/completed` 이벤트 |
| 실측 | 2.1.195~2.1.272 (2.1.272에서 신뢰 메뉴·`answer_menu`·`approve_plan`) | codex-cli 0.153.4, 2026-09-10 live 5/5 |
| unit loop 연결 | 연결됨 (`default_session_factory`) | **연결 안 됨 → 추가** |

실행 흐름은 다음과 같다.

- unit loop가 작업(유닛)마다 새 세션을 띄우고, 게이트로 판정한 뒤 세션을 닫는다.
- 게이트 실패 피드백은 같은 시도 안에서 그 세션에 다시 준다. 작업 하나를 한 세션이 끝까지 맡는다.
- 재시도는 새 세션에서 한다. 같은 실패 지문이 반복되면 effort를 먼저 올리고, 그다음 모델을 바꾼다.

쓰지 않는 방식:

- **서브에이전트.** 조율 세션에 딸린 하위 실행이라 독립 세션이 아니다. 사용자에게 질문할 수 없고, 결과는 요약만 돌아온다. plan 모드 → 의도 대조 → 승인 흐름도 태울 수 없다.
- **`claude -p` 헤드리스.** Anthropic이 구독 한도에서 분리하겠다고 예고했다가 보류한 영역이다([정책](research.md#policy)). 또 이 레포는 처음부터 `-p`를 피하고 대화형 세션을 구동해 왔다.

<a id="plan-intent"></a>
## 계획과 의도 대조

P-001 원문은 "plan 모드를 사용해도 좋지만, 작업 계획을 반드시 검토하고 최초 의도와 부합하는지 확인한 뒤에 작업을 진행"하라고 한다. 이를 작업 세션마다 적용한다.

1. unit loop가 작업 세션을 plan 모드로 시작하고 계약을 보낸다.
2. 세션이 계획을 내면 승인 메뉴에서 멈춘다.
3. 드라이버가 계획 본문을 얻는다.
   - Codex: 승인 전에 계획 본문이 제공된다.
   - Claude: `pending.plan`이 비는 경우가 있다. 승인 대기 중에는 transcript에 ExitPlanMode가 아직 기록되지 않을 수 있기 때문이다.
   - Claude 쪽 대응: 훅 스크립트가 ExitPlanMode의 `tool_input`을 저장하도록 고친다. 지금은 이벤트 이름·세션·도구 이름만 기록한다.
4. 의도 확인 역할(RTE-013, Astra medium)이 **별도의 새 세션**에서 계획을 대조한다. 대조 대상은 계약·최초 요청·확정 목록이다.
5. 대조 결과에 따라 처리한다.
   - 일치하면 `approve_plan()`.
   - 불일치하면 `reject_plan(피드백)`으로 같은 작업 세션에 수정을 요구한다.
   - 계약 자체가 틀렸으면 작업을 멈추고 분할(S4)로 돌린다.

지금의 unit loop는 bypass 모드로 시작하고, 승인 메뉴가 뜨면 검토 없이 `approve_plan()`한다. 이 부분을 바꾼다.

<a id="questions"></a>
## 작업 세션의 질문

작업 세션이 질문을 띄우면 **추측한 답을 넣지 않는다.** 지금의 unit loop는 질문 메뉴에 `menu_default_answer`("Use your best judgement and continue; do not ask again.")로 답한다. 이는 원칙 1과 반대이므로 바꾼다.

1. 질문 내용(`pending.questions`, Codex는 app-server 질문 요청)을 확정 목록에 `open`으로 올리고 작업을 `blocked`로 멈춘다.
2. 조율 세션이 사용자에게 묻고, 답을 정본에 반영한다.
3. 계약 revision을 올려 **새 세션**에서 다시 실행한다.

<a id="checking"></a>
## 결과 확인

unit loop의 결정적 판정을 그대로 쓴다.

- 게이트 계층: exists / build / unit / behavior / integration / perf
- 작업 전에 게이트가 이미 통과하면 게이트 결함으로 본다(must-fail-first).
- 비정상적으로 싸게 통과하면 다시 실행한다. 오래된 산출물도 검사한다.
- 실패를 분류한다(하네스 / 거절 / 게이트 결함 / 환경 / 코드). 실패마다 지문을 남긴다.
- 커밋은 드라이버가 한다(`commit_by: driver`).

추가하는 것:

- **쓰기 범위 검사.** 드라이버가 커밋 전에 변경 파일이 `write_set` 안인지 확인한다. 밖이면 실패다.
- **결과 보고.** 작업 세션의 응답·사용 도구·transcript 경로·게이트 출력을 결과 디렉터리에 남긴다. 지금의 `state.json`과 세션 snapshot을 확장한다.
- **독립 리뷰(Q-004).** 위험 작업은 게이트 통과 뒤 별도의 새 세션이 리뷰한다. 입력은 계약·diff·게이트 출력이다. 가능하면 구현과 다른 공급자를 쓴다.
- **기존 실패(Q-005).** 요청과 무관한 기존 실패는 사용자에게 판단받는다.

<a id="failure"></a>
## 막힘·실패 처리

| 결과 | 처리 |
| --- | --- |
| 질문(blocked) | 위 [질문 절차](#questions)를 따른다 |
| 게이트 실패 | 기존 unit loop 정책을 따른다. 같은 시도 안에서는 게이트 피드백을 준다. 재시도는 새 세션에서 하고, 같은 지문이 반복되면 사다리를 올린다. 환경 실패는 복구 명령을 한 번 실행한다 |
| 쓰기 범위를 넓혀야 함 | 분할(S4)로 돌아가 의존성을 다시 본다. 세션이 스스로 범위를 넓히지 않는다 |

<a id="order"></a>
## 순서와 병렬

unit loop는 `depends_on` 순서대로 하나씩 실행한다. 막힌 작업이 생겼을 때 멈출지 다음 작업으로 넘어갈지는 기존 설정 `on_unit_blocked: halt | skip`으로 정한다([OD-9](open-decisions.md#od-9)). 병렬 실행은 지원하지 않는다([OD-8](open-decisions.md#od-8)).

<a id="roles"></a>
## 역할과 모델

역할은 [model-routing.csv](../app-plan/model-routing.csv)를 따른다. 정확한 모델 ID와 effort는 실행 시점에 확인한다.

| 역할 | RTE | 실행 위치 | 설계 기본값 |
| --- | --- | --- | --- |
| 조율·확정 도출·정본·분할 | RTE-001, RTE-012 | 사용자가 연 CLI 세션 (스킬) | 고성능·높은 effort |
| 의도 대조 | RTE-013 | 새 세션 (Codex 팩토리가 필요) | Astra medium (P-001 8) |
| 구현 | RTE-003 | 새 세션 (`step2step.claude`) | Opus 5.5 max/xhigh |
| 작고 명확한 구현 | RTE-017 | 새 세션 | Sonnet 5 medium (D-068) |
| 독립 리뷰 | RTE-014 | 새 세션 | 고성능. 가능하면 구현과 다른 공급자 |
| 조사 | RTE-004, RTE-005 | 새 세션 두 개, 서로 결과를 보지 않음 | Astra max / Fable 5.1 max |
