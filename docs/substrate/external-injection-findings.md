# 이미 실행 중인 Claude Code 세션에 주입하기 — 검증 결과 (PoC)

> **리팩터링 주석 (2026-07-23)**: 이 문서는 작성 시점의 레이아웃 기준 기록이다. 이후
> 패키지가 통합되어 — 당시 `poc/` = 현 `step2step/core/`, 당시 `external/` = 현
> `step2step/attach/` — 본문 경로·모듈명·명령(`python -m poc` → `python -m step2step`,
> `python -m external.attach_runner` → `python -m step2step.attach.attach_runner`)은
> 원문 그대로 둔다.

> 요약: **된다.** 우리가 ConPTY로 소유하지 않은(남이 이미 띄운) Claude Code 세션에도
> **키 입력 주입 + 화면 읽기**가 가능하며, **classic conhost와 Windows Terminal(ConPTY)
> 양쪽 모두에서 프롬프트 제출 → 실행 → 완료 감지 → 응답 수신까지 E2E로 검증**됐다.
> 방식은 Windows 콘솔 API: `AttachConsole` + `WriteConsoleInput`(주입) +
> `ReadConsoleOutputCharacter`(읽기). 이 문서는 그 실험 하네스(`external/`)와 실측 결과,
> 그리고 러너 통합 스케치다.

## 1. 결론 (실측 표)

`external/experiment.py`로 throwaway Claude 세션을 conhost·WT 각각에 띄워 attach·측정:

| 단계 | 내용 | conhost | WT (ConPTY) |
|------|------|:---:|:---:|
| B | attach + 화면 스크랩 + `looks_idle` 감지 | ✅ | ✅ |
| **C1** | **텍스트 주입이 입력 프롬프트에 표시 (핵심)** | ✅ | ✅ |
| C2 | backspace로 문자 삭제 | ✅ | ✅ |
| C2 | shift+tab로 권한 모드 전환(bypass→auto) | ✅ | ✅ |
| C2 | esc로 입력줄 클리어 | ❌ | ❌ |
| **D** | **프롬프트 제출 → 실행 → 완료 감지 → `PROBE_OK` 응답** | ✅ | ✅ |

증거 로그: `runtime/attach-experiment-conhost.log`, `runtime/attach-experiment-wt.log`
(각 단계의 스크랩 화면 원문 포함).

> 특히 **WT/ConPTY 세션에 제3자(무관한 detached 프로세스)가 AttachConsole해서 주입**되는지가
> 이 use-case의 관건이었는데, 실측으로 **된다**가 확인됐다. 이게 안 됐다면 접근 자체가 무의미했다.

## 2. 왜 되는가 (핵심 원리)

Windows에서 Node/Ink 기반 raw-mode TUI는 콘솔 호스트가 주는 VT 바이트 스트림을 읽는 게
**아니다**. `process.stdin.setRawMode(true)` → libuv `uv_tty_set_mode(RAW)`는 콘솔 입력 모드를
`ENABLE_WINDOW_INPUT`으로 두고(‑ `ENABLE_VIRTUAL_TERMINAL_INPUT` 아님), **`ReadConsoleInputW`로
`INPUT_RECORD`를 직접 읽어** 스스로 VT 이스케이프로 변환한다.

따라서 그 **입력 버퍼에 `INPUT_RECORD`를 넣으면** 곧 키 입력이다 — 그게 `WriteConsoleInput`이다.
ConPTY도 동일 버퍼를 쓴다(`VtInputThread`가 터미널의 VT를 파싱해 같은 InputBuffer에 `INPUT_RECORD`를
append). 즉 우리가 `WriteConsoleInput`으로 채우는 버퍼 = libuv가 `ReadConsoleInput`으로 비우는 버퍼.
conhost든 ConPTY든 원리가 같아서 양쪽 다 통한 것이다.

읽기(`ReadConsoleOutputCharacter`)는 콘솔 화면 버퍼를 비파괴적으로 스크랩하며, 창 포커스/가시성과
무관하게(픽셀이 아니라 버퍼를 읽으므로) 동작한다.

