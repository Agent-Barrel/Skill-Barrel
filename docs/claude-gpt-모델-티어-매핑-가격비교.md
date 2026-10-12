# Claude vs GPT 모델 티어 매핑 & 가격 비교

> 기준일: 2026년 10월 7일 (이전 판: 2026년 9월 11일)
> 가격 단위: USD / 1M tokens (표준 요금, Input / Output)
> 성능 근거: Artificial Analysis Intelligence Index v4.3.2 (2026-10-07 조회), Coding Agent Index v1.5 (2026-10-06 수집)
> 블렌디드 단가: AA 방식, 캐시 읽기 : 입력 : 출력 = 7 : 2 : 1 가중 평균
> Index 실행 비용: AA가 Intelligence Index 전체 평가를 한 번 돌리는 데 쓴 비용 (토큰 효율까지 반영된 실비용 지표)

---

## 0. 9/11 판 이후 바뀐 것

| 날짜 | 변경 | 문서에 미친 영향 |
|---|---|---|
| 9/22 | **Claude Opus 5.5** 출시 — $4 / $20, 캐시 읽기 $0.20 (Opus 5 대비 입출력 20%, 캐시 60% 인하) | 플래그십 Claude 교체, AA 1위 (58) |
| 9/22 | **GPT-6 Sol · GPT-6 Luna** 출시 — GPT-5.6 대비 약 절반 가격 ($2 / $10, $0.10 / $0.50) | 경량 GPT 교체 (Luna) |
| 9/28 | **Claude Sonnet 5.5** 출시 — $2 / $10 동결, 출력 30% 이상 빠름 | 중간 Claude 교체, AA 2위 (56) |
| 9/29 | **GPT-6.1 Sol** 출시 (DevDay) — $2 / $10, 캐시 읽기 $0.10 | 플래그십·중간 GPT가 모두 GPT-6.1 Sol로 수렴 |
| — | AA Intelligence Index v4.3 → v4.3.2, Coding Agent Index v1.4 → v1.5 | 모든 점수 재수집 |
| 예고 | Claude Haiku 5.5 "수주 내 합류" (9/22·9/28 발표), 10/7 현재 미출시 | 경량 티어는 아직 Haiku 4.5 |

---

## 1. 요약 매핑 테이블

| 티어 | Claude | GPT | Claude 가격 | GPT 가격 | 우위 (AA v4.3.2, max) |
|---|---|---|---|---|---|
| **프론티어** | Fable 5.1 | GPT-6 Astra | $10 / $50 | $10 / $50 | 동점 (53 vs 53) |
| **플래그십** | Opus 5.5 | GPT-6.1 Sol | $4 / $20 | $2 / $10 | Claude (58 vs 52) |
| **중간** | Sonnet 5.5 | GPT-6.1 Sol | $2 / $10 | $2 / $10 | effort별 역전 (high 이하 GPT, xhigh 이상 Claude) |
| **경량** | Haiku 4.5 | GPT-6 Luna | $1 / $5 | $0.10 / $0.50 | GPT 압승 (17 vs 38) |
| **제한배포 / 사이버** | Mythos 5.1 | GPT-5.6 Cyber | $10 / $50 | $12.50 / $75 | 둘 다 trusted access |

Haiku 4.5는 effort 파라미터를 지원하지 않아 Reasoning 변형 점수를 썼습니다.

### 구조적 대응 관계

- **라인업 단수가 다릅니다.** Anthropic은 4단(Fable / Opus / Sonnet / Haiku), OpenAI GPT-6 세대는 3단(Astra / Sol / Luna)입니다. GPT-6에는 Terra 후속도, $4 / $20 가격대 모델도 없습니다. 그래서 GPT-6.1 Sol 하나가 Opus 5.5와 Sonnet 5.5 양쪽의 대항마가 됩니다.
- **가격 티어와 AA 순위가 어긋납니다.** max 기준 Opus 5.5 (58) > Sonnet 5.5 (56) > Fable 5.1 = Astra (53) > GPT-6.1 Sol (52). Anthropic 공식 가이드도 "대부분의 워크로드는 Opus 5.5로 시작하고, Opus 5.5를 높은 effort로 돌려도 eval이 모자랄 때 Fable 5.1"을 권합니다.
- **Fable 5.1** = 안전장치가 적용된 일반 공개 버전 / **Mythos 5.1** = 동일 모델의 trusted access 버전 (Project Glasswing)
- OpenAI 쪽은 Daybreak 프로그램으로 대응: `gpt-daybreak-blue-latest` → `gpt-5.6-sol`, `gpt-daybreak-red-latest` → `gpt-5.6-cyber`. 10/7 현재 두 별칭 모두 GPT-6 기반 스냅샷이 없습니다.

