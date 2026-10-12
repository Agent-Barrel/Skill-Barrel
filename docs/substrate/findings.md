# 실측 검증 & 설계 결정 (Findings & Decisions)

이 문서는 구현 중 **실제로 띄워서 확인한** Claude Code TUI(v2.1.195) 동작과, 그에 따른 설계
결정의 "왜"를 정리합니다. 화면 인식이 깨지거나 동작을 바꿀 때 먼저 보세요.

## A. 실측으로 확인한 사실

### 권한/트러스트
- `--dangerously-skip-permissions`로 띄우면 **워크스페이스 트러스트 다이얼로그가 안 뜨고**, 턴
  중 권한 프롬프트도 없음 → 완전 무인 가능. (사용자 전역 설정의 `skipDangerousModePermissionPrompt`
  덕에 "bypass로 시작?" 확인창도 안 뜸.)
- 참고: 인터랙티브(TTY)이면서 스킵이 아닐 때는 새 폴더에서 트러스트 다이얼로그가 뜰 수 있음
  (그래서 `_handle_trust` 안전망 유지).

### 화면 마커
- **작업 중**: 푸터에 `esc to interrupt` 표시(가장 안정적인 "working" 신호).
- **idle**: 입력창 + 푸터 `⏵⏵ … (shift+tab to cycle)`. `shift+tab to cycle`은 idle/working 양쪽에서
  항상 보여 idle 판정의 anchor로 적합(웰컴 배너가 스크롤돼도 유지됨).
- **스피너 동사는 랜덤**("Shenaniganing…", "Hashing…", "Crystallizing…" 등) → 특정 동사에 의존 금지.
- 입력창 프롬프트 문자는 `❯`.
- **다이얼로그 판별은 `screen.classify_dialog` 하나로 모은다** — `plan_approval` / `question` /
  `unknown` / `None`. "번호 목록이 보인다"는 판별이 아니다(응답 본문도 번호 목록을 쓴다);
  각 다이얼로그 고유 문구가 판별자다. 자세한 내용은 아래 두 절.

### Stop 훅
- 메인 에이전트 턴 종료마다 **정확히 1회** 발생. 서브에이전트는 별도 `SubagentStop`이라 우리
  신호엔 안 잡힘.
- **plan 모드의 승인 메뉴에선 Stop 훅이 안 울림**(에이전트가 턴 도중 사용자 선택 대기 상태).
  → plan의 "계획 완료"는 화면(승인 메뉴)으로 감지해야 함.
- **승인 직후 실행 턴에서는** Stop 훅이 정상적으로 울림 → 그걸로 실행 완료 감지.
- 훅의 `args` 폼이 v2.1.195에서 동작 확인(신호 파일에 줄 추가됨).

### 대기 중 상호작용은 트랜스크립트에 없을 수 있다 (2.1.224~225 실측) ⚠

`transcript.pending_tool_use()`를 **실시간 감지기로 쓰면 안 된다.** 대기 중인
`AskUserQuestion`/`ExitPlanMode`의 `tool_use` 행은 JSONL에 **없을 수 있고**, 해소되는
시점에 **원래 타임스탬프로 소급 기록**된다 — 사후에 보면 처음부터 있었던 것처럼 보인다.

| 관측 | 결과 |
|---|---|
| 장시간 세션(백그라운드 셸 + 서브에이전트 3개)이 질문 메뉴에서 대기 | 7시간 반 동안 415 레코드 중 **0건**. ESC로 접은 뒤에야 index 417에 ts=메뉴가 뜬 시각으로 등장 |
| `calibrate_dialogs` throwaway 세션 3회 | 2회는 대기 중에도 행이 **있었고**, 1회는 **없었다**(`pending_interaction.source`가 transcript/screen으로 갈림) |

즉 존재 여부가 실행마다 다르다 → **판정은 화면(`screen.classify_dialog`)이 하고, 트랜스크립트는
이미 내용이 있을 때만 원문 보강용으로 쓴다.** 이 전제를 믿던 코드가 실제로 무엇을 놓쳤는지는
`docs/guide/09-questions-autopilot.md` §2.1 참고.

