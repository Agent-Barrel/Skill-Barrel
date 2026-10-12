# Codex CLI 제어

현재 Python `step2step`에 Codex 제어 모듈을 추가했다. Claude Code는 `step2step.claude`의 PTY 구현을,
Codex는 별도 `codex app-server --listen stdio://` 프로세스를 사용한다.
ChatGPT 구독 로그인을 재사용하며 API 키 로그인으로 자동 전환하지 않는다.
프로젝트·역할별 도구 선택, 제품 웹 UI 연결은 이 변경의 범위가 아니다.

## 실행 조건

- Python 3.12 이상. Codex 모듈 자체는 표준 라이브러리만 사용한다.
- `codex`가 PATH 또는 `~/.local/bin`에 있어야 한다. `codex_exe`로 지정할 수도 있다.
- `codex login status`가 ChatGPT 로그인을 표시해야 한다.
- 검증 버전: macOS, `codex-cli 0.153.4`. app-server의 실험적 Plan API를 사용하므로
  다른 버전은 아래 실제 테스트를 실행해 확인한다. Windows 실제 검증은 수행하지 않았다.

공식 프로토콜: <https://learn.chatgpt.com/docs/app-server>

## Python API

```python
from step2step.codex import SessionHandle, TurnOutcome

with SessionHandle.start(workdir="./my-project", app_dir="./session-logs") as h:
    first = h.run_turn("hello.txt에 HELLO를 기록해줘.")
    if first.outcome is not TurnOutcome.COMPLETED:
        raise RuntimeError(first)
    second = h.run_turn("방금 만든 파일을 읽고 내용을 알려줘.")
    print(second.response)
    print(h.session_id)
```

Claude는 `from step2step.claude import SessionHandle, run_session`으로 명시적으로 선택한다.
기존 루트의 Claude API와 `step2step.core`·`step2step.attach` 호환 경로는 제거되었다.
공통 터미널 제어는 `step2step.terminal`에 있으며, Codex는 기존 app-server 전송을 유지한다.
공통 인터페이스는 `step2step.contracts.SessionControl`이다. 상위 오케스트레이터는 핸들을
주입받고 `capabilities`를 확인하면 된다. Codex 제어 코드가 Claude의 실행·화면·훅 코드를
호출하지 않으며, Codex import는 Claude PTY 스택을 로드하지 않는다.

주요 인자:

| 인자 | 기본값·동작 |
|---|---|
| `mode` | `bypass`. `plan`은 계획 후 승인을 기다린다. |
| `model`, `effort` | 생략 시 Codex의 유효 기본값. 모델별 지원 effort를 조회해 검증한다. |
| `system_prompt_append` | 해당 대화의 developer instructions. 프로젝트 규칙 파일을 덮어쓰지 않는다. |
| `approval_policy` | `never`. `on-request`, `untrusted`도 지정할 수 있다. |
| `sandbox_mode` | `danger-full-access`. `workspace-write`, `read-only`도 가능하다. |
| `request_timeout` | 초기화·일반 RPC 요청 30초. |
| `turn_timeout` | 논리 작업의 대기 시간 합계 600초. 계획·실행 모두 포함한다. |
| `stall_seconds` | 진행 이벤트가 없는 상태 120초. |
| `app_dir` | 기본 `<workdir>/.step2step`; 기본 위치에는 git ignore 파일을 생성한다. |
| `snapshot_dir` | 지정하면 재개용 세션 메타데이터를 추가 저장한다. |
| `logger` | 상태 메시지를 받는 콜백. |

초기 대화는 read-only로 생성하고 매 작업 턴에 요청한 권한을 적용한다. 이는 Codex가 writable
대화를 만들면서 작업 폴더 신뢰를 전역 설정에 기록하는 부작용을 피하기 위한 것이다.
계획 생성 턴은 항상 read-only이다. 실행 턴은 지정한 sandbox·승인 정책을 사용한다.
로그인 토큰은 Codex CLI가 관리한다. 제어 모듈은 토큰을 읽어 출력하거나 복사하지 않는다.

## 질문·권한·계획 처리

