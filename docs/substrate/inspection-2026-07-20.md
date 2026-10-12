# step2step 정밀점검 리포트 (2026-07-20)

> **리팩터링 주석 (2026-07-23)**: 이 문서는 작성 시점의 레이아웃 기준 기록이다. 이후
> 패키지가 통합되어 — 당시 `poc/` = 현 `step2step/core/`, 당시 `external/` = 현
> `step2step/attach/` — 본문 경로·모듈명·명령(`python -m poc` → `python -m step2step`,
> `python -m external.attach_runner` → `python -m step2step.attach.attach_runner`)은
> 원문 그대로 둔다.

Claude Code TUI 자동구동 모듈에 대해 **코드 리뷰 + 실제 작동 테스트**로 "현재 구현이 의도대로 작동하는가"를 검증하고, 발견한 결함을 전면 수정한 뒤 재검증한 기록. 이 모듈은 향후 **AtoZ 개발 하네스**(컨셉 → 기획 Q&A → 개발 → 테스트 → 배포)의 서브모듈로 편입될 예정이며, 그 관점의 준비도까지 평가한다.

## 환경

| 항목 | 값 |
|------|-----|
| Claude Code | **2.1.215** (문서상 검증 시점 2.1.195보다 20릴리스 최신) |
| Python / pywinpty / pyte | 3.12.3 / 3.0.5 / 0.8.2 |
| OS | Windows 11 (26200) |
| 테스트 모델 | **haiku** (사용량 절약, 사용자 요구) |
| 라이브 세션 수 | 총 7회 (Phase 1 4회 + Phase 4 3회, 전부 haiku) |

## 총평

**현행 구현의 4개 실행 경로(bypass · plan · attach + 프롬프트 파싱/훅/안전가드)는 2.1.215에서 의도대로 end-to-end 작동함**을 라이브로 확인했다. 22일 전(2.1.195) 기준으로 튜닝된 TUI 마커도 **드리프트 없음**. 다만 **헤드리스(무TTY) 임베딩에 치명적인 결함 2건(D1·D2)** 을 포함해 총 12건의 결함을 발견했고, 전부 수정 후 재검증으로 해소했다. 서브모듈 편입 시 필요한 **응답 캡처 API(기획 Q&A 루프의 기반)** 도 신설했다.

---

## 1. 테스트 판정 매트릭스

### Phase 1 — 현행(수정 전) 기준선

| 테스트 | 판정 | 핵심 증거 |
|--------|------|-----------|
| 정적/단위 (파싱·훅·가드·probe) | ✅ PASS | parse_prompts 6벡터, SignalWatcher, `_forbidden_pid`(self/조상/사망 거부), probe.py Win32 배관 |
| C1 bypass E2E (2턴) | ✅ PASS | `completed=2`, 둘 다 `signal`, `hello.txt`=`PONG\nPONG2`, 고아 0 |
| C2 plan E2E (2턴, 재진입) | ✅ PASS | 둘 다 `approved+signal`, 마커 무드리프트, 승인 후 파일 실증 |
| C3 결함 프로브 (한국어 + 번호목록) | ⚠️ 결함 재현 | 한국어 왕복 클린(`�` 0); 번호목록 턴이 **완료됐는데 `skipped`**(D2 라이브) |
| attach E2E (conhost, --kill) | ✅ PASS | `ATTACH_OK` 파일, 타깃 격리·정리, 고아 0 |

### Phase 4 — 수정 후 재검증

| 테스트 | 판정 | 핵심 증거 |
|--------|------|-----------|
| C1′ bypass 3턴 (번호목록 중간 포함) | ✅ PASS | `completed=3`, **번호목록 턴이 `signal`로 완료**(C3 대비 역전), 런 지속, F7 응답 캡처 동작 |
| C2′ plan 2턴 (재진입) | ✅ PASS | 둘 다 `approved+signal`, `[mode] could not switch` 0건 (F4 무회귀) |
| attach′ (conhost, F8/F11 경로) | ✅ PASS | 마커 기반 타깃 식별, `ATTACH_OK`, exit 0 |
| pytest 단위 스위트 | ✅ 48 pass | 신설 자동화 테스트 전건 통과 |

**주목할 before→after**: C3에서 "1. alpha / 2. beta / 3. gamma"로 답한 턴은 Stop 훅으로 완료(signal_lines 증가)됐음에도 질문 메뉴로 오탐되어 `skipped`, `completed=1`로 기록됐다. C1′에서 동일 프롬프트를 중간에 넣자 이제 `signal`로 완료되고 런이 3턴까지 정상 진행(`completed=3`)됐다.

---

## 2. 결함 대장 (판정 근거 + before→after)

