# 구현 계획의 정본

> **보관 문서 (2026-10-06):** 이 폴더는 더 이상 정본이 아니다. 현재 방향은 [docs/plan](../../plan/README.md)에, 보관한 이유는 [docs/archive](../README.md)에 있다.

2026-09-19 통합, 2026-09-23 D-068/D-069 후속 반영. 기존 계획과 `2026-09-18-follow-up`의 Q-001~Q-021, P-001~P-002 및 추가 사용자 요청을 현재 SOT에 반영했다. 이 디렉터리는 제품 구현의 기준이며 실제 구현·실험 완료를 뜻하지 않는다. 과거의 질문·추천·답변은 archive에 보존하며 구현에는 아래 현재 문서만 사용한다.

## 어디서 시작하는가

1. 특정 기능 구현: [features.csv](features.csv)에서 `ID`로 찾고 `요구사항ID`, `처리규칙`, `입력`, `출력`, `예외처리`, `검수기준`을 읽는다.
2. 해당 행의 `상세명세`에서 전이·권한·복구 경계를 확인한다. `라우팅ID`는 역할 설정, `근거ID`는 결정/연구 원문을 연결한다. 문서는 필요한 절과 revision을 함께 전달한다.
3. [implementation-gap.csv](implementation-gap.csv)로 재사용/신규 작업을 확인하고 `구현단계`와 `검증ID`를 따라 [roadmap](roadmap.md) 및 실제 검증 계획을 준비한다.
4. 전체 구조부터 보려면 [architecture.md](architecture.md) → [데이터 계약](specs/data-contracts.md) → 담당 주제의 상세명세 순서로 읽는다. 과거 답변 의도 확인이 필요할 때만 결정의 `원문출처`를 연다.

예: `FEAT-071` → `REQ-062` → `P-001`과 `RTE-013` → `specs/orchestration.md#task-input` → `M3`, `V-12`. 계획 자동 승인과 실제 최초 의도 확인의 차이까지 이 경로에서 확인할 수 있다.

## 문서별 책임

| 정본 | 내용·참조 단위 |
| --- | --- |
| [requirements.csv](requirements.csv) | 70개 요구사항. 무엇을 제공할지와 사용자 관점의 조건. `REQ-001`~`REQ-070`. |
| [features.csv](features.csv) | 81개 기능. 구현 동작·입출력·예외·검수와 상세명세/역할/단계/검증 연결. `FEAT-001`~`FEAT-081`. |
| [model-routing.csv](model-routing.csv) | 역할·티어 대응 17행의 모델/강도·대안·전환·계정/기술 확인·설정 근거. `RTE-001`~`RTE-017`. |
| [decisions.csv](decisions.csv) | 93개 결정/원칙의 현재 의미·적용 경계·후속 관계·원문·관련 행. `D-068`은 최신 모델·명확한 작업의 효율 배정, `D-069`는 유연한 외부 연동을 반영. |
| [research.csv](research.csv) | 기존 조사 `RES-001`~`RES-028` 통합, 후속 조사 묶음 `RES-029`~`RES-034`. 당시 사실/현재 적용/남은 확인을 구분. 이번에 새로 조사·검증한 결과가 아님. |
| [verification.csv](verification.csv) | `V-01`~`V-14`의 시나리오·통과/실패 처리·필요 입력. 현재 모두 미실험이며 실행 시 버전/환경/증거를 연결. |
| [implementation-gap.csv](implementation-gap.csv) | 전 기능 81행의 기존 코드 관찰·필요 작업. 상세 코드 근거 `E-01`~`E-10`과 관찰 한계는 [근거 설명](implementation-gap.md). |
| [architecture.md](architecture.md), [roadmap.md](roadmap.md) | 런타임/정본/권한 경계, `M0`~`M5` 구현 순서와 `O-01`~`O-12`의 실험/입력/전체 revision 승인. |
| [source-map.csv](source-map.csv) | 원래 36개 파일 각각의 보존 위치와 현재 정본 대응. 파일 이동/합침의 누락 추적용이며 정책을 따로 정의하지 않음. |
| [00-original-flow.md](00-original-flow.md) | 최초 구상 원문 그대로. 현재 정책은 이후 결정과 연결해서 읽음. |

## 상세명세의 경계

| 문서 | 소유하는 규칙 |
| --- | --- |
| [workflow](specs/workflow.md) | 사전 평가·조사/인터뷰·세 승인 묶음·와이어프레임/API/UI/이미지·명세 수정·승인 전 실험 |
| [repositories](specs/repositories.md) | Git 지식/정책·도구·연결·작성자·허용 반영·새 비공개 저장·독립 다중 저장소·공통 문서 |
| [orchestration](specs/orchestration.md) | 작은 작업·SOT/역할·의도 확인·의존성/자원 스케줄·실행·별도 리뷰/기존 실패·완료·실패 |
| [accounts-and-budget](specs/accounts-and-budget.md) | 공식 CLI/프로필/설정·모델/전환·유료 소비와 월예산·위임·전경 화면 인계 |
| [memory-and-lifecycle](specs/memory-and-lifecycle.md) | 기억 축적/적용/삭제·장애/명시 종료 재개·취소 보관·프로젝트 보관/삭제·경험 일반화 |
| [remote-and-slack](specs/remote-and-slack.md) | 온라인 콘솔·인증/중앙 보존·7일 큐·수락/편집/삭제 경합·DM/채널 |
| [install-and-update](specs/install-and-update.md) | DMG·제한 root helper·절전·Tauri updater 동의/서명/교체/복구/CDN |
| [resources](specs/resources.md) | 첨부·전 작업 자원의 소유권/소비자/수명·최종 산출물 보호·삭제 결과/실패 |
| [data-contracts](specs/data-contracts.md) | 위 규칙을 연결하는 공통 타입·상태·불변 조건. 각 주제의 정책을 다시 정의하지 않음 |