---

## 2. 티어별 상세

### 2-1. 프론티어 티어 — 여전히 동점, 하지만 더는 AA 1위가 아님

| 항목 | Claude Fable 5.1 | GPT-6 Astra |
|---|---|---|
| Intelligence Index v4.3.2 (max / high) | 53 / 51 | 53 / 51 |
| Coding Agent Index v1.5 (max) | 62.2 | 61.6 |
| Index 실행 비용 (max / high) | $13,129 / $5,242 | **$5,324 / $2,925** |
| Index 출력 토큰 (max / high) | 188M / 62M | **60M / 26M** |
| Input / Output | $10 / $50 | $10 / $50 |
| 캐시 읽기 | **$0.25** (0.025x) | $1.00 (0.1x) |
| 캐시 쓰기 | $12.50 (5분) / $20 (1시간) | $12.50 |
| 블렌디드 단가 | **$7.18** | $7.70 |
| 컨텍스트 / 최대 출력 | 1M / 128K | 1.05M (입력 최대 922K) / 128K |
| 롱컨텍스트 할증 | 없음 | **272K 초과 시 입력·캐시 2x / 출력 1.5x** |
| 출력 속도 (max) | 65 tok/s | 56 tok/s |
| Knowledge cutoff | 2026-06 | 2026-04-30 |
| 출시 | 2026-09-01 | 2026-09-03 |

**핵심 포인트**

- 리스트 가격이 완전히 동일합니다. 차별점은 캐시 요금, 롱컨텍스트 할증, 그리고 토큰 소모량입니다.
- 동점은 max뿐 아니라 high에서도 유지됩니다(51 vs 51). 다만 같은 점수를 내는 데 Fable 5.1은 출력 토큰을 2.4~3.1배 쓰고, Index 실행 비용이 1.8~2.5배입니다.
- AA 기준으로는 Opus 5.5가 high(54)에서 이미 두 모델의 max(53)를 넘습니다. 다만 AA 지수가 장시간 비동기 작업을 충분히 반영하지 못할 수 있습니다. Anthropic은 Fable 5.1을 "ambitious, long-running, asynchronous work"용으로 포지셔닝합니다.
- 벤더 자체 벤치마크는 신뢰하기 어렵습니다. OpenAI 표는 거의 모든 행에서 Astra가 이기고, Anthropic 표는 모든 행에서 Fable 5.1이 이깁니다.
- 지표 버전에 따라 순위가 흔들려 왔습니다: v4.1 (Fable 66 vs Astra 61) → v4.2 (57 vs 55) → v4.3 (53 vs 53) → **v4.3.2 (53 vs 53)**. 인용할 때 반드시 버전과 날짜를 명시해야 합니다.

### 2-2. 플래그십 티어 — Opus 5.5 vs GPT-6.1 Sol (단가 2배 차)

| effort | Intelligence (Opus 5.5 / GPT-6.1 Sol) | Index 실행 비용 (Opus 5.5 / GPT-6.1 Sol) |
|---|---|---|
| low | 42 / 42 | $860 / $250 |
| medium ← 두 모델의 API 기본값 | **51** / 48 | $1,627 / $361 |
| high | **54** / 50 | $2,172 / $521 |
| xhigh | **56** / 51 | $4,057 / $662 |
| max | **58** / 52 | $8,708 / $1,082 |

