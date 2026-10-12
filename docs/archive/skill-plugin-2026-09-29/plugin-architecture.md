# 구성: 플러그인 + 기존 실행 기반

구성은 두 층이다. 새로 만드는 것은 조율 층과 실행 층의 보완뿐이고, 실행 층은 이 레포에 이미 있는 구현을 쓴다. 표에서 `(검증)`으로 표시한 항목은 [spike](validation.md)에서 실제 동작을 확인한다.

| 층 | 무엇 | 어디서 | 구현 상태 |
| --- | --- | --- | --- |
| 조율 층 | 확정 도출·정본·분할·실행 요청·결과 수신 | 사용자가 연 Claude Code / Codex 세션 + 플러그인(스킬·훅) | 새로 만든다 |
| 실행 층 | 작업마다 새 세션 → 계획·의도 대조 → 구현 → 게이트 → 커밋 | unit loop(`barrel/core/unitloop.py`, `orchestration/drivers/unit_loop.py`) + `step2step` | 있음. [보완 필요](#gaps) |

<a id="flow"></a>
## 두 층의 연결

1. 조율 세션의 스킬이 확정·정본·분할을 마친 뒤 두 가지를 쓴다.
   - 대상 레포에 `roadmap.json`(작업 계약 목록)과 `tasks/*.md`(계약 본문)
   - 실행 설정 `run.json`: target_repo, git 정책, north_star, ladder, budget, gates, preflight
2. 스킬이 `unit_loop.py --config run.json --dry-run`을 실행한다. 설정·preflight·프롬프트 미리보기·fail-first 게이트를 세션 없이 확인한다.
3. 통과하면 같은 명령을 `--dry-run` 없이 백그라운드로 실행한다. 작업마다 새 세션이 뜬다.
4. 조율 세션은 결과 디렉터리의 `state.json`과 로그로 진행을 확인한다.
   - 종료 코드: 0 모두 완료 / 2 blocked·halt / 3 설정 실패 / 4 중지 파일
   - 멈춘 작업의 질문은 조율 세션이 사용자에게 가져온다.
5. 멈추려면 중지 파일을 만든다(`results/<name>/<name>.stop` 또는 대상 레포의 `.unit-loop-stop`).

<a id="layout"></a>
## 플러그인 구성 (조율 층)

```text
barrel/                          플러그인
  skills/                        Agent Skills 표준 SKILL.md, 두 CLI 공용
    barrel-start/                요청 분류·사전 평가·트랙
    barrel-clarify/              확정 항목 도출·질문·닫힘 검사
    barrel-spec/                 정본 작성·의도 요약·승인 요청
    barrel-decompose/            작업 분할 → roadmap.json · tasks/*.md · run.json
    barrel-run/                  dry-run → 실행 → 진행·막힘 수신
    barrel-memory/               공통 기억 읽기·쓰기
  hooks/hooks.json
  .claude-plugin/plugin.json
  .codex-plugin/plugin.json      (검증: 한 트리에 두 매니페스트)
```

- 실행 층 코드(`step2step`, `barrel/core`, `orchestration/drivers`)는 지금은 이 레포에 있다. spike에서는 플러그인 설정이 이 레포 경로와 `.venv` Python을 가리킨다. 배포 형태는 검증 뒤에 정한다.
- 최상위 `bin/`에 실행 파일을 두지 않는다. 있으면 Chat·Cowork가 플러그인 설치를 거부한다.

<a id="enforcement"></a>
## 강제 지점

작업 세션은 `step2step`이 별도 프로세스로 띄우는 **최상위 세션**이다. 이 세션도 사용자 범위의 플러그인과 훅을 그대로 불러온다(검증). 그래서 훅은 환경변수 `BARREL_TASK`로 두 세션을 구분한다.

- 실행 층이 작업 세션을 띄울 때 `BARREL_TASK=T-003`을 넘긴다.
- `step2step`은 `CLAUDE*` 변수만 지우므로 이 변수는 그대로 전달된다. 훅 프로세스도 부모 환경을 물려받는다.

| 규칙 | 방법 |
| --- | --- |
| 방법론 발동 | 조율 세션(`BARREL_TASK` 없음)에서는 SessionStart가 방법론 색인과 현재 단계를 주입한다. 작업 세션에서는 해당 계약의 위치만 주입한다 |
| 조율 세션은 제품 코드를 고치지 않는다 | `BARREL_TASK`가 없으면 PreToolUse가 정본·계약 파일 밖의 쓰기를 거부한다 |
| 작업 세션은 쓰기 범위 안에서만 쓴다 | `BARREL_TASK`의 `write_set` 밖 쓰기를 PreToolUse가 거부한다(검증). 드라이버도 커밋 전에 다시 검사한다 |
| 승인 기록 위조 금지 | 사용자 입력 이벤트의 훅이 사용자가 입력한 승인 명령을 보고 직접 기록한다. 모델이 승인 파일을 쓰면 거부한다(검증: 슬래시 명령이 어느 이벤트로 들어오는지) |
| 추측 금지 | 작업 세션의 질문은 실행 층이 받아 `blocked`로 멈춘다([질문](task-sessions.md#questions)) |
| 최종 방어선 | 드라이버의 쓰기 범위 검사·게이트 판정 뒤에만 커밋한다. `--no-verify` 같은 우회는 PreToolUse가 거부한다 |

훅은 흐름을 막는 장치다. 에이전트를 계속 돌리는 장치가 아니다. 작업을 끝까지 몰아붙이는 Stop 훅은 쓰지 않는다.

<a id="gaps"></a>
## 실행 층의 보완 목록

| 필요한 동작 | 지금의 구현 | 보완 |
| --- | --- | --- |
| 작업마다 새 세션 | unit loop가 시도마다 `SessionHandle.start` | 없음 |
| 계획 → 의도 대조 → 승인 | bypass로 시작. 승인 메뉴는 검토 없이 `approve_plan()` | plan 모드로 시작한다. Claude 계획 본문을 확보하도록 훅이 ExitPlanMode 입력을 저장한다. 별도 세션에서 의도를 대조한 뒤 `approve_plan` / `reject_plan` |
| 질문은 추측하지 않고 멈춤 | `menu_default_answer`로 자동 응답 | 질문을 확정 목록에 올리고 `blocked`로 멈춘다 |
| Codex 작업 세션 | `step2step.codex`는 있으나 unit loop와 연결 안 됨 | `provider: codex`용 세션 팩토리 |
| 쓰기 범위 | 없음 | `write_set` 필드, 커밋 전 검사 |
| 결과 보고 | `state.json`, 세션 snapshot, 로그 | 응답·도구·게이트 출력·transcript 경로를 작업별로 정리 |
| 독립 리뷰 | 없음 | 위험 작업은 게이트 뒤 별도 새 세션 |
| 계약 필드 | id·prompt·gates·depends_on·model·effort·references | decisions·write_set·provider 추가 |

<a id="state"></a>
## 상태 파일

| 파일 | 위치 | Git |
| --- | --- | --- |
| 의도 요약, 확정 목록, 요구·기능 CSV, 와이어프레임·API·디자인 | 프로젝트 문서 위치([저장소 계약](../app-plan/specs/repositories.md#documents)) | 포함 |
| `roadmap.json`, `tasks/*.md` | 대상 레포 (unit loop 기존 방식) | [OD-5](open-decisions.md#od-5) |
| 실행 상태, 세션 snapshot, 로그 | 결과 디렉터리 (기본 `orchestration/results/<name>/`, `orchestration/logs/`) | 제외. 대상 레포에 부기 파일을 남기지 않는 기존 방식 |
| 공통 선호·경험 | `~/.barrel/memory/` | 제외. [기억 계약](../app-plan/specs/memory-and-lifecycle.md#memory) |

<a id="vendors"></a>
## CLI별 차이 (조율 층)

| 항목 | Claude Code 2.1.284 | Codex 0.155.1 |
| --- | --- | --- |
| 스킬 경로 | 플러그인 `skills/`, `~/.claude/skills`, `.claude/skills` | 플러그인, `.agents/skills`, `~/.agents/skills` |
| 스킬 목록 예산 | 컨텍스트 1%, 스킬당 설명 1,536자 | 컨텍스트 2%, 설명 1,024자 |
| 훅 | 이벤트 30여 개. 플러그인을 켜면 적용 | 이벤트 12개. 훅마다 사용자가 한 번 신뢰해야 한다(관리형 훅은 자동) |
| 배포 | 마켓플레이스. 데스크톱 Code 탭에서 설치. 조직 관리자가 필수 설치 지정 가능 | `codex plugin marketplace add` |

<a id="budget"></a>
## 컨텍스트 예산

- 스킬 본문은 짧은 절차와 체크리스트로 쓴다. 상세 규칙은 스킬 폴더의 참조 파일로 뺀다. 현재 `docs/plan`(약 55만 byte)을 그대로 넣지 않는다.
- 작업 세션에는 스킬 색인 대신 계약 하나만 준다.
- Claude Code 훅의 주입 문자열은 1만 자로 제한된다.
