# 설치·관리자 helper·절전·Tauri 업데이트

근거: D-047/D-051~060/D-064/D-066, Q-007. 기술 조사 RES-023/024와 V-07~09를 함께 적용한다. 아래 버전별 관찰은 **2026-09-18 조사 기록**이며 이 정리 작업에서 재조사·제품 실험을 수행하지 않았다. 도입 시 실제 안정 버전과 호환 core/API를 다시 검증한다.

<a id="helper"></a>
## 관리자 보조 서비스와 절전

일반 UI·Rust core·CLI는 로그인한 일반 사용자 권한으로 실행한다. 화면 조작은 해당 GUI 세션의 사용자 프로세스가 담당한다. root helper는 앱 번들에 포함하고 `SMAppService` LaunchDaemon으로 등록한다. 작은 Objective-C/Swift bridge는 ServiceManagement·XPC·전원/권한 상태 같은 필요한 macOS API에 한정한다.

`PrivilegedOperation`은 operation ID, 요청한 로컬 task/attempt, 대상 사용자·허용 행동·실제 경로/자원, 유효시간, delegation revision, 기대 사전 상태, 결과 receipt·복구 방법을 가진다. helper는 연결자의 코드 서명·지정 requirement/Team ID·audit identity와 요청 범위를 자체 검사한다. 보조 서비스 접근 소켓·XPC를 열어 둔 사실이나 UID만으로 임의 root 실행을 허용하지 않는다. 원격 payload나 AI가 만든 검증되지 않은 shell 문자열을 그대로 root shell에 전달하는 API는 두지 않는다. 필요한 작업 종류는 좁은 operation으로 추가하고 승인된 대상·인자·작업 소유권을 검증한다.

최초 실행은 `/Applications`의 설치 위치·서명·helper 등록 상태를 확인하고 필요한 관리자 승인·System Settings 안내를 제공한다. 권한 거절/철회·로그아웃·helper 프로토콜 불일치 시 관련 작업만 보류한다. helper가 존재해도 SIP/TCC·보안 정책을 우회할 수 없으며 화면 권한·접근성·파일 접근 등의 상태는 각각 확인한다. 권한이 없는 테스트를 통과로 표시하지 않는다.

절전은 `follow_os`, `prevent_idle_sleep_on_ac_while_active`, `prevent_idle_sleep_while_active`의 초기 설정안을 사용한다. Slack/콘솔에서 같은 설정 revision을 변경한다. 필요한 작업이 끝나거나 중단되면 power assertion을 해제하고 crash·배터리/AC 변경·절전/깨우기 이후 상태를 재평가한다. 강제 잠자기를 막는 루프나 잠금 해제 자동화는 만들지 않는다.

<a id="updater"></a>
## Tauri updater와 릴리스

### 배포물과 사용자 동의