### AskUserQuestion 위젯 (실측 2.1.225)
- 판별자는 위젯 **푸터**: `Enter to select · … · Esc to cancel`. **중간 문구는 모양에 따라 다르다** —
  질문이 여럿이면 `Tab/Arrow keys to navigate`, 하나면 `↑/↓ to navigate`. 그래서 마커는 양 끝만 쓴다.
- 질문이 여럿이면 탭 바 `←  ☐ a  ☐ b  ✔ Submit  →`, 하나면 헤더 행 ` ☐ Config format`.
- 위젯이 스스로 붙이는 행 `3. Type something.` / `4. Chat about this`는 답이 아니다. 게다가 **3과 4
  사이에 구분선이 끼어** 옵션이 연속되지 않으므로, 구분선에서 파싱을 끊으면 4를 놓친다.
- 작업 패널(`4 tasks …` + todo)이 위젯 **아래에** 렌더된다 → 꼬리 10줄만 보면 옵션을 통째로 놓친다.
- **ESC로 접힌다**(실측). 다만 대기 중인 위젯은 `is_working`이 아니므로 working만 보고 ESC를 누르는
  로직은 한 번도 키를 안 보낸다 — `Runner.interrupt()`가 이것 때문에 무동작이었다.
- 실화면은 `tests/fixtures/screens/`에 고정돼 있고, 재캡처는
  `python -m step2step.core.calibrate_dialogs <throwaway-dir> [--save]`.

### plan 승인 메뉴 (실측)
- 메뉴 옵션 **(2.1.225 재확인)**: `1. Yes, and bypass permissions` / `2. Yes, manually approve edits` /
  `3. Tell Claude what to change`(+ 들여쓴 `shift+tab to approve with this feedback`).
  **기본 하이라이트 `❯`는 1번**. (구버전에서 관측되던 `No, refine with Ultraplan …`은 사라졌다.)
- 앵커 문장은 `Claude has written up a plan and is ready to execute. Would you like to proceed?`이고,
  그 **위쪽에** `Ready to code?` 배너와 **플랜 본문**이 함께 떠 있다. 본문에 번호 목록이 있으면
  옵션으로 오인되므로 **앵커 아래만** 파싱해야 한다(`screen.plan_approval_options`).
- 승인(Enter) 직후에도 메뉴가 잠시 화면에 남는다("잔상"). 바로 다시 상태를 물으면 승인 대기로
  또 읽히므로, 답한 쪽은 **메뉴가 사라지는 것을 확인한 뒤** 다음 대기로 넘어가야 한다.
- **옵션 1 텍스트는 런치 방식에 따라 다름**: `--dangerously-skip-permissions` 런치 →
  `"Yes, and bypass permissions"`(원래 bypass로 복귀), `--permission-mode plan` 런치 →
  `"Yes, and use auto mode"`. 둘 다 "무인 진행"이고 항상 1번·기본값이라 **Enter 한 번으로 정확히
  선택됨**.
  - ※ **이 툴은 항상 `--dangerously-skip-permissions`로만 띄우므로 실제로는 늘
    `"Yes, and bypass permissions"`를 봅니다.** (`--permission-mode plan`은 사용하지 않음 — 위
    "use auto mode"는 비교용 관찰일 뿐.)
- 승인 전엔 작업 파일이 안 생기고(계획 단계는 읽기 위주) 신호=0, 승인(Enter) 후 실행되어 파일이
  생성되고 Stop 훅 발생. 즉 **"계획 → (작업 안 함) → 1번 선택 → 실제 작업 수행"이 실측 PASS**
  (예: `approve_proof.txt`에 `LINE1`/`LINE2` 두 줄 생성 확인).

### 종료
- `Ctrl-D`(EOF)·`sendeof`로는 종료 안 됨. **`Ctrl-C`(raw `\x03`)** 로 종료됨.
- "Press Ctrl-C again to exit" **확인창이 짧음**: 두 번째 Ctrl-C가 빨라야 함(실측: 0.3s 간격은
  종료, 0.8s 간격은 실패=확인창만 다시 뜸).
