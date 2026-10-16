# skill 방향의 출발점

갱신 2026-10-16 · 상태: 아래 어긋나는 점 1~10번과 그 뒤에 남은 질문(Q11~Q24)을 모두 정했다. Q16까지는 [정한 내용](#decisions)에 요약했고, 2026-10-12에 정한 Q17~Q24는 [구현 준비 점검 기록](readiness-2026-10-12.md)에 정리했다. 이 결정들을 모두 [skill-plugin/](skill-plugin/README.md) 영어 정본에 반영했다. 정본은 2026-10-08에 다시 썼고, 2026-10-11에 한 번 더 고쳤으며, 2026-10-13~16에 Q17~Q24를 반영해 개정했다.

> **제품 이름:** 2026-10-06에 **Barrel**로 정했다([Q09](interview/q09-slack-and-dashboard.md)). Python 패키지 이름도 `barrel/`이다.

> **레포 이전:** 2026-10-12에 이 레포를 [Agent-Barrel/Skill-Barrel](https://github.com/Agent-Barrel/Skill-Barrel)로 옮겼다. 커밋 기록 없이 파일만 가져와 새로 시작했다. 그래서 이 폴더의 문서에 나오는 커밋 해시와 `archive/tauri-desktop-app` 브랜치는 이전 레포의 것이다.

이 폴더는 제품을 Claude Code와 Codex 안에서 불러 쓰는 skill로 다시 만들기 위한 출발점이다. 사용자 요청 원문, 원래 구상한 제품 흐름, 작업 원칙, 설계 정본이 들어 있다. 아래 [어긋나는 점](#conflicts)은 2026-10-06~08 인터뷰에서 정했고, 결과는 [정한 내용](#decisions)에 요약했다. 사용자 답변 원문은 [interview/](interview/README.md)에 있다. 다른 세션이 이어서 작업할 때 알아야 할 맥락(작업 규칙, 읽는 순서, 저장소 사실)은 [session-context.md](session-context.md)에 있다. 확인한 코드·벤더 사실과 spike 항목은 정본의 [research.md](skill-plugin/research.md)와 [validation.md](skill-plugin/validation.md)로 옮겼다.

<a id="source"></a>
## 요청 원문 (2026-10-06)

```text
지금 이 레포는 claude code 와 codex 를 사용해서 별도의 에이전트로 동작하는 앱을 Tauri 로 만들려고 작업 중인 레포인데, 이렇게 하지 않고 다른 방식으로 작동하게 하고 배포하려고 해.
지금 같은 별도 에이전트 앱이 아니라, claude code 나 Codex의 스킬로 부를 수 있게 해서 이 스킬을 사용하면 작업 방식 자체를 변경( 자기가 직접 맥락을 가지고 작업하는게 아니라 각 세션을 두뇌로 사용하고 문서를 통해 맥락을 파악하며 subagent 뿐만 아니라 신규 코딩 에이전트 세션도 오케스트레이션하면서, 오케스트레이터도 필요한 경우 재시작하고 유저에게 정확한 요구사항과 명세를 도출해서 의도와 정확히 align 된 결과물을 만들기까지 끊임없이 작동.)하고, @docs/plan/00-original-flow.md 에 있는 것처럼 코딩에이전트가 작업할 수 있도록 하려고 해. @docs/plan/insight.md 도 함께 적용할거야.
이를 위해, 현재 로컬 main 브랜치에 지금까지 작업한 내용은 별도 브랜치로 보존한 뒤 origin 에 push 하고, Tauri 사용한 별도 에이전트 개발 작업 내용은 전부 정리해서 origin main 브랜치에서 skill 을 통한 작동방식으로 개발이 진행될 수 있도록 해줘.
```

같은 대화에서 사용자가 정한 것:

- 이전 로컬 main(`b045f50`)은 `archive/tauri-desktop-app` 브랜치로 보존하고 origin에 올렸다.
- main은 origin/main(`be46fa4`)에서 다시 시작했다. Rust/Tauri 구현 94커밋은 보존 브랜치에만 있다.
- main에서 Rust/Tauri 재작성 설계, 이전 Python 웹 앱, 옛 실행 기록과 리포트를 지웠다. 설치형 앱의 계획 문서는 [docs/archive/app-plan](../archive/app-plan/README.md)으로 옮겼다.
- 이번에는 정리와 방향 문서까지만 한다. 플러그인 골격을 만들고 초안을 전면 개정하는 일은 다음 단계에서 한다.

## 입력 문서

| 문서 | 담긴 내용 |
| --- | --- |
| [00-original-flow.md](00-original-flow.md) | 원래 구상한 제품 흐름(0~12번). 2026-10-06에 사용자가 고쳤다. 두 CLI 모두에 skill로 배포하고, 어려운 판단은 Claude Fable이나 GPT Astra에게 묻고, 구현은 Opus 5.5가 맡는다. 1번 아래에 맥락 관리 규칙이 추가됐고, 11번에 Slack MCP 연동이 명시됐다. |
| [insight.md](insight.md) | 작업을 주제 트리로 나누는 방법, 최소 단위 맥락과 상호 참조, 작업마다 필요한 맥락만 주는 원칙, 맥락 충돌을 작업 전에 정리하는 원칙, 문서를 영어로 먼저 쓰고 따로 번역하는 지침 |
| [skill-plugin/](skill-plugin/README.md) | 설계 정본(영어). 2026-10-08에 인터뷰 Q01~Q16으로 정한 내용을 반영해 다시 썼고, 2026-10-13~16에 Q17~Q24와 두 차례 구현 준비 점검 결과를 반영해 개정했다. 2026-09-29 초안 9개는 [보관 문서](../archive/skill-plugin-2026-09-29/README.md)로 옮겼고, 아래 [어긋나는 점](#conflicts) 표의 링크는 그 보관본을 가리킨다. |

main에 남은 코드 가운데 새 방향이 기반으로 삼을 수 있는 것은 두 가지다. `step2step`은 `-p` 없이 대화형 Claude Code 세션을 PTY로 새로 띄우고 Codex는 app-server로 구동한다. unit loop(`barrel/core/unitloop.py`, `orchestration/drivers/unit_loop.py`)는 유닛마다 새 세션을 하나씩 맡기고 게이트로 판정한다.

<a id="conflicts"></a>
## 초안과 이번 요청이 어긋나는 점

| # | 주제 | 2026-09-29 초안 | 2026-10-06 요청 | 정할 것 |
| --- | --- | --- | --- | --- |
| 1 | 끝까지 작동 | 목표를 이룰 때까지 에이전트를 반복 구동하지 않는다. 막히면 멈추고 사용자에게 돌아간다([비목표](../archive/skill-plugin-2026-09-29/README.md#non-goals)). | 의도와 정확히 맞는 결과물이 나올 때까지 끊임없이 작동한다. | 계속 작동하는 범위. 어떤 상황에서는 여전히 멈추고 사용자에게 묻는지 |
| 2 | 작업을 맡는 주체 | 작업마다 unit loop와 `step2step`으로 새 세션을 띄운다. subagent는 독립 세션이 아니고, 사용자에게 질문할 수 없고, plan 승인 흐름을 태울 수 없어서 쓰지 않는다([실행](../archive/skill-plugin-2026-09-29/task-sessions.md#execution)). | subagent와 새 코딩 에이전트 세션을 함께 오케스트레이션한다. | 어떤 일을 subagent에 맡기고 어떤 일을 새 세션에 맡기는지 |
| 3 | 오케스트레이터 | 사용자가 연 CLI 세션이 조율 세션이다([원래 구상과의 대응](../archive/skill-plugin-2026-09-29/migration.md#original-flow) 0번). 이 세션이 unit loop를 띄우고 진행을 지켜본다([두 층의 연결](../archive/skill-plugin-2026-09-29/plugin-architecture.md#flow)). | 세션은 두뇌로만 쓰고 맥락은 문서로 파악한다. 필요하면 오케스트레이터도 재시작한다. | 재시작 조건, 상태를 넘기는 문서, 새 오케스트레이터 세션을 띄우는 주체 |
| 4 | 대상 CLI | spike는 Claude Code 조율로 먼저 한다([OD-2](../archive/skill-plugin-2026-09-29/open-decisions.md#od-2)). | 원래 구상 0번이 "Codex와 Claude Code에서 쓸 수 있는 skill로 배포"로 바뀌었다. | spike에서 두 CLI를 모두 다룰지, 다룬다면 어떤 순서로 할지 |
| 5 | 구독 계정 | 여러 계정을 번갈아 쓰지 않는다. `step2step`이 자식 세션에서 `CLAUDE*` 변수를 지워서 `CLAUDE_CONFIG_DIR`로 계정을 나누는 방식은 지금 구조에서 동작하지 않는다([원래 구상과의 대응](../archive/skill-plugin-2026-09-29/migration.md#original-flow) 1번). | 원래 구상 1번: confdir와 `CODEX_HOME`으로 구독 계정마다 폴더를 나눠 쓴다. | 여러 계정을 지원할지, 지원한다면 skill 구조에서 어떻게 나눌지 |
| 6 | 작업 분할 | 확정된 정본을 작은 코드 작업 목록(`roadmap.json` 유닛)으로 나눈다([작업 크기](../archive/skill-plugin-2026-09-29/task-sessions.md#size)). | insight: 대주제, 중주제, 소주제의 트리로 나누고 대주제부터 아래로 재귀 실행한다. | 로드맵을 트리로 둘지, 몇 단계까지 나눌지 |
| 7 | 공통 기억 | 프로젝트 정본 파일과 `~/.barrel/memory`를 세션 시작 때 주입한다([원래 구상과의 대응](../archive/skill-plugin-2026-09-29/migration.md#original-flow) 1-1번). | 기억 파일을 최소 단위 맥락으로 나누고 서로 참조하게 한다. 계획 초안을 쓰고, 필요한 맥락을 읽어 고치고, 그 맥락이 참조하는 맥락을 따라가며 다시 고친다. | 기억 파일의 단위와 참조 형식, 계획을 고쳐 가는 반복의 종료 조건 |
| 8 | 한국어 문서 | 다루지 않았다. | insight: 문서는 영어로 먼저 쓰고, 번역 지침을 준 별도 작업으로 번역한다. [Skill-Techblog](https://github.com/KANG-YEONWOOK/Skill-Techblog)를 활용한다. | 한국어로 내보낼 산출물의 범위, 번역 단계를 두는 위치 |
| 9 | Slack, 대시보드 | spike는 벤더 표면만 쓴다([OD-7](../archive/skill-plugin-2026-09-29/open-decisions.md#od-7)). | 원래 구상 11번: Slack MCP로 소통한다. 12번: 데스크톱 대시보드형 UI가 필요하다. | Slack MCP를 첫 범위에 넣을지, 대시보드를 무엇으로 대신할지 |
| 10 | 기존 코드 | Rust는 개발 동결하고 아무것도 지우지 않는다([OD-3](../archive/skill-plugin-2026-09-29/open-decisions.md#od-3)). | 보존 브랜치로 옮기고 main에서 지운다. | 결정됨(2026-10-06) |

<a id="decisions"></a>
## 정한 내용

위 1~10번과 그 뒤에 남은 질문(11번)을 어떻게 정했는지 요약한다. 요약이므로, 내용이 다르면 [인터뷰 기록](interview/README.md)의 답변 원문을 따른다.

1. **끝까지 작동** ([Q01](interview/q01-keep-working-scope.md), [Q06](interview/q06-task-tree.md))
   - 확정 없이 무작정 돌리지 않는다. 요구사항 도출과 기능명세 단계에서 사람의 의도를 확인할 정보를 모두 뽑아 문서로 남긴다.
   - 구현에 들어가기 전에, AI가 정리한 작업 의도를 사용자가 검토한다.
   - 실행 중에 AI가 판단할 수 있는 것은 그대로 진행한다. 사람에게 묻는 것은 두 경우뿐이다.
     - 기획 의도, 요구사항 명세, 기능 명세로도 방향을 유추할 수 없을 때
     - 새로운 의사결정이 필요할 때
   - 막힌 작업만 멈추고, 그 작업과 무관한 작업은 계속한다.
   - 마지막에 "의도와 맞다"는 판정은 요구사항 명세서와 기능명세서를 근거로 AI가 한다.
   - 사람이 처음 정한 내용을 바꾸면, 그 변경과 충돌해 함께 바뀌어야 하는 것도 맥락과 같이 보여 주고 함께 정하게 한다.
2. **작업을 맡는 주체** ([Q02](interview/q02-subagent-vs-session.md))
   - 새 세션(`step2step`)이 맡는 일:
     - 구현
     - 계획 승인이 필요한 작업
     - 다른 공급자가 필요한 일. [Q16](interview/q16-engines-and-verification.md) 이후로는 공급자로 일을 나누지 않는다. 설정이 고른 엔진이 부모 세션과 다른 CLI이면 새 세션으로 띄운다.
     - 오케스트레이터가 재시작돼도 이어져야 하는 작업
   - subagent는 읽기만 하는 짧은 일을 맡는다. 맥락 수집, 조사, 독립 검토가 여기에 든다.
   - 작업 세션도 그 안에서 subagent를 쓸 수 있다.
3. **오케스트레이터** ([Q03](interview/q03-orchestrator-restart.md), [Q03-3](interview/q03-3-launcher-and-slack.md), [Q04-2](interview/q04-2-orchestrator-on-both-cli.md))
   - skill을 실행한 세션은 세션 실행기로 오케스트레이터 세션을 띄우고 역할을 끝낸다.
   - 사람에게 묻는 질문은 Slack으로 한다.
   - 실행기는 `step2step`을 바탕으로 만든다(Claude는 PTY, Codex는 app-server). 실행기는 띄운 세션을 쥐고 있고, skill을 실행한 세션이 닫혀도 계속 돈다.
   - 오케스트레이터는 단계가 끝날 때, 구현 중에는 중주제 하나를 마칠 때, 맥락이 한도에 가까워질 때 인계 문서를 쓴다. 그다음 같은 실행기로 다음 오케스트레이터를 띄우고 끝난다. 교체에 사람이 입력할 것은 없다.
   - 교체할 때 `/clear`를 입력하는 방식(Q03)과 skill 세션이 질문을 중계하는 방식(Q03-2)은 쓰지 않는다.
4. **대상 CLI** ([Q04](interview/q04-target-cli.md), [Q04-2](interview/q04-2-orchestrator-on-both-cli.md))
   - 처음부터 Claude Code와 Codex를 모두 지원한다. 오케스트레이터도 둘 중 어느 쪽이든 될 수 있고, Codex용 세션 실행기도 만든다.
   - 진행 순서는 Claude Code 다음 Codex다. spike 통과 기준에는 두 CLI를 모두 넣는다.
5. **구독 계정** ([Q05](interview/q05-accounts.md))
   - PC에 이미 등록된 계정(Claude는 `CLAUDE_CONFIG_DIR`, Codex는 `CODEX_HOME`)을 찾아 쓴다. 없으면 계정별 설정까지 해 준다.
   - 한 계정을 쓸 수 없게 되면 다음 계정을 쓴다.
6. **작업 분할** ([Q06](interview/q06-task-tree.md))
   - 기능명세가 끝나면 대주제와 중주제까지 나눈다. 나눈 결과는 작업 의도 요약과 함께 검토받는다.
   - 소주제(말단 작업)는 그 중주제 차례가 왔을 때, 관련 맥락을 따라 읽으며 나눈다.
   - 말단 작업은 다음 네 조건을 모두 만족하는 크기로 나눈다. AI가 제안했고 사용자가 이의를 말하지 않았다.
     - 새 세션 하나가 맥락 압축 없이 끝낼 수 있다.
     - 결과가 하나다.
     - 쓸 파일 범위를 미리 적을 수 있다.
     - 검증 방법이 정해져 있다.
7. **공통 기억** ([Q07](interview/q07-shared-memory.md))
   - 기억은 대상 프로젝트 레포 안에 두고 git으로 추적한다. 실행 상태는 레포 밖에 둔다.
   - 기억 단위마다 파일을 하나 두고, 파일 머리에 ID, 종류, 한 줄 요약, 관련 ID를 적는다.
   - 종류별 색인 파일에 단위마다 한 줄씩 적는다. 인터뷰 답변 원문도 기억 단위로 남긴다.
   - 계획을 고쳐 가는 반복은 두 조건을 모두 만족하면 멈춘다. AI가 제안했고 사용자가 이의를 말하지 않았다.
     - 마지막 읽기에서 계획이 바뀌지 않았다.
     - 읽은 단위의 참조를 모두 읽었거나, 색인 요약을 보고 무관하다고 판단했다.
8. **한국어 문서** ([Q08](interview/q08-korean-docs.md))
   - 영어가 정본이다. 기억 단위, 작업 계약, 세션끼리 주고받는 문서는 영어로만 쓴다.
   - 사람이 보는 글만 한국어로 내보낸다. 영어 원문을 바탕으로 Skill-Techblog 스킬로 쓴다.
   - 사용자 답변 원문은 받은 언어 그대로 둔다.
   - 예외가 둘 있다. 진행 보고는 실행기의 고정 문형으로 보낸다. Slack 언어를 영어로 고르면 영어 원문을 그대로 보낸다(Q10).
9. **Slack과 대시보드** ([Q09](interview/q09-slack-and-dashboard.md), [Q10](interview/q10-slack-progress-reports.md), [Q10-2](interview/q10-2-pc-view-stop-language.md), [확정 내용 종합](interview/q10-confirmed.md))
   - **Slack 연결:**
     - 전용 Slack 봇이 질문과 진행 보고를 보낸다.
     - 답은 Socket Mode로 받고, 실행기가 기다리는 오케스트레이터에 넣는다.
     - 에이전트가 Slack을 읽을 때는 공식 Slack MCP를 쓴다.
     - 프로젝트마다 채널 하나, 질문마다 스레드 하나를 쓴다.
   - **진행 보고:**
     - 대시보드 대신 진행 상황을 Slack에 새 메시지로 계속 보낸다. 큰 일은 채널 본문에, 말단 작업 같은 세부는 스레드에 보낸다.
     - 사람이 해야 할 일에만 멘션한다.
     - 상태 요약은 요청할 때, 단계나 대주제가 끝날 때, 3시간 동안 조용할 때 보낸다.
   - **질문:** `[{프로젝트명}-질문]`으로 시작하고, 스레드로 답해 달라고 적는다. 답이 없으면 1, 2, 4, 8시간 뒤에 다시 멘션하고, 그 뒤로는 8시간마다 멘션한다.
   - **언어:** Slack 언어는 한국어가 기본이고, 영어로 바꿀 수 있다.
   - **Slack이 끊겼을 때:** 복구될 때까지 기다렸다가 현황과 쌓인 질문만 보낸다.
   - **PC 화면:**
     - 실행기가 띄우는 가벼운 로컬 웹 화면을 둔다. 이 화면에서는 작업 현황을 보고, 작업을 중지하거나 재개하는 것만 한다.
     - 화면을 닫아도 Spotlight의 Barrel 앱이나 Slack의 "화면" 명령 등으로 다시 열 수 있다.
   - **작업 중지:** Slack과 PC 화면 모두에서 할 수 있다. 프로젝트 실행 전체를 즉시 멈추고, 재개하면 멈춘 곳부터 이어서 한다.
   - **제품 이름:** Barrel로 바꿨다.
10. **기존 코드** (2026-10-06 요청 대화)
    - Rust/Tauri 구현과 이전 Python 웹 앱은 `archive/tauri-desktop-app` 브랜치에 보존하고 main에서 지웠다.
11. **나중에 남은 질문** ([Q11](interview/q11-launcher-topology.md)~[Q16](interview/q16-engines-and-verification.md), 2026-10-07~08)
    - **실행기:** PC에 하나만 둔다. 이 실행기가 모든 프로젝트 실행과 Slack 연결 하나를 맡는다(Q11).
    - **모델 배정:** 프로젝트의 `.barrel/config.json`에 두고 팀이 함께 쓰고 고친다. PC에 등록된 CLI와 계정을 모두 쓰고, 쓸 수 없으면 다른 계정이나 다른 CLI로 넘긴다(Q12).
    - **단계의 깊이:** AI가 요청의 영향 범위(국소, 확장, 전체)를 보고 정한다. 구현 전 작업 의도 검토는 빼지 않는다(Q13).
    - **병렬 실행:** 서로 무관하고 쓰는 파일이 겹치지 않는 말단 작업을 worktree에서 동시에 돌린다. 기본은 2개다(Q14).
    - **작업 계약:** 대상 레포의 `.barrel/tasks/`에 두고 git으로 추적한다(Q15).
    - **엔진:** Claude Code와 Codex는 Barrel을 돌리는 엔진일 뿐이라 공급자별로 일을 나누지 않는다. 조사한 뒤에는 따로 검증하고, 모델과 effort는 작업 난이도에 맞춘다(Q16).

## 다음 단계

1. ~~위 표의 1~9번을 사용자와 정한다.~~ 2026-10-06에 마쳤다([interview/](interview/README.md), [정한 내용](#decisions)).
2. ~~아직 묻지 않은 질문을 정한다.~~ 2026-10-07~08에 Q11~Q16으로 마쳤다([정한 내용](#decisions) 11번).
3. ~~정한 내용으로 skill-plugin/을 개정해 새 정본으로 삼는다.~~ 2026-10-08에 [skill-plugin/](skill-plugin/README.md)을 영어 정본으로 다시 썼다([Q08](interview/q08-korean-docs.md)). 이번에는 한국어판을 만들지 않았다.
   - 2026-10-11에 한 번 더 점검했다. 인터뷰 답과 어긋난 두 곳(Q02, Q05)을 바로잡고, 흐름이 실제로 돌아가는 데 필요한 빈 곳을 채웠다.
   - 새로 채운 기본값과 이어받지 않은 보관 결정은 [open-decisions.md](skill-plugin/open-decisions.md)에 검토 대상으로 적었다.
4. ~~2026-10-12에 정한 Q17~Q24를 정본에 반영한다.~~ 2026-10-13~16에 반영했다.
   - [구현 준비 점검 기록](readiness-2026-10-12.md)의 항목이 정본의 어디에 들어갔는지는 [migration.md](skill-plugin/migration.md#readiness)에 있다.
   - 예전 계획의 결정 93개도 모두 [migration.md](skill-plugin/migration.md#archived)에서 반영한 곳이나 이어받지 않은 이유를 찾을 수 있다.
5. [validation.md](skill-plugin/validation.md)의 spike를 실행한다. 인터뷰 중에 모은 항목과 정본을 쓰며 더한 항목을 모두 이 문서에 모았다.