| 항목 | Claude Opus 5.5 | GPT-6.1 Sol |
|---|---|---|
| Coding Agent Index v1.5 | max 66.0 | max 60.1 (xhigh 62.9) |
| Input / Output | $4 / $20 | $2 / $10 |
| 캐시 읽기 | $0.20 (0.05x) | **$0.10** (0.05x) |
| 캐시 쓰기 | $5 (5분) / $8 (1시간) | $2.50 |
| 블렌디드 단가 | $2.94 | **$1.47** |
| 출력 속도 (max) | **97 tok/s** | 60 tok/s |
| 컨텍스트 / 롱컨텍스트 할증 | 1M / 없음 | 1.05M / 272K 초과 시 2x·1.5x |
| Knowledge cutoff | 2026-06 | 2026-04-30 |
| 출시 | 2026-09-22 | 2026-09-29 |

- Opus 5.5는 Opus 5 대비 입출력 20%, 캐시 읽기 60% 인하($0.50 → $0.20)입니다. Anthropic은 "일반 워크로드에서 Opus 5보다 40% 저렴하고, 출력은 30% 이상 빠르다"고 밝혔습니다.
- **Opus 5.5의 API 기본 effort는 `medium`입니다** (Opus 5는 `high`). 기본값 그대로 쓰면 AA 51로, 이전 판의 Opus 5 (max) 51과 같은 수준입니다.
- 점수는 medium 이상에서 Opus 5.5가 앞서고 low에서는 동점입니다. 비용 곡선은 크게 다릅니다. GPT-6.1 Sol은 effort를 올려도 실행 비용이 $250 → $1,082로 완만하지만, Opus 5.5는 $860 → $8,708로 가파릅니다.
- OpenAI는 GPT-6.1 Sol을 "Astra에 가까운 성능을 Astra 입출력 단가의 1/5에" 제공한다고 소개합니다. AA 기준으로는 max 52 vs Astra 53입니다.
- 이전 판의 비교 대상이던 GPT-5.6 Sol($4 / $20 프로모션가, 최소 2026-11-21까지 유효)은 Opus 5.5와 가격이 같지만 AA 47(v4.3)로 GPT-6.1 Sol보다 낮아, 신규 도입 이유가 약합니다. 다만 Daybreak Blue의 기본 스냅샷은 여전히 이 모델입니다.

### 2-3. 중간 티어 — effort에 따라 순위가 뒤집힘 (여전히)

| effort | Intelligence (Sonnet 5.5 / GPT-6.1 Sol) | Coding Agent (Sonnet 5.5 / GPT-6.1 Sol) | Index 실행 비용 (Sonnet 5.5 / GPT-6.1 Sol) |
|---|---|---|---|
| low | 36 / **42** | 42.1 / **57.2** | $545 / $250 |
| medium ← GPT 기본값 | 41 / **48** | 45.9 / **61.4** | $710 / $361 |
| high ← Claude 기본값 | 47 / **50** | 55.0 / **60.1** | $1,215 / $521 |
| xhigh | **52** / 51 | 62.9 / 62.9 | $2,748 / $662 |
| max | **56** / 52 | **68.4** / 60.1 | $9,074 / $1,082 |

| 항목 | Claude Sonnet 5.5 | GPT-6.1 Sol |
|---|---|---|
| Input / Output | $2 / $10 | $2 / $10 |
| 캐시 읽기 | $0.20 (0.1x) | **$0.10** (0.05x) |
| 블렌디드 단가 | $1.54 | **$1.47** |
| 출력 속도 | **101~125 tok/s** | 48~60 tok/s |
| Fast mode | 미지원 | $4 / $20 |