- 턴 직후 Claude가 **자동-메모리 후처리**("running stop hook" / "Churned/Crystallizing for Ns")로
  잠깐 더 바쁨. 이때 Ctrl-C는 종료가 아니라 그 작업을 인터럽트. → 종료 전 **PTY 출력이 멎을
  때까지(진짜 idle) 기다리고**, 필요시 ESC로 후처리를 정리한 뒤 Ctrl-C 페어를 보냄.
- 빈(턴 없는) 세션은 Ctrl-C 페어로 바로 종료됨.

### 모드 전환 (shift+tab)
- `shift+tab` = `\x1b[Z`. ConPTY로 잘 전달됨.
- 순환 순서: `bypass → auto → default → accept-edits → plan → (다시 bypass) → …`
- 횟수로 세면 키 입력이 한 번 씹힐 때 어긋남 → **푸터에 목표 모드가 보일 때까지 반복**이 안전.

### 플래그 조합
- `--dangerously-skip-permissions`와 `--permission-mode plan`을 같이 주면 **순서 무관하게 skip가
  우선**(푸터 `bypass permissions on`, 승인 메뉴 없이 바로 실행). → plan 모드는 런타임 `shift+tab`로.

| 플래그 | 결과 모드 |
|--------|-----------|
| `--permission-mode plan` 단독 | plan mode on |
| `--dangerously-skip-permissions` 단독 | bypass permissions on |
| 둘 다(어느 순서든) | **bypass permissions on** |

### 입력/붙여넣기
- bracketed paste로 멀티라인 입력 OK(중간 줄바꿈이 제출로 오인되지 않음).
- 매우 큰 붙여넣기(>10k)는 UI에 `[Pasted …]` 플레이스홀더로 보이지만 내용은 전송됨.
- 선행 `/`(슬래시 커맨드)·`!`(셸)·`@`·`#`는 특수 취급될 수 있음 → 일반 텍스트 프롬프트 권장.
- 슬래시 커맨드(예: 종료용 `/exit`)는 **한 글자씩** 타이핑해야 명령 팔레트가 인식(한 번에
  `"/exit"` 쓰면 안 먹음). 단 팔레트 하이라이트가 들쭉날쭉해 종료엔 Ctrl-C가 더 안정적.

### 모델·effort 제어 (2.1.220 실측, calibrate_model V7~V20)

**기동 플래그**
- `--model <alias|full>`과 `--effort <low|medium|high|xhigh|max>`가 인터랙티브 기동에서 그대로 먹는다.
  `--dangerously-skip-permissions`와 함께 써도 문제없다.
- 트랜스크립트 assistant 레코드가 실측을 준다: 모델은 `message.model`, effort는 **레코드 최상위
  `effort` 필드**. effort를 보고하지 않는 모델(haiku)은 `null`이다.
- 기동 플래그는 **전역 설정을 건드리지 않는다.** 세션 하나에만 적용된다.

**`/model` 피커 (`/model`을 인자 없이 제출)**

```
  Select model
  Switch between Claude models. Your pick becomes the default for new sessions. …

    1. Default (recommended)  Opus 5 with 1M context · Best for everyday, complex tasks
    2. Opus (1M context)      Opus 5 with 1M context · Best for everyday, complex tasks
    3. Fable                  Fable 5 · Most capable for your hardest and longest-running tasks
    4. Sonnet                 Sonnet 5 · Efficient for routine tasks
  ❯ 5. Haiku ✔                Haiku 4.5 · Fastest for quick answers

  ○ Low effort ←/→ to adjust                 ← 미지원 모델이면 "○ Effort not supported for Haiku"
  Use /fast to turn on Fast mode (Opus 5).
  Enter to set as default · s to use this session only · Esc to cancel
```

- 행에 **번호와 `❯` 포인터가 둘 다 있다.** 이름과 설명은 **공백 2칸 이상**으로 나뉘고, `✔`가
  현재 모델을 가리킨다. 200×50에서 모델 5개는 전부 보였다(`… +N models` 오버플로 미재현).
- **↑/↓ = 모델 행, ←/→ = effort.** effort 위젯은 행별이 아니라 **목록 전체에 한 줄**이고 항상
  포커스된 행의 값을 보여준다 → 반드시 **행 먼저, 그다음 effort**, 그리고 매 조절 후 행이
  안 움직였는지 확인해야 한다.
