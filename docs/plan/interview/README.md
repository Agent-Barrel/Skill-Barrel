# 설계 인터뷰 기록

[어긋나는 점](../README.md#conflicts)을 정하기 위해 사용자에게 한 질문과 답변을 하나씩 기록한다. 질문 하나에 문서 하나를 두고, 사용자 답변은 받은 그대로 적는다. 다른 계획 문서에는 사용자가 요청할 때 반영한다. 설계를 판단할 때는 이 폴더의 답변 원문을 먼저 확인한다.

제품 이름은 Q09 답변에 따라 Barrel이다. 2026-10-12 사용자 지시([Q17-2](q17-2-repo-list-config-and-updates.md))에 따라 기록에 남아 있던 이전 이름을 모두 지웠다. 답변 원문에 들어 있던 것은 `[이전 이름]`으로 바꿨다.

Q17부터는 2026-10-12 구현 준비 점검에서 나온 질문이다. 점검 결과와 정본에 반영할 목록은 [readiness-2026-10-12.md](../readiness-2026-10-12.md)에 있다.

| 번호 | 주제 | 문서 |
| --- | --- | --- |
| Q01 | "끊임없이 작동"은 어디까지인가 | [q01-keep-working-scope.md](q01-keep-working-scope.md) |
| Q02 | subagent와 새 세션에 각각 어떤 일을 맡기는가 | [q02-subagent-vs-session.md](q02-subagent-vs-session.md) |
| Q03 | 오케스트레이터는 언제, 어떻게 재시작하는가 | [q03-orchestrator-restart.md](q03-orchestrator-restart.md) |
| Q03-2 | 오케스트레이터 교체를 자동으로: 최초 세션을 부트로더로 | [q03-2-bootloader-session.md](q03-2-bootloader-session.md) |
| Q04 | 처음부터 두 CLI를 모두 지원하는가 | [q04-target-cli.md](q04-target-cli.md) |
| Q03-3 | skill을 실행한 세션은 오케스트레이터만 띄우고 끝난다. 질문은 Slack으로 | [q03-3-launcher-and-slack.md](q03-3-launcher-and-slack.md) |
| Q04-2 | 오케스트레이터도 Claude와 Codex 모두에서 | [q04-2-orchestrator-on-both-cli.md](q04-2-orchestrator-on-both-cli.md) |
| Q05 | 구독 계정을 어떻게 나눠 쓰는가 | [q05-accounts.md](q05-accounts.md) |
| Q06 | 작업 트리를 언제, 어디까지 미리 나누는가 | [q06-task-tree.md](q06-task-tree.md) |
| Q07 | 공통 기억을 어디에, 어떤 형태로 두는가 | [q07-shared-memory.md](q07-shared-memory.md) |
| Q08 | 어떤 문서를 한국어로 두고, 무엇을 정본으로 삼는가 | [q08-korean-docs.md](q08-korean-docs.md) |
| Q09 | Slack을 어떻게 연결하고, 대시보드는 무엇으로 만드는가 (같은 메시지에 앱 이름 Barrel 지시) | [q09-slack-and-dashboard.md](q09-slack-and-dashboard.md) |
| Q10 | Slack 진행 보고를 어떻게 보내는가 (대시보드 대신 Slack, 같은 답에 PC 화면·작업 중지·언어 선택 추가) | [q10-slack-progress-reports.md](q10-slack-progress-reports.md) |
| Q10-2 | 작업 중지는 어떻게 하고, PC 화면은 무엇으로 만드는가 | [q10-2-pc-view-stop-language.md](q10-2-pc-view-stop-language.md) |
| Q10 확정 | Q10과 Q10-2에서 확정한 Slack 진행 보고, 작업 중지, PC 화면 (종합 문서) | [q10-confirmed.md](q10-confirmed.md) |
| Q11 | 실행기를 PC에 하나만 두는가, 프로젝트마다 두는가 | [q11-launcher-topology.md](q11-launcher-topology.md) |
| Q12 | 모델 배정과 다른 CLI로 넘기기 (같은 답에 남은 항목을 인터뷰하라는 지시) | [q12-model-config-and-cli-fallback.md](q12-model-config-and-cli-fallback.md) |
| Q14 | 구현 세션을 동시에 여러 개 돌리는가 (Q13보다 먼저 물었다) | [q14-parallel-sessions.md](q14-parallel-sessions.md) |
| Q13 | 작은 요청에도 인터뷰와 승인 단계를 모두 거치는가 | [q13-depth-by-impact.md](q13-depth-by-impact.md) |
| Q15 | 작업 트리와 작업 계약을 어디에 두는가 | [q15-task-files-in-repo.md](q15-task-files-in-repo.md) |
| Q16 | 어떤 조사를 두 공급자가 따로 하고 합치는가 (답: 공급자로 나누지 않는다. CLI는 엔진일 뿐) | [q16-engines-and-verification.md](q16-engines-and-verification.md) |
| Q17 | 예전 계획에서 정한 결정 중 빠진 것을 되살리는가 (답: 13묶음 모두) | [q17-restore-archived-decisions.md](q17-restore-archived-decisions.md) |
| Q18 | 같은 프로젝트에 새 요청이 오면 진행 중인 실행에 합치는가, 따로 돌리는가 | [q18-one-run-per-request.md](q18-one-run-per-request.md) |
| Q19 | 스택 확정을 받아야 하는 "새 기술"은 어디까지인가 | [q19-new-technology-threshold.md](q19-new-technology-threshold.md) |
| Q20 | 관리자 권한과 자격증명을 어떻게 받는가 (같은 답에 sudo 전용 도구 지시) | [q20-credentials-and-sudo-tool.md](q20-credentials-and-sudo-tool.md) |
| Q17-2 | 되살린 결정의 후속 지시: 레포 목록, 개인 설정 분리, 자동 업데이트 (같은 답에 이전 이름 삭제 지시, 확인 질문의 답 포함) | [q17-2-repo-list-config-and-updates.md](q17-2-repo-list-config-and-updates.md) |
| Q21 | 원격에서 자동 업데이트할 때 동의를 받는가 (답: 동의도 알림도 없이 실행할 때 확인) | [q21-auto-update-consent.md](q21-auto-update-consent.md) |