## 상태와 충돌을 읽는 방법

`requirements/features/model-routing.csv`의 `확정`은 정책이 정해졌다는 뜻이며 코드/호환 검증 완료가 아니다. `초안`은 목표에 필요한 구현 설계, `기술검증필요`는 실제 지원/왕복 확인을 특히 요구한다. 후속 사용자 결정이 확정되어도 상세 구현 행은 초안일 수 있다. 역할의 `설정근거`에서 사용자 선택·허용 수준·설계 기본값을 구분한다.

현재 고품질 대응은 **Astra max ↔ Fable 5.1 max**를 유지한다(D-067). D-068은 가벼운 작업의 Astra medium 고정 우선만 후속 변경하여, **작업 단위가 작고 세부 지시·검수가 명확하면 Sonnet 5 등 효율 모델을 허용**한다. Opus 5.5·Sol 6 등 최신 모델은 프로필별 실제 ID/effort를 확인해 라우팅한다. 후보의 정확한 순서는 사용자 확정이 아닌 [모델 정책](specs/accounts-and-budget.md#model-policy)의 설계 기본값이다. SOT·독립 리뷰의 고품질 역할과 사전 평가·의도 확인의 medium은 유지한다.

Jev는 [선택적 분류 보조](specs/accounts-and-budget.md#routing-classifier)이며 실제 API·비용 원장·품질 검증은 후속 구현이다. D-069의 [MCP·에이전트 위임 외부 연동](specs/accounts-and-budget.md#external-adapters)도 공통 실행 계약과 실환경 검증이 남아 있다. 사용자 추가 원문과 공유 링크는 [후속 요청](specs/accounts-and-budget.md#follow-up-2026-09-23)에 보존한다.

`decisions.csv`의 `후속 반영`은 현재결정/적용범위에 뒤의 답변을 반영한 상태다. `기준선 기록`은 당시 승인만, `참고 종합`은 조사/기존 지시 정리만 뜻한다. P-002나 질문 당시의 추천을 독립 사용자 결정으로 승격하지 않는다. 채택하지 않은 ‘항상 별도 리뷰’, 내부 서브에이전트 제한/전수 감시, 압축 전용 관문/세션 교체, GPT 우선 이미지 생성을 현재 요구로 되살리지 않는다.

D-021은 당시 25개 주제의 요구 기준선 승인이다. 이번 통합 revision 전체·기능+와이어프레임·스택+상세 디자인의 승인을 대신하지 않는다. 이미 합의한 개별 정책은 재질문하지 않으며 실제 착수 범위의 산출물 revision과 기술 검증을 따로 처리한다. 자동 완료는 D-024를 유지한다.

현재 CSV와 상세명세는 함께 일관된 계약이다. 사용자 원문/후속 답변에 반하는 설계안을 우선하지 않는다. 충돌을 발견하면 `후속근거ID`와 원문으로 범위를 확인하고 해당 현재 행/절을 같이 보정한다. ID 숫자만으로 모든 문서에 일괄 우선순위를 매기지 않는다. 과거 archive의 ‘다음 세션 반영’·‘미정’ 문구는 당시 기록이며 현재 미결 목록이 아니다.

<a id="csv-schema"></a>
## CSV 열·참조 계약

UTF-8 BOM, CRLF, 모든 셀 인용, 한 행 한 레코드를 유지한다. 여러 ID/문서 참조는 `;`로 구분한다. 위치는 물리적 행 번호보다 **파일 + ID + 열 이름**으로 인용한다. 빈 참조는 직접 연결이 없다는 뜻이며 미승인/실패/미검증을 빈값으로 대체하지 않는다.

- 기존 공통 7열 `대분류, 중분류, 소분류, 기능명, 주체, 상세설명, 처리규칙`과 기존 11/15/19열 순서를 보존한다. `ID`는 삭제/재번호 없이 유지한다.
- requirements는 기존 11열 뒤 `상세명세`를 더한 12열이다.
- features는 기존 15열 뒤 `상세명세, 라우팅ID, 구현단계, 검증ID`를 더한 19열이다. AI 판단이 없는 제어 기능은 `라우팅ID`가 비어 있을 수 있다. 역할 연결은 해당 AI 판단에만 적용하며 저장·취소·승인 검증 같은 결정적 제어를 매번 모델 호출로 바꾸지 않는다.
- model-routing은 기존 19열 뒤 `설정근거, 기능ID, 상세명세`를 더한 22열이다. 새 역할도 사용자 모델 확정으로 오인하지 않는다.
- `근거ID`는 D/Q/P 결정 또는 RES 조사, `요구사항ID`는 REQ, `라우팅ID`는 RTE, `검증ID`는 V, `구현단계`는 M을 참조한다. `상세명세` 경로는 이 디렉터리 기준이다. 코드 근거 E와 미결 O는 각각 근거 설명/roadmap에서 조회한다.
- 결정·조사·검증·차이·출처 CSV는 각기 다른 원장이다. 기능 CSV의 실행 상태 enum이나 기존 Python 18열 parser에 그대로 넣지 않는다. 제품 schema 이식은 M0에서 별도로 수행한다.

후속 변경은 결정의 현재 의미/관계 → 요구·기능·역할 행 → 담당 상세명세 → 구현 단계/검증 순으로 같이 갱신한다. 새 문서 대신 기존 주제의 절을 먼저 사용하고, 길어지면 책임별로 나눠 `상세명세`를 갱신한다. 원문은 보존하고 답변을 대화에만 쌓아두지 않는다.