- effort 사다리: `low → medium → high → xhigh → max`(바 `/effort` 슬라이더에는 `ultracode`도 있다).
- **Esc는 진짜 no-op**이다 — `⎿  Kept model as <X>`만 찍고 아무것도 바꾸지 않는다.

**세션 중 변경은 대화 캐시를 무효화한다**
- 커밋하면 2차 확인창이 뜬다. **턴이 하나라도 지난 세션에서만** 나타난다(빈 세션에선 안 나옴).

```
  Switch model?
  Your next response will be slower and use more tokens
  This conversation is cached for the current model. Switching to Opus 5 (1M context) (default)
  means the full history gets re-read on your next message.
  ❯ 1. Yes, switch to Opus 5 (1M context) (default)
    2. No, go back
```

- 번호 + `❯`의 평범한 선택 메뉴라 기존 `menu_options`/`highlighted_option`으로 그대로 읽힌다.
  옵션 1이 기본 하이라이트다.
- 비용: 수락하면 **다음 메시지에서 전체 히스토리를 다시 읽는다.** 긴 세션일수록 비싸다 →
  기본은 기동 플래그, 세션 중 변경은 의도적으로만.

**어떤 경로가 사용자 전역 `~/.claude/settings.json`을 쓰는가 (핵심)**

`model`/`effortLevel` 두 키를 매 키 입력 전후로 읽어 확인했다.

| 경로 | 전역 `model` | 전역 `effortLevel` | 화면에 찍히는 줄 |
|---|---|---|---|
| `--model` / `--effort` 기동 플래그 | 안 씀 | 안 씀 | (없음) |
| 피커 + `s`, effort 손 안 댐 | **안 씀** | **안 씀** | `Set model to <X> for this session only` |
| 피커 + ←/→ + `s` | 안 씀 | **씀** | `Set model to <X> for this session only with <e> effort` |
| 피커 + Enter | **씀** | **씀** | `Set model to <X> and saved as your default for new sessions` |
| `/model <alias>` | **씀** | 안 씀 | `Set model to <X> and saved as your default for new sessions` |
| `/effort <level>` | 안 씀 | **씀** | `Set effort level to <e> (saved as your default for new sessions): <설명>` |

- 즉 **세션 한정 effort 변경 경로는 세션 중에 존재하지 않는다.** 피커가 "for this session only"라고
  찍어도 effort는 전역에 기록된다. 세션별 effort를 원하면 **기동 시 `--effort`가 유일한 방법**이다.
- `/model <alias>`는 확인창 없이 바로 적용되고 전역 기본값을 바꾼다.
- 확정 줄들은 스크롤백에 남는다 → 검증은 Stop 훅과 같은 **baseline 상대 비교**여야 한다.

**바 `/effort` 슬라이더는 열지 않는다**

```
  Effort
                    Faster                                 Smarter
                    ──────────▲────────────────────────────────┆──────────────────
                    low     medium     high     xhigh      max       ultracode
  ←/→ to adjust · Enter to confirm · Esc to cancel
```

- 값이 **삼각형 마커의 좌표**로만 표현돼 평문 파싱이 위치 의존적이다. 게다가 이 화면은
  `is_model_dialog`/`is_switch_confirm`/`looks_like_question` 어디에도 안 걸리고 `looks_idle`이
  True다 — 열어 두면 러너가 유휴로 오판한다. 그래서 **항상 인자형 `/effort <level>`을 쓴다.**

**그 밖**
- 피커가 열려 있는 동안 `looks_like_question`이 True다 → `peek_state()`가 `AWAITING_UNKNOWN_DIALOG`로
  오분류한다. 모델 조작은 턴 사이에만 하므로 실사용에서 문제되지 않지만, 실패 경로가 반드시
  `finally`에서 다이얼로그를 닫아야 하는 이유다.
- 배너 첫 줄에 현재 상태가 찍힌다(`Sonnet 5 with medium effort · Claude Max`). 다만 배너는 긴
  세션에서 스크롤아웃되므로 상태 소스로 쓰지 않는다.