```python
from step2step.codex import SessionHandle, TurnOutcome

with SessionHandle.start(workdir="./my-project", mode="plan") as h:
    pending = h.send_prompt("간단한 메모 저장 기능을 계획해줘.")
    while True:
        result = h.wait_turn(pending)
        if result.outcome is TurnOutcome.AWAITING_PLAN_APPROVAL:
            print(result.pending.plan)
            h.approve_plan()  # 오케스트레이터의 검토 정책에 따라 호출
            # 수정 필요 시: pending = h.reject_plan("SQLite를 사용해줘.")
        elif result.outcome is TurnOutcome.AWAITING_MENU:
            interaction = result.pending
            if interaction.kind == "ask_user_question":
                # question id마다 실제 사용자/오케스트레이터의 답변을 전달한다.
                answers = {q["id"]: input(q["question"] + " ") for q in interaction.questions}
                h.answer_questions(answers, request_id=interaction.request_id)
            else:
                # 명령/파일 승인도 상위 정책이 결정한다.
                print(interaction.raw["params"])
                h.answer_approval("decline", request_id=interaction.request_id)
        else:
            print(result.outcome, result.response)
            break
```

- `send_prompt` → `wait_turn`으로 한 작업을 소유한다. 대기 결과는 완료가 아니다.
- 질문 답변·계획 승인 후에는 **같은 PendingTurn**으로 기다린다.
  `reject_plan`만 새 토큰을 반환하므로 반환값으로 교체한다.
- `answer_questions`는 모든 질문 ID에 대한 문자열 또는 문자열 목록을 받는다.
  단일 질문은 `answer_menu(1부터 시작하는 번호)`와 `answer_menu_text(text)`도 지원한다.
- `answer_approval`은 서버가 제공한 결정 중 `accept`, `acceptForSession`, `decline`,
  `cancel`을 지원한다. 영구 규칙 수정, 추가 권한 요청과 MCP elicitation 등 다른 서버 요청은
  `UNSUPPORTED`와 원본 요청으로 반환한다. 자동 승인하지 않는다.
- 응답은 요청 ID·턴 ID에 묶이고 한 번만 전송한다. 이미 해결되거나 취소된 요청은 거부한다.
- 계획 완성 후 실행은 별도 물리 턴이지만 하나의 논리 작업으로 처리한다. 계획만 만들어서는
  배치 완료 건수가 증가하지 않는다.

상태 조회는 다른 스레드에서도 가능하다. 전송·대기·답변·설정·종료는 핸들을 생성한
스레드에서 호출해야 한다. 모듈은 오케스트레이터 대신 질문의 정답이나 승인 정책을 결정하지 않는다.

## 모델·effort와 관측

```python
rows = h.available_models()  # 공통 ModelRow: name, label, supported_efforts 등
h.set_model(rows[0].name, effort=rows[0].supported_efforts[0])
result = h.run_turn("짧게 확인해줘.")
state = h.model_state(refresh=True)
```

변경은 다음 턴부터 적용된다. `ModelState.model/effort`는 마지막으로 서버에서 관측한
설정이고, `requested/requested_effort`는 요청한 설정이다. `source="requested"`는 아직 관측값과
요청값이 다름을 뜻한다. `server-config`는 서버가 보고한 설정이며 모델 내부 실행 계측을 뜻하지 않는다.
전역 저장(`persist=True`)과 TUI picker 전략은 지원하지 않고 명시적인 오류를 낸다.

- `peek_state()`, `health()`: 실행·대기·한도·연결 상태.
- `pending_interaction()`: 현재 질문·승인 요청.
- `transcript_turns()`: 실제 물리 턴별 프롬프트, 최종 응답, 진행 메시지, 계획, 도구, 오류.
- `screen_tail()`: 최근 활동 로그. **실제 터미널 화면이 아니며** `screen_source="activity_log"`이다.
- `snapshot()`: 세션 ID와 재개에 필요한 경로·설정.

런타임 디렉터리에는 세션 메타데이터, 정규화된 `transcript.json`, 회전하는 `events.jsonl`,
CLI 진단용 `stderr.log`를 저장한다. 상태의 `rate_limits`와 `usage`는 Codex가 보고한 값이며,
`usage_reset_text`의 시각은 원본 Unix timestamp이다. `turn_count`는 로컬 메타데이터가 있을 때
논리 작업 수를 유지하며, 외부에서 생성된 대화를 재개해 메타데이터가 없으면 기록의 물리 턴 수를 사용한다.

## 중단·실패·재개

