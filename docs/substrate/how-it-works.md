# 동작 원리 (How it works)

## 1. 전체 구조

러너(파이썬 프로세스)가 `claude.exe`를 **ConPTY(가짜 콘솔)** 안에서 띄워, 그 입출력을 완전히
소유합니다. 사람이 보는 터미널 대신 러너가 키 입력을 써넣고 화면을 읽습니다.

```
┌─────────────────────────── 러너 프로세스 (python -m step2step.claude) ────────────────────┐
│                                                                                    │
│   prompts.py ─(프롬프트 리스트)─▶ runner.py (상태기계)                                │
│                                      │   ▲                                          │
│                          write(키 입력)│   │ on_data(바이트)                          │
│                                      ▼   │                                          │
│   hooks.py(신호 감시) ◀──파일──┐   pty_session.py ──▶ ConPTY ──▶ claude.exe (TUI)    │
│                              │        │                                            │
│   screen.py(pyte 화면) ◀─────┘────────┘ (읽은 바이트를 pyte에 먹여 "현재 화면" 유지)    │
└────────────────────────────────────────────────────────────────────────────────┘
                              │
              claude가 Stop 훅 실행 → 신호 파일에 한 줄 append
```

구성요소 4개:

| 구성요소 | 파일 | 역할 |
|----------|------|------|
| PTY 세션 | `pty_session.py` | `claude.exe`를 ConPTY에 spawn, 백그라운드 reader 스레드가 출력을 계속 읽음 |
| 화면 리더 | `screen.py` | 읽은 바이트를 `pyte` 가상 스크린에 먹여 "지금 화면" 텍스트를 제공(상태 판정용) |
| 완료 신호 | `hooks.py` | 세션에 `Stop` 훅을 주입, 턴 종료마다 신호 파일에 한 줄 추가됨. 러너가 카운트 감시 |
| 상태기계 | `runner.py` | 위 셋을 엮어 "주입 → 완료 감지 → 다음" 을 자동 반복 |

## 2. 완료 감지 — 왜 신호 파일인가

TUI는 ANSI 이스케이프로 화면을 다시 그리기 때문에, "턴이 끝났다"를 화면 텍스트만으로 판단하면
취약합니다. 대신 **문서화된 `Stop` 훅**을 씁니다.

- 러너가 임시 설정 파일을 만들어 `claude --settings <file>`로 **그 세션에만** `Stop` 훅을 주입.
- 훅은 작은 파이썬 스크립트(`signal_hook.py`)를 실행해 신호 파일에 한 줄(`타임스탬프\tStop\t세션ID`)을 append.
- `Stop`은 메인 에이전트 턴이 끝날 때 정확히 1회 발생(서브에이전트는 별도 `SubagentStop`이라 오신호 없음).
- 러너는 **프롬프트 제출 직전에 현재 줄 수(baseline)를 기록**하고, 줄 수가 baseline보다 커질 때까지
  대기 → 그 턴이 끝났다는 결정론적 신호. (제출 직전 기록이라 초고속 턴도 레이스 없음.)

보조 안전장치(화면 기반):

- **적응형 스톨**: 신호가 없어도 화면이 변하거나 `esc to interrupt`(작업 중 표시)가 보이면 살아있는
  것 → 죽이지 않음. "신호 없음 + 화면 무변화"가 `STALL_SECONDS`(기본 180s) 지속될 때만 스톨.
- **idle-without-signal 폴백**: 입력창이 분명히 idle이고 조용한데 신호가 안 왔으면(훅 누락 가능)
  경고 로그 후 완료로 간주.

**응답 캡처**: 턴 완료가 감지되면 러너는 그 턴의 응답을 뽑는다 — Claude가 남기는 클린 JSONL
트랜스크립트(`~/.claude/projects/**/<세션ID>.jsonl`)를 core의 transcript 모듈로 파싱해 해당 턴의
`response`(어시스턴트 텍스트)와 `tools`(그 턴에 쓴 툴 이름 목록)를 얻고, 트랜스크립트가 없으면
화면 tail로 폴백한다. 이 값은 턴별 결과 dict와 `on_turn` 콜백으로 상위 앱에 즉시 전달되며, 종료
시 트랜스크립트는 `runtime/transcript-<세션ID>.jsonl`로도 복사된다.

## 3. 입력 주입

```python
write("\x1b[200~" + 프롬프트텍스트 + "\x1b[201~")   # bracketed paste
sleep(0.15)
write("\r")                                         # Enter로 제출
```

bracketed paste로 감싸면 멀티라인·백틱·`---`이 그대로 "붙여넣기"로 들어가 중간 줄바꿈이 제출로
오인되지 않습니다. 마지막의 `\r` 하나만 제출입니다(텍스트는 CRLF→LF로 정규화).

**단, 슬래시 커맨드는 예외입니다.** 붙여넣기로는 명령 팔레트가 열리지 않아(실측), `/model` 같은
커맨드는 `_type_text`가 **한 글자씩** 써넣습니다.