- 미측정: `ANTHROPIC_MODEL`(스크럽 대상이 아님)과 명시 `--model`의 우선순위, 모델이 많을 때의
  `… +N models` 가상화 동작, effort 양끝에서의 wrap 여부.

### 트랜스크립트
- **정정 (2.1.215 실측)**: PTY 구동 세션도 `~/.claude/projects/**/<sid>.jsonl`을 실제로 남긴다
  → `runtime/transcript-*.jsonl`로 복사되고 `result["transcript"]`로 노출된다. core의 transcript 모듈이
  이를 per-turn `{prompt, response, tools}`로 파싱한다(F7 응답 캡처의 기반). 없을 때를 대비한
  항상 존재하는 폴백 기록은 `runtime/pty-*.log`(원본 전체). (초기 문서의 "JSONL을 남기지 않음"은
  구버전 관찰로, 현재는 반증됨 — 검수 보고서(inspection-2026-07-20) 참고.)
- 턴마다 `~/.claude/projects/<slug>/memory/`에 auto-memory 디렉터리가 생김.
- **다만 "완료된 대화의 기록"이다.** 아직 해소되지 않은 상호작용은 안 들어 있을 수 있으므로
  실시간 상태 판정에 쓰면 안 된다(위 "대기 중 상호작용은 트랜스크립트에 없을 수 있다" 참고).

### 환경(pywinpty)
- `pywinpty` 3.0.5 / `pyte` 0.8.2는 휠로 설치(컴파일러 불필요). `node-pty`는 Node 24에서 네이티브
  빌드가 필요해 회피.
- `PtyProcess.spawn(argv, cwd, env, dimensions=(행,열))`, `read()`는 str 반환·EOF 시 `EOFError`.
- 러너가 비대화형(툴) 부모에서 돌아도 ConPTY는 새 가짜 콘솔을 만들므로 정상 동작.

## B. 설계 결정 (왜 이렇게 했나)

