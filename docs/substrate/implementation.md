# 구현 세부 (Implementation)

모듈별 책임과 주요 함수, 핵심 로직을 정리합니다. (코드는 `step2step` 패키지 — 아래 H2 절은
별도 표기가 없으면 `claude` 서브패키지의 모듈입니다. `prompts`·`paths`는 패키지 최상위,
PTY와 화면 렌더링은 공통 `terminal` 패키지에 있습니다.)

## prompts (패키지 최상위) — 프롬프트 파서

`prompts.md` → 프롬프트 문자열 리스트.

- `parse_prompts(text)` / `load_prompts(path)`
- 규칙(순서대로):
  1. UTF-8 읽기, BOM 제거.
  2. **선행 YAML 프런트매터 스킵** — 단, 첫 비어있지 않은 줄이 `---`이고 다음 `---`까지가 전부
     `key:` 형태일 때만(그래야 "구분자로 쓴 선행 `---`"을 프런트매터로 오인하지 않음).
  3. **코드펜스 인지 분리** — ```` ``` ````/`~~~` 안의 `---`은 구분자로 보지 않음.
  4. 각 조각 trim, 빈 조각 제거.
- 정규식: 구분자 `^\s*---\s*$`, 펜스 `^\s*(`{3,}|~{3,})`, YAML 키 `^\s*[A-Za-z_][\w-]*\s*:`.

## hooks — 완료 신호(Stop 훅)

- `SIGNAL_HOOK_SOURCE` / `write_signal_hook(path)` — 런타임에 `runtime/signal_hook.py`를 생성.
  이 스크립트는 stdin으로 들어온 훅 JSON을 읽고 신호 파일(argv[1])에
  `"<time>\t<hook_event_name>\t<session_id>\n"` 한 줄을 append.
- `build_settings(python_exe, hook_script, signal_file, form="args")` — `Stop` 훅만 등록하는 설정 dict.
  - `form="args"`(기본): `{"type":"command","command":"<python.exe>","args":[<script>,<sig>]}` — **셸을 안
    거쳐** Windows의 Git-Bash vs PowerShell 모호성·따옴표 문제를 회피.
  - `form="shell"`: 슬래시 경로 단일 커맨드 문자열(폴백).
  - `Stop`만 등록(서브에이전트의 `SubagentStop`은 등록 안 함 → 오신호 방지). `matcher` 없음.
- `write_settings(path, settings)` — `json.dump`로 파일 기록(따옴표/역슬래시 escape 자동).
- `SignalWatcher(path)` — `.reset()`(시작 시 비움), `.count()`(개행으로 끝난 **완결된 줄만** 셈),
  `.lines()`.

## screen — Claude TUI 마커와 파싱

버전에 따라 바뀔 수 있는 문자열을 **여기 한 곳**에 모음(튜닝 포인트).

- 공통 `step2step.terminal.screen.ScreenReader(cols, rows)` — `pyte.Screen`+`Stream`을 래핑. reader 스레드가 `feed(data)`로 먹이고
  (락 보호), 러너 스레드가 `text()`/`rows()`/`tail(n)`로 현재 화면을 읽음.
- 마커(튜닝 대상):
  - `WORKING_MARKERS = ["esc to interrupt", "to interrupt"]` — 작업 중 표시.
  - `TRUST_MARKERS` — 트러스트 다이얼로그(스킵 모드에선 미출현, 안전망).
  - `IDLE_MARKERS = ["shift+tab to cycle", "? for shortcuts", ...]` — 입력창 준비됨(가장 안정적인 건
    `shift+tab to cycle`: idle/working 둘 다, 웰컴 배너가 스크롤돼도 항상 푸터에 있음).
  - 모드 판정: **푸터 줄**(`MODE_LINE_HINT="to cycle"`로 찾음) 안에서 키워드 매칭
    (`MODE_KEYWORDS = plan→"plan", bypass→"bypass", accept-edits→"accept edit", auto→"auto mode"`).
    전체 화면이 아니라 푸터로 한정해 "plan"이라는 단어가 (계획 본문 등) 다른 곳에 있어도 오판하지
    않음. 느슨한 키워드라 `"plan mode on"→"plan mode"` 같은 문구 변경에도 견딤.
  - `PLAN_APPROVAL_MARKERS = ["would you like to proceed","ready to code","yes, and bypass permissions","yes, and use auto mode"]`
    (옵션 1 텍스트는 런치 방식에 따라 bypass/auto로 다름 — 실측 기록은 findings 문서).
- 판정 함수: `is_working`, `is_trust_dialog`, `looks_idle`, `looks_like_question`(번호 선택 메뉴만
  보수적으로 감지), `current_mode`(푸터의 현재 모드), `is_plan_approval`(승인 메뉴 = 승인 마커 +
  번호 메뉴).
- `ScreenReader.row_flags()` — `rows()`와 **인덱스가 맞는** 행별 스타일 `{bold, colored, reverse}`.
  pyte는 bold(SGR 1)·reverse(SGR 7)·fg는 추적하지만 dim(SGR 2)은 안 한다 → 위젯이 포커스 행을
  bold+색으로 그리고 나머지를 dimColor로 그리면, **포인터 문자가 없어도** 하이라이트를 찾을 수 있다.
  이걸 쓰는 파서는 `tail()`이 아니라 **전체 화면 텍스트**를 받아야 인덱스가 맞는다.

### `/model` 피커 파싱

- 키 상수: `CURSOR_UP/DOWN/LEFT/RIGHT`, `ESCAPE`.
- 마커: `MODEL_DIALOG_MARKERS=["select model"]`(짧게 — 폭이 좁으면 본문 문장이 줄바꿈된다),
  `MODEL_NOISE_MARKERS`(본문·`currently using` 등 옵션이 아닌 줄), `MODEL_PERSIST_HINT="set as
  default"`, `MODEL_SESSION_HINT="use this session only"`, `EFFORT_UNSUPPORTED`,
  `SWITCH_CONFIRM_MARKERS`, `SWITCH_ACCEPT_PREFIX="yes, switch to"`, `EFFORT_TOKENS`.
- 타입: `ModelRow{label, name, index, row, highlighted, current}` /
  `ModelDialog{rows, highlighted, highlight_source, effort, effort_is_default, effort_supported,
  hidden_rows, persist_hint, session_only_hint, raw}` /
  `ModelConfirmation{model, scope, effort, trailing, line}`.
- `parse_model_dialog(text, row_flags=None)` — `select model`이 있는 **마지막** 줄을 앵커로 잡고
  그 아래만 본다(작업 푸터의 `thinking with xhigh effort`가 다이얼로그 effort로 새는 것을 막는
  영역 한정 — `is_working`의 푸터 스코핑과 같은 정신). 행은 **번호도 포인터도 optional**로 파싱하고,
  이름/설명은 **공백 2칸 이상**으로 나눈다(`name`이 매칭 대상 — 설명에 다른 모델명이 들어 있다).
  하이라이트는 ① 포인터가 정확히 하나 → ② `row_flags`에서 스타일 행이 정확히 하나 → ③ **둘 다
  아니면 `highlighted=None`**. `None`은 "못 읽었다"는 1급 결과이고 호출자는 반드시 중단한다.
- `find_model_confirmations(text)` / `find_effort_confirmations(text)` — 확정 줄을 **전부, 순서대로**
  반환한다. 확정 줄은 스크롤백에 남는 시스템 메시지라 "존재하는가"가 아니라 **baseline 대비 증가**로
  검증해야 한다(Stop 훅 카운트와 같은 관용구).
- `model_matches(label, target)` / `matching_model_rows(rows, target)` — 표시 라벨("Opus 5")과 별칭
  ("opus")·풀네임("claude-opus-5")을 양방향 prefix로 맞춘다. 느슨한 만큼 여러 행이 걸릴 수 있어
  `matching_model_rows`는 정확 일치를 우선하고, 그래도 여럿이면 호출자가 **모호성으로 실패**시킨다.
- `parse_kept_model/effort`(Esc 취소 줄), `current_effort`(작업 스피너의 effort — `·` 구분자가 있는
  줄에서만 읽는 보수적 판정).

## terminal.pty_session — 공통 PTY 래퍼

- `PtySession(argv, cwd, cols, rows, env, raw_log_path, on_data, max_log_bytes=50MB,
  log_generations=2)`
- `spawn()` — `PtyProcess.spawn(argv, cwd, env, dimensions=(rows, cols))`. (pywinpty 3.0.5는
  `dimensions=(행, 열)` 순서.) 백그라운드 reader 스레드 시작.
- reader 루프 — `read(4096)`(str 반환, EOF 시 `EOFError`). 읽은 데이터를 ① raw 로그 파일에 기록,
  ② `mirror`면 stdout에도 출력(takeover용), ③ `on_data` 콜백(=pyte feed) 호출. `last_output_ts`
  갱신(적응형 스톨용).
- raw 로그 **회전** — 한 세대가 `max_log_bytes`(UTF-8 바이트)를 넘기려는 쓰기 직전에
  `pty-<sid>.log` → `.log.1` → `.log.2`(`log_generations`만큼 보관)로 밀고 새로 연다. 예전에는
  상한에서 기록을 **멈춰** 장시간 세션의 끝부분이 사라졌다(자율 실행 기록 사고 3). 리더 스레드의
  쓰기와 소유 스레드의 `close_log()`는 락으로 직렬화된다. `log_paths()`가 현재+세대 파일 목록.
- `write(s)`, `sendcontrol(ch)`, `isalive()`, `setwinsize`, `terminate()`, `close_log()`.

## runner — 상태기계 (핵심)

### 상수
`COLS,ROWS=200,50`, `TRUST_WAIT=45`, `INIT_IDLE_WAIT=60`, `CONFIRM_WAIT=12`, `STALL_SECONDS=180`,
`SETTLE_QUIET=0.8`, `POLL=0.15`, `SHIFT_TAB="\x1b[Z"`, `MODE_SWITCH_TRIES=10`,
`BRACKET_START/END`, `ENTER="\r"`.

예산·진행(무한 대기 금지): `DEFAULT_TURN_TIMEOUT=7200`(`timeout=None`의 뜻 — 절대 "영원히"가
아니다), `PROGRESS_SECONDS=1800`·`PROGRESS_POLL=30`(출력이 계속 나와도 `progress_sample()`이
평평하면 `noisy_stagnation`), `MIN_FREE_MB=512`(preflight 경고).
다이얼로그 폐루프: `KEY_VERIFY_DELAY=0.35`, `INJECT_VERIFY_TIMEOUT=20`, `PLAN_REJECT_RE`.

모델/effort: `EFFORT_LEVELS=("low","medium","high","xhigh","max")`(=`--effort`가 받는 값),
`EFFORT_LADDER`(+`ultracode` — ←/→ **방향**을 고를 때만 쓰고 진행은 화면으로 확인),
`CHAR_TYPE_DELAY=0.03`, `SLASH_ECHO_WAIT=4`, `DIALOG_WAIT=8`, `DIALOG_SETTLE=0.5`,
`KEY_STEP_DELAY=0.30`, `NAV_STEP_PAD=4`, `CONFIRM_LINE_WAIT=15`, `ABORT_ESC_TRIES=5`.

### 모듈 함수
- `child_env()` — `os.environ` 복사 후 `ANTHROPIC_API_KEY`·`ANTHROPIC_AUTH_TOKEN`(`SCRUB_ENV`)과
  **`CLAUDE`로 시작하는 모든 변수**(CLAUDECODE, CLAUDE_CODE_* 등 — 접두사 스크럽)를 제거하고
  `TERM=xterm-256color`를 설정. `ANTHROPIC_MODEL`은 **의도적으로 통과** — 호출측이 스폰 세션의
  모델을 고를 수 있게. → 깨끗한 최상위 세션 + **API 키 제거로 구독 사용 보장(비용 방지)**.
- `resolve_claude(explicit)` — `shutil.which("claude")` → `~/.local/bin/claude.exe` → 명시 경로.
- `run_session(prompts, workdir, *, mode="bypass", app_dir=None, on_stall="pause",
  claude_exe=None, extra_args=None, send_mode="paste", hook_form="args", logger=None,
  on_turn=None) -> dict` — **앱이 쓰는 진입점**. `app_dir` 기본은 레포 루트(paths 모듈).
  `extra_args`는 `claude`에 그대로 전달(예: `["--model", "haiku"]`); `on_turn`은 턴마다
  `{index, status, signal_lines, response, tools}` dict로 호출되는 콜백(상위 하네스의 즉시 반응용).

### Runner 클래스 라이프사이클
| 메서드 | 역할 |
|--------|------|
| `__init__(... mode="bypass" ...)` | 설정 저장, `mode`는 `bypass`/`plan` 검증, 세션 UUID 생성 |
| `_prepare()` | `signal_hook.py`/신호 파일/설정 파일 생성, 신호 reset |
| `_argv()` | `claude --session-id … --settings … --dangerously-skip-permissions` (양 모드 공통) |
| `_spawn()` | 작업 폴더 mkdir, `ScreenReader`/`PtySession` 생성·spawn |
| `_handle_trust()` | 트러스트 다이얼로그 수락 시도(스킵 모드선 보통 통과) |
| `_wait_initial_idle()` | 입력창 준비 대기 |
| `_ensure_mode(target)` | 푸터가 `target`(예: plan)될 때까지 `shift+tab`(최대 10회), 매번 선체크 |
| `preflight()` | 스폰 전 점검 `{"fatal","warnings"}`: claude 실행파일·runtime 쓰기 가능(치명), 디스크 여유(경고). SessionHandle.start가 치명이면 시작 거부 |
| `progress_sample(probe)` | 진행 표본 `{transcript_bytes, transcript_records, hook_events, stop_count[, probe]}` — 출력량과 분리된 "진짜 진행" 판정용 |
| `_send_prompt(idx,text)` | baseline 기록 → bracketed paste(또는 plain) → Enter |
| `_confirm_working(baseline, baseline_events)` | 턴이 **정말 시작됐는가**: 작업중 표시·신호 증가·이벤트 증가·식별된 다이얼로그 중 하나(spec R3). 없으면 Enter 1회 재전송 — 단 다이얼로그·usage 배너·trust·피커가 떠 있으면 재전송하지 않고 False(`confirm_reason="blocked"`) |
| `_wait_for_signal(baseline, timeout)` | 신호>baseline 대기(적응형 스톨/idle 폴백, **턴 예산 초과도 stall**) → `signal`/`idle-fallback`/`stall`/`eof` |
| `_wait_plan_ready(baseline, timeout)` | 승인 메뉴 대기(plan용, 예산 유한) → `approval`/`signal`/`idle-fallback`/`stall`/`eof` |
| `_wait_turn_event(…, timeout, stall_seconds, progress_seconds, progress_probe)` | SessionHandle의 결과 주도 대기. 마감은 **매 틱** 검사 → `deadline_exceeded`; 진행 표본이 평평하면 `noisy_stagnation`; 침묵은 `stalled` |
| `_process_prompt(idx,text)` | 모드 분기 → `_process_prompt_bypass` / `_process_prompt_plan` |
| `_process_prompt_bypass` | 주입→확인→신호대기→settle→(번호 메뉴면 가드) |
| `_process_prompt_plan` | plan 진입→주입→승인 메뉴 대기→**검증된** 승인(`approve_plan_menu`: 옵션 1이 하이라이트된 "Yes…" 행일 때만 Enter, 메뉴 소멸 확인)→실행 신호 대기 |
| `select_dialog_option(kind, index)` / `approve_plan_menu()` / `reject_plan_menu()` | 다이얼로그 폐루프: 매 키 전 재검증(`_guard_dialog`: 생존·Stop·PostToolUse·working·같은 종류·같은 위젯) → 화살표 1키 → `KEY_VERIFY_DELAY` 후 재독(2회 무이동이면 ESC+`DialogError`) → 커밋 직전 재독 → Enter → `_confirm_dialog_gone`(소멸·PostToolUse·Stop·working 중 하나, `INJECT_VERIFY_TIMEOUT`). 숫자 키·맹목 Enter·두 번째 Enter 없음 |
| `_capture_response(idx)` | 턴 응답 캡처 — 클린 JSONL 트랜스크립트를 파싱해(턴 index 매칭) `response`/`tools` 추출, 없으면 화면 tail 폴백 |
| `_emit_turn(rec)` | `on_turn` 콜백 발화(설정된 경우, try/except 가드 — 콜백 오류가 런을 중단시키지 않음) |
| `_stall(idx)` | 멈춤 처리(pause/skip/abort, 비-TTY면 abort) |
| `_interactive_stall`/`_takeover` | pause 시 대화형 인계(라인 입력 전달, 출력 미러) |
| `_shutdown()` | ESC로 후처리 정리 후 Ctrl-C 페어로 클린 종료(최후 terminate) |
| `_finalize()`/`_copy_transcript()` | 종료, raw 로그 안내, (있으면) 클린 JSONL을 `runtime/transcript-<sid>.jsonl`로 복사 |
| `run() -> dict` | 전체 시퀀스 구동, 구조화 결과 반환 |

### `run()` 반환 구조 (상위 앱이 쓰는 결과)
```python
{
  "mode": "plan"|"bypass",
  "session_id": "<uuid>",
  "workdir": "<abs path>",
  "transcript": "<클린 JSONL 경로>",   # Claude가 안 남겼으면 None
  "total": 2,
  "completed": 2,          # status가 signal/approved/idle 로 시작하는 개수
  "aborted": False,
  "results": [
    {"index": 1, "status": "approved+signal", "signal_lines": 1,
     "response": "…그 턴의 어시스턴트 텍스트…", "tools": ["Write"]},
    {"index": 2, "status": "approved+signal", "signal_lines": 2,
     "response": "…", "tools": []},
  ],
}
```
`status` 값: `signal`, `idle-fallback`, `approved+signal`/`approved+idle-fallback`(plan), `skipped`,
`aborted`, `eof`. `response`는 그 턴의 클린 어시스턴트 텍스트(JSONL 트랜스크립트 우선, 폴백은
화면 tail), `tools`는 그 턴에 쓴 툴 이름 목록(예: `AskUserQuestion`, `ExitPlanMode`).

### 모델·effort 제어 (runner)

`_ensure_mode`의 관용구("횟수를 세지 말고 화면이 목표를 보일 때까지")를 그대로 확장한다.

- `_type_text(text)` — **한 글자씩** 쓴다. 붙여넣기로는 명령 팔레트가 안 열린다(실측).
- `_enter_slash_command(line)` — 타이핑 후 **컴포저 에코를 확인한 뒤에만** Enter. 확인 실패면 ESC.
- `_guard_model_dialog(base)` — **모든 키 입력 직전에** 실행. EOF / Stop 카운트 증가(`stop-raced`) /
  상호작용 이벤트 발생(`interaction-raced`) / `is_working`(`working-raced`) / 다이얼로그 소멸
  (`dialog-vanished`) 중 하나라도 걸리면 즉시 중단하고, **다음 키를 쓰지 않는다.**
- `_select_model_row(target)` — 행 이동. 매 스텝 재독으로 하이라이트 이동을 확인하고, 2회 연속
  무변화면 `nav-ignored`. 목표가 여러 행에 걸리면 `ambiguous-model`, 없으면 `model-not-listed`.
- `_adjust_effort(target, row_name)` — ←/→. 매 스텝마다 effort가 바뀌었는지 **그리고 행이 그대로인지**
  둘 다 확인한다(위젯이 목록 전체에 한 줄이라 행이 밀리면 다른 모델의 effort를 보게 된다).
- **커밋 전 게이트** — 마지막으로 한 번 더 재독해 하이라이트 이름과 effort가 요청과 같은지 확인한다.
  여기서 어긋나면 ESC. **검증에 실패하는 어떤 경로도 커밋 키를 쓰지 않는다**(테스트가 강제).
- 커밋: `persist=False`면 `session_only_hint`를 확인하고 `s`. 힌트가 없으면 **Enter로 폴백하지 않고**
  `no-session-key`로 실패한다. `persist=True`면 Enter.
- `_await_model_confirmation` — baseline 대비 새 확정 줄을 기다리며, 도중에 `Switch model?` 확인창이
  뜨면 `_resolve_switch_confirm`으로 처리한다(하이라이트 라벨이 `yes, switch to`로 시작함을 확인한
  뒤에만 Enter — 2지 선다에 맹목적 Enter를 넣지 않는다).
- 스코프 검증: 확정 줄의 scope가 요청(`session`/`default`)과 다르면 `scope-mismatch`로 **크게 실패**.
  조용히 성공으로 넘기면 조작자의 전역 설정이 움직였는데 아무도 모르게 된다.
- 진입점: `set_model_via_picker`, `set_model_via_command`(`/model <alias>`),
  `set_effort_via_command`(`/effort <level>`). 실패는 모두 `ModelControlError(stage=..., screen_tail=...)`.

## session — SessionHandle (증분 턴 API)

`SessionHandle.start(workdir, role, system_prompt_append, model, effort, extra_args, mode,
app_dir, claude_exe, logger, snapshot_dir, turn_timeout=DEFAULT_TURN_TIMEOUT)`.
`preflight()`가 치명이면 `ControlError`로 시작을 거부한다.

| 메서드 | 역할 |
|--------|------|
| `send_prompt(text) -> PendingTurn` | 전제: 입력창 idle(working·다이얼로그·usage 배너면 `ControlError`). 주입 후 `_confirm_working`으로 **제출 확인**; 결과가 `PendingTurn.submitted/baseline_turns/transcript_seen`에 실린다 |
| `wait_turn(pending, timeout=None, stall_seconds, progress_seconds, progress_probe)` | `timeout=None` = 핸들의 `turn_timeout`(유한). `COMPLETED_IDLE`인데 트랜스크립트가 안 늘었고 제출도 미확인이면 **`SUBMIT_FAILED`**(직전 턴 응답을 재활용하지 않는다). 소비된 턴마다 `snapshot()` 재저장 |
| `answer_menu(i)` / `answer_menu_text(text)` / `answer_questions({q: 답})` | 대기 중인 AskUserQuestion에 화살표+Enter 폐루프로 답한다(단일 질문만; 탭 바 위젯은 `UnsupportedOperation`). 실패는 `DialogError(stage, screen_tail)` |
| `approve_plan() -> bool` / `reject_plan(feedback) -> PendingTurn` | 검증된 승인(False = Enter가 안 먹힘, 재시도 없음) / "Tell Claude what to change" 행 선택 후 피드백을 새 턴으로 |
| `interrupt() -> bool` | ESC로 접기. **False를 버리지 말 것** — 세션이 아직 붙잡혀 있다는 뜻 |
| `health()` | `alive, state, idle_for, mode, write_errors, turn_count, usage_limited, no_progress_for` |
| `snapshot()` / `load_snapshot(path)` / `from_snapshot(snap)` | 세션 정체 영속(턴마다·stop 시 갱신). `from_snapshot`은 같은 기동 사양으로 **새** 세션을 띄운다(`--resume` 미검증) |
| `watch(on_event)` | 읽기 전용 와치독(`watchdog.SessionWatchdog`, `HEALTH_POLL=2s`): `died`/`usage_limited`/`dialog_waiting`/`silent`/`no_progress`/`recovered` |

## transcript — 클린 JSONL 파싱 (응답 캡처)

Claude Code가 `~/.claude/projects/<프로젝트 슬러그>/<세션ID>.jsonl`로 남기는 클린 트랜스크립트를
턴 단위 구조로 파싱한다. 모듈 자체는 읽기 전용 — `runtime/`로의 사본 기록은 runner의
`_copy_transcript`가 한다.

- `find_transcript(session_id)` — 세션 ID로 클린 JSONL 경로 탐색(없으면 `None`).
- `parse_transcript(path)` — 턴 리스트로 파싱(각 턴 `{index, prompt, response, tools}`).
- `turn_asks_question(turn)` — 그 턴이 사용자에게 질문하는 턴인지 판정(`AskUserQuestion`/
  `ExitPlanMode` 툴 감지 포함) — 기획 Q&A 루프의 기반.
- `last_model_effort(path)` — 마지막 assistant 레코드의 `{model, effort, records}`. 모델은
  `message.model`, effort는 **레코드 최상위 `effort`**. "무엇으로 돌았는가"의 최고 권위 소스다 —
  화면은 우리가 **요청한** 것을 보여줄 뿐이고, 설정 오버라이드나 조직 effort 상한이 있으면 둘이
  갈린다. effort를 보고하지 않는 모델은 `None`(직전 값을 물려주지 않는다).
- 세 함수 모두 패키지 공개 API로 재수출: `from step2step.claude import find_transcript,
  parse_transcript, turn_asks_question`.

## claude.__main__ — Claude CLI
플래그: `--workdir`(필수), `--prompts`(필수), `--mode bypass|plan`, `--on-stall pause|skip|abort`,
`--send-mode paste|plain`, `--hook-form args|shell`, `--model`, `--effort`, `--claude`, `--list`,
추가 인자(`extra`).
시작 시 stdout/stderr를 UTF-8로 재설정(박스 문자 출력이 cp949 콘솔에서 깨지지 않게). 끝에
요약과 프롬프트별 status 출력.

## paths (패키지 최상위) — 경로 단일화
`REPO_ROOT`(패키지 폴더의 상위 = 레포 루트)와 `RUNTIME_DIR`(`REPO_ROOT/runtime`)의 단일 정의.
재편 전 파일마다 반복되던 `Path(__file__).parent.parent`류 계산 9곳을 대체 — 경로 정책이 한
모듈에만 있다. (소스 체크아웃 실행 전제: 패키지가 레포 루트 바로 아래에 있을 때 성립.)

## calibrate — 마커 재튜닝 도구
마커에 의존하지 않는 시간 기반 캡처. `python -m step2step.claude.calibrate <임시폴더> [프롬프트] [초]`로
띄워 0.5초마다 화면을 덤프(+ `--debug-file`). Claude 버전이 바뀌어 화면 인식이 깨지면 이 덤프를
보고 screen 모듈의 마커를 갱신.

## calibrate_model — `/model` 피커 재튜닝 도구
`python -m step2step.claude.calibrate_model <임시폴더> [model] [effort]`. calibrate의 형제 모듈이며
(그쪽 CLI는 위치 인자 계약이라 서브커맨드를 넣지 않았다) 결정적으로 다른 점이 하나 있다 —
**먼저 실제 프롬프트를 한 번 보낸다.** 캐시 무효화 확인창은 대화에 메시지가 있어야만 뜨므로,
빈 세션에서 찍은 캡처는 아예 다른 화면을 측정하게 된다.

매 키 전후로 화면 텍스트 + `row_flags()` + 파서 판정 + **`~/.claude/settings.json`의 `model`/
`effortLevel` 실값**을 덤프한다. 피커에서 Enter는 절대 누르지 않고 `s`만 쓰며, 단계 사이에는
`settle_idle()`로 ESC해 다이얼로그를 닫는다(닫지 않으면 다음 단계가 이전 단계가 열어 둔 화면에
타이핑한다 — 실제로 첫 실행에서 그렇게 어긋났다). 종료 시 전역 설정이 바뀌었으면 **원래 내용으로
되돌린다**: 인자형 `/model`·`/effort`의 스코프는 "실제로 써 보게 두는 것" 외에 측정할 방법이 없고,
캘리브레이션 한 번이 조작자의 기본 모델을 바꿔 놓아서는 안 되기 때문이다.

## 산출물 (runtime/)
실행 시 생성: `hooks-settings-<sid>.json`, `signal_hook.py`, `run-<sid>.signal`(턴마다 한 줄),
`pty-<sid>.log`(원본 PTY 기록의 현재 세대; 50MB마다 `.log.1`, `.log.2`로 회전하므로 끝부분은
항상 남는다), `transcript-<sid>.jsonl`(클린 JSONL 사본 — Claude가 남긴 경우), `run.log`(러너
구조화 로그), `session-<sid>.json`(snapshot_dir를 준 경우).

## 튜닝 포인트 요약
- TUI 문자열이 바뀌면 → claude의 screen 모듈 마커들.
- `/model` 피커 렌더링이 바뀌면 → calibrate_model로 다시 재고, screen 모듈의 `MODEL_*` 마커와
  행/effort 정규식을 갱신.
- 타이밍(시작/스톨/확인 대기) → claude의 runner 모듈 상단 상수.
- 훅 호출 방식이 안 먹으면 → `hook_form="shell"` 폴백.
- 종료가 안정적이지 않으면 → `_shutdown`의 ESC/Ctrl-C 타이밍.