심각도는 **하네스 임베딩 관점**. 판정 근거: [라이브]=실제 세션, [단위]=Claude 무비용 assert, [리뷰]=코드 정독.

| ID | 결함 | 심각도 | 근거 | 수정 (Fix) |
|----|------|--------|------|-----------|
| **D1** | 무TTY(헤드리스)면 `on_stall="skip"`도 무시하고 런 전체 abort | **P0** | [단위][라이브] | **F1**: 정책 우선 판정 — `skip`은 TTY 무관 스킵, `pause`+무TTY만 abort |
| **D2** | 정상 번호목록 응답을 질문 메뉴로 오탐 → 완료 턴이 skipped/abort | **P0** | [라이브] C3 | **F2**: 턴종료 질문가드를 `idle-fallback`(훅 미발화)일 때만 적용 |
| **D3** | `SCRUB_ENV` 불완전 — `CLAUDE_CODE_CHILD_SESSION`/`CLAUDE_PID`/`CLAUDE_EFFORT`/`CLAUDE_CODE_EXECPATH` 누수 | **P0** | [단위] | **F3**: `CLAUDE*` 접두사 전부 스크럽(+auth), `ANTHROPIC_MODEL`은 보존 |
| **D4** | `WORKING_MARKERS`의 헐거운 `"to interrupt"` — 응답 본문이 working 오탐 → shutdown 강제종료 | **P0** | [단위] | **F4**: working/mode 감지를 footer 영역으로 스코프 + 바닥 마커 제거 |
| **D6** | `current_mode`가 위→아래 첫 "to cycle" 라인 채택 → 본문 언급이 실제 footer 무시(실측: bypass인데 'plan' 반환) | P1 | [단위] | **F4**: footer 영역을 아래→위로 탐색 |
| **D5** | CLI가 abort/미완에도 exit 0 → 상위 하네스가 CLI로 실패 감지 불가 | P1 | [리뷰] | **F5**: exit 0=전건완료 / 1=abort·미완 / 2=사용법 |
| **D6′(기능갭)** | 응답 텍스트 캡처 API 부재 → 기획 Q&A 루프 구현 불가 | **P0(갭)** | [리뷰] | **F7**: per-turn `response`/`tools`, `on_turn` 콜백, `poc/transcript.py` |
| **D7** | attach 타깃 new-pid-diff 레이스(25초 창 사용자 세션 오선택 가능) | P1 | [리뷰] | **F11**: 고유 `--session-id` 마커를 CommandLine으로 대조해 양성 식별 |
| **D8** | attach 이모지(아스트랄) 주입 시 ctypes 예외 크래시 | P2 | [단위] | **F12**: UTF-16 서로게이트 페어로 분할 주입 |
| **D9** | 소유 경로 프로세스 트리 미정리(MCP 고아), pty 로그 무제한, write 예외 은폐 | P1 | [리뷰] | **F10**: `taskkill /T`(스폰 자식 한정), 스레드 조인, 로그 상한, write 오류 관측 |
| **D10** | `_check_guard`가 `SystemExit` 발생(라이브러리 부적합) | P2 | [단위] | **F13**: 타입 예외 `AttachGuardError`, CLI만 exit 2로 매핑 |
| **D11** | 문서 드리프트: `run_session` docstring 승인문구 오류, `experiment.py` ESC 주석 모순 | P2 | [리뷰] | **F13**: docstring/주석 정정, dead code(`strip_ansi`) 제거 |
| **D12** | 2.1.215 마커 드리프트 여부 | — | [라이브] | **기각** — bypass/plan/attach 전 경로가 기존 마커로 정상 작동 |

**기각된 후보**: "idle 플리커로 조기 idle-fallback"은 코드상 180초 무출력 게이트(`runner.py`)로 방지됨을 확인 — 오탐으로 기각.

**재검증 중 자가 발견·수정한 회귀**: F11 초기 구현에서 마커로 `uuid4().hex`(하이픈 없는 32자)를 `--session-id`에 넣어 Claude가 형식 거부로 즉시 종료 → 타깃 미검출. Phase 4 attach′에서 포착, 정식 UUID(`str(uuid4())`)로 수정 후 재검증 통과. (Phase 4 재검증 단계가 실제로 회귀를 잡아낸 사례.)

**부수 발견 (긍정)**: 문서는 "PTY 구동 세션은 클린 JSONL transcript를 남기지 않음"이라 했으나, **2.1.215에서는 `~/.claude/projects/**/<sid>.jsonl`이 실제 생성됨**. 이를 F7의 견고한 기반으로 활용(화면 스크랩 대신 JSONL 파싱으로 클린 응답 추출).

---

## 3. 개선 사항 (서브모듈 준비)