- 입출력 단가는 같고 캐시 읽기만 GPT-6.1 Sol이 절반입니다.
- high 이하에서는 GPT-6.1 Sol, xhigh부터는 Sonnet 5.5가 앞섭니다. Coding Agent Index도 같은 패턴입니다. GPT-6.1 Sol은 low에서도 57.2로 effort에 둔감하고, Sonnet 5.5는 low 42.1 → max 68.4로 가파릅니다. Claude·GPT 모델 중 **Coding Agent Index 최고점은 Sonnet 5.5 max(68.4)** 로, Opus 5.5 max(66.0)나 Fable 5.1(62.2)보다 높습니다.
- 각자의 기본 effort로 비교하면(Sonnet high 47 vs Sol medium 48) 점수는 비슷하고 Index 실행 비용은 3.4배 차이입니다.
- **Sonnet 5.5 max는 Opus 5.5 max보다 비쌉니다.** Index 출력 토큰이 416M으로 Opus 5.5 max(260M)의 1.6배이고, 실행 비용도 $9,074 vs $8,708입니다. 캐시 읽기 단가도 Opus 5.5와 같은 $0.20입니다. "Sonnet은 항상 Opus의 절반 비용"이라는 가정은 높은 effort에서 깨집니다.
- Sonnet 5.5의 강점은 속도입니다. AA 측정 101~125 tok/s로 GPT-6.1 Sol의 약 2배입니다.
- Sonnet 5.5는 Sonnet 최초로 사이버 safeguard를 적용합니다. 고위험 사이버 작업은 Sonnet 5로 눈에 보이게 폴백됩니다.
- Sonnet 5의 $2/$10은 원래 8월 31일 종료 예정이던 인트로 가격이었으나 **영구 표준가로 확정**되었고, 예정되어 있던 $3/$15 인상은 시행되지 않았습니다. Sonnet 5.5도 같은 가격입니다. ($3/$15로 안내하는 자료는 낡은 정보입니다.)
- GPT-5.6 Terra($2 / $12)와 GPT-6 Sol($2 / $10, 캐시 읽기 $0.20, AA max 48)도 가격표에 남아 있습니다. 다만 같은 입출력가의 GPT-6.1 Sol이 캐시 단가와 점수 모두 우위입니다.

### 2-4. 경량 티어 — Claude의 구멍 (Haiku 5.5 대기 중)

| 항목 | Haiku 4.5 (Reasoning) | GPT-6 Luna (low / max) |
|---|---|---|
| Intelligence Index v4.3.2 | 17 | **22 / 38** |
| Index 실행 비용 | $594 | **$11 / $122** |
| 출력 속도 | 109 tok/s | 133 / 128 tok/s |
| 첫 토큰까지 (TTFT) | 14.5초 | **2.5초** / 106초 |
| Input / Output | $1 / $5 | **$0.10 / $0.50** |
| 캐시 읽기 | $0.10 | $0.01 |
| 블렌디드 단가 | $0.77 | **$0.077** |
| 컨텍스트 | 200K | 1.05M |
| Knowledge cutoff | 2025-02 | 2026-05-18 |

GPT-6 Luna가 GPT-5.6 Luna($0.20 / $1.20)의 절반 이하 가격으로 내려오면서 Haiku 4.5와의 단가 차가 10배가 됐습니다. 가장 낮은 low effort(22)도 Haiku 4.5(17)보다 높고, Index 실행 비용은 1/54입니다. Haiku 4.5는 2025년 10월 스냅샷(`claude-haiku-4-5-20251001`)이라 세대 차이가 그대로 드러납니다. **대량 분류·전처리·라우팅 워크로드에서는 Luna 쪽이 합리적**입니다. 단, Luna max는 첫 토큰까지 100초가 넘으므로 지연에 민감한 경로는 low~medium으로 돌리세요.

Anthropic은 9/22과 9/28 발표에서 "Claude Haiku 5.5가 수주 내 합류한다"고 예고했지만, 10/7 현재 가격표에는 없습니다. Haiku 4.5에 대한 Anthropic의 유지 약속은 "2026-10-15 이전에는 퇴역하지 않음"까지입니다. Haiku 5.5가 나오면 이 티어를 다시 비교해야 합니다.

### 2-5. 제한배포 / 사이버 티어

| 항목 | Claude Mythos 5.1 | GPT-5.6 Cyber |
|---|---|---|
| 접근 | Project Glasswing 승인 조직 | Daybreak Red 승인 (`gpt-daybreak-red-latest`) |
| 가격 | $10 / $50 (캐시 읽기 $0.25) | $12.50 / $75 (캐시 읽기 $1.25) |
| 컨텍스트 | 1M | 400K (입력 최대 272K) |
| 기반 | Fable 5.1과 동일 모델 | GPT-5.6 Sol 기반 |

GPT-6 기반 사이버 모델은 9월 말 DevDay 공개설이 보도됐지만, 10/7 현재 OpenAI 가격표와 Daybreak 별칭에는 `gpt-5.6-cyber`만 있습니다.

---

## 3. 스티커 가격에 나타나지 않는 비용 요인

가격표만 비교하면 실제 청구서와 어긋납니다. 아래 4가지가 훨씬 큰 영향을 줍니다.