## 3. 실측된 키 인코딩 (`external/winconsole.py`의 `SPECIAL_KEYS`)

| 논리 키 | `INPUT_RECORD.KeyEvent` | 상태 |
|--------|-------------------------|------|
| 일반 문자 | `UnicodeChar=<char>` (문자당 keydown 1개) | ✅ 37자 주입·표시 확인 |
| Enter | `UnicodeChar=0x0D, VK=0x0D` | ✅ 제출됨 |
| Backspace | `UnicodeChar=0x08, VK=0x08` | ✅ 삭제됨 (0x7F 변형도 준비돼 있으나 0x08로 충분) |
| Shift+Tab | `VK=0x09(TAB), dwControlKeyState=SHIFT_PRESSED(0x10)` | ✅ 모드 순환 |
| Esc | `UnicodeChar=0x1B, VK=0x1B` | ⚠ 키는 들어가나 **입력줄 클리어 효과 없음** |
| Ctrl+C | `UnicodeChar=0x03, VK=0x43, LEFT_CTRL_PRESSED(0x08)` | ⛔ 미검증(세션 종료 위험으로 제외) |

- **입력 클리어는 esc가 아니라 backspace 반복**으로 해야 한다(실험의 `_clear_input`이 그렇게 함).
- **멀티라인/bracketed-paste**(`\x1b[200~ … \x1b[201~`)는 이번에 격리 검증 안 함 → 다음 단계.
  단일 라인은 문자별 keydown 주입으로 충분.

## 4. "합법 IPC 채널"은 왜 못 쓰나

실행 중인 `claude.exe` CLI는 **인바운드 포트를 하나도 열지 않는다**. `~/.claude/ide/<port>.lock`의
WebSocket은 **VS Code 확장이 서버, CLI가 클라이언트**이고, 노출 메서드는 에디터 툴(선택영역·진단·
diff)과 `selection_changed`/`at_mentioned` 알림뿐 — **대화에 사용자 턴을 밀어넣는 메서드가 없다**
(CVE-2025-52882도 파일 유출/에디터 조작이지 입력 주입이 아님). 그래서 라이브 세션에 사용자 프롬프트를
넣는 길은 **콘솔 stdin 키 주입**뿐이고, 이 문서의 방식이 유일하게 성립하는 경로다.

## 5. 리더 선택: 콘솔 읽기 채택 (UIA 불필요)

- `ReadConsoleOutputCharacter`가 conhost·WT 양쪽에서 **가시 프레임 전체(배너+푸터+입력박스)를 정확히**
  반환했고(idle 감지 그대로 통과), 창이 백그라운드/가려져 있어도 동작한다.
- UIA `TextPattern`은 이론상 대안이지만, **대상 창 HWND 탐색이 까다롭다**(WT 멀티탭, conhost 창조차
  `EnumWindows`로 즉시 안 잡힘 — `uia_compare.py`에서 hwnd=0). 이 use-case엔 이점이 없어 **불필요**.
  `external/uia_reader.py`는 참고/폴백용으로만 남겨둔다.

## 6. 안전장치 (진짜 세션 격리)

- **new-pid-diff**: 런치 직전 `claude.exe` PID 집합을 스냅샷하고, 런치 후 **새로 생긴** PID만
  타깃으로 삼는다. 사용자의 라이브 세션·데스크톱 앱·VS Code 확장은 전부 "이전" 집합이라 **구조적으로
  제외**된다. 추가로 부모가 콘솔 호스트(conhost/OpenConsole/WindowsTerminal)인지 확인해 TUI 프로세스로 고정.
- **guard 파일**: 오케스트레이터가 sanction한 단 하나의 PID를 `runtime/attach-target.pid`에 적고,
  `winconsole` CLI는 `--pid`가 그 파일과 정확히 일치하지 않으면 **attach 전에 거부**(Phase A에서 잘못된
  PID 거부까지 확인).
- **콘솔 격리**: attach/inject/read는 항상 **detached(콘솔 없는) 자식 프로세스**에서 수행 →
  `AttachConsole`/`FreeConsole` 댄스가 우리(러너/현재 세션) 콘솔을 절대 안 건드림.
