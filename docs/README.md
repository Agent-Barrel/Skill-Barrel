# 문서

이 레포는 Claude Code와 Codex 안에서 skill로 불러 쓰는 작업 방식을 만든다. 2026-10-06에 설치형 데스크톱 앱에서 이 방향으로 바꿨다. 처음 읽는다면 [plan/](plan/README.md)부터 본다.

## 현재 방향 (plan/)

| 문서 | 내용 |
|------|------|
| [README.md](plan/README.md) | 이번 방향을 정한 요청 원문, 2026-09-29 초안과 어긋나는 점, 다음 단계 |
| [00-original-flow.md](plan/00-original-flow.md) | 원래 구상한 제품 흐름(0~12번) |
| [insight.md](plan/insight.md) | 작업 분할과 맥락 관리 원칙, 한국어 문서 작성 지침 |
| [skill-plugin/](plan/skill-plugin/README.md) | Barrel 설계 정본(영어, 2026-10-08, 2026-10-11 점검). 2026-09-29 초안은 [archive/](archive/README.md)로 옮겼다. |

## 실행 층 (step2step, unit loop)

| 문서 | 내용 |
|------|------|
| [step2step.md](step2step.md) | Claude Code 대화형 세션을 PTY로 띄워 프롬프트를 차례로 넣는 방법. bypass/plan 모드, 모델과 effort 지정, 동작 원리와 한계를 다룬다. |
| [codex-control.md](codex-control.md) | Codex를 app-server로 구동하는 `step2step.codex` 사용법 |

`substrate/`는 `step2step` 패키지(core = PTY 구동, attach = 콘솔 주입) 자체를 다루는 문서 6개다. 이 문서들은 다른 문서를 경로 대신 이름으로 언급하므로(자기완결 원칙), 위치는 이 색인에서 찾는다.

| 문서 | 내용 |
|------|------|
| [overview.md](substrate/overview.md) | **개요** — 무엇을, 왜, 무엇이 검증됐는지 / 빠른 시작 / 폴더·모듈 지도 |
| [how-it-works.md](substrate/how-it-works.md) | **동작 원리** — 구성요소, 완료 감지, 응답 캡처, 상태기계, bypass/plan 모드 시퀀스, 종료, 모델·effort 제어 |
| [implementation.md](substrate/implementation.md) | **구현 세부** — 모듈·함수별 상세, 결과 구조, 튜닝 포인트 |
| [findings.md](substrate/findings.md) | **실측 검증 & 설계 결정** — Claude Code TUI 동작 사실과 "왜 이렇게 했나" (반복 사실들의 원 출처) |
| [external-injection-findings.md](substrate/external-injection-findings.md) | **attach 모드 PoC 기록**(dated) — 이미 실행 중인 세션에 Win32 콘솔 주입, 실측 키 인코딩 |
| [inspection-2026-07-20.md](substrate/inspection-2026-07-20.md) | **검수 보고서**(dated) — 하네스 임베딩 관점 결함 12건·픽스, 응답 캡처 API, v2.1.215 재검증 |

## 참고

| 문서 | 내용 |
|------|------|
| [claude-gpt-모델-티어-매핑-가격비교.md](claude-gpt-모델-티어-매핑-가격비교.md) | Claude와 GPT 모델의 티어 대응과 가격 비교(2026-10-07 기준) |

## 보관 (archive/)

[archive/](archive/README.md)에는 설치형 앱의 계획 문서를 보관한다. 앱 코드, 이전 Python 웹 앱, 옛 실행 기록은 이전 레포의 `archive/tauri-desktop-app` 브랜치에 있다. 이 레포는 2026-10-12에 이전 레포의 파일만 가져와 새로 시작했으므로 그 브랜치가 없다.

## 로컬 보관 (done/, git 추적 안 함)

- **구현 가이드 (`done/guide/`).** 이전 Python 웹 앱의 구현 서술 10개다. 2026-09-10 리팩터(`step2step/core` → `claude`+`terminal`) 이전 구조를 기준으로 쓰였다.
- **자율 실행 개선 (`done/autonomy/`).** 2026-08-12~13 외부 Rust 프로젝트 12유닛 자율 실행에서 드러난 사고 3건, 구조적 결함 9건, 자체복구·범용화 제안 6개 문서다. 2026-09-15에 `step2step`과 unit loop(`barrel/core/{verify,gates,failures,preflight,unitloop}.py`, `orchestration/drivers/unit_loop.py`)에 반영했다. 대응표는 `done/autonomy/README.md` 상단에 있다.

## 한 줄 요약 (step2step)

```
러너(파이썬) ──spawn──▶ PTY(가짜 터미널) ──▶ claude (인터랙티브 TUI)
        ▲                                         │
        │   화면 읽기(pyte) + Stop 훅 신호 파일 ◀──┘
        └── "프롬프트 주입 → 완료 감지 → 다음 프롬프트" 를 자동 반복
```

- **주입**: bracketed paste로 프롬프트를 입력창에 넣고 Enter
- **완료 감지(결정론적)**: 세션에 주입한 `Stop` 훅이 턴 종료마다 신호 파일에 한 줄 추가 → 러너가 카운트 증가를 감지
- **모드**: `bypass`(무인 직진) / `plan`(계획 후 자동 승인)