`interrupt()`는 현재 턴의 종료를 확인한 뒤 `True`를 반환한다(확인 못 하면 `ControlError`;
공유 계약에서 `interrupt() -> bool`이다). `stop()`은 턴과 백그라운드 명령을
정리하고 소유한 서버를 종료한다. `stop(force=True)`는 서버와 소유한 프로세스 트리를 종료한다.
중복 종료는 허용한다. POSIX에서는 다른 프로세스 그룹의 자식도 출생 시각을 확인해 정리하며,
Windows에서는 소유 PID에 `taskkill /T`를 사용한다.

`COMPLETED`는 서버의 성공 완료 이벤트로만 판정한다. 실패, 취소, EOF, 한도 초과, 미지원 요청은
서로 다른 결과다. `STALLED`(진행 이벤트가 `stall_seconds` 동안 없음)와 `DEADLINE_EXCEEDED`
(`turn_timeout` 소진)는 대기만 종료하며 서버 작업이 계속 진행 중일 수 있다. 계속
기다리거나 명시적으로 중단해야 한다. 반복 대기는 작업의 전체 제한 시간을 초기화하지 않는다.
질문·계획에 답하기 위해 호출자에서 보낸 시간은 작업 대기 시간에 합산하지 않는다.

연결 단절·RPC 타임아웃은 자동 재전송하지 않는다. 서버가 요청을 받았는지 불확실할 수 있기 때문이다.
저장된 대화는 명시적으로 재개한다.

```python
h = SessionHandle.resume(saved_session_id, workdir="./my-project", app_dir="./session-logs")
# 기록을 확인하고 다음 행동을 결정한다. 이전 프롬프트가 자동 실행되지는 않는다.
print(h.transcript_turns())
h.stop()
```

## 배치와 CLI

```python
from step2step.codex import run_session

summary = run_session(["hello.txt를 만들어줘.", "파일 내용을 확인해줘."], "./my-project")
assert summary["completed"] == summary["total"] and not summary["aborted"]
```

배치의 `mode="plan"`은 기존 Claude 배치처럼 계획을 자동 승인하고 실행한다. 질문·명령 승인은
`interaction_handler(handle, interaction)` 콜백이 처리한다. 콜백이 없거나 답하지 않으면 배치를
중단한다. `on_turn(record)`는 논리 작업마다 호출한다. `on_stall="skip"`은 중단을 확인한 후
다음 프롬프트로 넘어간다. `pause`는 호출자 개입을 위해 배치를 종료한다. 세션을 유지하는
수동 개입은 `SessionHandle`을 사용한다.

```sh
python -m step2step.codex --prompts prompts.md --list
python -m step2step.codex --workdir ./my-project --prompts prompts.md --mode bypass
python -m step2step.codex --workdir ./my-project --prompts prompts.md --mode plan --turn-timeout 300
```

CLI 종료 코드는 성공 0, 미완료·중단 1, 설정·인증·실행 오류 2다. 실제 모델 ID와 effort는
설치된 CLI가 반환한 목록을 사용하며 Claude 별칭을 Codex에 전달하지 않는다.

## 검증 기록 — 2026-09-10

최종 결과: 전체 비라이브 테스트 **683 passed, 2 skipped** (라이브 9개 제외),
Codex 라이브 테스트 **5 passed**. 마지막 import 정리 후 관련 테스트 168개도 다시 통과했다.
기존 FastAPI/Starlette 테스트 의존성 경고 1개는 이번 변경과 무관하다.

```sh
.venv/bin/python -m pytest -q -m 'not live'
STEP2STEP_CODEX_LIVE=1 .venv/bin/python -m pytest -q -s tests/codex/test_live.py
```

Codex 실제 검증: 파일 생성·연속 수정, 모델·effort 변경, 저장된 대화 재개, 역할 지침 유지, 질문 도구 응답,
계획 거절·재계획·승인·실행, 명령 승인, 작업 중단 후 다음 턴, 별도 CLI의 계획 자동 승인 배치. 각 테스트는 임시 디렉터리를
사용하고 전역 TOML 설정 불변 및 서버 프로세스 종료를 검사한다.

Claude 실제 검증도 시도했으나 로컬 `Claude Code 2.1.267`이 `Login expired · Please run /login`을
반환하여 완료하지 못했다. 로그인 갱신 후 기존 `tests/test_live.py`를 다시 실행해야 한다.
자동 회귀 테스트 결과와 Codex 라이브 결과는 이번 변경의 검증 근거이며, Claude 인증 문제를
코드 회귀로 간주하지 않는다.
