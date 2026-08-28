# 잡핑 (JobPing) — 실행 계획 v2

> 대기업 자체 채용 페이지를 주기 체크해서, 사용자가 등록한 키워드에 맞는 **새 경력직 공고**가 뜨면 푸시로 알리는 iOS 유틸리티.
> 플랫폼(사람인/원티드 등)은 소스로 쓰지 않는다. 회사 공식 채용 페이지만 쓴다.

이 문서가 계획의 단일 출처(source of truth)다. 단계가 끝날 때마다 여기를 갱신한다.

---

## 0. v1 계획에서 바뀐 것 (요약)

| # | v1 | v2 | 이유 |
|---|---|---|---|
| 1 | 어댑터가 채용 페이지 HTML을 파싱 | **브라우저가 부르는 XHR을 직접 호출** | 세 곳 다 SPA. HTML엔 공고가 없음 |
| 2 | 앱이 공고 리스트를 보여줌 | **읽기 API(API Gateway) 추가** | v1엔 앱이 데이터를 받아올 경로가 아예 없었음 |
| 3 | `device_token`으로 사용자 식별 | **`install_id`(Keychain UUID)로 식별, 토큰은 속성** | APNs 토큰은 재설치·복원·갱신 때 바뀜. 토큰이 PK면 구독 권한이 날아감 |
| 4 | jobs 테이블 PK=company, SK=job_id | **+ LSI(first_seen_at) + TTL** | 원안으론 "최신순 리스트" 쿼리가 불가능 |
| 5 | 신규 판정 = 처음 본 job_id | **URL 정규화 후 해시 + source_id 우선** | 트래킹 파라미터 하나 붙으면 같은 공고가 매번 신규로 잡혀 오알림 폭탄 |
| 6 | 결과 0건이면 Slack 알림 | **연속 N회 0건 / 직전 대비 급감일 때 알림** | 새벽·주말엔 진짜 0건이라 오탐이 계속 뜸 |
| 7 | Lambda 1개가 수집+매칭+푸시 | **collector → SQS → notifier 분리** | 어댑터 하나가 타임아웃 나면 그날 푸시 전체가 죽음 |
| 8 | 무료 제한을 앱에서 체크 | **서버에서 권한 판정** | 클라 게이팅은 우회 가능. 푸시 발송량 결정 주체가 서버라 어차피 서버가 알아야 함 |
| 9 | 회사별 어댑터 | **소스 1개 = 계열사 N곳** | 삼성·SK는 그룹 통합 포털이다. `Job.company`는 그룹이 아니라 계열사여야 한다 — 반도체 지망생에게 삼성생명 공고를 보낼 순 없다 |
| 10 | `recruit.skhynix.com`을 SK 소스로 | **`skcareers.com` 그룹 포털** | SK하이닉스 단독 사이트가 아니라 여기에 27개사가 다 있다 |
| 11 | 테슬라 본사 `cua-api` | **MokaHR 테슬라 코리아** | 본사 API는 데이터센터 IP에 403. MokaHR은 차단이 없고 한국 공고만 주며 게시일까지 준다 |
| 12 | 공고 = 제목 하나 | **`roles`(세부 직무) 추가** | 삼성 공고 1건에 세부 직무가 10여 개. 사용자 키워드는 제목이 아니라 거기 있다 |
| 13 | (없음) | **앱스토어 심사 리스크 대응** | 4.2(최소기능)·5.2(상표) 리젝 위험이 실제로 있음. 설계 단계에서 반영 |

---

## 1. 아키텍처

```
EventBridge (30분)
      │
      ▼
 collector Lambda ── 소스별 개별 try/except + 타임아웃 ──► 각 그룹 채용 포털
      │                                              (samsung / skcareers / tesla_kr …)
      │  신규 공고만 (조건부 PutItem)
      ▼
 DynamoDB: jobs ──────────────┐
      │                       │
      │ 신규 job_id            │  GET /v1/jobs
      ▼                       ▼
    SQS ──► notifier Lambda   api Lambda ◄── HTTP API ◄── iOS 앱
              │                    ▲
              │ APNs (HTTP/2, .p8) │ POST /v1/devices
              ▼                    │ POST /v1/purchases/validate
          Apple Push          DynamoDB: devices
                                   ▲
                       App Store Server Notifications V2
                              │
                       webhook Lambda
```

