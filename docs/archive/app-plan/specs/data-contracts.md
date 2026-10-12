# 공통 데이터 계약과 상태

필드 이름은 구현을 위한 의미 계약이며 직렬화 스키마/버전은 M0에서 고정한다. Rust/TypeScript가 같은 fixture로 호환을 검증한다. 내부 경로·모델 전체를 제품 UI에 노출할 필요는 없다. 개별 정책은 [기능 CSV](../features.csv)와 각 상세 문서가 소유한다.

| 계약 | 필수 정보·불변 조건 |
| --- | --- |
| Project / WorkRequest | `project_id`, 상위 일반 폴더와 repository ID 집합, `request_id`, 신규/유지보수 목적, 유지할 동작, 요청 상태. 같은 프로젝트에 여러 요청이 있어도 기억은 프로젝트에 연결. |
| Assessment | 요청·입력 revision, 실제 모델/강도, 읽은 범위, 부족한 맥락, 국소/확장/전체 검토 이유, 영향 FEAT, 재사용 승인, 의존성·환경 요구, 재평가 조건. |
| SpecRevision / Approval | 문서 종류, 불변 내용 hash·저장 참조, 부모 revision, REQ/FEAT 연결, 승인자/채널/시각, 적용 범위·전제. 승인 번호만 있고 본문이 바뀌는 구조 금지. |
| ResearchTopic | 결정할 문제, 조사 시각, 출처·확인 사실·해석·대안·제약·미확인점, 공급자별 결과, 갱신 조건. 교차 조사하지 않은 결과를 교차 확인으로 표시하지 않음. |
| MemoryItem / ContextBundle | 범위·종류·출처·검증 증거·revision·삭제 표식. 번들은 참조한 정확한 명세·기억·정책 버전, 적용 조건과 누락 범위를 포함. |
| TaskContract | 요청/FEAT/승인 참조, 선행 작업, `read_set`, `write_set`, 외부 효과 범위, 입력 hash, 기억·위임·예산 revision, 검증 계획, 예상 복구 방식, 실행 attempt·lease 세대. |
| AccountProfile / RoleRoute | 공급자·별칭·로컬 설정 위치, 확인된 계정 정체성, CLI 버전, 모델/강도 능력과 관측 시각, 과금 유형·허용 경로. 인증 비밀은 DTO에 포함하지 않음. |
| Delegation / BudgetReservation | 프로젝트·환경·자원·허용 행동·비용·유효 조건, 정책 revision. 예약 통화·기간·상한/추정·정산 상태, 공급자 사용 증거. |
| Question / Command | `command_id`, 장치/프로젝트/요청, 질문 종류와 `question_id`, 대상 revision, 기대 상태 버전, 발신 채널·권한, 생성/만료 시각, payload schema. |
| Receipt / DomainEvent | 명령 ID, `received / accepted / applied / rejected / expired` 및 이유, 로컬 이벤트 순번. 실행 완료는 별도 작업 결과이며 수신 확인과 혼동하지 않음. |
| VerificationEvidence / SideEffect | FEAT·검수기준·입력/산출물 hash·환경·명령·실제 결과·시각·제약. 외부 효과는 의도·idempotency key·외부 receipt·상태 조회·불명확 여부를 보존. |

아래 공통 타입은 각 주제의 상세 계약을 함께 따른다.

| 계약 | 필수 정보·불변 조건 |
| --- | --- |
| DriverCapabilities / SessionEvent | CLI 버전·인증 유형·모델/effort·질문/권한/cancel/resume 능력, session/turn/attempt ID와 정규화 이벤트. 미지원 입력을 조용히 축소하지 않음. |
| ExperimentContract | 승인 전 격리 실험의 목적·성공 조건·입출력/쓰기 범위·예산·권한·정리 조건. 제품 구현 권한과 분리. |
| SourceRevision / Attachment | Slack 원본 식별·편집 세대·불변 command ID, 첨부 출처·hash·확보 상태·consumer·정리 상태. |
| PrivilegedOperation | task/attempt·호출자·위임 revision·허용 대상/행동·유효 조건·idempotency/receipt/복구. root는 명시 범위만 실행. |
| ManagedResource | 앱 소유 root·resource/owner ID·consumer/lease·retain reason·결과 승격·삭제 상태/실패/재시도. 마지막 참조 후 확인된 삭제. |
| UpdateState / Compatibility | 동의한 릴리스 식별, download/verify/drain/install/restart/health 단계, app/helper/protocol/schema 범위. 비호환 DB에 실행 파일만 롤백하지 않음. |

