# Q-002. GitHub 연결 시점과 Git 준비

> 보존 기록: 아래는 통합 전 원문/당시 판단이다. 현재 구현 기준은 [정본 안내](../../README.md)와 decisions.csv의 후속 관계를 따른다.


- 질문일·조사일: 2026-09-18
- 상태: **답변 원문 기록 완료 — GitHub 연결 시점 확정, 기술 추천은 별도**
- 선행 답변: [Q-001 사용자 답변 원문](001-git-delivery.md#사용자-답변-원문)
- 질문 대상: GitHub 계정·연결이 없는 비개발자가 신규 프로젝트를 시작하는 경우

## 질문의 배경

Q-001에서 사용자는 비개발자에게 Git 허용 범위를 묻지 않고 에이전트가 작업 단위와 병합까지 관리하도록 확정했다. 또한 Git 관련 설정이 없는 PC의 설치·가입 안내 방안을 조사해 달라고 요청했다.

기존 기획은 Git 실행 파일을 호출하는 방향을 제시하지만, Git이 없는 Mac의 설치 방식, 커밋 작성자 설정, GitHub 연결의 필수 여부는 구체화하지 않았다. `제품 회원가입 없음`(D-035)은 이 제품의 회원가입 정책이며 GitHub 가입 필요 여부의 답변으로 대체할 수 없다.

## 공식 자료로 확인한 사실

아래는 조사 결과다. 이 프로젝트에서 설치·로그인·패키징 실험을 수행한 결과가 아니다.

| 구분 | 확인 내용 | 출처 |
| --- | --- | --- |
| Git과 gh의 역할 | Git은 로컬 파일 변경과 이력을 관리한다. gh는 GitHub 인증·저장소·PR 등 GitHub 기능을 제공한다. gh 설치를 Git 설치의 대체로 취급하면 안 된다. | [GitHub Set up Git](https://docs.github.com/en/get-started/git-basics/set-up-git), [GitHub CLI](https://github.com/cli/cli) |
| 커밋 작성자 | Git의 이름·이메일 설정은 커밋에 기록되는 작성자 정보다. 저장소별 설정이 가능하며 GitHub 로그인과 별개다. | [Git First-Time Git Setup](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup) |
| 로컬과 원격 | 로컬 저장소 생성·커밋과 GitHub로 업로드하는 작업은 구분된다. GitHub Desktop도 로컬 저장소를 만든 뒤 Publish repository로 GitHub에 게시하는 흐름을 제공한다. | [GitHub Desktop 첫 저장소 안내](https://docs.github.com/en/desktop/overview/creating-your-first-repository-using-github-desktop) |
| GitHub 로그인 | gh는 공식 브라우저 인증 흐름을 제공한다. 사용자는 브라우저에서 계정 로그인과 필요한 인증을 수행할 수 있다. | [gh auth login](https://cli.github.com/manual/gh_auth_login) |
| GitHub 계정 생성 | GitHub 계정이 없으면 공식 가입 화면에서 생성·이메일 확인이 필요하다. gh를 설치한 것만으로 계정이 생성되거나 가입 절차가 끝나지 않는다. | [GitHub 계정 생성](https://docs.github.com/en/account-and-profile/how-tos/account-management/creating-an-account-on-github) |
| Git 인증 연결 | gh를 Git credential helper로 사용할 수 있다. 실제 앱 적용 시 사용자 기존 설정과 적용 범위를 구분해야 한다. | [gh auth setup-git](https://cli.github.com/manual/gh_auth_setup-git) |
| macOS의 Git 설치 | 공식 안내는 Homebrew·MacPorts·Apple Command Line Tools 경로를 제시한다. 예전 독립 설치 프로그램은 2021년 이후 갱신이 없어 현재 안내에서 제외했다. | [Git macOS 설치](https://git-scm.com/install/mac) |
| gh 설치 | 공식 macOS 사전 빌드 배포물이 있어 Homebrew를 반드시 설치해야 하는 것은 아니다. 배포물 출처 검증 방법도 제공한다. | [GitHub CLI 설치·배포물 검증](https://github.com/cli/cli#installation) |
| 앱에서 관리하는 Git | GitHub Desktop의 dugite-native는 애플리케이션에서 사용할 이동 가능한 Git을 만드는 도구 체계다. 최종 사용자가 직접 설치하는 제품이 아니며 앱에 Git을 포함하는 방식의 참고 자료다. | [desktop/dugite-native](https://github.com/desktop/dugite-native) |

## 설치·설정 방안에 대한 추천

**후속 결정:** 아래는 질문 당시 추천이다. [Q-008 사용자 답변](008-git-tool-provisioning.md)에서 앱이 Git·gh를 준비하되 전역 설치를 허용하고, 필요한 npm·Homebrew 등도 승인 후 PC에 세팅하도록 정했다. 아래의 앱 전용 경로를 최신 사용자 확정 정책으로 취급하지 않는다.

**Git과 gh를 앱이 준비하고, 사용자는 공식 브라우저에서 GitHub 가입·로그인·인증을 수행하는 방향을 추천한다.** 비개발자에게 도구 선택이나 터미널 명령 작성을 요구하지 않는 것이 목적이다. 아래 내용은 작성자의 기술 추천이며 사용자 확정 사항이 아니다.

1. 기존에 실제 실행 가능한 Git이 있으면 호환성을 확인해 재사용한다. 없으면 앱이 관리하는 Git 패키지를 준비하는 방식을 우선 검토한다. GitHub Desktop의 도구 체계를 참고할 수 있다. 이 방식은 패키징·서명/공증·라이선스 고지와 해당 배포물의 의무·업데이트 책임이 필요하므로 검증 전 도입 완료로 표시하지 않는다. Apple Command Line Tools는 별도 설치를 안내할 수 있는 대안이다.
2. GitHub 연동을 사용할 때 공식 gh 배포물을 앱 전용 경로에서 관리하거나 호환되는 기존 설치를 재사용하는 방식을 추천한다. Git·gh를 준비하기 위해 Homebrew나 GitHub Desktop 앱을 필수로 설치하게 하는 흐름은 우선안으로 추천하지 않는다.
3. GitHub 연결 화면은 필요한 가입·로그인과 연결 상태를 설명한다. 기본 인증 후보는 gh의 브라우저 인증과 HTTPS다. 사용자의 GitHub 비밀번호나 직접 발급한 토큰을 제품 대화창에 입력하는 절차를 기본으로 두지 않는다. 기존 회사 저장소·SSO·SSH 환경을 일괄 변경하는 결정은 아니다.
4. Git 커밋 작성자 설정은 후속 [Q-012](012-git-author-identity.md)에서 앱 자동 설정을 허용했다. 기존 작성자 설정을 재사용하고, 없으면 연결된 GitHub 계정 정보 또는 미연결 시 앱 명의를 사용한다. 앱이 준비하는 설정은 프로젝트 범위이며 과거 기록을 소급 변경하지 않는다. 브라우저·Playwright·Computer Use로 사용자 로그인을 받은 뒤 후속 설정을 자동 처리하는 경로도 허용했다. 기존 코드의 고정 `Barrel / barrel@local` 값을 이 전체 정책의 대체로 이식하지 않는다.
5. 사용자 화면에는 설치·인증 상태와 필요한 다음 행동을 보여주고, 실제 작업 분할·커밋·병합은 Q-001에 따라 에이전트가 관리한다.

위 방향은 Rust 코어에서 Git·gh 프로세스를 호출할 수 있다는 설계 제안이며 Node/Python 배포 런타임이나 GitHub Desktop UI를 추가로 채택한 결정이 아니다.

## 발견한 구현상의 확인 사항

이 항목들은 후속 검증·질문을 위한 기록이며 현재 질문의 답변으로 함께 확정되지 않는다.

- gh 공식 문서는 시스템 자격 증명 저장소 사용 실패 시 평문 파일 저장으로 대체될 수 있다고 설명한다. 제품에서 실제 저장 위치와 실패 처리를 확인해야 한다. 단순 로그인 성공을 Keychain 저장 성공으로 간주하지 않는다.
- Git/gh 설정·credential helper·기존 계정 재사용이 사용자의 개인 개발 환경에 미치는 범위를 검증해야 한다. 설정 디렉터리 분리만으로 Keychain 계정 격리가 보장된다고 가정하지 않는다.
- 새 Mac에서 Git이 실제로 실행되는지, Git/gh 설치·인증 취소와 네트워크 실패 후 준비 상태를 어떻게 이어가는지 검증해야 한다.
- 앱 관리 Git 후보의 필요한 명령·worktree·submodule·LFS·인증·서명 커밋 호환성 및 macOS 배포 조건을 확인해야 한다. 이번 조사는 해당 기능의 실험 통과가 아니다.
- GitHub 계정 연결과 프로젝트 코드 업로드·저장소 생성은 다른 동작이다. 새 저장소의 소유자·공개 범위·자동 생성/업로드 정책은 후속 확인 대상이다.
- GitHub 코드 저장소를 앱 전체의 백업·복원 기능으로 표현하지 않는다. D-055의 SQLite·기억·작업 상태에 관한 OS 백업 정책은 별도로 유지한다.
- 이번 질문은 GitHub 연결이 없는 비개발자의 신규 시작에 관한 것이다. 원격 서비스의 초기 자동화 범위는 후속 [Q-017](017-git-hosting-support.md)에서 GitHub부터 제공하도록 확정했다. GitLab 등은 로컬 개발과 기존 인증으로 가능한 일반 Git 작업을 지원하고 서비스별 설정·MR 처리는 사용자가 맡는다. 실제 기업용 서버·인증 환경의 호환성은 별도 기술 검증과 구분한다.

## 질문 원문

**Q-002. GitHub 계정이 없는 비개발자에게, 신규 프로젝트 개발을 시작하기 전 GitHub 가입·연결을 필수로 할까요?**

1. **연결을 권장하되 건너뛰기 허용 — 추천:** 온보딩에서 GitHub 연결을 안내하지만, 건너뛰어도 Mac 안에서 개발·커밋·병합까지 진행합니다. 원격 저장소가 필요한 작업을 시작할 때 연결을 다시 안내합니다.
2. **개발 시작 전 연결 필수:** 가입·로그인을 온보딩에 포함하고, GitHub 연결이 완료된 뒤 신규 프로젝트 구현을 시작합니다. 처음부터 원격 저장소를 이용할 수 있지만 가입·인증이 끝나지 않으면 구현을 기다립니다.

이 질문은 GitHub 연결의 필수 여부와 시점을 정하는 질문입니다. 위 설치·작성자 설정의 기술 추천과 새 원격 저장소 생성·공개 범위까지 일괄 승인하는 질문은 아닙니다.

## 사용자 답변 원문

```text
1
```

## 답변으로 확정된 내용

사용자는 Q-002의 **1번, 연결을 권장하되 건너뛰기 허용**을 선택했다. 당시 선택지 문구는 위 질문 원문에 보존한다.

1. GitHub 계정·연결이 없는 비개발자에게 온보딩에서 GitHub 연결을 안내하고 권장한다.
2. 연결을 건너뛰어도 Mac 안에서 신규 프로젝트 개발·커밋·병합까지 진행할 수 있다.
3. 원격 저장소가 필요한 작업을 시작할 때 GitHub 연결을 다시 안내한다.

확정 범위는 GitHub 연결의 필수 여부와 시점이다. 위 설치·작성자 설정의 기술 추천, 새 원격 저장소의 생성·소유자·공개 범위·업로드 위임은 이 번호 답변으로 확정되지 않았다.

## 다음 세션 반영 대상

후속 [Q-008](008-git-tool-provisioning.md)에서 Git·gh 준비 정책과 전역 설치 허용, 승인받은 추가 개발 도구 설정을 확정했다. [Q-012](012-git-author-identity.md)에서는 작성자 자동 설정과 브라우저 로그인 후 자동 설정 경로를 허용했다. 이 문서의 원래 번호 답변은 GitHub 연결 시점에 관한 답변으로 유지하며, 후속 답변의 원문과 보완 내용을 함께 확인한다.

- `README.md`, `02-product-decisions.md`, `04-resolved-details.md`: 비개발자 온보딩에서 GitHub 연결을 권장하되 필수 조건으로 두지 않는 결정에 연결한다.
- `03-architecture-and-roadmap.md`: GitHub 미연결 상태의 로컬 구현·커밋·병합과 원격 작업 진입 시 연결 안내를 반영한다.
- `requirements.csv`, `features.csv`, `01-implementation-gap.md`: 최초 준비 상태·GitHub 연결 건너뛰기·로컬 실행·원격 작업 대기를 요구·기능·검수 조건에 반영한다. 구체 ID 정렬은 다음 세션에서 수행한다.
- 이 문서는 신규 답변 기록이다. 기존 계획·CSV·코드는 이번 답변 기록 과정에서 수정하지 않았다.
