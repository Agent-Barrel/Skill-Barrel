# 기존 계획에서 옮기기

<a id="original-flow"></a>
## 원래 구상과의 대응

[00-original-flow.md](../../plan/00-original-flow.md)의 항목별 처리다.

| # | 원래 구상 | 전환안 |
| --- | --- | --- |
| 0 | Codex 기본, 어려운 판단은 Fable 조언, 구현은 Opus, 조사는 양사 종합 | 역할별 모델 배정은 에이전트 정의로 유지한다. 조율 세션은 사용자가 연 CLI이고, 다른 공급자는 하위 세션으로 부른다. 기본 CLI는 [OD-2](open-decisions.md#od-2) |
| 1 | CLI 탐색, 계정별 설정 폴더로 구독 최대 활용 | 탐색은 필요 없다(사용자가 이미 CLI 안에 있다). 다른 공급자 CLI가 있는지만 확인하고, 없으면 단일 공급자로 줄여 운영한다. 다계정 순환은 하지 않는다. 참고로 `step2step`은 자식 세션 환경에서 `CLAUDE*` 변수를 지운다. 그래서 `CLAUDE_CONFIG_DIR`로 계정을 나누는 방식은 지금 구조에서 동작하지 않는다 |
| 1-1 | 벤더 메모리와 무관한 공통 기억 | 유지한다. 프로젝트 정본 파일과 `~/.barrel/memory`를 세션 시작 때 주입한다 |
| 2 | 시작: 컨셉 입력 / 유지보수 대상과 내용 입력 | 유지한다. 자동 발동 또는 명시 명령 |
| 3·4 | 요구사항, 기능명세 인터뷰 | 유지한다. 확정 도출(S2)과 정본·승인(S3) |
| 5 | 질문 전 유사 서비스 조사, 맥락·고려사항과 함께 질문 | 유지하고 강화한다. [도출 방법](clarification.md#discovery) 3, [질문 형식](clarification.md#questions) |
| 6 | 구현 준비 진입 | [닫힘 조건](clarification.md#closure)을 충족해야 진입한다 |
| 7·8 | 기술 조사, 스택 확정 | 유지한다. 전체 트랙의 세 번째 묶음, 조사는 새 세션 |
| 9 | 확정 정보로 구현 | 작은 작업과 작업당 새 세션. 실행은 기존 unit loop와 `step2step`이 맡는다 |
| 10 | 필요한 것은 요청하고, Computer Use·Playwright로 직접 설정 | 벤더 도구(브라우저 자동화, computer use)를 쓴다. 외부 작업 위임 범위는 확정 항목으로 기록한다 |
| 11 | Slack 소통 | 자체 중계는 없다. 필요하면 Slack MCP나 Claude in Slack을 쓴다([OD-7](open-decisions.md#od-7)) |
| 12 | 데스크톱 대시보드 | 자체 앱은 없다. 실행 층의 진행 상태(`state.json`·로그)를 조율 세션이 요약해 보여준다. 전용 화면은 [OD-7](open-decisions.md#od-7) |

<a id="features"></a>
## 81개 기능의 처리 (분류안)

[features.csv](../app-plan/features.csv)의 기능을 전환안에서 어떻게 다룰지 나눈 것이다. 분류는 설계 판단이며, 확정되면 features.csv의 상태·상세명세에 반영한다.

| 구분 | 수 | FEAT |
| --- | --- | --- |
| 방법론 → 스킬 | 32 | 002, 003, 004, 008, 010, 021, 022, 023, 026, 030, 031, 032, 036, 047, 048, 049, 050, 057, 062, 063, 064, 065, 066, 067, 070, 072, 073, 074, 075, 076, 077, 078 |
| 결정적 보조 → 훅·실행 층(unit loop 게이트·상태) | 24 | 007, 009, 016, 017, 018, 019, 024, 025, 027, 028, 029, 033, 034, 035, 044, 045, 046, 058, 068, 069, 071, 079, 080, 081 |
| 전환 후 불필요 | 9 | 001, 005, 006, 011, 013, 052, 053, 059, 060 |
| 벤더 기능으로 대체 또는 제외 | 16 | 012, 014, 015, 020, 037, 038, 039, 040, 041, 042, 043, 051, 054, 055, 056, 061 |

- **불필요:** 설치 안내, CLI 탐색·버전 관리, 계정 프로필 분리, 모델 지원 탐지, 중단 원인 분류, 개인 설정 선택 도입, 업데이트, 관리자 helper. 사용자가 이미 공식 CLI 안에서 작업하므로 필요 없어진다.
- **대체·제외:**
  - 계정 대체 경로, 월예산 원장·동시 사용 제어, 다중 프로젝트 스케줄러
  - PC 사용 조정·화면 예약, 절전 설정
  - Slack·중계·원격 콘솔·브라우저 pairing·대시보드, EC2 중앙 배포
  - 필요하면 벤더 기능을 쓰고, 별도 요구가 생기면 다시 결정한다.

<a id="specs"></a>
## 상세명세의 처리

| 명세 | 처리 |
| --- | --- |
| [workflow](../app-plan/specs/workflow.md) | 그대로 쓴다. 스킬 본문의 원천이다 |
| [orchestration](../app-plan/specs/orchestration.md) | 작업 입력·의도 확인·검증·리뷰·기존 실패·실패 대응은 그대로 쓴다. 스케줄러와 상태 전이는 unit loop의 순차 실행과 `state.json`으로 대체한다 |
| [repositories](../app-plan/specs/repositories.md) | 그대로 쓴다. Git 반영은 작업 세션과 조율 세션이 공식 git/gh로 수행한다 |
| [memory-and-lifecycle](../app-plan/specs/memory-and-lifecycle.md) | 기억 종류와 적용 원칙은 쓴다. 체크포인트·재개는 unit loop 방식으로 대체한다. 다시 실행하면 완료된 작업은 건너뛰고, 남은 작업은 새 세션에서 실행한다 |
| [resources](../app-plan/specs/resources.md) | 작업 브랜치·worktree 정리 규칙만 쓴다 |
| [accounts-and-budget](../app-plan/specs/accounts-and-budget.md) | 모델 정책만 쓴다. 계정·예산·위임 원장은 대상이 아니다 |
| [install-and-update](../app-plan/specs/install-and-update.md), [remote-and-slack](../app-plan/specs/remote-and-slack.md) | 대상이 아니다. 플러그인 배포와 벤더 기능으로 대체한다 |
| [data-contracts](../app-plan/specs/data-contracts.md) | 확정 목록·작업 계약·결과 보고·승인 원장 형식으로 새로 정리한다 |

<a id="code"></a>
## 기존 코드

> **2026-10-06 결정:** [OD-3](open-decisions.md#od-3)이 정해졌다. 아래 표의 이전 Python 웹 앱, Rust workspace, React 콘솔, TS relay, `docs/implementation/`은 main에서 지웠고 모두 `archive/tauri-desktop-app` 브랜치에 있다. 아래 문단과 표는 결정 전 기록이다.

삭제하지 않는다. 처리는 [OD-3](open-decisions.md#od-3)에서 정한다. 근거는 [기존 구현](research.md#existing)에 있다.

| 자산 | 전환안에서의 역할 |
| --- | --- |
| `step2step/claude` | **실행 층.** 작업마다 실제 대화형 Claude Code 세션을 새로 띄운다. plan 승인·거절, 질문 메뉴 응답, 모델·effort 지정, 교착·마감 처리를 포함한다 |
| `step2step/codex` | **실행 층.** Codex app-server 세션을 띄운다. 계획 본문을 승인 전에 받을 수 있다. unit loop와 연결하는 작업이 필요하다 |
| `barrel/core/unitloop.py`, `gates.py`, `failures.py`, `preflight.py`, `orchestration/drivers/unit_loop.py` | **실행 층.** 작업 목록을 세션 하나씩에 맡기고 게이트로 판정한다. [보완 목록](plugin-architecture.md#gaps)을 반영한다 |
| 이전 Python 웹 앱 (인터뷰·answerer·`decisions.md` 원장·18열 CSV와 검증) | 확정 도출 스킬의 참고로 쓴다. `spec_csv.py`의 검증 규칙은 재사용 후보다. develop 단계는 P0 기능 전체를 한 세션에서 구현하므로 원칙 3과 맞지 않아 쓰지 않는다 |
| Rust workspace (`crates/`, `apps/desktop`) 약 29만 줄 | 개발 동결. 작업 계약·의도 확인·검증 증거·리뷰, 양사 독립 조사 흐름은 설계 참고로 쓴다 |
| React 콘솔, TypeScript relay (`apps/console`, `apps/relay`) | 개발 동결 |
| `docs/implementation/` | 구현 이력으로 보존 |

<a id="sot-update"></a>
## 정본 반영 순서

방향이 확정되고 [검증](validation.md)을 통과한 뒤에만 한다. 상위 [README](../app-plan/README.md)의 후속 변경 순서를 따른다.

1. [decisions.csv](../app-plan/decisions.csv)에 전환 결정을 추가한다. 원문 출처는 [사용자 원문](README.md#source)이다. 설치형 앱을 전제한 결정(예: D-036의 Rust·Tauri 선택)은 후속 변경 관계로 연결한다.
2. [requirements.csv](../app-plan/requirements.csv)에서 설치형·중계·Slack·EC2 전제 요구를 조정한다(예: REQ-001, REQ-035, REQ-038, REQ-053).
3. [features.csv](../app-plan/features.csv)에 위 분류를 반영한다. 제외·대체 기능은 이유와 함께 표시한다.
4. [model-routing.csv](../app-plan/model-routing.csv)의 역할을 에이전트 정의와 연결한다.
5. 상세명세를 위 표대로 고친다. [architecture.md](../app-plan/architecture.md)는 플러그인 구조로 다시 쓴다.
6. [roadmap.md](../app-plan/roadmap.md)의 M0~M5를 플러그인 단계로 바꾸고, [verification.csv](../app-plan/verification.csv)를 새 검증으로 바꾼다.
7. 이 폴더는 정본에 흡수한 뒤 archive로 옮긴다.