- **F7 응답 캡처**: `run_session`/`Runner`가 반환하는 각 turn에 `response`(클린 응답 텍스트)와 `tools`(그 턴에 쓴 툴 이름) 추가. `on_turn(rec)` 콜백으로 턴마다 상위 하네스가 즉시 반응 가능. `poc/transcript.py`의 `find_transcript`/`parse_transcript`/`turn_asks_question`로 JSONL 직접 파싱 지원. **이것이 기획 Q&A 루프의 최소 기반**(`AskUserQuestion`/`ExitPlanMode` 툴 감지 포함).
- **F8 모델/인자 주입**: `run_session(extra_args=[...])`, attach CLI `--claude-arg` — 테스트를 haiku로 강제하는 데 사용. (dash로 시작하는 값은 argparse 특성상 `--claude-arg=--model` `=` 문법 필요.)
- **F9 패키징**: `pyproject.toml`(name=step2step) + `step2step/` 별칭 패키지 — 상위 하네스는 `from step2step import run_session`로 의존 가능(기존 `from poc import ...`도 불변 유지).
- **Phase 3 자동화 테스트 신설**: 기존 테스트 0개 → `tests/`에 pytest 48개(파싱·훅·screen 예측자·stall 정책·env 스크럽·transcript·guard·winconsole·CLI) + 옵트인 라이브 스모크(`-m live`, `STEP2STEP_LIVE=1`). `requirements-dev.txt` 추가.

---

## 4. 하네스 서브모듈 준비도

| 하네스 단계 | 매핑 | 준비도 |
|-------------|------|--------|
| 개발 / 테스트 / 배포 (자동 실행) | bypass 모드 | ✅ **준비됨** (P0 수정 반영 후). 헤드리스에서 `on_stall="skip"` 안전, 번호목록 응답 무해화 |
| 승인 게이트 단계 | plan 모드 | ✅ **준비됨** — 계획 자동승인 + 재진입 검증 완료 |
| 컨셉 → 기획 Q&A (사용자에게 질문하며 구체화) | F7 응답/툴 캡처 | 🟡 **기반 마련** — 응답·질문(`AskUserQuestion`) 감지 가능. 단, 질문에 대한 **답변 재주입 루프**는 상위 하네스가 구현해야 함(자유형 질문 자동 응답은 미구현) |
| 기존 세션 구동 | attach 모드 | 🟡 **실험적** — 단일라인 프롬프트 한정(멀티라인/브래킷페이스트·plan·Ctrl-C 미지원). 마커 기반 타깃 격리로 안전성 강화 |

---

## 5. 안전성 감사 (기존 세션 무영향)

- 모든 라이브 테스트를 **PID diff + CommandLine(세션 uuid) 매칭**으로만 정리. `taskkill /IM claude.exe` 미사용.
- 내 세션(claude PID **16200**)과 사용자의 다른 세션은 시종 보호. 안전가드 `_forbidden_pid`가 자기/조상 세션을 거부함을 [단위]로 선증명.
- 테스트 중 **외부 세션 33996**(사용자 등이 시작, 부모=powershell)이 나타났으나, 내 테스트 서명과 불일치 → **미접촉**. 안전 프로토콜이 의도대로 작동.
- 매 세션 종료 후 고아 스윕 = 공집합. 드라이버 강제중단(C2′ 1회) 시에도 ConPTY 티어다운으로 자식 정리됨(고아 0).
- `git status`에 의도된 변경만 존재(런타임 산출물은 gitignore).

## 6. 잔여 로드맵 (범위 외 — 차기)

- attach 모드: 멀티라인 브래킷 페이스트, plan 모드, Ctrl-C 검증
- 기획 Q&A: 질문 감지 → 답변 생성 → 재주입 루프(상위 하네스 레벨 설계)
- ~~POSIX(리눅스/맥) 지원~~ — (2026-08 완료) spawn 경로는 `ptyprocess`로 이식됨. AttachConsole 기반 attach 모드만 Windows 전용으로 남는다.
- TUI 대폭 변경 시 `python -m poc.calibrate`로 `poc/screen.py` 마커 재튜닝(계약 유지)

## 부록 — Fix ↔ 파일

F1/F2/F7 `poc/runner.py` · F3 `poc/runner.py(child_env)` · F4 `poc/screen.py` · F5 `poc/__main__.py` · F7 `poc/transcript.py`(신규) · F10 `poc/pty_session.py` · F1/F2 `external/attach_runner.py` · F8/F11 `external/target.py`+`attach_runner.py` · F12/F13 `external/winconsole.py` · F13 `external/experiment.py` · F9 `pyproject.toml`+`step2step/`(신규) · 테스트 `tests/`(신규)