**collector를 회사별로 쪼개지 않고 한 Lambda 안에서 스레드풀로 도는 이유**: 회사가 10개 이하고 각 fetch가 수 초라, Lambda를 N개로 늘리면 배포/관측 비용만 늘고 얻는 게 없다. 격리는 어댑터별 `try/except` + per-adapter 타임아웃으로 충분하다. 회사가 30개를 넘거나 fetch가 30초를 넘기 시작하면 그때 SQS 팬아웃으로 쪼갠다.

### 데이터 모델

**`jobs`**
| 속성 | 값 |
|---|---|
| PK `company` | **계열사** 키 — `samsung_ds`, `sk_hynix`, `tesla_kr` (그룹이 아니다) |
| SK `job_id` | `sha1(company + source_id)[:16]` — 없으면 `identity_url`+제목 해시 |
| `first_seen_at` | ISO8601. **"신규" 판정의 기준은 이것** |
| `posted_at` | 소스가 주면 저장, 없으면 null (삼성·테슬라는 줌, SK는 안 줌) |
| `title`, `url`, `location`, `department`, `employment_type` | |
| `roles[]` | 세부 직무. 매칭 품질의 대부분이 여기서 나온다 (3절) |
| `expires_at` | TTL. first_seen + 90일 |
| LSI `by_first_seen` | PK=`company`, SK=`first_seen_at` → 회사별 최신순 리스트 |

신규 판정은 `PutItem` + `ConditionExpression: attribute_not_exists(job_id)`. 성공 = 신규. 별도 조회 라운드트립이 없다.

**`devices`**
| 속성 | 값 |
|---|---|
| PK `install_id` | 앱이 Keychain에 저장하는 UUID (재설치해도 유지) |
| `device_token` | APNs 토큰. **바뀔 수 있는 값** |
| `keywords[]`, `companies[]`, `push_enabled` | |
| `tier` | `free` \| `pro` |
| `original_transaction_id`, `expires_at_ms` | StoreKit2 검증 결과 |
| `quiet_hours` | 기본 23:00–08:00 KST |

**`deliveries`** — PK=`install_id`, SK=`job_id`, TTL 7일. 재시도 시 중복 푸시 방지.

**`adapter_health`** — PK=`adapter`, 마지막 성공 시각·건수·연속 실패 횟수. 알림 판정에 씀.

### API (앱 계약)

```
POST /v1/devices           install_id, device_token, keywords[], companies[], push_enabled
GET  /v1/jobs?companies=samsung_ds,tesla_kr&since=<iso>&limit=50
GET  /v1/companies         구독 가능한 계열사 목록 (registry.app_companies())
POST /v1/purchases/validate  signed transaction JWS → tier 갱신
POST /v1/appstore/notifications  (Apple → 우리, 갱신/해지/환불)
```

인증: 로그인이 없으므로 `install_id` + 앱 발급 서명 헤더. 남용 방지는 API Gateway throttling + install_id별 쿼터로 충분하다. (돈이 걸린 건 `/purchases/validate`뿐이고 거긴 Apple 서명을 검증하므로 install_id 위조로 얻을 게 없다.)

---

## 2. 수집 소스 (확정)

세 소스 모두 실제 응답으로 검증했다. `2026-08-28` 기준 **삼성 16건 + SK 96건 +
테슬라 65건 = 177건**이 흐른다.

| 소스 | 엔드포인트 | 형식 | 계열사 |
|---|---|---|---|
| `samsung` | `POST samsungcareers.com/hr/list.data` | HTML 조각 | 26곳 |
| `skcareers` | `POST skcareers.com/Recruit/GetRecruitList` | JSON | 27곳 |
| `tesla_kr` | `POST hire-r1.mokahr.com/api/outer/ats-apply/website/jobs/v2` | JSON | 1곳 |

셋 다 파라미터 하나만 틀려도 **에러가 아닌 응답**을 돌려준다(삼성 500, SK
404 HTML, MokaHR 302 루프). 발굴 절차와 함정은 `docs/ADAPTER-GUIDE.md`에 있다.