| 결정 | 이유 |
|------|------|
| **Python + pywinpty + pyte** | 휠 설치로 컴파일러 불필요. node-pty는 Node 24 네이티브 빌드 리스크. |
| **완료 = Stop 훅(신호 파일)** | 화면 텍스트 추정보다 결정론적·버전 안정적(문서화된 기능). |
| **`--settings` 파일 + `args` 폼** | 인라인 JSON의 Windows 따옴표 지옥, 셸(Git-Bash vs PowerShell) 모호성 회피. |
| **제출 직전 baseline 기록** | 초고속 턴에서도 신호 레이스 없음. |
| **적응형 스톨(고정 타임아웃 X)** | 20분짜리 정상 빌드 턴을 죽이지 않기 위해. "신호無+화면無변화"만 스톨. |
| **env 스크럽(API 키 제거 등)** | 구독 사용 보장(비용 방지) + 깨끗한 최상위 세션. |
| **화면 200×50 고정, 리사이즈 안 함** | 리사이즈는 전체 재드로로 화면 스크래핑을 깨뜨림. 작은 화면은 컴팩트 레이아웃이라 마커가 달라짐. |
| **plan: 플래그 대신 shift+tab** | 플래그 조합이 안 됨(skip 우선). 런타임 전환이 유일하게 동작. |
| **plan 승인: 옵션 1 자동 선택(Enter)** | 옵션 1은 "무인 진행"(skip 런치선 "Yes, and bypass permissions")이고 항상 기본 하이라이트라 Enter로 정확히 선택됨. "manually approve edits"는 편집마다 멈춰 자동화 부적합. |
| **종료: ESC 정리 후 Ctrl-C 페어** | 자동-메모리 후처리 중 Ctrl-C는 종료가 아니라 인터럽트라서. |
| **마커를 screen.py에 집약** | TUI 문자열 변화 시 한 파일만 고치면 됨. |
| **모드 판정은 푸터 키워드** | 푸터 줄에서 `plan`/`bypass` 등 키워드만 봄. 문구 변경에 강하고, 화면 다른 곳의 "plan" 단어 오판 방지. |
| **claude 버전 고정 안 함** | 사용자 요구. 항상 최신 claude 사용(auto-update). TUI가 바뀌면 핀이 아니라 core의 screen 모듈 마커를 calibrate로 재튜닝해 대응. |
| **모델/effort 기본은 기동 플래그** | `--model`/`--effort`는 TUI를 전혀 건드리지 않고, 전역 설정도 안 쓰고, 캐시 무효화도 없다. "작업 단위마다 난이도에 맞는 새 세션"이라는 주 사용처가 이것만으로 충족된다. 세션 중 전환은 컨텍스트를 못 버릴 때만. |
| **피커 커밋 기본은 `s`(세션 한정)** | Enter는 사용자 전역 `~/.claude/settings.json`의 `model`을 덮어쓴다(실측). 구동된 자식 세션이 조작자의 기본값을 말없이 바꾸면 안 된다. `persist=True`일 때만 Enter. 푸터에 `s` 힌트가 없으면 **Enter로 폴백하지 않고 실패**시킨다 — 폴백이야말로 막으려는 그 사고다. |
| **effort 변경은 `persist=True` 필수** | 실측상 세션 중 effort를 바꾸는 모든 경로가 전역 `effortLevel`을 쓴다(피커의 세션 한정 커밋조차). 조용히 전역을 바꾸느니 거절하고 "기동 시 `--effort`를 쓰라"고 말하는 편이 정직하다. |
| **피커는 키 주입 금지 규칙의 문서화된 예외** | AskUserQuestion 메뉴에 키를 안 넣는 이유는 "오해석 시 엉뚱한 항목을 **실행**"이다. 피커는 다르다 — ① 잘못 골라도 모델 선택일 뿐이고 즉시 확정 줄로 인쇄되며 트랜스크립트로 독립 검증된다, ② 인덱스가 아니라 **알려진 목표 라벨**과 매칭한다(닫힌 정적 목록), ③ Esc가 진짜 no-op이라 중단이 공짜다, ④ 커밋 키는 행과 effort를 **같은 틱에 재검증한 뒤에만** 쓰인다. 모든 실패는 Esc를 쓰지 커밋 키를 쓰지 않는다. |
| **바 `/effort` 슬라이더는 안 연다** | 값이 삼각형 마커의 좌표로만 표현돼 위치 의존 파싱이고, 열려 있으면 `looks_idle`이 True라 러너가 유휴로 오판한다. 인자형 `/effort <level>`만 쓴다. |
| **하이라이트 못 읽으면 추측 금지** | `parse_model_dialog`는 포인터도 스타일도 유일하지 않으면 `highlighted=None`을 **1급 결과로** 반환하고, 드라이버는 Esc 후 실패한다. 추측이야말로 잘못된 모델을 커밋시키는 유일한 길이다. |

## C. 한계 / 주의

- **비공식 통합**: TUI 구동은 공식 지원 경로가 아님(공식은 `-p`/SDK). 화면 의존부는 Claude 버전
  변화에 취약 → `python -m step2step.core.calibrate`로 재튜닝.
- **plan 모드 비용/속도**: 단계마다 계획+승인+실행이라 bypass보다 느림.
- **자유서술형 되물음**: Stop 훅은 Claude가 질문으로 턴을 끝내도 울림. 번호 메뉴는 멈춤 가드로
  잡지만, 자유서술형 질문은 스톨 경로로만 감지 → **자기완결형 프롬프트 권장**.
- **슬래시/특수 시작 프롬프트**: `/`·`!`로 시작하는 프롬프트는 별도 처리 필요(현재 일반 텍스트 가정).
  모델 제어 경로만 예외로 슬래시 커맨드를 **한 글자씩** 타이핑하고, 컴포저 에코를 확인한 뒤에만
  Enter를 보낸다.
- **세션 중 모델/effort 변경은 전체 히스토리 재읽기를 유발한다.** 긴 세션에서는 실질 비용이 크다.
  이미 목표 상태면 아무 키도 보내지 않고 단락시킨다(`force=False`).
- **세션 한정 effort는 세션 중에 불가능하다.** 기동 시 `--effort`만이 전역을 안 건드린다.
