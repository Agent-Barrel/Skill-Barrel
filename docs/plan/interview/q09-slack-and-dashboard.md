# Q09. Slack을 어떻게 연결하고, 대시보드는 무엇으로 만드는가

- 질문일: 2026-10-06
- 관련: [어긋나는 점 9번](../README.md#conflicts), [원래 구상](../00-original-flow.md) 11·12번, [Q03-3](q03-3-launcher-and-slack.md)
- 기록 원칙: 사용자 답변은 받은 그대로 적는다. 아래 "선택지 대응"은 찾아보기 편하도록 붙인 요약이며, 내용이 다르면 답변 원문이 우선한다.

## 질문 (사용자에게 보낸 내용)

### 왜 지금 묻는지

원래 구상 11번(질문과 요청은 Slack으로, slack MCP 연동)과 12번(데스크톱에서 작업 상태를 보고 추가로 소통할 수 있는 대시보드형 UI)이 남아 있었다. Q03-3에서 사람에게 묻는 질문은 Slack으로 하기로 했으므로, 질문을 어떻게 보내고 답이 온 것을 어떻게 알아차릴지 정해야 했다.

### 확인한 사실

- **공식 Slack MCP:**
  - Slack이 직접 운영하는 MCP 서버(`mcp.slack.com/mcp`)가 2026-02-17에 정식 출시됐다. 메시지 보내기, 스레드 읽기, 검색, canvas 작성을 지원한다.
  - Claude Code는 공식 플러그인(`/plugin install slack@claude-plugins-official`)을 설치하면 MCP가 자동으로 설정된다.
  - Codex용 공식 플러그인은 아직 skill만 들어 있고 MCP는 연결돼 있지 않다. 직접 설정하는 우회 방법은 있다.
  - ([Slack 공지](https://docs.slack.dev/changelog/2026/07/31/slack-skills-plugin/), [slackapi/slack-skills-plugin](https://github.com/slackapi/slack-skills-plugin))
- **알림 문제:** 공식 Slack MCP는 사용자 본인 토큰(OAuth)으로 동작한다. 그래서 MCP로 보낸 질문은 본인이 쓴 메시지로 올라가고, 본인에게는 알림이 가지 않는다.
- **답 도착 감지:** MCP는 답이 왔다고 먼저 알려 주지 않는다. 실시간으로 받으려면 Slack 앱(봇)의 Socket Mode가 필요하다. 공개 URL 없이 WebSocket으로 이벤트를 받고, 앱 토큰(`xapp-`)과 봇 토큰(`xoxb-`)이 필요하다. ([Socket Mode](https://docs.slack.dev/apis/events-api/using-socket-mode/))
- **참고 자료:** 보존 브랜치의 Python 웹 앱에 질문함, 실시간 세션 패널, 이벤트 피드 화면이 있었다(보존 브랜치의 `orchestration/reports/`에 있는 화면 캡처).

### 선택지

**9-a. Slack 연결 방식**
- **X (추천)** 전용 Slack 봇과 공식 Slack MCP를 함께 쓴다.
  - 질문과 진행 보고는 봇이 보내므로 알림이 간다.
  - 프로젝트마다 채널 하나, 질문 하나마다 스레드 하나를 쓴다.
  - 답은 스레드에 달면 실행기가 Socket Mode로 바로 받아, 해당 오케스트레이터 세션에 새 턴으로 넣는다([Q04-2](q04-2-orchestrator-on-both-cli.md)). Claude와 Codex 오케스트레이터 모두 같은 방식으로 동작한다.
  - 공식 Slack MCP는 에이전트가 Slack 내용을 찾아보거나 읽을 때 쓴다.
  - 봇 설정은 skill이 처음 실행될 때 준비한다. 앱 설정(manifest)까지 skill이 만들고, 사용자는 워크스페이스 설치 승인과 토큰 입력만 한다. 설치 과정까지 브라우저 자동화로 대신할 수 있는지는 spike에서 확인한다.
- **Y** 공식 Slack MCP만 쓴다. 설정은 OAuth 한 번이면 되지만, 질문이 본인 계정으로 올라가서 알림이 오지 않고, 답을 주기적으로 조회해야 한다. Codex는 MCP를 직접 설정해야 한다.

**9-b. 대시보드**
- **P (추천)** 실행기가 로컬 웹 페이지(localhost)를 띄운다. 작업 트리, 세션별 상태, 대기 중인 질문, 최근 보고를 보여 주고, 이 페이지에서도 질문에 답하거나 지시를 보낼 수 있다. Slack과 같은 질문함을 쓴다. 데이터는 레포의 기억 단위([Q07](q07-shared-memory.md))와 실행 상태 파일에서 읽는다.
- **Q** 별도 화면 없이 Slack을 대시보드로 쓴다. 프로젝트 채널에 상태 canvas나 고정 메시지를 두고 갱신한다.

## 사용자 답변 (2026-10-06, 원문 그대로)

```text
X, P로 해줘. 대시보드는 좋은 UI/UX 를 가지고 있으면서도 가볍게 작동할 수 있는게 뭐가 있을지 이따 더 고민해보자.
또, 이 앱 이름을 [이전 이름] 이 아니라 'Barrel' 으로 해줘. 폴더 제목 명 빼고 바꿔야할 부분들 전부 바꿔줘. step2step 은 내부 모듈 명이니까 안바꿔도 돼.
```

> **원문을 바꾼 곳 (2026-10-12):** 이전 제품 이름을 레포에 남기지 말라는 사용자 지시([Q17-2](q17-2-repo-list-config-and-updates.md))에 따라, 원문의 그 단어만 `[이전 이름]`으로 바꿨다. 나머지는 받은 그대로다.

## 선택지 대응 (요약, 원문이 우선)

- 9-a: **X.** 전용 Slack 봇(질문·보고 발송, Socket Mode로 답 수신)과 공식 Slack MCP(에이전트의 Slack 조회)를 함께 쓴다.
- 9-b: **P.** 실행기가 로컬 웹 대시보드를 띄운다. 좋은 UI/UX를 가지면서 가볍게 동작할 수 있는 구현 방법은 나중에 따로 검토한다(미결).

  > **이후 변경(2026-10-07):** 진행 상황은 Slack에 새 메시지로 계속 보내고, 질문에 답하기와 지시 보내기도 Slack에서 한다. PC에는 작업 현황을 보고 작업을 중지하는 가벼운 화면만 둔다. [Q10](q10-slack-progress-reports.md), [Q10-2](q10-2-pc-view-stop-language.md), 확정 내용을 모은 [q10-confirmed.md](q10-confirmed.md)를 본다.
- 같은 메시지의 별도 지시:
  - 앱 이름을 **Barrel**로 바꾼다.
  - 폴더 제목 이름은 빼고, 바꿔야 할 부분은 전부 바꾼다.
  - `step2step`은 내부 모듈 이름이므로 바꾸지 않는다.