```python
for ch in "/model":            # 한 글자씩 (CHAR_TYPE_DELAY=0.03s)
    write(ch)
# 컴포저가 방금 친 텍스트를 되비출 때까지 확인한 뒤에만
write("\r")
```

에코 확인 전에는 Enter를 보내지 않습니다 — 무엇이 들어갔는지 모르는 입력창에 제출을 눌러선
안 되기 때문입니다. 확인에 실패하면 ESC로 지우고 중단합니다.

## 4. 상태기계 (공통 골격)

```
STARTUP ─▶ TRUST ─▶ INIT_IDLE ─▶ [ 프롬프트 처리 ] × N ─▶ DONE(종료)
                                      │
                                      └─ 모드에 따라 bypass / plan 경로
```

- **STARTUP**: 설정/훅 생성(`_prepare`) → spawn(`_spawn`). argv:
  `claude --session-id <uuid> --settings <file> --dangerously-skip-permissions`
  + 지정했으면 `--model <모델>` `--effort <레벨>` + 호출자의 `extra_args`
  (cwd = 작업 폴더, 환경변수 스크럽). 화면은 200×50 고정(리사이즈 안 함).
- **TRUST**(`_handle_trust`): 트러스트 다이얼로그가 뜨면 수락 시도. 단 `--dangerously-skip-permissions`
  에서는 안 뜨므로 보통 "이미 신뢰됨"으로 통과(안전망으로만 유지).
- **INIT_IDLE**(`_wait_initial_idle`): 입력창이 준비될 때까지 대기.
- **프롬프트 처리 루프**: 모드별(아래). 각 결과를 구조화해 수집.
- **DONE**(`_shutdown`/`_finalize`): 클린 종료 + 산출물 정리.

## 5. bypass 모드 시퀀스 (`_process_prompt_bypass`)

```
baseline = 신호 줄 수
프롬프트 주입 + Enter
└▶ _confirm_working: "esc to interrupt" 또는 신호 증가가 보일 때까지(미보이면 Enter 1회 재전송)
└▶ _wait_for_signal: 신호 > baseline 까지 대기 (적응형 스톨/폴백)
└▶ settle(조용해질 때까지) → 다음 프롬프트
```

## 6. plan 모드 시퀀스 (`_process_prompt_plan`)

plan 모드는 turn이 "승인 메뉴"에서 멈추고 그 지점엔 `Stop` 훅이 **안** 울리는 게 핵심 차이입니다.
또 승인하면 세션이 auto 모드로 바뀌므로, **프롬프트마다 plan 모드로 재진입**합니다.

```
_ensure_mode("plan"):  푸터 줄에 "plan" 키워드가 보일 때까지 shift+tab(=\x1b[Z) 반복(최대 10회)
baseline = 신호 줄 수
프롬프트 주입 + Enter
└▶ _wait_plan_ready: 다음 중 하나까지 대기
      • is_plan_approval(승인 메뉴) → "approval"
      • 신호 > baseline (계획 없이 끝난 경우, 예: 단순 질문) → "signal"
      • idle/스톨 → 폴백/스톨 처리
└▶ approval 이면: approve_base = 현재 신호 줄 수; Enter (기본 하이라이트된 1번 "Yes, and bypass permissions" 선택)
└▶ _wait_for_signal(approve_base): 승인 후 실행 턴이 끝나며 Stop 훅이 울림 → 완료
└▶ settle → 다음 프롬프트(다시 _ensure_mode("plan"))
결과 status = "approved+signal"
```

> **이 툴은 항상 `--dangerously-skip-permissions`로만 띄웁니다. `--permission-mode plan` 플래그는
> 쓰지 않습니다.** 두 플래그를 같이 주면 skip가 이겨서 plan이 안 되기 때문(실측 근거는 findings 문서).
> 그래서 plan 모드는 플래그가 아니라, 사람이 하듯 런타임에 `shift+tab`으로 전환합니다. 즉 이 툴이
> 쓰는 모드는 **bypass(기본)** 와 **plan(shift+tab으로 진입)** 둘 뿐이고, 어느 경우든 **권한 관련**
> 런치 플래그는 `--dangerously-skip-permissions` 하나입니다(모델·effort 플래그는 별개 — 아래 9절).

모드 순환 순서(실측): `bypass → auto → default → accept-edits → plan → (다시 bypass) → …`
`_ensure_mode`는 횟수로 세지 않고 **푸터에 목표 모드가 보일 때까지** 누르므로 시작 모드와 무관합니다.

## 7. 종료 (`_shutdown`)

턴 직후 Claude가 자동-메모리 후처리("running stop hook" / "Churned for 2s")로 잠깐 더 바쁘고,
그때 Ctrl-C를 보내면 종료가 아니라 그 작업이 인터럽트됩니다. 그래서:

```
1) PTY 출력이 멎고(=진짜 idle) 작업 중이 아닐 때까지 ESC로 후처리를 정리하며 대기
2) 짧은 간격(0.25s)의 Ctrl-C 페어 전송 — "Press Ctrl-C again to exit" 확인창 통과
   (확인창이 짧아 0.3s는 되고 0.8s는 안 됨)
3) 안 되면 최후수단으로 terminate
```

## 8. 멈춤(stall) 처리 (`_stall`, `--on-stall`)

신호도 없고 화면도 오래 무변화이거나(또는 예기치 않은 메뉴), 처리할 수 없는 상태가 되면:

- `pause`(기본): 현재 화면을 출력하고, **대화형 터미널이면** 사용자가 인계받아 직접 입력
  (`a`bort / `w`ait / `s`kip / `t`akeover). 비대화형(TTY 아님)이면 안전하게 abort.
- `skip`: 다음 프롬프트로 건너뜀.
- `abort`: 전체 중단.

러너가 **의도적으로 모는** 메뉴는 셋입니다 — plan 승인 메뉴(옵션 1이 하이라이트된 "Yes…"일 때만
Enter, 소멸 확인), `/model` 피커(9절), 그리고 `SessionHandle.answer_menu`가 답하는 AskUserQuestion
위젯(화살표 1키마다 하이라이트를 되읽고, 목표 행이 확인될 때만 Enter — 숫자 키·맹목 Enter 없음).
그 외 번호 목록이 감지되면 자동 진행하지 않고 멈춤 정책을 따릅니다.

**대기는 언제나 유한합니다.** 턴 대기의 `timeout=None`은 "영원히"가 아니라 `DEFAULT_TURN_TIMEOUT`
(2시간)이고 마감은 매 틱 검사됩니다(`deadline_exceeded`). 침묵(`stalled`)과 별도로, 출력은 계속
나오는데 트랜스크립트·훅 이벤트·(하네스가 주는) 작업트리 해시가 30분간 그대로면
`noisy_stagnation`으로 끝납니다 — 자율 실행 기록의 5시간 반짜리 턴이 이 둘 다 없어서 났습니다.
그리고 프롬프트 제출은 확인됩니다: 작업 표시·신호·이벤트·다이얼로그 중 하나가 보여야 "시작됐다"이고,
idle로 끝났는데 트랜스크립트가 안 늘었으면 직전 턴의 응답 대신 `submit_failed`를 돌려줍니다.

## 9. 모델·effort 제어

세션이 쓸 모델과 추론 effort를 정하는 길은 둘입니다.

**기동 시(권장)** — `--model`/`--effort`를 argv에 얹습니다(4절 STARTUP). TUI를 전혀 건드리지 않고,
사용자 전역 설정도 바꾸지 않으며, 대화 캐시도 멀쩡합니다. "작업 난이도에 맞춰 세션을 나눠 띄운다"는
쓰임은 이것만으로 끝납니다.

**세션 도중** — 컨텍스트를 버릴 수 없을 때, 사람이 하듯 `/model` 피커를 몹니다.

```
/model 을 한 글자씩 타이핑 + 에코 확인 → Enter
└▶ 피커 렌더 대기 → 파싱(행 목록·하이라이트·effort 위젯·푸터 힌트)
└▶ ↑↓ 로 목표 모델 행까지 (매 누름 전 상태 재검증, 누른 뒤 하이라이트 이동 확인)
└▶ ←→ 로 목표 effort 까지 (매 조절 후 행이 안 밀렸는지도 확인)
└▶ 커밋 직전 한 번 더 재독 — 하이라이트와 effort가 요청과 같은가?
└▶ `s`(세션 한정) 또는 Enter(전역 기본값 저장)
└▶ "Switch model?" 캐시 무효화 확인창이 뜨면 옵션 1을 확인하고 Enter
└▶ "Set model to <X> …" 시스템 줄을 baseline 대비로 확인
```

매 키 직전에 다시 봅니다 — 세션이 죽었는가, 턴이 끝났는가(Stop 카운트 증가), 질문 메뉴가
떴는가, 작업이 시작됐는가, 다이얼로그가 사라졌는가. 하나라도 걸리면 **다음 키를 누르지 않고**
멈춥니다. 검증에 실패하는 어떤 경로도 커밋 키를 쓰지 않고 ESC로 빠져나옵니다. 하이라이트를
못 읽으면 추측하지 않고 중단합니다.

세션 도중 변경은 **다음 턴에 전체 히스토리를 다시 읽게 만듭니다**(TUI가 그렇게 경고합니다).
이미 목표 상태면 키를 하나도 보내지 않고 단락합니다. 그리고 effort는 어떤 경로로 바꾸든
사용자 전역 `effortLevel`이 기록됩니다 — 세션 한정 effort는 기동 `--effort`만 가능합니다.
실측 표와 피커 렌더링 전문은 findings 문서에, 함수 단위 상세는 implementation 문서에 있습니다.
