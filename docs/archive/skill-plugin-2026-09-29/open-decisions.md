# 확정이 필요한 결정

이 전환안이 스스로 따르는 [질문 형식](clarification.md#questions)으로 정리했다. **OD-1~3은 spike 전에 정해야 한다.** OD-4~10은 spike를 추천값으로 진행하고, 결과를 보고 정해도 된다.

| ID | 결정 | 시점 | 추천 |
| --- | --- | --- | --- |
| OD-1 | 작업 세션의 실행 기반 | spike 전 | Python unit loop + `step2step`을 보완해 쓴다. Rust 엔진의 계약·흐름은 참고 |
| OD-2 | 조율 세션의 기본 CLI | spike 전 | spike는 Claude Code 조율로 먼저. 원래 구상(Codex 기본)과 달라지므로 확정 필요 |
| OD-3 | 기존 구현의 처리 | spike 전 | **결정됨(2026-10-06).** [아래](#od-3) 참고 |
| OD-4 | 트랙별 승인 범위 | spike 후 | 트랙 표대로 |
| OD-5 | `roadmap.json`·계약 파일의 Git 포함 | spike 후 | 대상 레포에 두되 커밋은 선택. 실행 상태는 대상 레포 밖 |
| OD-6 | 교차 모델 조사의 범위 | spike 후 | 전체 트랙의 조사와 독립 공백 검토에만 기본 적용 |
| OD-7 | 사용 표면 (비개발자·Slack·대시보드) | spike 후 | spike는 CLI와 데스크톱 Code 탭만 |
| OD-8 | 작업 병렬 실행 | spike 후 | 기본 순차 (unit loop 현재 동작) |
| OD-9 | 막혔을 때 다음 작업을 계속할지 | spike 후 | `on_unit_blocked: halt` |
| OD-10 | 정본 문서 형식 | spike 후 | 요구·기능·결정은 기존 CSV, 나머지는 마크다운과 JSON |

<a id="od-1"></a>
## OD-1 작업 세션의 실행 기반

- **정할 것:** "작업마다 새 코딩 에이전트 세션"을 이 레포의 어느 구현으로 돌릴지. 근거는 [research](research.md#existing)에 있다.
- **왜 지금:** spike에서 보완할 코드와 실측 대상이 이 선택으로 정해진다.
- **선택지:**
  1. **Python unit loop + `step2step`.** 작업마다 실제 대화형 Claude 세션을 `-p` 없이 새로 띄운다. 이 드라이버는 실측됐다.
     - 이미 있는 것: 게이트 계층, 실패 분류, effort·모델 사다리, 중지 파일, 드라이버 커밋.
     - 보완할 것: 계획 캡처와 의도 대조, 질문 시 멈춤, Codex 팩토리, 쓰기 범위 검사([보완 목록](plugin-architecture.md#gaps)).
     - 참고: 9/16에 일반화한 unit loop 엔진 자체는 가짜 세션 테스트만 있다.
  2. **Rust 엔진.** 작업마다 새 프로세스를 띄운다. 흐름 전체가 구현돼 있다.
     - 구현된 흐름: 조사·인터뷰·세 묶음 승인, 작업별 의도 확인 세션, 호스트 검증, 리뷰 세션.
     - 한계: 인증된 실제 CLI로 돈 기록이 없다. Claude는 `--print` stream-json(`-p` 경로)을 쓰고 PTY가 없다. SQLite·Tauri 앱 구조를 전제한다.
  3. **1을 실행 기반으로 쓰고, 2에서 계약·흐름 설계를 가져온다.**
- **추천:** 3. 실측된 세션 드라이버는 1에만 있고, 1은 `-p` 과금 변동 영역도 피한다. 2의 계약 구조(작업 계약·의도 확인·검증 증거·리뷰)는 1을 보완할 때 설계 기준으로 쓴다.

<a id="od-2"></a>
## OD-2 조율 세션의 기본 CLI

- **정할 것:** 확정 도출과 분할을 사용자가 어느 CLI에서 하는 것을 기본으로 할지. 실행 층의 작업 세션 공급자는 작업마다 `provider`로 따로 정한다.
- **왜 지금:** [원래 구상](../../plan/00-original-flow.md) 0은 "Codex 기본"이다. 그런데 두 CLI의 준비 상태가 다르다.
  - Claude Code: 훅 동작이 문서로 확인됐다.
  - Codex: 훅마다 사용자가 한 번 신뢰해야 한다. 환경변수로 세션을 구분하는 방식은 확인하지 않았다.
- **선택지:**
  1. Claude Code 기본
  2. Codex 기본 (원래 구상대로)
  3. 둘 다 동등하게 지원
- **추천:** spike는 Claude Code 조율로 먼저 하고, 같은 과제를 Codex 조율로 반복해 비교한다. 역할별 모델(구현 Opus, 의도 대조 Astra 등)은 어느 쪽을 기본으로 하든 작업 계약의 `provider`·`model`로 유지한다.

<a id="od-3"></a>
## OD-3 기존 구현의 처리

- **결정(2026-10-06):** 사용자가 추천과 다르게 정했다. Rust 엔진, React 콘솔, TS relay, 이전 Python 웹 앱은 `archive/tauri-desktop-app` 브랜치에 보존하고 main에서 지웠다. main에는 `step2step`과 unit loop 실행 층(`barrel/core`의 unitloop, gates, failures, preflight, verify, gitops와 `orchestration/drivers/unit_loop.py`)만 남았다. 재사용 후보로 꼽았던 `spec_csv.py`도 이 브랜치에 있다. 아래 추천과 표는 결정 전 기록이다.
- **추천:** 삭제는 없다.

| 자산 | 처리 |
| --- | --- |
| `step2step` (Claude PTY, Codex app-server) | 실행 층으로 사용 |
| unit loop (`barrel/core/unitloop.py`, `gates.py`, `failures.py`, `preflight.py`, `orchestration/drivers/unit_loop.py`) | 실행 층으로 사용하고 보완 |
| 이전 Python 웹 앱 (인터뷰·answerer·결정 원장·18열 CSV) | 확정 도출 스킬의 참고. CSV 검증(`spec_csv.py`)은 재사용 후보 |
| Rust 엔진·React 콘솔·TS relay | 개발 동결. 계약·흐름 설계는 참고 |

<a id="od-4"></a>
## OD-4 트랙별 승인 범위

- **정할 것:** 국소·확장 트랙에서 세 묶음 승인(D-010)을 줄여도 되는지.
- **선택지:**
  1. [트랙 표](workflow.md#tracks)대로: 국소는 의도 요약만, 확장은 영향 문서만, 전체는 세 묶음
  2. 모든 요청에 세 묶음
- **추천:** 1. 작은 수정에 전체 승인을 요구하면 비용이 커진다([research](research.md#prior-art)). D-010은 전체 트랙에 그대로 적용된다.

<a id="od-5"></a>
## OD-5 `roadmap.json`·계약 파일의 Git 포함

- **추천:** unit loop의 기존 방식대로 대상 레포에 두되, 커밋 여부는 선택으로 한다. 실행 상태는 대상 레포 밖의 결과 디렉터리에 둔다. 이는 [저장소 계약](../app-plan/specs/repositories.md#documents)의 실행 상태 제외 원칙과 같다.

<a id="od-6"></a>
## OD-6 교차 모델 조사의 범위

- **추천:** 두 곳에 기본 적용한다. 전체 트랙의 기술·유사 서비스 조사와 독립 공백 검토다. 두 공급자가 서로의 결과를 보지 않는 병렬 조사는 Rust 엔진의 방식(`research.rs`)을 따른다. 나머지 조사는 선택이다.

<a id="od-7"></a>
## OD-7 사용 표면

- **정할 것:** 원래 구상 11(Slack)·12(대시보드)와 비개발자 지원(REQ-001)을 어느 수준으로 요구할지.
- **선택지:**
  1. 벤더 표면만 쓴다. Claude Desktop Code 탭은 터미널 없이 플러그인을 설치할 수 있다.
  2. 1에 더해 알림용 Slack MCP를 붙인다. unit loop의 `notify` 설정도 이 용도로 쓸 수 있다.
  3. 전용 화면을 따로 만든다.
- **추천:** spike는 1로 한다. 2와 3은 결과를 보고 정한다.

<a id="od-8"></a>
## OD-8 작업 병렬 실행

- **추천:** 기본은 순차 실행이다(unit loop의 현재 동작). 병렬은 쓰기 집합 분리(D-032)와 worktree 격리를 구현하고 검증한 뒤 허용한다.

<a id="od-9"></a>
## OD-9 막혔을 때 다음 작업을 계속할지

- **선택지:** unit loop의 기존 설정 `on_unit_blocked`를 쓴다.
  - `halt`: 멈추고 사람을 기다린다.
  - `skip`: 다음 작업으로 넘어간다.
- **추천:** `halt`. 막힌 작업에 의존하는 작업이 있을 수 있고, 질문을 먼저 해결하는 것이 원칙 1에 맞다.

<a id="od-10"></a>
## OD-10 정본 문서 형식

- **추천:**
  - 요구·기능·결정은 기존 CSV 스키마([README](../app-plan/README.md#csv-schema))를 유지한다.
  - 작업 계약은 unit loop의 `roadmap.json`과 `tasks/*.md`로 둔다.
  - 의도 요약과 확정 목록은 마크다운으로 둔다.