### 3-1. 토큰 효율 (가장 큰 반전)

| 모델 (max) | AA 점수 | Index 출력 토큰 | Index 실행 비용 |
|---|---|---|---|
| Claude Opus 5.5 | 58 | 260M | $8,708 |
| Claude Sonnet 5.5 | 56 | 416M | $9,074 |
| Claude Fable 5.1 | 53 | 188M | $13,129 |
| GPT-6 Astra | 53 | 60M | $5,324 |
| GPT-6.1 Sol | 52 | 67M | $1,082 |
| GPT-6 Luna | 38 | 144M | $122 |
| Claude Haiku 4.5 (Reasoning) | 17 | 78M | $594 |

- OpenAI 모델은 같은 점수를 훨씬 적은 출력 토큰으로 냅니다. **Astra는 Fable 5.1과 같은 점수를 실행 비용 약 41%로 달성**합니다. GPT-6.1 Sol은 Opus 5.5보다 6점 낮지만 비용은 1/8입니다.
- Claude 5.5 모델은 effort를 올릴수록 토큰이 비선형으로 늘어납니다. Opus 5.5는 high → max에서 출력 토큰이 4.9배(53M → 260M) 늘고 점수는 4점 오릅니다. 비용 대비 효율 구간은 high 이하입니다.
- Claude 안에서도 역전이 있습니다. Opus 5.5 high(54점, $2,172)는 Fable 5.1 max(53점, $13,129)보다 점수가 높고 비용은 1/6입니다.

### 3-2. 토크나이저 차이

Claude 4.7 이후 모델(Fable 5.1, Opus 5.5, Sonnet 5.5 포함)은 **동일한 텍스트에 대해 약 30% 더 많은 토큰을 생성**합니다. Haiku 4.5는 이전 토크나이저를 씁니다. 즉 Claude 쪽 스티커 가격은 실제보다 싸 보입니다. 마이그레이션 시 반드시 실제 토큰 카운트를 재측정하세요.

### 3-3. 캐시 경제학 (에이전트 워크로드의 핵심)

| 모델 | 캐시 읽기 | 입력가 대비 |
|---|---|---|
| Fable 5.1 / Mythos 5.1 | $0.25 | 0.025x |
| Opus 5.5 | $0.20 | 0.05x |
| Sonnet 5.5 | $0.20 | 0.1x |
| Haiku 4.5 | $0.10 | 0.1x |
| GPT-6 Astra | $1.00 | 0.1x |
| GPT-6.1 Sol | $0.10 | 0.05x |
| GPT-6 Luna | $0.01 | 0.1x |

- Fable 5.1 캐시 읽기는 Fable 5 대비 75% 인하입니다. Anthropic 추산으로 일반 워크로드는 약 25%, 고도 에이전트 워크로드는 최대 약 45% 절감됩니다.
- Opus 5.5 캐시 읽기는 Opus 5 대비 60% 인하이고, **Sonnet 5.5와 같은 $0.20**입니다. 캐시 읽기 비중이 큰 에이전트 루프에서는 Opus와 Sonnet의 비용 차가 생각보다 작아집니다.
- Astra 캐시 읽기는 Fable 5.1의 4배입니다. 반대로 GPT-6.1 Sol 캐시 읽기는 Opus 5.5·Sonnet 5.5의 절반입니다. 시스템 프롬프트나 레포 컨텍스트를 반복 재사용하는 구조라면 이 차이가 복리로 누적됩니다.

### 3-4. 롱컨텍스트 할증

- **OpenAI (GPT-6 / GPT-5.6 전 라인)**: 272K 입력 토큰 초과 시 요청 전체에 입력·캐시 읽기·캐시 쓰기 2배, 출력 1.5배를 적용합니다. 최대 입력은 922K입니다.
- **Claude**: 4.6 이후 1M 컨텍스트까지 할증이 없습니다. 900K 요청과 9K 요청이 동일 단가입니다. 단, Haiku 4.5는 컨텍스트 자체가 200K입니다.

---

## 4. 할인 옵션 비교