### 소스별로 확인된 사실

**삼성** — `strType=B`로 **서버가 경력만 걸러준다.** `strCompany`로 계열사
필터도 된다. 다만 지금 이 포털에 올라온 경력 공고는 **전체 16건이고 전부
"외국인 경력사원 채용"**이다(신입 0건, 인턴 0건). 삼성전자의 일반 국내 경력
채용이 이 포털에 안 올라온다는 뜻이고, **이건 제품 가치에 직결되는 문제다.**
1순위로 확인할 것: 삼성전자 경력 공고가 실제로 어디에 게시되는가.

**SK** — `recruit.skhynix.com`이 아니라 그룹 포털이 소스다. SK하이닉스 포함
27개사, 경력 96건. 페이지네이션이 없고 한 번에 전부 준다.

**테슬라** — 본사 API(`www.tesla.com/cua-api/...`)는 데이터센터 IP에 403을
주지만, 테슬라 코리아는 MokaHR을 쓰고 여기는 차단이 없다. **게시일(`openedAt`)
까지 주는 유일한 소스**다. MokaHR은 여러 회사가 쓰는 ATS라 `MokaHRAdapter`를
상속해 `org_id`/`site_id`만 바꾸면 새 회사가 붙는다.

### 로케일 함정 (설계에 반영됨)

SK의 `recruitType`은 요청 언어에 따라 `"Experienced"` 또는 `"경력"`으로 온다.
영어 기준으로 필터를 짜고 한국어로 요청하면 **필터가 전부 걸러내 0건이 되는데
예외가 나지 않는다.** 사용자에게는 "채용이 없구나"로 보이고 앱이 고장난 걸
아무도 모른다. 실제로 한 번 겪었다.

그래서 두 가지를 규칙으로 박았다: 로케일 의존 값은 모든 표기를 등록하고,
**모르는 값이 오면 예외를 던진다.** 회사명도 같은 이유로 한/영 둘 다 등록한다.

같은 원칙에서 어댑터는 `verified` 플래그를 갖고, 미검증 소스의 회사는 앱
목록에 노출하지 않는다. **동작하지 않는 회사를 목록에 띄우는 것이 이 앱의
최악의 실패 모드다.**

### 다음 확장

현대차·기아·LG·네이버·카카오는 스켈레톤만 있다(`adapters/skeletons.py`에 각
회사에 대해 알아낸 것을 메모해뒀다). 한국 대기업은 대부분 그룹 통합 포털이라
소스 하나가 계열사 수십 곳을 커버한다 — 회사 수보다 소스 수가 훨씬 적다.

---

## 3. 키워드 매칭 (v1에 정의가 없던 부분)

"제목에 키워드가 포함되면"은 한국어에서 그대로 쓰면 망가진다.

- 정규화: NFKC → 소문자 → 공백/하이픈/점/언더스코어 제거. `Dev Ops`, `DevOps`, `dev-ops`가 같아짐
- 동의어 사전: `인프라 ↔ infra ↔ infrastructure`, `반도체 ↔ semiconductor ↔ 소자`, `백엔드 ↔ backend ↔ 서버`
- 매칭 대상: 제목 + 부서명 + **세부 직무(`roles`)**. 본문은 저장하지 않는다(4절)
  - `roles`가 매칭의 대부분을 만든다. 삼성 공고 제목은 "R&D분야 경력사원
    채용(DX부문)"처럼 뭉뚱그려져 있고, "데이터 엔지니어링"은 그 안에 묶인
    직무 태그에만 있다. 실제 데이터로 확인: 제목만 보면 0건, `roles`까지 보면 1건
- 제외 키워드 지원: `신입`, `인턴` 제외 (경력직 앱이므로 기본 제외 후보)
- **1회 실행당 디바이스별 푸시 상한 5건.** 넘으면 "새 공고 12건" 묶음 1건으로. 상한 없이 보내면 채용 시즌에 알림 20개가 한 번에 터지고 그날로 알림이 꺼진다

---

## 4. 법무 / 앱스토어 (v1에 없었고, 리젝 사유가 되는 것들)

