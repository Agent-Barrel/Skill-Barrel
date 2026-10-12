# 기존 구현과 목표 계약의 차이

기능별 대조의 정본은 [implementation-gap.csv](implementation-gap.csv)다. 기존 61개 기능 관찰을 유지하고 후속 기능 20개를 연결했다. 아래는 재사용 근거와 이식 시 주의점만 소유한다. 현재 목표 동작은 [features.csv](features.csv)와 상세명세를 따른다.

## 관찰 범위와 검증 한계

| 구현 판정 | 의미 |
| --- | --- |
| 존재 | 표에 명시한 범위의 구현이 확인됨. 제품 전체 검수 통과와는 구분한다. |
| 부분 구현 | 필요한 하위 기능이 있으나 통합, 예외 처리 또는 새 검수기준이 빠져 있음. |
| 미구현 | 조사한 실행 경로·모델·UI에 해당 제품 기능이 없음. CLI 자체 능력이나 문서의 계획은 구현으로 세지 않는다. |
| 기획과 불일치 | 유사 기능은 있으나 그대로 사용하면 승인·데이터·변경 정책 등 확정된 기획을 위반함. |

CSV의 `확정 / 초안 / 기술검증필요`는 **기획 결정 상태**다. 위 구현 판정과 별개다. 아래 E 항목은 코드·테스트 근거 묶음이며, 테스트 파일의 존재나 통과가 해당 FEAT 전체를 검증했다는 뜻은 아니다. `FakeAgentRunner`·모의 전송 테스트와 실제 구독·배포 검증도 구분한다.

이전 코드 조사 세션에서 `.venv/bin/python -m pytest tests barrel/tests -m 'not live' -q`를 실행한 결과는 **850 passed, 2 skipped, 9 deselected, 1 warning / 99.90초**였다. 경고는 FastAPI TestClient의 httpx 사용에 관한 폐기 예정 경고다. 라이브 CLI 계정 전환, 실제 추가 과금, Slack, 중앙 서버, 패키징·복구 검증은 이 결과에 포함되지 않는다. 문서 작성 후에는 이 테스트를 재실행하지 않고 문서 무결성을 별도로 확인한다.

이번 통합은 기존 분석 기준 `50da927`와 2026-09-18 후속 문서의 코드 관찰을 정리했다. 현재 HEAD의 전체 코드·실제 공급자/네트워크/배포를 다시 감사하거나 아래 과거 테스트를 재실행한 결과가 아니다. 신규 기능의 판정도 이 기록 범위에서의 차이다. `features.csv`의 명세 상태와 `implementation-gap.csv`의 구현 판정, `verification.csv`의 미실험 상태를 서로 바꾸어 읽지 않는다.

## 재사용 가능한 증거 E-01~E-10

