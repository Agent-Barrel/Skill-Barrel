# 개요 (Overview)

이 문서는 `step2step.claude`의 동작을 설명합니다. Codex는 별도
`step2step.codex`에서 제어하며, 터미널 입출력은 `step2step.terminal`에 분리되어 있습니다.

## 무엇을 하는가

`prompts.md` 같은 마크다운 파일에 `---`로 구분해 적어둔 프롬프트들을, **새로 띄운 인터랙티브
Claude Code 세션**에 한 개씩 자동으로 입력·실행합니다. 한 프롬프트의 턴이 끝나면(=Claude가
응답을 마치고 다시 입력 대기로 돌아오면) 다음 프롬프트를 보냅니다. 사람이 옆에서 타이핑하는
것과 같은 흐름을 코드로 자동화한 것입니다.

이 아이디어의 출발점: VSCode가 터미널을 열 때 venv 활성화 명령을 stdin으로 흘려보내면, 그
터미널에서 돌던 Claude Code의 입력창에 그 텍스트가 들어가더라 — 즉 **stdin 주입이 먹힌다**는
관찰. 그래서 우리는 러너가 직접 Claude를 가짜 터미널(ConPTY)에 띄워 입출력을 완전히 통제합니다.

## 핵심 특징

- **`-p` 미사용**: 인터랙티브 TUI만 구동(구독으로 동작). `-p`/--print, Agent SDK 모두 안 씀.
- **결정론적 완료 감지**: 문서화된 `Stop` 훅을 그 세션에만 주입해 턴 종료를 신호 파일로 감지.
  (화면 텍스트 추정에 의존하지 않음 — 화면 읽기는 보조/모드 판정용)
- **두 가지 모드**(호출 시 선택):
  - `bypass` — `--dangerously-skip-permissions`로 권한 질문 없이 바로 실행.
  - `plan` — plan 모드로 계획을 세운 뒤 러너가 **자동 승인**(옵션 1 "Yes, and bypass permissions")하여 실행.
    (둘 다 런치 플래그는 `--dangerously-skip-permissions` 하나뿐 — `--permission-mode plan`은 안 씀.)
- **무인 진행**: `--dangerously-skip-permissions`에서는 워크스페이스 트러스트/권한 다이얼로그가
  뜨지 않아 완전 무인 가능.
- **안전장치**: 적응형 스톨 감지(느린 턴은 안 죽임), 멈춤 시 pause/skip/abort 정책, 전체 PTY
  로그 보존.
- **모듈 API**: `from step2step.claude import run_session` — 구조화된 결과(턴별 `response`/`tools`,
  클린 트랜스크립트 경로 포함)를 돌려줘 상위 앱이 후속 동작 결정 가능.
- **모델·effort 제어**: 기동 시 `--model`/`--effort`(권장 — TUI 미개입, 전역 설정 무변경), 또는
  세션 도중 `/model` 피커를 사람처럼 조작(↑↓ 모델, ←→ effort)해 컨텍스트를 유지한 채 전환.
  피커 커밋은 기본이 `s`(세션 한정)라 사용자 전역 기본값을 건드리지 않는다.

## 검증 상태

다음 환경에서 양쪽 모드 모두 엔드투엔드로 실제 구동 확인:

- Windows 11, Python 3.12.3, `pywinpty` 3.0.5, `pyte` 0.8.2
- Claude Code `claude` — **v2.1.195 최초 검증, v2.1.215 재검증(2026-07-20)** (`~/.local/bin/claude.exe`)

