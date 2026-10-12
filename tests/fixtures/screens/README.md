# 화면 픽스처 (Claude Code 2.1.224)

`screen.py`의 다이얼로그 판별은 TUI 문자열에 의존한다. 그 문자열이 **실제로 어떻게 렌더되는지**를
합성 문자열이 아니라 실화면으로 고정해 두기 위한 픽스처다. 새 Claude Code 버전에서 판별이 깨지면
`python -m step2step.claude.calibrate_dialogs <throwaway-dir>`로 다시 캡처해 이 파일들을 교체한다.

모든 파일은 `ExternalSession.text()` / `ScreenReader.tail()`이 돌려주는 형태 —
**빈 줄이 제거된 화면 텍스트** — 그대로다.

| 파일 | 출처 | 왜 이 모양인가 |
|---|---|---|
| `plan_approval.txt` | **실캡처** — `calibrate_dialogs`, v2.1.225 | 승인 메뉴. `Ready to code?`와 `… is ready to execute. Would you like to proceed?`가 **둘 다** 나오므로 앵커는 "마지막 것"을 써야 한다. 옵션 3종의 실제 문구와, 옵션 3 아래 붙는 `shift+tab to approve with this feedback` 들여쓰기 줄까지 그대로 |
| `plan_approval_numbered_body.txt` | 위에서 **파생** (플랜 본문만 번호 목록으로 교체) | 앵커 스코핑 회귀용. 본문의 `1. Yes, this numbered line is a trap…`이 옵션 1로 읽히면 **엉뚱한 항목을 Enter로 실행**하게 된다 |
| `ask_user_question.txt` | **실캡처** — `calibrate_dialogs`, v2.1.225 | 질문이 **하나**인 AskUserQuestion 위젯. 탭 바가 없고 대신 헤더 행 ` ☐ Config format`이 붙으며, 푸터 중간이 `↑/↓ to navigate`다. 헤더 행을 파싱하지 않으면 질문 문장에 그대로 섞여 들어간다 |
| `ask_user_question_tabs.txt` | 실화면 **구조** + 내용 중립화 | 질문이 **여럿**인 위젯. 원본은 사유(私有) 프로젝트 내용이라 질문/옵션 문장만 무해하게 바꾸고 **TUI 크롬은 한 글자도 건드리지 않았다**. 함정 3가지: ① 탭 바(`← ☐ … ✔ Submit →`) ② 옵션 3과 4 사이에 **구분선이 끼어 옵션이 연속되지 않음** ③ 위젯 **아래에** 작업 패널 5줄이 렌더돼 꼬리 10줄만 보면 옵션을 놓친다. 푸터 중간이 `Tab/Arrow keys to navigate`로 위와 다르다 |
| `working_with_task_panel.txt` | 실화면 **구조** + 내용 중립화 | 진행 중 화면. 번호 목록도 다이얼로그 푸터도 없으므로 어떤 판별기도 여기서 걸리면 안 된다. 모드 줄 아래로 에이전트 패널 4줄이 더 붙는 배치가 핵심 |

두 질문 위젯의 푸터 중간 문구가 서로 다르다는 점이 `QUESTION_FOOTER_MARKERS`가
양 끝(`Enter to select` / `Esc to cancel`)만 보는 이유다.

## 여기 없는 것

`ask_user_question_tabs.txt`의 원본은 프롬프트·전략 내용을 담고 있어 이 레포에 넣지 않았다.
판별에 쓰이는 것은 크롬(푸터·옵션 마커·구분선 배치)뿐이므로 회귀 가치는 동일하다.