CSV의 **기획 결정 상태**, 실행기의 **작업 상태**, 채널의 **전달 상태**를 분리한다. 아래 **프로젝트 수명**과 **취소 변경 선택**도 독립된 축이다. UI에서 ‘확정’, ‘완료’, ‘전달됨’을 같은 색상·단어로 뭉개지 않는다.

## 후속 결정으로 추가되는 계약

| 계약 | 필수 의미·불변 조건 |
| --- | --- |
| UserGitContext | 사용자 유형, Git 지식과 프로젝트 정책의 각각의 답변/출처/유효성. unknown/missing/정책 없음은 구분. |
| ProjectRepository | project/repository ID, 일반 상위 폴더, 정규화 실제 경로·remote/host/owner/visibility, 역할, 시작 branch/commit, 접근·CI/배포 조건. |
| GitDeliveryPolicy | 저장소별 허용 범위·대상·사용자/자동 기본 출처·revision·간접 배포 위임. 기존 사용자 변경 포함 여부는 별도 근거. |
| GitIdentity | 저장소별 실제 작성자·출처(existing/user/app/GitHub)·연결 계정·적용 시점. 기존 사용자 설정과 앱 임시 명의를 구별. |
| RepositoryChange / DeliveryReceipt | task/attempt별 변경 소유권, 기준/현재 HEAD·diff hash·검수/리뷰, commit/push/PR/실제 merge 결과·불명 상태. 저장소 간 원자성 가정 금지. |
| ProjectDocumentRef | 문서 ID·책임 저장소·path·행/절/REQ/FEAT·revision/commit/hash·workcopy/snapshot 관계·민감정보/게시 범위. |
| DesignArtifact / ApiContract | 관련 기능·화면/흐름·입력 기능/와이어프레임 revision·API 입출력/권한/오류·상세 시안·소비자/제공자·검수. |
| ApprovalBundle | requirements / features+wireframe / stack+design, 구성 문서별 revision/hash·비해당 사유·승인자/채널·기대 상태. 단일 문서 승인으로 새 부속자료 승인 금지. |
| IntentCheck | task·plan hash·최초 의도/승인 참조·입력 문서 revision·검토 역할·결과/근거·영향 변경 시 무효화. 실행 전 유효성 검사. |
| ReviewEvidence | 필요 위험도 근거·구현/리뷰 session ID·대상 코드/명세 hash·실제 테스트·필수 결함/선택 개선·수정/재검토·현재 유효성. |
| BaselineFailureEvidence | 선택 시작점/사용자 변경·전후 환경/명령/출력/원인·변경 영향·입증 수준·분리/확장 질문/답변. 실패 원시 결과 보존. |
| VisualAsset | 디자인 목적·생성 경로/출처·관련 승인·확보 상태·hash·사용 위치·최종/임시 구분·소비자·실제 화면 증거. |
| ResumeIntent | app exit reason·명시적 종료 marker·계속하기 수락, task별 pause/cancel/기존 blocker. 재시작이 사용자 의도를 지우지 않음. |
| CancelledChanges | task/attempt·변경 소유권·기준 revision·diff/필수 근거·pending/keep/discard 선택·중단/정리 결과. |
| ProjectLifecycle | active/archived/deletion_pending/deleted·전이 명령/기대 버전·작업 drain·변경 보존 선택·앱 삭제 범위·외부 보존·실패/재시도. |
| SharedExperienceDerivation | 프로젝트별 출처·고유 정보/일반 노하우·독립 근거·파생 참조·일반화/삭제 결과·원본 증거 삭제와 재현 한계. |

프로젝트 수명 상태와 취소 변경 선택은 CSV의 명세 상태와도 구분한다. 위 영문 enum은 설계 계약이며 사용자에게 내부 명칭을 그대로 선택시키는 요구가 아니다. 작업 상태의 `blocked`와 입력/승인 대기 이유는 구체적으로 표시한다.

전이는 기대 revision/상태를 조건으로 SQLite 트랜잭션과 outbox에 함께 기록한다. 외부 효과·파일 생성/삭제·여러 Git 저장소 commit은 DB와 단일 원자 트랜잭션이 아니므로 의도/receipt·복구 저널·소유권으로 중간 상태를 조정한다. 재시작 후 상태를 확인하지 않고 성공/삭제 완료/무료 정산을 추정하지 않는다.
