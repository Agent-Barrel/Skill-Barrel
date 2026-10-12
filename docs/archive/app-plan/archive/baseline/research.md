# 기획 리서치와 기술 확인 기록

> 보존 기록: 아래는 통합 전 원문/당시 판단이다. 현재 구현 기준은 [정본 안내](../../README.md)와 decisions.csv의 후속 관계를 따른다.


확인 기준일: RES-001~009는 2026-09-16, 후속 조사는 2026-09-17. 아래는 공식 문서 및 로컬 자료의 요약이다. 조사 사실과 사용자 선택을 구분하며 최신 선택은 D-039~066를 따른다. RES-010~020은 [아키텍처 문서의 조사 표](03-architecture-and-roadmap.md#7-공식-자료-조사와-적용-근거)에 있다. 모델·요금·인증·제품 기능은 도입 시점에 다시 확인한다. 직접 인용 대신 핵심 사실을 요약했다.

`RES-###`는 CSV의 근거 참조다. **확인 사실**, **이 제품에 대한 해석**, **남은 확인**을 구분한다. 경쟁 제품의 소개 문구만으로 구현 품질이나 모든 예외 처리가 검증되었다고 보지 않는다.

## RES-001 — 요구사항에서 구현으로 이어지는 단계

출처: [Kiro Specs](https://kiro.dev/docs/specs/), [Quick Spec](https://kiro.dev/docs/specs/quick-spec/), [Specs best practices](https://kiro.dev/docs/specs/best-practices/).

- 확인 사실: Kiro는 요구사항·설계·작업을 연결하며, 직접 문서 편집과 대화를 통한 수정 후 후속 산출물을 맞추는 흐름을 설명한다. Quick Spec은 초기에 질문을 모으고 중간 관문을 줄이는 별도 방식이다. 버그 수정에서는 현재 동작·기대 동작·유지할 동작을 구분한다.
- 적용 해석: 단계별 문서 연결과 변경 영향 추적을 참고한다. 이 제품은 사용자 결정에 따라 요구사항·기능·스택 승인을 별도로 유지한다. 유지보수 시 유지할 동작도 명시하는 기능은 초안이다.
- 남은 확인: 승인 버전과 변경 후 재승인 범위. Kiro의 파일 구조나 구현 스택을 그대로 채택하지 않는다.

## RES-002 — 비개발자에게 질문하고 작업을 맡기는 방식

출처: [Replit Agent](https://replit.com/products/agent), [Build with Agent](https://docs.replit.com/learn/build-with-agent), [Zapier AI workflow generation](https://help.zapier.com/hc/en-us/articles/15703650952077-Use-the-power-of-AI-to-generate-Zap-workflows).

- 확인 사실: Replit은 자연어로 목표를 설명하고 계획·맥락·실제 앱 확인·체크포인트를 활용하는 흐름을 제시한다. Zapier 문서는 자동 구성과 진행 중 질문 방식을 구분하며, 수행 요약과 펼쳐 보는 설명, 사용자가 연결하거나 직접 처리해야 하는 작업을 안내한다. Zapier 자료 갱신일은 2026-05-29다.
- 적용 해석: 동일 도메인의 개발 에이전트와 다른 도메인의 업무 자동화를 함께 비교했다. 질문에는 결정할 내용·맥락·추천·대안·고려 사항을 먼저 담고 상세 조사 근거는 열람 가능하게 한다. 인증 등 사람에게 필요한 행동은 구체적으로 요청한다.
- 남은 확인: 기본 설명의 분량, 상세 근거 화면, 인터뷰 한 번에 제시할 질문 수는 UI 인터뷰에서 정한다.

## RES-003 — 공통 메모리와 대규모 프로젝트 맥락

출처: [Kiro steering](https://kiro.dev/docs/steering/), [Devin repository indexing](https://docs.devin.ai/onboard-devin/index-repo), [Devin DeepWiki](https://docs.devin.ai/work-with-devin/deepwiki).

- 확인 사실: Kiro는 전역·워크스페이스 지침과 조건별 포함을 설명한다. 사용자 정의 에이전트에는 명시적 포함 설정이 필요할 수 있다. Devin은 선택한 브랜치의 인덱싱과 개발 환경 설정을 구분하고, 구조 설명·소스 링크를 제공한다. 큰 저장소는 일부 영역의 설명이 빠질 수 있어 추가 페이지나 메모가 필요하다.
- 적용 해석: 사용자 공통 선호와 프로젝트 지식을 분리하고 요약을 원본 근거에 연결하는 방향이 적합하다. 인덱스가 있다는 이유만으로 맥락이 완전하다고 판단하지 않는다. 검토 범위에는 최신성과 누락 여부도 반영한다.
- 남은 확인: 저장·검색 기술, 갱신 방식, 충돌 우선순위, 삭제 전파 및 복구. 이 제품의 정본 메모리는 CLI 자체 메모리에 의존하지 않는다.

## RES-004 — 구독 계정과 설정 디렉터리

출처: [Codex authentication](https://learn.chatgpt.com/docs/auth), [Codex advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced), [Claude Code authentication](https://code.claude.com/docs/en/authentication), [Claude Code settings](https://code.claude.com/docs/en/settings).

- 확인 사실: Codex는 `CODEX_HOME`으로 설정·상태 위치를 지정하며 기본값은 `~/.codex`다. 인증 정보는 파일 또는 자격 증명 저장소에 저장될 수 있다. Claude의 설정 디렉터리는 `CLAUDE_CONFIG_DIR`이며 인증 파일과 macOS Keychain 항목도 디렉터리 구분의 영향을 받는다. Claude의 API 키 환경변수는 구독 로그인보다 우선 적용될 수 있다.
- 적용 해석: 사용자가 입력한 계정 별칭에 대응하는 디렉터리를 관리하고 각 실행에 명시적으로 전달한다. 기존 사용자 셸의 전역 설정을 바꾸는 방식은 확정하지 않았다. 원문의 `confdir`은 기술적으로 `CLAUDE_CONFIG_DIR`로 구체화한다.
- 남은 확인: 폴더 분리만으로 모든 인증 저장 방식에서 계정이 격리되는지, 실행 중 실제 계정 확인과 동시 실행이 가능한지 검증해야 한다. API 키가 존재한다는 이유만으로 추가 과금 경로를 선택해서는 안 된다. 계정 별칭을 실제 로그인 검증으로 오인하지 않는다.

## RES-005 — 모델·추론 강도·추가 과금

출처: [Claude model configuration](https://code.claude.com/docs/en/model-config), [Claude costs](https://code.claude.com/docs/en/costs), [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra), [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

- 확인 사실: Claude 문서는 Fable 5.1 사용에 필요한 CLI 버전과 일부 게이트웨이에서의 별칭 차이를 설명한다. 조사 시점의 Fable 5.1 최소 버전은 2.1.257이다. Fable·Opus5·Sonnet5에는 low/medium/high/xhigh/max가 기재되며 Haiku4.5는 같은 추론 강도 지원표에 포함되지 않는다. 기본 fallback chain은 일부 과부하·서버 오류를 다루지만 사용량 소진·인증·과금·전송 오류 전체를 처리하지 않는다. 일부 구독·좌석에서는 Fable이 usage credits를 쓰며 비대화형 실행의 과금 동작도 확인해야 한다. `--model`과 대화 중 `/model`의 설정 지속 범위는 다를 수 있다.
- 확인 사실: CLI가 표시하는 API 환산 비용을 구독의 실제 추가 청구액으로 간주할 수 없다. 사용량 표시도 최신 청구 상태와 시차가 있을 수 있다. OpenAI API 모델 페이지의 지원 강도와 CLI의 계정별 모델 메타데이터는 별도로 확인해야 한다.
- 적용 해석: 품질 프리셋은 사용자 결정 D-022를 따른다. 공급자 전체 사용량 소진에 대한 교차 전환은 앱의 책임이다. 승인된 예산 없이 비대화형 실행의 자동 추가 과금에 진입하지 않도록 설계한다.
- 남은 확인: 계정별 모델 권한·실제 청구 경로·모델 식별자·CLI 버전 호환성과 예산 차단 가능성. Fable의 경고·중단은 사용자가 보고한 경험이며 공식 문서로 빈도를 검증한 결과는 아니다. 허용된 작업만 대체 경로로 이어가고 경고 원인과 미완료 상태를 기록한다.

## RES-006 — Slack 연동과 대화 단위

출처: [Devin Slack integration](https://docs.devin.ai/integrations/slack), [Slack Socket Mode](https://docs.slack.dev/apis/events-api/using-socket-mode/).

- 확인 사실: Devin은 Slack 앱 연결, 사용자 연결, 스레드 내 세션 대화를 설명한다. Slack Socket Mode는 공개 HTTP 수신 서버 없이 WebSocket으로 이벤트를 받지만 앱·토큰 설정이 필요하다. Socket Mode 앱은 공개 Slack Marketplace 등록에 제약이 있다.
- 적용 해석: 사용자 결정에 따라 작업 요청별 스레드와 선택형 Slack 연동을 채택한다. 설치형 일반 사용자 제품을 위해 로그인·중계 서버를 둘 수 있으나 구체적인 전달 방식은 선택하지 않았다.
- 남은 확인: OAuth·권한 범위·연결 해제·중복 이벤트·동시 답변·PC 오프라인 시 처리·중계 데이터 보존. Slack 사용이 모든 상황에서 중계 서버를 반드시 요구한다는 뜻은 아니다.

## RES-007 — 환경 설정과 로컬 실행의 경계

출처: [AWS IAM best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html), [Claude Code Remote Control](https://code.claude.com/docs/en/remote-control).

- 확인 사실: AWS는 임시 자격 증명·역할·최소 권한을 권장한다. 장기 IAM 키 발급이 유일한 연결 방식은 아니다. Claude Remote Control은 로컬 프로세스의 실행을 전제로 하며 원격 UI 연결이 클라우드 실행을 뜻하지 않는다.
- 적용 해석: 원문 AWS 예시는 보존하되 실제 연결은 프로젝트 환경에 적합한 인증 방식을 조사한다. 필요한 로그인·MFA·OS 권한은 사용자에게 요청하고 위임 범위 안의 나머지 설정을 수행한다. 로컬 PC가 멈췄을 때 앱이 이어서 처리할 범위를 별도로 설계한다.
- 남은 확인: 외부 작업 재시도의 중복 방지, 접속 해제와 권한 변경, 절전·종료 후 복구. 실제 계정 연결이나 배포를 수행한 검증은 아직 없다.

## RES-008 — 운영체제와 프로젝트 유형

출처: [Kiro installation](https://kiro.dev/docs/getting-started/installation/), [Replit project editor](https://docs.replit.com/learn/projects-and-artifacts/project-editor).

- 확인 사실: Kiro는 여러 데스크탑 운영체제를 지원하며 Replit은 웹·모바일 등의 프로젝트 작업 흐름을 설명한다.
- 적용 해석: macOS 우선과 일반 소프트웨어 범위는 사용자 결정이다. 타 제품의 지원 목록만으로 이 제품이 동일한 환경을 모두 지원할 수 있다고 판단하지 않는다.
- 남은 확인: 패키징·업데이트·서명·배포 경로와 프로젝트별 빌드·실기기·배포·검증 환경. 특정 데스크탑 프레임워크를 선택하지 않았다. 원문의 PyQt 언급도 라이선스 조사 없이 유료 전용이라고 단정하지 않는다.

## RES-009 — 로컬 코드 및 모델 자료

확인일: 2026-09-16. 아래는 파일을 읽은 관찰이며 제품의 실동작 검증 결과가 아니다.

| 자료 | 확인 내용 | 계획에 미치는 영향 |
| --- | --- | --- |
| [저장소 README](../../../../README.md), `step2step.claude`, `step2step.codex`, `step2step.contracts.SessionControl` | Claude PTY와 Codex app-server 제어 기반 및 공통 세션 계약이 존재한다. | 기존 기반을 검토해 통합할 수 있다. 전체 역할 라우터가 구현되었다는 뜻은 아니다. |
| [barrel 진입점](../../../../barrel/__main__.py), [Claude runner](../../../../barrel/agents/claude_runner.py) | 진입점의 runner 선택은 Fake 또는 Claude이며 Claude runner는 현재 `step2step.claude`를 가져온다. | 오래된 README 설명만으로 import가 깨졌다고 판단하지 않는다. Codex 중심 통합은 후속 코드 작업이다. |
| [설정](../../../../barrel/config.py) | 현재 autopilot 기본 흐름은 요구사항·기능 자동 승인 후 구현으로 이어질 수 있다. | D-010의 세 단계 명시적 승인과 맞추는 후속 변경이 필요하다. 이번에는 변경하지 않는다. |
| [기존 CSV 스키마](../../../../barrel/core/spec_csv.py), [기능 저장소](../../../../barrel/core/features_store.py) | 런타임 명세는 18개 열과 별도 상태 체계를 쓰며 CSV 쓰기 경로와 DB 반영 로직이 존재한다. | 이번 기획 CSV는 별도 스키마다. 현재 런타임에 그대로 넣거나 마이그레이션했다고 간주하지 않는다. |
| [서비스](../../../../barrel/core/service.py) | 프로젝트별 작업 잠금과 여러 프로젝트 레코드를 다루는 코드가 있다. | 과거 문서의 단일 프로젝트 설명으로 현 코드의 범위를 제한하지 않는다. 자원·비용 조정은 별도 설계가 필요하다. |
| [모델 티어·가격 비교 자료](../../../claude-gpt-모델-티어-매핑-가격비교.md) | 2026-09-11 자료는 Fable/Astra, Opus/Sol, Sonnet/Terra, Haiku/Luna 대응과 제한 접근 모델을 설명한다. | 사용자 요청에 따라 대체 후보 선정에 사용한다. 점수·가격을 이번 계획에서 재검증된 수치로 복제하지 않는다. |

로컬 Codex 모델 캐시의 `fetched_at`은 `2026-09-16T13:54:18.443733Z`였다. 필터링하여 모델·지원 강도만 확인했으며 인증 정보는 문서에 포함하지 않았다. Astra·Sol·Terra는 low/medium/high/xhigh/max/ultra, Luna는 low/medium/high/xhigh/max가 기록돼 있었다. 이는 해당 환경의 캐시 관찰이다. 라이브 서버 확인, 모든 구독에 대한 보장, API의 ultra 지원 증거로 사용할 수 없다. Astra의 공식 API 페이지와 로컬 CLI 관찰을 구분해 `ultra`는 실제 CLI 지원 확인 후 선택하도록 한다.

## 리서치 운영 방식

주제마다 결정할 문제, 조사 날짜, 공식 출처, 대안, 장단점, 제약, 적용 범위, 미확인 내용을 보존한다. 같은 주제의 후속 질문에는 유효한 근거를 재사용하며 모델·요금·라이선스·지원 버전처럼 변할 수 있는 조건은 의사결정 시 다시 확인한다. Codex와 Claude가 모두 사용 가능하면 각 조사 결과의 일치·차이·누락을 비교해 종합한다. 한 공급자만 사용한 결과를 양사 교차 확인으로 표시하지 않는다.

이번에는 문서와 소스 읽기를 수행했다. CLI 계정 전환, 추가 과금, Slack 연결, PC 화면 양보, 실제 배포, 장애 복구를 실험하지 않았다. 해당 항목은 기능명세의 `기술검증필요` 및 후속 기술 리서치로 남긴다.

## RES-021 — Claude 구조화 CLI와 구독·권한

확인일: 2026-09-17. 출처: [headless](https://code.claude.com/docs/en/headless), [CLI reference](https://code.claude.com/docs/en/cli-reference), [settings](https://code.claude.com/docs/en/settings), [permissions](https://code.claude.com/docs/en/permissions), [sandboxing](https://code.claude.com/docs/en/sandboxing).

- 확인 사실: `-p`의 JSON/stream-json·명시적 session resume와 구조화 입출력이 제공된다. `--bare`는 OAuth/Keychain 로그인 경로를 읽지 않으므로 구독 인증과 호환되는 격리 기본값이 아니다. `total_cost_usd` 같은 클라이언트 비용 추정은 실제 청구액과 다르다. 설정 source·MCP·권한 옵션의 적용 범위를 구분해야 한다.
- 적용: D-056의 JSON 우선·PTY 보완. 공식 구독 로그인 유지, API로 묵시 전환 금지. 질문/권한 전달을 없애거나 bypass로 처리해 성공으로 표시하지 않는다. 앱이 세션·프로세스 수명을 관리하고 CLI의 background 기능만으로 durable 실행을 구현하지 않는다.
- 남은 확인: 실제 구독·모델·질문·permission·cancel/resume 왕복, 프로젝트/개인 설정 묵시 로딩, 파일/외부 효과 통제. Bash sandbox만으로 모든 도구의 접근을 제한했다고 하지 않는다.

## RES-022 — 공식 CLI 공존과 버전·설정 격리

출처: [Claude setup](https://code.claude.com/docs/en/setup), [Claude 조건](https://code.claude.com/docs/en/legal-and-compliance), [Codex app-server](https://learn.chatgpt.com/docs/app-server), [Codex advanced config](https://learn.chatgpt.com/docs/config-file/config-advanced), [Codex sandbox](https://learn.chatgpt.com/docs/sandboxing).

- 확인 사실: 공식 CLI는 자체 인증·설정·업데이트 수명을 가진다. Codex의 설정 경로 분리와 지원 protocol/schema, Claude의 settings source 및 관리 정책 우선순위를 함께 확인해야 한다. 인증 디렉터리 분리만으로 OS 자격 증명 저장소 격리를 증명하지 못한다.
- 로컬 관찰: 이 인터뷰에서 버전 명령으로 Codex CLI `0.154.0`, Claude Code `2.1.273`을 확인했다. 이는 버전 관찰이며 제품 드라이버 호환·로그인 격리 통과 증거가 아니다. 인증 비밀을 추출하거나 계정 설정을 바꾸지 않았다.
- 적용: D-048/D-049. 호환 기존 바이너리 우선, 필요시 검증된 변경 없는 공식 버전을 별도 관리한다. 사용자별 공식 로그인 유지와 배포 조건 검토가 필요하며 구독 프록시나 토큰 수집을 도입하지 않는다.

## RES-023 — DMG와 SMAppService 관리자 보조 서비스

출처: [Tauri DMG](https://v2.tauri.app/distribute/dmg/), [Tauri macOS 서명](https://v2.tauri.app/distribute/sign/macos/), [Apple SMAppService](https://developer.apple.com/documentation/servicemanagement/smappservice), [helper 전환](https://developer.apple.com/documentation/servicemanagement/updating-helper-executables-from-earlier-versions-of-macos), [Apple SIP](https://support.apple.com/en-us/102149).

- 확인 사실: DMG는 앱 번들 설치를 전달할 수 있다. SMAppService는 앱 번들에 포함된 helper/LaunchDaemon을 등록하며 관리자 승인과 상태 처리가 필요하다. root 권한이 SIP와 사용자별 TCC 권한을 해제하는 것은 아니다.
- 적용: 일반 사용자 core/UI/CLI와 좁은 관리자 operation을 수행하는 helper를 분리한다. caller 서명·audit identity·task 위임·경로/자원을 검증한다. 첫 설치의 권한 준비와 업데이트 후 helper 재연결을 초기부터 검증한다. Objective-C/Swift bridge는 필요한 macOS API에 한정한다.
- 남은 확인: 실제 서명 앱에서 등록·거절·취소·재등록·bundle 교체·옛 프로세스 종료·권한 철회. PKG가 반드시 필요하다거나 항상 관리자 승인을 없앨 수 있다고 단정하지 않는다.

## RES-024 — Tauri updater로 확정한 자동 업데이트

최신 확인일: **2026-09-18**. 출처: [Tauri updater](https://v2.tauri.app/plugin/updater/), [공식 릴리스 목록](https://tauri.app/release/updater/all-versions/), [v2.10.1 릴리스](https://github.com/tauri-apps/plugins-workspace/releases/tag/updater-v2.10.1), [v2.10.1 updater 구현](https://github.com/tauri-apps/plugins-workspace/blob/updater-v2.10.1/plugins/updater/src/updater.rs), [v2.10.1 명령 구현](https://github.com/tauri-apps/plugins-workspace/blob/updater-v2.10.1/plugins/updater/src/commands.rs), [JavaScript API](https://tauri.app/reference/javascript/updater/), [CloudFront 버전 경로](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/UpdatingExistingObjects.html).

- 버전 확인: 공식 릴리스 목록의 최신 안정 updater는 `2.10.1`(2026-04-04)이며 해당 태그의 Cargo manifest·Rust·JS 소스를 대조했다. 이 저장소에는 아직 Tauri/Cargo/npm 제품 manifest나 lockfile이 없으므로 설치 버전이 아니라 **M1 검증 출발 후보**다. 구현 착수 시 최신 안정판·호환 core/API를 다시 확인하고 검증한 조합을 잠근다.
- 판단: **현재 Rust/Tauri/React, 사용자 동의, CDN 버킷이라는 요구에 적합하다.** Rust API에서 확인·다운로드·설치를 나누고 React는 제품 상태를 표시할 수 있다. updater 전용 동적 서버 없이 정적 JSON을 제공할 수 있어 현재 구성의 통합·운영 부담을 줄이는 선택이다. 이는 구조에 근거한 판단이며 성능·설치 성공률 비교 실험 결과가 아니다.

| 확인한 기능·제약 | 소스 근거와 제품 적용 |
| --- | --- |
| macOS 배포 | `.app.tar.gz`와 `.sig`, 정적 JSON의 `darwin-aarch64` URL/서명 내용 사용. 최초 DMG와 구분. Apple 코드 서명·공증과 artifact 서명은 별도이며 JSON 전체가 서명으로 인증되는 것은 아니다. |
| 동의·시점 제어 | `check → download → install` API를 분리할 수 있다. 제품의 버전별 동의·작업 drain·재시작 동작은 core가 연결한다. macOS는 설치 후 새 버전으로 relaunch해야 한다. |
| 검증 완료 시점 | `updater.rs` 649~719행: 완료 callback 뒤 서명 검증, `download()`가 성공해야 검증 완료다. `install(bytes)` 자체는 signature 검증을 다시 호출하지 않는다. 완료 이벤트만 보고 verified로 전이하거나 임의 캐시 bytes를 설치하면 안 된다. |
| RAM·전송량 | 같은 download 구현이 전체 archive를 `Vec<u8>`에 모아 검증한다. 기본 경로에 차등 업데이트·디스크 스트리밍 설치를 가정하지 않는다. peak RAM·전체 다운로드 크기·재시도 비용을 실제 번들로 측정한다. |
| 권한 | 1254~1303행: 이동 실패가 PermissionDenied이면 관리자 인증으로 앱 교체를 시도한다. 제품 root helper가 있다는 사실로 이 인증을 없앨 수 있다고 약속하지 않는다. |
| rollback | 일반 경로는 기존 앱을 임시 위치로 옮긴 뒤 새 앱을 이동하며, 관리자 경로는 기존 경로 제거 후 새 경로 이동이다. 후속 실패에서 이전 앱을 복원하는 완전한 트랜잭션은 해당 함수에 없다. ‘업데이트 실패 시 앱이 항상 원래대로 남는다’고 가정할 수 없다는 소스 기반 판단이다. |
| 임시 파일 | 1223~1230행은 내부 임시 디렉터리를 만들고 일부 삭제 오류를 무시한다. 플러그인 자체가 앱의 ManagedResource 원장·crash 후 정리 결과를 보장하지 않는다. 정리 어댑터의 소유권·실패 관찰이 필요하다. |
| 스레드·경로 | 관리자 인증은 main thread로 dispatch한 결과를 기다린다. Rust의 동기 install을 UI/main thread에서 직접 막아 실행하지 않는다. 설치·temp 위치의 volume 관계, 권한과 특수문자 경로는 실제 검사한다. |
| helper·DB | updater는 번들 교체 도구이며 SMAppService 등록·옛 helper 종료·새 프로토콜·SQLite migration 상태를 처리하지 않는다. [Apple SMAppService](https://developer.apple.com/documentation/servicemanagement/smappservice)의 수명/권한을 별도 관리한다. |

적용 계약은 [04의 7절](04-resolved-details.md#7-tauri-updater릴리스-계약)에 반영했다. 첫 구현부터 안전한 설치 전 복구 자원 확보·진행 중 작업 정리·helper handshake·삭제 실패 추적을 함께 검증한다. 서명·TLS 검사를 완화해서 설치 성공률을 높이는 방법은 쓰지 않는다. `allowDowngrades`는 DB 호환 rollback을 대신하지 않으며 초기 자동 경로에서는 사용하지 않는다.

공식 저장소의 [macOS 압축 해제 오류 보고](https://github.com/tauri-apps/plugins-workspace/issues/2455)와 [외장 volume 오류 보고](https://github.com/tauri-apps/plugins-workspace/issues/1983)는 구버전·특정 조건의 재현 사례로만 사용한다. 이를 모든 현재 설치의 실패나 해결 완료로 일반화하지 않는다. v2.10.1 소스의 경로·권한 동작과 함께 M1/V-07의 재현 입력으로 삼는다.

남은 실험: 서명된 두 앱 릴리스의 정상 설치·관리자 취소·기존 앱 이동 직후 오류/crash·재시작·helper 수명·DB migration·임시 정리 실패. key 회전도 기존 설치가 새 key를 신뢰하는 호환 절차를 검증하며 key 유실을 자동 복구 가능하다고 약속하지 않는다. 이 조사에서는 앱 빌드·설치·업데이트를 실제 실행하지 않았다.

## RES-025 — Slack 원본 변경·첨부

출처: [Events API](https://docs.slack.dev/apis/events-api/), [message_changed](https://docs.slack.dev/reference/events/message/message_changed/), [message_deleted](https://docs.slack.dev/reference/events/message/message_deleted/), [block_actions](https://docs.slack.dev/reference/interaction-payloads/block_actions-payload/), [파일 처리](https://docs.slack.dev/messaging/working-with-files/).

- 확인 사실: 이벤트는 빠른 ACK와 별도 중복·재전송 처리가 필요하다. 편집 이벤트는 원본 message 식별과 편집 metadata를 포함하며 본문 불변 변경도 고려해야 한다. 삭제 행위자가 항상 제공되는 것으로 가정할 수 없다. 비공개 파일 다운로드는 권한이 필요하다. 새 파일 업로드 경로는 외부 업로드 URL 획득/완료 API이며 폐기된 `files.upload`를 새 구현 기준으로 쓰지 않는다.
- 적용: 본인 Slack 계정만 조작, revision 버튼 승인. source revision과 불변 command ID·Mac receipt로 수락 전/후 편집·삭제를 나눈다. 파일 참조만으로 필수 입력 확보를 표시하지 않는다. 최대 7일 중앙 queue 정책과 Slack 자체 원본 보존은 별개다.
- 남은 확인: 실제 scope·DM/채널/thread·actor 부재 삭제·역순/중복·첨부 권한 철회·accept 경합·서버와 Mac crash를 V-05에서 확인한다.

## RES-026 — 작업 수명 기반 정리와 근거 보존

출처: [Nix garbage collection](https://nix.dev/manual/nix/2.35/package-management/garbage-collection), [Bazel sandboxing](https://bazel.build/docs/sandboxing), [Playwright trace](https://playwright.dev/docs/trace-viewer-intro), [SQLite secure_delete](https://www.sqlite.org/pragma.html#pragma_secure_delete).

- 확인 사실: 사용 중인 root/참조를 보호하는 자원 회수와 작업별 입력·출력 공간 분리 원리가 있다. 검증 trace는 필요한 실패·재시도 근거로 제한할 수 있다. SQLite 삭제 옵션 하나로 virtual table shadow·외부 백업까지 완전 삭제를 보장할 수 없다.
- 적용 판단: Nix/Bazel 설치를 선택한 것이 아니다. D-062/D-063을 위해 앱 자원을 생성 시 등록하고 명시한 마지막 소비자 후 정리한다. 결과/필수 근거는 승격하고 사용자 원본은 보호한다. AI cleanup agent의 자유로운 경로 판단보다 deterministic 소유권·lease·참조·삭제 결과 검사를 사용한다.
- 남은 확인: 실제 CLI/빌드/브라우저가 만드는 앱 소유 잔여물, crash orphan, 삭제 경합·실패, 디스크 부족. OS 백업 정책은 D-055이며 forensic secure erase까지 약속하지 않는다.

## RES-027 — 유료 소비와 예산 증거

출처: [Codex pricing](https://learn.chatgpt.com/docs/pricing), [Claude headless](https://code.claude.com/docs/en/headless), [Claude costs](https://code.claude.com/docs/en/costs).

- 확인 사실: 구독 포함 사용, 추가 크레딧, CLI가 표시하는 API 환산/추정 비용과 실제 청구는 구분해야 한다. 두 프로필·타 앱·지연 보고를 포함한 전체 지출 강제 상한을 로컬 표시만으로 보장하지 못한다.
- 적용: D-033/D-050. 구매가 아닌 유료 소비월에 차감하고, 실제 기간을 모르면 미확정 예약을 유지한다. 엄격 모드는 검증된 상한 없는 유료 경로를 비활성화한다. 실제 가격·지원 모델·외부 사용 통제는 V-02에서 확인한다.

## RES-028 — 사내 EC2 실제 배포

출처: [AWS security groups](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html), [CloudFront object updates](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/UpdatingExistingObjects.html), [Fastify WebSocket](https://github.com/fastify/fastify-websocket).

- 적용 판단: D-051~053의 실제 EC2 배포를 위한 기본안은 단일 VM의 정적 UI·Fastify/WebSocket/Bolt·PostgreSQL·HTTPS다. TLS·방화벽·재시작·비밀 관리·큐 본문 보존을 배포 구성으로 명시한다. CDN release bucket과 중앙 요청 relay는 다른 책임이며 제품 회원가입·결제 사이트가 아니다.
- 남은 입력: VM·접속 방법·도메인/TLS·Slack 앱·버킷/CDN·운영비 위임. 사용자가 실제 배포 단계에 제공하므로 현재 문서 작업에서 요청하지 않는다. 서버 규모·운영값은 실측 후 조정하며 실제 배포 완료를 문서만으로 선언하지 않는다.
