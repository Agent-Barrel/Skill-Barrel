# Q03-3. skill을 실행한 세션은 오케스트레이터만 띄우고 끝난다. 질문은 Slack으로

- 답변일: 2026-10-06
- 관련: [Q03](q03-orchestrator-restart.md), [Q03-2](q03-2-bootloader-session.md)의 정정, [원래 구상](../00-original-flow.md) 11번
- 기록 원칙: 사용자 답변은 받은 그대로 적는다. 내용이 다르면 답변 원문이 우선한다.

## 직전에 AI가 보고한 내용 (요약)

[Q03-2 검토](q03-2-bootloader-session.md#가능성-검토-ai-분석-2026-10-06)에서 AI는 skill을 실행한 세션을 "부트로더"로 계속 살려 두는 구조를 제안했다. 이 세션이 드라이버를 띄우고, 오케스트레이터의 질문을 받아 사용자에게 보여 주고, 답을 넘기는 구조였다. 그리고 "모든 단계에서 사용자는 부트로더 세션과만 대화한다"를 최종 결정으로 기록할지 물었다.

## 사용자 답변 (2026-10-06, 원문 그대로)

```text
뭔소린지 모르겠네
사람이 부트로더라는 말이 너가 더 헷갈리게 만든거야?
아니 내가 어떤 세션에서 skill 을 실행하면 이 세션에서 오케스트레이터 클로드 세션을 호출하고, skill을 실행한 세션은 그냥 오케스트레이터 클로드 세션 호출하고 역할이 끝나는거야. 그리고 사람한테 질문은 슬랙으로 하는거라고 명시해놨는데 '부트로더'세션이 왜 질문을 받아와야되는지 모르겠네
내 말 제대로 이해하고 작업한건 맞아?
```

## 요약 (원문이 우선)

- skill을 실행한 세션은 오케스트레이터 Claude 세션을 호출하는 일만 하고 역할이 끝난다.
- 사람에게 묻는 질문은 Slack으로 한다(원래 구상 11번). skill을 실행한 세션이 질문을 받아 올 이유가 없다.
- [Q03-2 검토](q03-2-bootloader-session.md#가능성-검토-ai-분석-2026-10-06)의 "부트로더가 질문을 중계한다"는 사용자 의도와 다르다.

## 가능성 검토 (AI 분석, 2026-10-06)

이 절은 사용자 답변이 아니라 사용자가 말한 구조를 AI가 확인한 결과다.

**결론: 사용자가 말한 구조대로 가능하다.** Claude Code의 백그라운드 세션(`claude --bg`)을 쓰면 별도 Python 드라이버 없이도 된다. 앞서 Q03, Q03-2에서 걱정한 "드라이버가 사용자 세션 종료 뒤에도 살아남는가" 문제도 Claude Code의 감독 프로세스가 맡는다.

### 흐름

1. 사용자가 아무 세션(Claude Code 또는 Codex)에서 skill을 실행한다.
2. 그 세션은 `claude --bg --name <이름> "<시작 지시>"`로 오케스트레이터 Claude 세션을 띄우고, 띄운 결과만 알린 뒤 역할을 끝낸다. 사용자는 이 세션을 닫아도 된다.
3. 오케스트레이터는 문서에서 맥락을 읽고 일한다. 사람에게 물을 것은 Slack으로 묻는다(원래 구상 11번).
4. 오케스트레이터의 맥락이 한도에 가까워지거나 한 단계가 끝나면, 오케스트레이터가 인계 문서를 쓰고 같은 방법(`claude --bg`)으로 다음 오케스트레이터를 띄운 뒤 끝난다.
5. 작업 세션([Q02](q02-subagent-vs-session.md)의 새 세션)도 오케스트레이터가 띄운다. Claude 작업 세션은 `claude --bg`로, Codex 작업 세션은 `step2step.codex`(app-server)로 띄운다.

### 근거 (공식 문서)

- **백그라운드 세션은 띄운 쪽이 닫혀도 계속 돈다.** "A separate supervisor process runs them, so you can close agent view, close your shell, or start a new interactive session and your dispatched work keeps going." 완전한 대화형 세션이고 구독 한도를 쓴다. `-p`와 함께 쓰면 거부된다. ([agent view](https://code.claude.com/docs/en/agent-view))
- **명령줄에서 띄우고 관리할 수 있다.**
  - 띄우기: `claude --bg "<prompt>"`에 `--model`, `--permission-mode`, `--name`, `--settings`, `--plugin-dir`를 붙일 수 있다.
  - 관리: `claude agents --json`(목록), `claude logs`, `claude stop`, `claude rm`.
- **설정을 일반 세션과 똑같이 불러온다.** 백그라운드 세션은 실행 디렉터리의 설정, 플러그인, skill, 훅, MCP 서버를 일반 세션처럼 읽는다. 그래서 오케스트레이터도 이 플러그인의 훅과 모니터를 쓸 수 있다.
- **교체 시점을 잴 수 있다.** 훅 입력의 `transcript_path`로 맥락 사용량을 계산하고, `additionalContext`로 "다음 끊는 지점에서 인계하라"는 지시를 넣을 수 있다([Q03 검토](q03-orchestrator-restart.md#가능성-검토-ai-분석-2026-10-06)).
- **Slack 답을 기다릴 수 있다.**
  - Slack MCP는 질문을 보내고 답을 읽는 데 쓴다.
  - MCP는 답이 왔다고 먼저 알려 주지 않는다. 그래서 플러그인 모니터(세션 내내 도는 백그라운드 명령, 출력 한 줄이 Claude에게 알림으로 감)가 Slack 답을 주기적으로 확인해, 답이 오면 오케스트레이터를 깨운다. ([플러그인 모니터](https://code.claude.com/docs/en/plugins/components))
  - [Q01](q01-keep-working-scope.md)대로, 답을 기다리는 동안 그 작업만 멈추고 다른 작업은 계속한다.
- **작업 세션이 끝난 것을 알 수 있다.** 같은 PC의 다른 세션이 한가해지면 알림을 받는 기능(`notify_when_idle`)이나, 결과 파일을 지켜보는 모니터로 안다. ([세션 간 메시지](https://code.claude.com/docs/en/cross-session-messaging))

### 확인이 필요한 것과 제약

1. **백그라운드 세션은 연구 프리뷰다.** 동작이 바뀔 수 있다. 문제가 생기면 이 레포의 `step2step`으로 세션을 띄우는 방식으로 대신한다.
2. **백그라운드 세션이 다시 백그라운드 세션을 띄울 수 있는지는 문서에 명시되지 않았다.** spike에서 확인한다(오케스트레이터 → 다음 오케스트레이터, 오케스트레이터 → 작업 세션).
3. **한가한 백그라운드 세션은 프로세스가 멈춘다.** 문서에는 "left idle with nothing running has its process stopped"라고 되어 있다. Slack 답을 기다리는 동안 모니터가 돌고 있으면 깨어 있는지, 멈췄다가 모니터 알림으로 다시 깨어나는지 spike에서 확인한다.
4. **Slack 연결 방식(토큰, 확인 주기)은 [어긋나는 점 9번](../README.md#conflicts)에서 정한다.**
5. **Codex에는 이런 백그라운드 세션 기능이 확인되지 않는다.** 따라서 Codex에서 skill을 실행해도 오케스트레이터는 Claude 세션으로 뜬다. 사용자 원문의 "오케스트레이터 클로드 세션"과 맞지만, [Q04](q04-target-cli.md)(두 CLI 지원)와의 관계는 사용자에게 확인한다.
