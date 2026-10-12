# 보관 문서

이 폴더에는 2026-10-06까지 이 레포가 만들던 설치형 데스크톱 앱(Rust/Tauri)의 계획 문서를 보관한다. 2026-10-06에 Claude Code와 Codex 안에서 동작하는 skill로 방향을 바꾸면서 이 문서들은 정본에서 빠졌다. skill을 설계할 때 방법론 규칙(작업 흐름, 오케스트레이션, 결정 기록)을 계속 참고할 수 있도록 main에 남겨 둔다. 2026-09-29에 쓴 skill 전환 초안도 2026-10-08에 새 정본으로 바꾸면서 이곳으로 옮겼다.

| 경로 | 내용 |
| --- | --- |
| [app-plan/](app-plan/README.md) | `b045f50` 시점의 `docs/plan` 전체. D-068과 D-069까지 반영한 판이다. |
| [skill-plugin-2026-09-29/](skill-plugin-2026-09-29/README.md) | 2026-09-29에 쓴 skill·플러그인 전환 초안 9개(한국어). 새 정본은 [docs/plan/skill-plugin/](../plan/skill-plugin/README.md)이다. |

app-plan 문서가 가리키는 코드(`crates/`, `apps/`, `docs/implementation/`, Python 웹 앱)는 main에서 지웠다. 이 코드는 이전 레포의 `archive/tauri-desktop-app` 브랜치에 그대로 있다. 이 레포는 2026-10-12에 이전 레포의 파일만 가져와 시작해서 그 브랜치가 없다. app-plan 안의 상대 링크 가운데 이 레포에 없는 파일을 가리키는 링크는 이전 레포의 그 브랜치에서 찾아야 한다.

보관 문서에 있던 이전 제품 이름은 2026-10-12 사용자 지시([Q17-2](../plan/interview/q17-2-repo-list-config-and-updates.md))에 따라 Barrel로 바꿨다. 옛 패키지를 가리키던 코드 경로도 지금 패키지 이름(`barrel/`)으로 적었다. 보존 브랜치에는 옛 경로가 그대로 있으므로, 그 브랜치에서 파일을 찾을 때는 경로가 다를 수 있다.

현재 방향은 [docs/plan](../plan/README.md)에 있다.