최초 설치용은 Developer ID 서명·공증된 DMG다. 자동 업데이트는 **Tauri v2 updater의 `.app.tar.gz` 및 `.app.tar.gz.sig`**를 사용한다. `createUpdaterArtifacts=true`, 고정 public key, HTTPS endpoint를 설정한다. 업데이트 artifact의 서명과 Apple 코드 서명·공증은 별개의 검증이다. 출처: [Tauri updater](https://v2.tauri.app/plugin/updater/), [macOS 서명](https://v2.tauri.app/distribute/sign/macos/).

2026-09-18 당시 조사에서는 공식 최신 안정 `tauri-plugin-updater 2.10.1`을 출발 후보로 확인했다. 제품 dependency를 이미 설치·확정한 뜻은 아니며 M1에서 core/API·OS와 함께 검증 후 lockfile로 고정한다. 현재 스택과의 적합성·구체 소스 제약은 [RES-024](../research.csv)에 기록했다. 효과는 Rust core·React·CDN 흐름의 통합 단순화이며 성능이나 장애 복구가 자동으로 보장된다는 뜻은 아니다.

정적 CDN JSON에는 `version`, `notes`, `pub_date`, `platforms.darwin-aarch64.url`, `platforms.darwin-aarch64.signature`를 둔다. signature는 `.sig`의 **내용**이며 파일 URL이 아니다. 이 JSON은 Tauri가 artifact에 하는 서명 검증과 동일한 ‘서명된 manifest’로 주장하지 않는다. HTTPS·배포 권한·불변 artifact 경로를 통제하고 서명된 번들 안의 앱/helper/DB 호환 정보도 확인한다. 초기 지원 외 플랫폼 항목을 가짜 URL로 채우지 않는다.

자동 확인 후 새 버전과 변경·중단 영향을 표시하고 사용자가 해당 릴리스의 설치에 동의해야 진행한다. 동의는 버전+artifact 식별자에 묶고 다른 배포물로 바뀌면 다시 받는다. 나중에 선택하면 강제 설치하지 않는다. 자동 확인 주기·다운로드 보관 한도는 조정 가능한 설정이며 정책으로 미리 합의된 숫자는 없다.

### 업데이트 상태와 복구

`UpdateState`는 `available → awaiting_consent → downloading → verified → draining → installing → restarting → health_check → completed`와 `deferred/failed/recovery_required`를 저장한다. 다운로드/설치를 분리하고 Rust core의 coordinator가 수행한다. 내장 UI에서 updater의 저수준 설치 API를 직접 호출해 동의·drain을 우회하지 않도록 capability를 좁힌다. 원격 UI는 허용된 제품 명령만 전송하며 네이티브 updater 권한을 받지 않는다.

`download()`의 성공 반환을 확인한 뒤에만 `verified`로 전이한다. v2.10.1의 download 완료 callback/Finished 이벤트는 서명 검증 전에 발생한다. `install(bytes)`는 별도 검증을 하지 않으므로 검증된 동일 bytes만 전달한다. 초기 경로는 같은 실행에서 검증한 bytes를 사용하고, crash·앱 재시작으로 이를 잃으면 다시 다운로드·검증한다. 장기 캐시 재사용을 추가한다면 다시 읽은 최종 bytes의 서명·릴리스 일치를 설치 직전에 검증하는 계약부터 추가한다.

기본 다운로드는 전체 archive를 RAM에 보유한다. updater bytes를 UI로 복사하지 않고 크기·메모리·디스크 여유를 검사한다. 크기 상한 초과·긴 drain 대기·취소에서는 다운로드 future/bytes를 해제하고 대기 상태를 보존한다. 실제 전송량에 따른 취소·timeout·큰 번들 peak RAM을 검증한다. 설치는 blocking 작업에서 실행하되 Tauri main event loop는 관리자 인증을 처리할 수 있게 유지한다. UI/main thread에서 동기 install로 대기하지 않는다.

drain은 새 작업을 받되 실행을 시작하지 않도록 대기시키고 실행 중 작업·CLI·외부 효과·helper 작업을 안전한 체크포인트까지 정리하는 단계다. DB/outbox/예약·자원 참조를 저장하고 기존 실행자가 실제로 멈췄는지 확인한다. 비중단 구간이 끝나지 않거나 외부 결과가 불명확하면 설치를 미루며 임의 timeout으로 강제 종료하지 않는다. 사용자 승인 없이 ‘종료할 때 설치’로 바꾸지 않는다.

번들 교체 전 helper 작업을 drain하고 등록·실행 상태를 기록한다. 새 앱은 app/helper/protocol/schema 호환성을 검사하고 SMAppService 등록·재연결 상태를 확인한 후 스케줄러를 다시 연다. 옛 helper가 새 파일로 자동 교체·재시작됐다고 가정하지 않는다. 구체 unregister/register/재시작 순서는 서명된 최소 앱 왕복 실험에서 확정하고 실패 시 기존 정상 버전으로 실행을 유지하거나 명시적 복구 상태로 남긴다.

**설치 중 오류의 자동 rollback을 플러그인 보장으로 두지 않는다.** v2.10.1에는 기존 번들 이동/제거 후 새 번들 이동이 실패할 수 있는 경계가 있고 완전한 복원 전이가 없다. `installing` 진입 전에 번들 밖의 앱 소유 공간에 재시작 가능한 update journal, 현재/목표 버전·서명/hash·DB 호환 범위, 복구할 수 있는 서명된 배포물과 공간을 확보한다. 플러그인의 내부 임시 backup만을 복구 근거로 삼지 않는다. 이는 이번 업데이트 동안 필요한 제한적 복구 자원이며 사용자 백업 제품 기능이 아니다.

기존 앱이 남아 있는 실패와 번들 경로가 없어지거나 불완전한 실패를 구분한다. 후자의 경우 앱 내부 UI만으로 복구가 가능하다고 하지 않는다. 자동 복구 경로의 실행 주체·고정 대상·서명 검증·권한·DB 호환을 M1에서 검증하고, 불가능한 경우 서명 DMG로 앱 실행 파일을 재설치하는 복구 절차를 준비한다. 이 절차에서 workspace 데이터를 초기화하지 않는다. 정상 업데이트는 동의 기반 자동 설치를 유지한다. 필요한 복구 자원을 확보하지 못한 상태에서는 설치를 시작하지 않는다.

DB migration은 적용 전 무결성·호환 범위를 확인하고 트랜잭션 가능한 단위를 사용한다. 필요한 제한적 migration 복구 파일은 작업 자원이며 건강 확인 후 정리한다. 이는 D-055에서 제외한 사용자 백업/내보내기 기능이 아니다. migration 후 구버전이 읽지 못하는 DB에 실행 파일만 자동 롤백하지 않는다. 자동 복구가 안전하지 않으면 복구 안내·진단 근거를 보존하고 실행을 보류한다.

Tauri macOS updater 소스에는 쓰기 권한이 부족할 때 관리자 권한을 요청하는 경로가 있다. 이것만으로 앱 번들 helper의 등록·승인·재연결이 해결되는 것은 아니다. root helper를 updater를 대신하는 무제한 설치기로 만들지 않고 실제 선택 버전의 권한·실패 경로를 검증한다. [공식 updater 소스](https://github.com/tauri-apps/plugins-workspace/blob/v2/plugins/updater/src/updater.rs).

인터넷 HTTPS 배포에서 `dangerousInsecureTransportProtocol`, `dangerousAcceptInvalidCerts`, `dangerousAcceptInvalidHostnames`는 비활성으로 유지한다. 자동 downgrade를 켜서 복구를 구현하지 않는다. 초기 지원 설치 위치는 `/Applications`의 정상 앱 번들이며 DMG에서 직접 실행·translocation·쓰기 불가·다른 volume/특수문자 경로는 설치 전 진단한다. 표준 위치로 이동/재실행이 필요하면 설명하고 사용자 파일을 임의로 이동하지 않는다.

플러그인이 내부에 만드는 temp 경로는 앱 원장에 저절로 등록되지 않는다. M1에서 선택한 버전의 생성·삭제 경계를 관찰해 앱 소유 update attempt와 연결하고 crash 후 소유권을 확인할 수 있는 정리 어댑터를 마련한다. 별도 설치 호스트가 필요하면 그 자식 시작 때 전용 temp root를 부여하는 안을 검증한다. 멀티스레드 core의 전역 `TMPDIR`를 설치 직전에 바꾸거나 시스템 temp 전체를 이름 prefix로 지우지 않는다. 소유권·오류를 관찰할 수 없는 부분은 upstream 개선 또는 좁은 어댑터 변경 대상으로 명시하고 V-09 통과 전 ‘모든 잔여물 정리’ 완료로 표시하지 않는다.

### CDN 게시와 배포 입력

릴리스는 변경 불가능한 버전 디렉터리에 앱/DMG/updater archive/signature/호환 정보/검증 결과를 모은다. 중첩 helper까지 서명·공증하고 최종 바이트 기준 서명·hash를 확인한다. **artifact 업로드 → CDN 다운로드·무결성 확인 → static JSON 갱신** 순서로 게시한다. 아직 다운로드할 수 없는 버전을 manifest로 먼저 알리지 않는다. 설치 동의 후 내려받는 artifact가 바뀌지 않도록 동일 버전 경로를 덮어쓰지 않는다. updater signing key는 앱·저장소·공개 버킷에 넣지 않는다.

초기부터 서명된 최소 앱 vA/vB로 DMG 설치→최초 권한→helper 허용 작업→Tauri update→새 helper 재연결→작업 재개를 검증한다. 서명 자격·CDN·EC2가 없으면 코드/로컬 실험과 외부 검증 상태를 분리하며 통과를 만들어내지 않는다. 필요한 값은 해당 단계에서 구체 산출물을 준비한 뒤 요청한다. 실제 EC2 배포와 공개 HTTPS/Slack 왕복은 향후 제품 납품 범위다.

업데이트와 절전/깨우기 후 스케줄러 재개는 [Q-007 재개 계약](memory-and-lifecycle.md#recovery)을 적용한다. 복구 가능한 작업은 자동 재개하되 직접 앱 종료의 계속하기 대기, 명시적 일시중지/취소, 기존 승인/예산/외부 결과 대기는 유지한다. 새 버전 건강 확인이 이 사용자 의도를 해제하지 않는다.
