# Q04. 처음부터 두 CLI를 모두 지원하는가

- 질문일: 2026-10-06
- 관련: [어긋나는 점 4번](../README.md#conflicts), 09-29 초안 [OD-2](../../archive/skill-plugin-2026-09-29/open-decisions.md#od-2)
- 기록 원칙: 사용자 답변은 받은 그대로 적는다. 아래 "선택지 대응"은 찾아보기 편하도록 붙인 요약이며, 내용이 다르면 답변 원문이 우선한다.

## 질문 (사용자에게 보낸 내용)

### 왜 지금 묻는지

원래 구상 0번이 "Codex 기본"에서 "Codex와 Claude Code에서 사용할 수 있는 스킬로 배포"로 바뀌었다. 반면 09-29 초안(OD-2)은 spike를 Claude Code로 먼저 하자고 추천했다. 이 답에 따라 첫 버전의 범위와 spike 통과 기준이 정해진다. 어느 쪽이든 Fable·Astra 조언, Opus 5.5 구현, 양사 교차 조사 때문에 두 CLI를 작업 세션으로는 함께 쓴다.

### 두 CLI의 현재 상태 (2026-10 공식 문서와 이 레포 기준)

| | Claude Code | Codex |
| --- | --- | --- |
| skill·플러그인 | `SKILL.md`, `.claude-plugin/plugin.json` | `SKILL.md`, `.codex-plugin/plugin.json` |
| 플러그인 훅 | 지원, 이벤트 약 30개 | 지원, 이벤트 12개. 사용자가 훅마다 한 번 신뢰해야 하고, 내용이 바뀌면 다시 신뢰 |
| A안(Q03)에 필요한 훅 | `SessionStart`(clear), `PreCompact`, `Stop`, `PostToolUse` 모두 있음 | 모두 있음 |
| subagent, `/goal` | 있음 | 있음 |
| 백그라운드 세션, 세션 간 메시지 | 있음 | 확인되지 않음 |
| step2step 드라이버 | unit loop에 연결됨, 2.1.272까지 실측 | live 5/5, unit loop 연결은 아직 없음 |

skill 본문은 두 CLI가 같은 `SKILL.md` 형식이라 함께 쓸 수 있다. 차이는 매니페스트, 훅 출력 형식, 훅 신뢰 안내 정도다. 한 저장소에 두 매니페스트를 둘 수 있는지는 spike에서 확인한다.

출처: [Claude 훅](https://code.claude.com/docs/en/hooks), [Codex 훅](https://learn.chatgpt.com/docs/hooks), [Codex 플러그인](https://developers.openai.com/codex/plugins/build)

### 선택지

- **A (추천) 처음부터 둘 다 지원한다.** skill 본문과 드라이버는 하나로 두고, CLI별 차이만 얇은 어댑터로 처리한다. spike 통과 기준에 두 CLI를 모두 넣는다. 진행 순서만 Claude Code 먼저, 바로 이어서 Codex로 한다. Claude 쪽 드라이버가 이미 unit loop에 연결돼 있고 훅 신뢰 단계가 없기 때문이다.
- **B** Claude Code만 먼저 완성하고 배포한다. Codex 오케스트레이터 지원은 다음 버전으로 미루고, 그동안 Codex는 작업 세션(조언·교차 조사)으로만 쓴다.
- **C** Codex를 먼저 한다(09-29 이전 원래 구상의 "Codex 기본").

## 사용자 답변 (2026-10-06, 원문 그대로)

질문 4에 해당하는 문장이다. 같은 메시지의 나머지(질문 3 후속)는 [Q03-2](q03-2-bootloader-session.md)에 전문을 기록했다.

```text
그리고 질문 4는 A안으로 진행해줘.
```

## 선택지 대응 (요약, 원문이 우선)

- **A.** 처음부터 Claude Code와 Codex를 모두 지원한다. 공유 코어에 얇은 어댑터를 붙이고, spike 통과 기준에 두 CLI를 모두 넣는다. 진행 순서는 Claude Code 다음 Codex다.