- **하이젠 규칙**: 컨트롤러는 `WriteConsoleInput`+`ReadConsoleOutput`만. `ReadConsoleInput` **금지**
  (타깃의 키를 훔쳐 "Enter 두 번" 버그 유발).

## 7. 하네스 파일 (`external/`)

| 파일 | 역할 |
|------|------|
| `winconsole.py` | ctypes: Attach/Free, `WriteConsoleInputW`, KEY_EVENT 빌더, `ReadConsoleOutputCharacterW`. CLI(op=inject/keys/read) + guard + detached `run_op` |
| `target.py` | throwaway Claude를 conhost/WT에 런치, new-pid-diff로 안전 탐지, guard 기록, kill |
| `experiment.py` | Phase B~D 오케스트레이션, `poc/screen.py` 술어로 판정, 로그 기록 |
| `probe.py` | Phase A: Claude 없이 더미 콘솔로 배관 검증 |
| `uia_reader.py`, `uia_compare.py` | (선택) UIA 리더 + 콘솔 리더 비교 |

재사용: `poc/screen.py`의 상태 술어(`looks_idle`/`is_working`/`current_mode`), `poc/runner.py`의
`child_env`/`resolve_claude`.

## 8. 구현: attach 러너 (`external/session.py` + `external/attach_runner.py`)

스케치를 실제 구현했다. **별도 러너** 방식(튜닝된 `poc/runner.py` ConPTY 경로는 **무손상**), **bypass 전용**.
깨끗한 이음새는 `poc/runner.py`의 `text()`(화면 소스)와 `pty.write`(입력 싱크)였고, attach 러너는 이 둘을
콘솔 API로 대체하되 `poc/screen.py` 술어와 `poc/runner.py` 상수를 그대로 재사용한다.

- **`ExternalSession`** (`external/session.py`) — 대상 PID에 **세션 내내 한 번 attach 보유**(러너
  프로세스 안에서 직접 API 호출 → 폴링 빠름):
  - `type_text(s)` / `key(name)` / `clear_input()`(backspace 반복) → `WriteConsoleInput`
  - `text()` → `ReadConsoleOutputCharacter`(뷰포트), 변경 시 타임스탬프 갱신
  - `idle_for()` = 화면 마지막 변경 이후 경과(소유 러너의 `pty.last_output_ts` 대체)
  - `isalive()` = `OpenProcess`+`GetExitCodeProcess`; attach 시 `SetConsoleCtrlHandler(None,True)`로
    대상 콘솔의 Ctrl 이벤트에 안 죽음
- **`AttachRunner`** (`external/attach_runner.py`) — bypass 구동, **완료는 화면 기반**:
  턴 종료 = **working→idle 엣지**(`is_working`를 본 뒤 더는 working 아님 + `looks_idle` + SETTLE(1.2s)
  지속). 시작 확인/Enter 재전송/stall(abort·skip·pause+takeover)/질문 가드 포함.
  (owned 러너처럼 결정론적 Stop 훅은 못 쓰지만 — 외부 세션엔 런치 시 `--settings` 주입 불가 — 화면
  기반으로 충분히 동작. 옵션으로 유저 설정 `~/.claude/settings.json`에 Stop 훅을 사전 등록하면 신호도 획득 가능.)

### 사용법
```
# 이미 실행 중인 세션에 붙기 (자기 세션/조상/비-claude PID는 거부)
python -m external.attach_runner --pid <PID> --prompts prompts.md

# 테스트/데모: throwaway 세션을 직접 띄워 붙기 (검증 후 --kill로 정리)
python -m external.attach_runner --launch conhost --kill
python -m external.attach_runner --launch wt --prompts prompts.md
```
- `--pid`: 대상 세션 PID. 안전검사(자기/조상/비-claude 거부) 통과 시 attach.
- `--launch conhost|wt`: `external.target`이 new-pid-diff로 안전하게 throwaway 런치+attach.
- `--kill`: 끝에 대상 종료(기본은 **detach만**, 세션 유지 — 우리 소유가 아니므로). 로그: `runtime/attach-run.log`.
- `--on-stall abort|skip|pause`(기본 abort).