| 근거 | 존재하는 범위와 연결 수준 | 코드·테스트 근거 | 이식 판단 |
| --- | --- | --- | --- |
| E-01 | 공급자 중립 세션 계약과 Claude PTY 제어. 질문·모델·추론 강도·중단·화면·스냅샷 처리. Claude 상위 runner에 연결됨. | [계약](../../step2step/contracts.py), [Claude 세션](../../step2step/claude/session.py), [PTY](../../step2step/terminal/pty_session.py), [세션 테스트](../../tests/test_session.py), [환경 정리 테스트](../../tests/test_env_scrub.py), [로그 회전 테스트](../../tests/test_pty_log_rotation.py) | 계약·상태 판정·재현 로그를 Rust 이식의 기준으로 사용. PTY 화면 해석은 재생 검증 후 채택. 스냅샷으로 새 세션을 만드는 것과 원래 CLI 세션의 네이티브 재개를 구분. |
| E-02 | Codex app-server stdio 제어, 계정 유형·모델 지원 확인, thread 재개. barrel의 실행 runner에는 미연결. | [세션](../../step2step/codex/session.py), [전송](../../step2step/codex/transport.py), [세션 테스트](../../tests/codex/test_session.py), [전송 테스트](../../tests/codex/test_transport.py) | 구조화 프로토콜 기반 드라이버를 우선 이식. 기존 환경변수 정리만으로 프로필 격리·실제 청구 경로까지 보장하지 않음. |
| E-03 | 신규·유지보수 입력, 인터뷰, 분석, 요구·기능 작성, 개발 루프. 실제 진입점은 Fake 또는 Claude runner. | [진입점](../../barrel/__main__.py), [runner](../../barrel/agents/claude_runner.py), [역할 계약](../../barrel/agents/runtime.py), [서비스](../../barrel/core/service.py), [파이프라인 테스트](../../barrel/tests/test_pipeline_fake.py), [runner 테스트](../../barrel/tests/test_claude_runner_unit.py) | 프롬프트·검증 가능한 전이 재사용. 전역 모델·추론 강도, 자동 승인, P0 중심 개발 흐름은 새 정책으로 대체. |
| E-04 | 로컬 저장소·공개 HTTPS URL 입력, 분석·환경 선행 검사, 여러 빌드 체계의 검증 명령 감지. | [분석](../../barrel/core/analyze.py), [환경 검사](../../barrel/core/preflight.py), [검증](../../barrel/core/verify.py), [분석 테스트](../../barrel/tests/test_analyze_fake.py), [clone 테스트](../../barrel/tests/test_clone.py), [환경 테스트](../../barrel/tests/test_preflight.py) | 저장소 입력·환경 관찰 재사용. 적응형 검토 범위 평가와 프로젝트별 실사용 검증 계획은 새로 연결. |
| E-05 | 기존 18열 기능 CSV의 검증·원자적 교체·변경 반영. 요구사항은 Markdown에서 추출. | [스키마](../../barrel/core/spec_csv.py), [저장소](../../barrel/core/features_store.py), [스키마 테스트](../../barrel/tests/test_spec_csv.py), [저장소 테스트](../../barrel/tests/test_features_store.py) | 원자적 쓰기·ID 참조 검증 원리를 재사용. 새 기획 CSV 스키마, 명세 결정 상태와 실행 상태 분리, 불변 승인 버전은 다시 구현. |
| E-06 | 로컬 질문·결정 ledger, 질문 텍스트 해시로 답 재사용, 문서 기반 자동 답변, 첫 답변 우선 처리. | [결정](../../barrel/core/decisions.py), [QA](../../barrel/core/qa.py), [서비스](../../barrel/core/service.py), [질문 흐름 테스트](../../barrel/tests/test_question_flow_fake.py), [결정 테스트](../../barrel/tests/test_decisions.py) | 저장·추적 기반 재사용. 질문 종류·대상 버전·유효 범위를 포함하는 새 계약 필요. 명세 충돌 확인을 자동 답변으로 생략하면 안 됨. |
| E-07 | 별도 UnitLoop의 작업 의존성, JSON 체크포인트, 실패 분류, 단계별 대체, 시간·턴 예산, 일반 알림. 현재 서비스·웹 진입점에서는 호출하지 않음. | [UnitLoop](../../barrel/core/unitloop.py), [실패 분류](../../barrel/core/failures.py), [루프 테스트](../../barrel/tests/test_unitloop.py), [실패 테스트](../../barrel/tests/test_failures.py) | 실행 계약·실패 분류·체크포인트 원리 재사용. 새 영속 스케줄러에 통합. 일반 webhook 알림을 Slack 연동으로, 시간 예산을 금액 예산으로 세지 않음. |
| E-08 | 테스트·빌드·e2e 등 실제 subprocess 실행, 제한 시간·프로세스 정리, 게이트 판정. 서비스 개발 루프에도 실제 검증 호출이 있음. | [검증 실행](../../barrel/core/verify.py), [게이트](../../barrel/core/gates.py), [검증 테스트](../../barrel/tests/test_verify.py), [게이트 테스트](../../barrel/tests/test_gates.py) | 실행·결과 수집 재사용. FEAT별 증거, 설치·배포·실사용 판정 연결 추가. 실패 재현 게이트는 적합한 회귀 수정에 적용하며 모든 작업에 억지로 적용하지 않음. |
| E-09 | 프로젝트·단계·질문·산출물·이벤트의 SQLite 저장과 프로젝트 slug별 잠금. | [모델](../../barrel/core/models.py), [DB](../../barrel/core/db.py), [서비스](../../barrel/core/service.py), [저장 테스트](../../barrel/tests/test_store.py), [서비스 테스트](../../barrel/tests/test_service_fake.py) | 도메인 개념·트랜잭션 의도 재사용. 새 DB 스키마와 마이그레이션, 물리 저장소 식별, 영속 작업·메모리·예산·이벤트 outbox 필요. |
| E-10 | FastAPI 로컬 UI, 프로젝트·산출물·질문·이벤트·세션 화면. 메모리 안의 백그라운드 job·세션 registry. | [웹 앱](../../barrel/web/app.py), [job](../../barrel/web/jobs.py), [registry](../../barrel/agents/registry.py), [웹 테스트](../../barrel/tests/test_web_fake.py), [registry 테스트](../../barrel/tests/test_registry.py) | 화면의 사용자 작업과 API 의미를 참고. HTML·polling 서버 자체는 React 공통 UI와 Rust/중앙 전송 어댑터로 대체. 로컬 서버를 그대로 인터넷에 공개하지 않음. |

## 이식 시 유지하면 안 되는 정책

