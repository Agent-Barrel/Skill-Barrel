# orchestration/

unit loop와 단일 작업 세션을 명령줄에서 돌리는 드라이버를 둔다. 실행 산출물(`logs/`, `results/`, `app_dirs/`)은 git이 추적하지 않는다.

| 파일 | 내용 |
| --- | --- |
| `drivers/unit_loop.py` | unit loop 드라이버. 로드맵의 유닛마다 새 세션 하나를 띄우고 게이트로 판정한다. 엔진은 `barrel/core/unitloop.py`이고 설정 예시는 `fixtures/unit_loop.example.json`이다. 옵션과 종료 코드는 파일 머리말에 있다. |
| `drivers/run_worker.py` | Claude Code 세션 하나에 `prompts/<이름>.md`의 프롬프트를 차례로 넣는다. 파일 안의 `WORKERS` 표는 2026-07-31 야간 구축 때 쓴 워크트리 설정이고, 표에 없는 이름은 레포 루트에서 실행한다. |
| `drivers/w0_v3_probe.py` | 대화형 세션에서 `claude --append-system-prompt`가 적용되는지 확인하는 실측 스크립트 |
| `drivers/w1_live_probe.py` | `SessionHandle`이 두 턴 대화를 이어 가는지 확인하는 실측 스크립트 |

2026-07-31 야간 구축 기록(워커 프롬프트, 리포트, 워크트리 현황)과 2026-08-13 starfort 실행 기록은 main에서 지웠다. 이전 레포의 `archive/tauri-desktop-app` 브랜치에 있는 `orchestration/`에서 볼 수 있다.