### 실측 (E2E)
`--launch conhost`/`--launch wt` 양쪽에서 프롬프트 제출 → 실행 → **화면 기반 완료 감지(`status=done`)** →
정리까지 통과. 안전 가드도 **자기 세션 PID(ancestor)**·비-claude·미존재 PID를 정확히 거부.

- **주의점**: ① 입력 클리어는 backspace 반복(esc 아님, 실측). ② 멀티라인은 각 `\n`이 Enter로 제출되므로
  아직 단일 라인 전제(bracketed-paste는 미검증). ③ 화면 폭/래핑은 타깃 콘솔 크기에 종속(마커 매칭엔 무해).
  ④ 동시에 사람이 그 세션을 타이핑하면 입력이 섞일 수 있음(단일-드라이버 가정).

## 9. 한계 / 남은 검증

- Ctrl+C, bracketed-paste(멀티라인)는 외부 모드에서 아직 미검증.
- WT에서 화면이 스크롤백을 넘어가는 경우 뷰포트만 읽힘(마커 감지엔 문제 없음).
- 사람과 자동 드라이버가 같은 세션을 동시에 조작하면 경합. 실제 통합 시 "인계/양보" 규약 필요.

## 10. 실세션 검증 (2026-08-08, 2.1.224) — 승인·질문 응답

§9의 "plan 승인 메뉴 자동 선택 미검증"이 해소됐다. 남의 세션(VS Code 터미널에서 사람이 띄운
장시간 세션)에 attach해 **일회성으로** 실행한 결과다. **기능으로 넣지는 않았다** — 아래는 다시
같은 일을 할 때 필요한 사실만 남긴 기록이다.

| 항목 | 결과 |
|---|---|
| plan 승인 메뉴에 **Enter 1회**로 옵션 1 선택 | ✅ `User approved Claude's plan` → bypass 복귀 → 실행까지 확인 |
| AskUserQuestion 메뉴를 **ESC로 접고 텍스트로 답변** | ✅ 1,092자 단일 라인 주입(60자씩 청크) 후 정상 턴으로 접수 |
| throwaway 세션 리허설(conhost, haiku)로 동일 경로 예행 | ✅ 실세션 투입 전 검증 |

### 반드시 지킬 것

1. **화면이 유일한 채널이다.** attach 모드는 훅을 주입할 수 없고, 트랜스크립트는 대기 중인
   상호작용을 담지 않을 수 있다(findings.md의 해당 절). 그래서 판정은 `screen.classify_dialog`,
   질문 내용은 `screen.parse_question_dialog`로 얻는다. **트랜스크립트만 보고 감지하려다
   질문 메뉴 앞에서 7시간 반을 놓친 것이 이 기록의 계기다.**
2. **identity는 pid + 생성시각으로 핀한다.** `GetProcessTimes`의 creation time을 처음 확인한 값과
   매 폴링마다 대조한다. 화면 마커(cwd·세션 id가 찍힌 경로)는 **스크롤되어 사라지므로** 장시간
   attach의 신원 근거가 못 된다 — 실제로 8시간 뒤 마커가 화면에서 사라져 있었다.
3. **모르는 다이얼로그 대비 "화면 무변화 경보"를 반드시 넣는다.** 우리가 모델링하지 않은 위젯이
   떠도 몇 분 안에 사람이 알아채야 한다. 이게 없어서 7시간 반이 조용히 흘렀다.
4. 승인은 **앵커 아래만 파싱**해서 옵션 1이 `Yes, …`인지 확인하고, 하이라이트가 1번이 아니면
   `↑`로 맞춘 뒤 **재확인하고** Enter. 검증에 실패하면 아무 키도 보내지 않는다.
5. 모델이 만든 메뉴에는 **번호 키를 주입하지 않는다**(ESC + 텍스트). `/model` 피커만 예외인
   이유는 §5·guide 09 §2.1과 동일하다.
6. 멀티라인 답변은 여전히 불가 — `\n`이 Enter로 제출되므로 **단일 라인**으로 만들어 청크 주입한다.