| 현재 동작 | 새 제품에서 필요한 경계 |
| --- | --- |
| dirty 저장소에서 preflight가 일괄 거절 | D-039/Q-018: 사용자 변경 보존, Git 지식/기존 정책에 맞는 시작 선택. [preflight](../../barrel/core/preflight.py), [테스트](../../barrel/tests/test_analyze_fake.py). |
| `gitops.remove_tree`의 OSError 무시 | D-062/D-063: [gitops](../../barrel/core/gitops.py)의 일부 정리 원리는 참고하되 삭제 실패를 원장에 기록하고 재시도. 사용자 원본은 보호. |
| `autopilot_enabled()` 기본 true, `_autopilot_gates()`에서 요구·기능 자동 승인 | 최신 사용자 결정은 세 단계 명시적 승인이다. 기존 주석에 적힌 과거 사용자 결정으로 새 결정을 덮어쓰지 않는다. |
| `artifact_content()`가 현재 파일을 읽고 `_new_artifact()`가 경로·버전 번호만 저장 | 승인 내용의 불변 snapshot/hash가 필요하다. 편집 후에도 과거 승인 내용을 재현해야 한다. |
| 질문 본문 해시가 같으면 이전 답 재사용, expired 질문도 답을 받을 수 있음 | 질문 종류·프로젝트·요청·대상 버전·조건이 맞는지 확인. 늦은 승인을 새 명세에 자동 적용하지 않는다. |
| 프로젝트 slug별 잠금 | 같은 실제 저장소를 다른 프로젝트로 등록하거나 공통 문서를 참조하면 충돌할 수 있다. 실제 자원·읽기/쓰기 범위를 잠근다. |
| CLI의 폭넓은 실행 권한 | 앱의 위임·의존성 계약을 대신하지 않는다. 경계를 실제로 제한할 수 없는 실행은 보수적으로 직렬화한다. |
| 기능의 `tested` 상태 및 일부 P0 구현 | 승인된 요청의 필수 검수기준·설치·배포·실사용 증거가 모두 유효한지 확인한다. |

## docs/rewrite와 현재 코드의 차이

[rewrite 문서](../rewrite/README.md)는 설계 참고 자료이며 현재 구현 목록이나 최신 제품 결정의 정본이 아니다. 아래 내용은 이번 소스 조사 결과를 우선한다.

| 검토 주제 | 현재 확인과 반영 |
| --- | --- |
| CLI 제어 방식 | 현재 Claude는 PTY, Codex는 app-server stdio다. 목표는 Codex stdio·Claude JSON 우선/PTY 보완(D-056). 기존 PTY 성공이 새 JSON 구독·권한 경로 통과는 아니다. |
| Claude import | 현재 runner는 `step2step.claude`를 사용한다. 이전 import 경로 변경을 아직 필요한 작업으로 반복 등록하지 않는다(E-03). |
| 로그 회전 | PTY의 `_log_write`·`_rotate_locked`와 회전 테스트가 존재한다. 새로 없는 기능처럼 산정하지 않는다(E-01). |
| 검증 스택 | `verify.py`는 Rust·Go·Maven·Node·Python 등을 감지한다. pytest 전용으로 평가하지 않는다(E-04/E-08). |
| 동시 실행·복구 | 여러 프로젝트 레코드와 잠금, 별도 UnitLoop 체크포인트는 있다. 앱 전체의 의존성 스케줄링·복구까지 완료된 것은 아니다(E-07/E-09/E-10). |
| 배포 대상·UI | 사내 소규모, Apple Silicon/macOS 15+ 목표, Rust/Tauri/React 내장·중앙 UI. 최초 DMG·Tauri updater·번들 root helper·실제 EC2 배포. 제품 결제·홍보 사이트는 제외. |
| 메모리·설치 용량 수치 | rewrite의 예상치는 이 저장소의 새 제품 실측값이 아니다. CLI·WebView·브라우저를 포함하는 사용 시나리오로 다시 측정한다. |

후속 정책에 따라 다음도 함께 바꾼다.

- `Project.repo_path` 한 개에 전체 프로젝트를 묶지 않는다. 독립 저장소 집합·공통 문서·저장소별 전달 결과가 필요하다.
- `git add -A`로 사용자 수정까지 자동 커밋하거나 고정 `Barrel/barrel@local` 작성자를 덮어쓰지 않는다. Git 지식/정책·작성자·소유 변경·목표 반영은 [저장소 계약](specs/repositories.md)을 따른다.
- `approve_plan` 호출만으로 계획의 최초 의도 확인을 대체하지 않는다. [작은 작업과 의도 확인](specs/orchestration.md#task-input), 위험도별 별도 리뷰와 기존 실패 판단을 연결한다.
- 단일 URL clone의 성공을 GitHub 로그인·private/SSH 접근·gh 인증·PR/병합·비공개 자동 저장 지원으로 확대하지 않는다. 기존 공개 HTTPS 경로가 GitHub만 허용했다고도 단정하지 않는다.
- 메모리 내 job/세션 registry를 자동 재개 정본으로 사용하지 않는다. [종료·복구·취소·프로젝트 수명](specs/memory-and-lifecycle.md)의 영속 전이가 필요하다.

범용 계약·fixture·실패 분류·원자적 쓰기 원리를 선택해 이식한다. Python 참조는 보존하고 기존 DB 전체 이전을 이번 범위로 추가하지 않는다. 단계와 실제 검증은 [roadmap.md](roadmap.md), [verification.csv](verification.csv)에서 조회한다.