| 검증 항목 | 결과 |
|-----------|------|
| bypass 모드 2-프롬프트 순차 실행 | `hello.txt` = `PONG`/`PONG2` 생성, 턴마다 신호 1→2, 깨끗한 종료 |
| plan 모드 2-프롬프트(계획→자동승인→실행) | 각 `approved+signal`, 2/2 완료 |
| 트러스트 다이얼로그 | `--dangerously-skip-permissions`에서 미출현 |
| 종료 | ESC로 후처리 정리 후 Ctrl-C 페어로 클린 종료 |
| 기동 `--model`/`--effort` (v2.1.220) | 트랜스크립트 실측이 요청값과 일치, 전역 설정 무변경 |
| 세션 중 `/model` 피커 전환 (v2.1.220) | 세션 한정(`s`) 커밋 후 다음 턴이 새 모델로 실행, `~/.claude/settings.json` 바이트 동일 |

표의 근거가 된 상세 실측 기록(TUI 마커, Stop 훅 동작, 승인 메뉴, 종료 시퀀스)은
findings 문서에 있다.

## 빠른 시작

```powershell
# 설치
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt   # pywinpty, pyte

# 프롬프트 분리 미리보기 (0 비용, Claude 안 띄움)
.\.venv\Scripts\python -m step2step.claude --list --prompts prompts.md

# 실행 (bypass / plan)
.\.venv\Scripts\python -m step2step.claude --workdir test-folder --prompts prompts.md
.\.venv\Scripts\python -m step2step.claude --mode plan --workdir test-folder --prompts prompts.md

# 모델·effort 지정 (작업 난이도별로 세션을 나눠 띄울 때)
.\.venv\Scripts\python -m step2step.claude --workdir test-folder --prompts prompts.md --model haiku --effort low
```

모듈로 호출:

```python
from step2step.claude import run_session, load_prompts
result = run_session(load_prompts("prompts.md"), "test-folder", mode="plan")  # 또는 "bypass"
print(result["completed"], "/", result["total"])
```

## 폴더 · 모듈 지도

```
(레포 루트)
  step2step/          파이썬 패키지 — 제품을 명시적으로 선택
    __init__.py       공통 계약 타입과 프롬프트 유틸리티
    contracts.py      SessionControl 및 공통 상태·결과 타입
    prompts.py        공통 프롬프트 파서
    paths.py          REPO_ROOT / RUNTIME_DIR 단일 정의
    claude/           Claude 전용 제어, CLI와 calibration (아래 표)
      attach/         Claude attach 실행 정책과 제품별 실험
    codex/            Codex app-server 제어와 CLI
    terminal/         PTY와 화면 렌더링
      attach/         Win32 콘솔 연결·입력·화면 읽기 및 공통 probe
  test-folder/        구동 대상(예시 작업 폴더)
  runtime/            실행 시 생성물(로그/신호/설정/트랜스크립트 사본) — 구현 아님
  .venv/              의존성(pywinpty, pyte)
  prompts.md          샘플 프롬프트(--- 구분)
  requirements.txt    의존성 목록
  README.md           사용법 요약
  docs/               이 문서들
```

| `claude/` 모듈 | 책임 |
|--------------|------|
| `runner` | **핵심 상태기계** + 모드 분기 + 모듈 진입점 `run_session()` |
| `screen` | Claude TUI 인식 문자열(마커) 및 다이얼로그 파싱 — 버전 바뀌면 여기만 손봄 |
| `hooks` | `Stop` 훅 주입(설정/`signal_hook.py` 생성) + 신호 파일 감시 |
| `transcript` | 클린 JSONL 트랜스크립트 파싱 → 턴별 `{prompt, response, tools}` |
| `session` | `SessionHandle` — 증분 대화, 턴 결과 주도 대기, 모델·effort 제어 |
| `calibrate` | 마커 재튜닝용 캡처 도구 (`python -m step2step.claude.calibrate`) |
| `calibrate_model` | `/model` 피커 전용 캡처 도구 — 실제 턴을 한 번 보낸 뒤 피커를 끝까지 조작 |

공통 `terminal.pty_session`은 전달받은 실행 명령의 PTY 입출력을 처리하고,
`terminal.screen`은 제품의 의미를 해석하지 않고 화면을 렌더링합니다.
`prompts`의 파싱 규칙과 기존 런타임 파일 위치는 유지됩니다.