- **본문 전문 저장·표시 금지.** 제목/URL/게시일/근무지/부서/직무명만 저장하고 원문은 `SFSafariViewController`로 원 사이트에서 보게 한다. 이건 원래 계획이 이미 맞게 잡은 부분이고, 유지하는 게 중요하다 (저작권 + 심사 4.5.2)
- **상표.** 앱 아이콘·스크린샷·앱 이름에 삼성/테슬라 등 로고나 워드마크를 쓰면 가이드라인 5.2 리젝. 앱 내 회사 표시는 텍스트만. 앱 설명에 "각 기업과 무관한 비공식 앱" 명시
- **가이드라인 4.2 (최소 기능).** 리스트 + 푸시만 있으면 "웹사이트 래퍼"로 리젝될 수 있다. 대응: 저장(북마크), 알림 히스토리, 키워드별 필터, 공유 — 이 정도는 MVP에 넣는다
- **구독(3.1.2).** 앱 내 구독 관리·복원 버튼, 개인정보처리방침 URL, EULA URL 필수
- **개인정보처리방침.** 푸시 토큰 수집을 명시. 그 외 개인정보는 수집하지 않는다고 쓸 수 있게 설계돼 있음 (로그인 없음)
- **크롤링 예의.** `robots.txt` 확인, 30분 주기 유지, User-Agent에 연락처 URL 명시. 회사가 차단 요청하면 즉시 제거

---

## 5. 운영 / 비용

- 소스 3개 × 48회/일 + 페이지네이션 ≈ **300~400 요청/일**. Lambda·DynamoDB·SQS 프리티어 안. 예상 월 $1–3 (대부분 Secrets Manager $0.40 + CloudWatch)
- 어댑터별 CloudWatch 지표: `fetched`, `new`, `duration_ms`, `error`
- Slack 알림 조건 (v1의 "0건이면 알림"을 교체):
  - 어댑터 예외 → 즉시
  - **연속 3회** 0건 → 알림 (새벽 오탐 방지)
  - 스키마 검증 실패(필드 누락/타입 불일치) → 즉시. HTML/API 구조 변경 조기 감지
- APNs 410 Unregistered → `devices`에서 삭제

---

## 6. 단계별 진행

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 레포 구조 (`backend/`, `ios/`, `docs/`) | ✅ 완료 |
| 2 | 어댑터 3개 + 로컬 검증 스크립트 + 오프라인 테스트 | ✅ 완료 — 라이브 177건 수집 확인 |
| **2.5** | **삼성전자 국내 경력 공고가 어디 올라오는지 확인** | ⏳ 2절 참고 |
| 3 | SAM 템플릿: DynamoDB + collector + notifier + APNs | |
| **3.5** | **읽기 API + OpenAPI 계약** (v2에서 추가) | |
| 4 | iOS MVP: 온보딩 → 리스트 → 푸시 수신 | |
| 5 | StoreKit 2 구독 + 서버 검증 + App Store Server Notifications | |

### 순서에 대한 제안
StoreKit(5단계)은 **사용자가 붙고 나서** 하는 걸 권한다. 구독 서버 검증 + Apple 웹훅은 체감상 3~4단계를 합친 것만큼 일이 큰데, 알림 품질이 검증되기 전에는 아무도 결제하지 않는다. 4단계까지 만들어서 본인이 2주 써보고 "푸시가 실제로 쓸모 있다"가 확인된 다음에 5단계로 가는 게 낫다. (물론 이건 제안이고, 순서는 그대로 가도 된다.)

---

## 7. iOS 앱 (4단계 상세 예정)

- SwiftUI, iOS 17+, `@Observable`, async/await `URLSession`
- `install_id`: Keychain (`kSecAttrAccessibleAfterFirstUnlock`) — 재설치 후에도 유지
- 푸시 권한: 온보딩 **마지막**에, "왜 필요한지" 화면을 한 번 보여준 뒤 요청 (선요청하면 거부율이 크게 오름)
- 캐시: 서버가 원본. 로컬은 오프라인 표시용 JSON 캐시면 충분 (SwiftData는 과함)
- 공고 열기: `SFSafariViewController` (`UIViewControllerRepresentable`)
- 푸시 페이로드에 `job_id` → 탭 시 해당 공고로 딥링크