| 옵션 | Claude | GPT |
|---|---|---|
| Batch API | 입출력 50% 할인 | Batch / Flex 모두 표준가의 50% |
| 고속 모드 | Fast mode = 표준가의 2배 (Opus 5.5 $8 / $40, Opus 5·4.8 $10 / $50). research preview, Claude API 전용, Batch와 병행 불가. Fable·Sonnet·Haiku 미지원 | Fast mode = 표준가의 2배 (Astra $20 / $100, GPT-6.1 Sol $4 / $20, Luna $0.20 / $1.00). 2026-07-30 Priority에서 이름 변경 |
| 캐시 읽기 | 입력가의 0.1x (Fable 5.1·Mythos 5.1 0.025x, Opus 5.5 0.05x) | 입력가의 0.1x (GPT-6.1 Sol 0.05x) |
| 캐시 쓰기 | 5분 1.25x / 1시간 2x | 1.25x |
| 리전 처리 | US 전용 추론(`inference_geo: "us"`) 1.1x. Claude 4.6 이후 전 모델, 캐시 포함 전 항목 | 데이터 레지던시 엔드포인트 10% 할증 (2026-03-05 이후 출시 모델) |

---

## 5. 실무 선택 가이드

| 상황 | 권장 | 이유 |
|---|---|---|
| 신규 워크로드 기본값 | **Opus 5.5 (medium)** 또는 **GPT-6.1 Sol (medium)** | 두 모델의 API 기본 effort. AA 51 vs 48, 실행 비용 $1,627 vs $361 |
| 단발성 추론, 토큰당 비용 민감 | **GPT-6.1 Sol** | 점수 대비 실행 비용 최저 (max 52점에 $1,082) |
| 어려운 추론·지식 작업 | **Opus 5.5 (high~max)** | AA 1위 (58). high(54)도 Fable·Astra의 max보다 높음 |
| 장시간 비동기 에이전트, Opus 5.5 상위 effort로도 eval 미달 | **Fable 5.1** | Anthropic 공식 권장 순서. 캐시 읽기 $0.25가 복리로 작용 |
| 코딩 에이전트 최고 점수 | **Sonnet 5.5 (max) + Claude Code** | Coding Agent Index 68.4. 단 토큰 소모가 가장 큼 |
| 응답 속도 우선 | **Sonnet 5.5** | 101~125 tok/s |
| 272K 초과 롱컨텍스트 상시 사용 | **Claude (Opus 5.5 / Sonnet 5.5 / Fable 5.1)** | 할증 없음 |
| 대량 분류 / 전처리 / 라우팅 | **GPT-6 Luna (low~medium)** | Haiku 4.5 대비 단가 1/10, low에서도 점수·TTFT 우위 |
| 비동기 배치 작업 | 양쪽 모두 Batch API | 50% 할인 |

### 라우팅 권장 패턴

```
일상 작업          → Opus 5.5 medium (또는 GPT-6.1 Sol medium)
속도 우선 작업     → Sonnet 5.5 (high 이하)
난이도 상승        → Opus 5.5 high~max (또는 GPT-6.1 Sol xhigh)
실패 루프 비용이   → Fable 5.1 / Astra
토큰 단가보다 클 때
대량 단순 작업     → GPT-6 Luna
```

---

## 6. 주의사항

1. **effort 레벨이 티어보다 체감 성능에 더 큰 영향을 줍니다.** Sonnet 5.5는 low 36 → max 56, Opus 5.5는 42 → 58입니다. 기본 effort도 모델마다 다릅니다: Opus 5.5·GPT-6.1 Sol·Luna는 `medium`, Fable 5.1·Sonnet 5.5는 `high`. OpenAI는 `reasoning.effort`(low / medium / high / xhigh / max, Luna는 none 추가), Claude는 `output_config.effort`(low ~ max)로 조절합니다. 벤치 점수 비교 시 effort가 정렬되어 있는지 반드시 확인하세요.

2. **하네스 차이를 모델 차이로 오인하지 마세요.** Coding Agent Index에서 GPT 모델은 Codex, Claude 모델은 Claude Code에서 측정됩니다. 점수 차의 일부는 스캐폴딩 몫입니다.

3. **AA의 Claude 5.x 점수는 폴백을 켠 상태의 측정입니다** (표기 "Default Fallback"). 거절 시 다른 모델이 이어받는 구성이므로, 폴백을 끄거나 폴백이 없는 환경에서 쓰면 점수와 비용이 달라질 수 있습니다.

4. **벤더 자체 벤치마크는 서로 다른 하네스·태스크 릴리스에서 측정됩니다.** 같은 벤치마크 이름이 같은 측정을 의미하지 않습니다. 예: Terminal-Bench 4.0에서 Opus 5.5는 Anthropic 발표 66.4%, AA 측정 약 60%입니다.

5. **가격과 모델 라인업은 빠르게 변합니다.** 예정된 변수: GPT-5.6 Sol 프로모션가(최소 2026-11-21까지), Claude Haiku 5.5 출시, GPT-6 기반 사이버 모델. 프로덕션 트래픽을 이전하기 전에 공식 문서에서 현재 요금을 재확인하세요.

6. **최종 판단은 자체 eval로.** 위 수치는 후보를 좁히는 용도이며, 실제 워크로드 성능을 대체하지 않습니다. Index 실행 비용도 AA 태스크 구성에서의 값일 뿐 실제 청구액이 아닙니다.

---

## 7. 출처

**공식 가격·모델 문서**

- OpenAI API Pricing — https://developers.openai.com/api/docs/pricing
- GPT-6 Astra 모델 페이지 — https://developers.openai.com/api/docs/models/gpt-6-astra
- GPT-6.1 Sol 모델 페이지 — https://developers.openai.com/api/docs/models/gpt-6.1-sol
- GPT-6 Luna 모델 페이지 — https://developers.openai.com/api/docs/models/gpt-6-luna
- Daybreak Blue / Red — https://developers.openai.com/api/docs/models/gpt-daybreak-blue-latest , https://developers.openai.com/api/docs/models/gpt-daybreak-red-latest
- Claude Platform 가격 문서 — https://platform.claude.com/docs/en/about-claude/pricing
- Claude 모델 개요 — https://platform.claude.com/docs/en/about-claude/models/overview
- Claude Fable — https://www.anthropic.com/claude/fable

**공식 발표**

- Claude Opus 5.5 — https://www.anthropic.com/news/claude-opus-5-5
- Claude Sonnet 5.5 — https://www.anthropic.com/claude-sonnet-5-5
- GPT-6 Sol and Luna (GPT-6.1 Sol 업데이트 포함) — https://openai.com/index/introducing-gpt-6-sol-and-luna/
- GPT-6 Astra — https://openai.com/index/gpt-6-astra/
- GPT-6 Astra System Card — https://deploymentsafety.openai.com/gpt-6-astra

**독립 벤치마크**

- Artificial Analysis: GPT-6 Astra 벤치마킹 (v4.1·v4.2 시절 수치) — https://artificialanalysis.ai/articles/benchmarking-gpt-6-astra
- Astra vs Fable 5.1 (max / high) — https://artificialanalysis.ai/models/comparisons/gpt-6-astra-vs-claude-fable-5-1 , https://artificialanalysis.ai/models/comparisons/gpt-6-astra-high-vs-claude-fable-5-1-high
- Opus 5.5 vs GPT-6.1 Sol — https://artificialanalysis.ai/models/comparisons/claude-opus-5-5-vs-gpt-6-1-sol (effort별 페이지는 두 모델 slug 뒤에 `-low` / `-medium` / `-high` / `-xhigh`)
- Sonnet 5.5 vs GPT-6.1 Sol — https://artificialanalysis.ai/models/comparisons/claude-sonnet-5-5-vs-gpt-6-1-sol (effort별 페이지 규칙 동일)
- GPT-6 Luna vs Haiku 4.5 — https://artificialanalysis.ai/models/comparisons/gpt-6-luna-vs-claude-4-5-haiku-reasoning , https://artificialanalysis.ai/models/comparisons/gpt-6-luna-low-vs-claude-4-5-haiku-reasoning
- GPT-6 Luna vs GPT-6 Sol — https://artificialanalysis.ai/models/comparisons/gpt-6-luna-vs-gpt-6-sol
- Coding Agent Index v1.5 — https://artificialanalysis.ai/agents/coding-agents (AA 페이지가 수치를 스크립트로 렌더링해, 수치는 benchlm.ai의 2026-10-06 수집본 https://benchlm.ai/benchmarks/aaCodingAgents 에서 인용)
