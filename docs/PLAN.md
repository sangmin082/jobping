# 잡핑 (JobPing) — 실행 계획 v2

> 대기업 자체 채용 페이지를 주기 체크해서, 사용자가 등록한 키워드에 맞는 **새 경력직 공고**가 뜨면 푸시로 알리는 iOS 유틸리티.
> 플랫폼(사람인/원티드 등)은 소스로 쓰지 않는다. 회사 공식 채용 페이지만 쓴다.

이 문서가 계획의 단일 출처(source of truth)다. 단계가 끝날 때마다 여기를 갱신한다.

---

## 0. v1 계획에서 바뀐 것 (요약)

| # | v1 | v2 | 이유 |
|---|---|---|---|
| 1 | 어댑터가 채용 페이지 HTML을 파싱 | **JSON API 우선, HTML은 최후수단** | 삼성·SK하이닉스·테슬라 전부 SPA거나 JSON API 기반. HTML엔 공고가 없음 |
| 2 | 앱이 공고 리스트를 보여줌 | **읽기 API(API Gateway) 추가** | v1엔 앱이 데이터를 받아올 경로가 아예 없었음 |
| 3 | `device_token`으로 사용자 식별 | **`install_id`(Keychain UUID)로 식별, 토큰은 속성** | APNs 토큰은 재설치·복원·갱신 때 바뀜. 토큰이 PK면 구독 권한이 날아감 |
| 4 | jobs 테이블 PK=company, SK=job_id | **+ LSI(first_seen_at) + TTL** | 원안으론 "최신순 리스트" 쿼리가 불가능 |
| 5 | 신규 판정 = 처음 본 job_id | **URL 정규화 후 해시 + source_id 우선** | 트래킹 파라미터 하나 붙으면 같은 공고가 매번 신규로 잡혀 오알림 폭탄 |
| 6 | 결과 0건이면 Slack 알림 | **연속 N회 0건 / 직전 대비 급감일 때 알림** | 새벽·주말엔 진짜 0건이라 오탐이 계속 뜸 |
| 7 | Lambda 1개가 수집+매칭+푸시 | **collector → SQS → notifier 분리** | 어댑터 하나가 타임아웃 나면 그날 푸시 전체가 죽음 |
| 8 | 무료 제한을 앱에서 체크 | **서버에서 권한 판정** | 클라 게이팅은 우회 가능. 푸시 발송량 결정 주체가 서버라 어차피 서버가 알아야 함 |
| 9 | 회사별 어댑터만 | **+ ATS 공용 어댑터(Workday 등)** | 어댑터 1개로 여러 회사 커버. 확장 비용이 회사당 O(1)에서 거의 0으로 |
| 10 | (없음) | **앱스토어 심사 리스크 대응** | 4.2(최소기능)·5.2(상표) 리젝 위험이 실제로 있음. 설계 단계에서 반영 |

---

## 1. 아키텍처

```
EventBridge (30분)
      │
      ▼
 collector Lambda ── 어댑터별 개별 try/except + 타임아웃 ──► 각 회사 채용 API
      │                                                    (Samsung, SK hynix, Tesla, …)
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
| PK `company` | `samsung` |
| SK `job_id` | `sha1(company + source_id)[:16]` — 없으면 정규화 URL+제목 해시 |
| `first_seen_at` | ISO8601. **"신규" 판정의 기준은 이것** |
| `posted_at` | 사이트가 주면 저장, 없으면 null (테슬라는 안 줌) |
| `title`, `url`, `location`, `department`, `employment_type` | |
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
GET  /v1/jobs?companies=samsung,tesla&since=<iso>&limit=50
GET  /v1/companies         지원 회사 목록 + 각 어댑터 헬스
POST /v1/purchases/validate  signed transaction JWS → tier 갱신
POST /v1/appstore/notifications  (Apple → 우리, 갱신/해지/환불)
```

인증: 로그인이 없으므로 `install_id` + 앱 발급 서명 헤더. 남용 방지는 API Gateway throttling + install_id별 쿼터로 충분하다. (돈이 걸린 건 `/purchases/validate`뿐이고 거긴 Apple 서명을 검증하므로 install_id 위조로 얻을 게 없다.)

---

## 2. 수집이 진짜 어려운 지점 (v1이 과소평가한 부분)

조사 결과 대상 3곳이 전부 단순 HTML 파싱으로는 안 된다.

| 회사 | 상태 | 대응 |
|---|---|---|
| 삼성전자 | `samsungcareers.com`은 SPA. HTML 응답에 "job" 문자열 0개 | 브라우저 DevTools에서 XHR 엔드포인트 1회 확정 → `JsonListSpec`에 매핑만 채움 |
| SK하이닉스 | `recruit.skhynix.com` — 동일 구조로 추정 | 동일 |
| 테슬라 | `cua-api/apps/careers/state`는 JSON API가 맞지만 **데이터센터 IP에서 403** (Akamai) | 아래 참조 |

**테슬라 403은 아키텍처 이슈다.** Lambda의 egress IP도 AWS 대역이라 같은 차단에 걸릴 가능성이 높다. 단계적 대응:
1. 브라우저에 준하는 헤더 일습(UA, Accept-Language, Sec-Fetch-*) 부착 — 이걸로 풀리는 경우가 꽤 있음
2. 안 되면 NAT Gateway EIP 고정 후 재시도 (평판 기반 차단이면 개선됨)
3. 그래도 막히면 **테슬라만 별도 경로**로 분리: GitHub Actions 러너나 집 라즈베리파이에서 수집 → 우리 API로 push. 어댑터 인터페이스가 같으므로 실행 위치만 바뀐다
4. 최악의 경우 v1 지원 목록에서 제외

이래서 어댑터는 `verified` 플래그를 갖고, 미검증 어댑터는 앱의 회사 목록에 노출하지 않는다. **"동작하지 않는 회사를 목록에 띄우는 것"이 이 앱의 최악의 실패 모드다** — 사용자는 알림이 안 오는 걸 앱 고장이 아니라 "채용이 없구나"로 오해한다.

### 확장 레버리지: ATS 공용 어댑터
한국 대기업은 자체 시스템이라 개별 어댑터가 불가피하지만, 외국계·계열사·스타트업 상당수는 **Workday / Greenhouse / Lever**를 쓴다. 이 셋은 API가 공개적이고 안정적이라 **어댑터 1개 = 회사 수십 개**다. `_workday.py`를 만들어두면 이후 회사 추가가 설정 한 줄이 된다.

---

## 3. 키워드 매칭 (v1에 정의가 없던 부분)

"제목에 키워드가 포함되면"은 한국어에서 그대로 쓰면 망가진다.

- 정규화: NFKC → 소문자 → 공백/하이픈/점/언더스코어 제거. `Dev Ops`, `DevOps`, `dev-ops`가 같아짐
- 동의어 사전: `인프라 ↔ infra ↔ infrastructure`, `반도체 ↔ semiconductor ↔ 소자`, `백엔드 ↔ backend ↔ 서버`
- 매칭 대상: 제목 + 부서명 (본문은 저장하지 않음 — 4절 참조)
- 제외 키워드 지원: `신입`, `인턴` 제외 (경력직 앱이므로 기본 제외 후보)
- **1회 실행당 디바이스별 푸시 상한 5건.** 넘으면 "새 공고 12건" 묶음 1건으로. 상한 없이 보내면 채용 시즌에 알림 20개가 한 번에 터지고 그날로 알림이 꺼진다

---

## 4. 법무 / 앱스토어 (v1에 없었고, 리젝 사유가 되는 것들)

- **본문 전문 저장·표시 금지.** 제목/URL/게시일/근무지/부서만 저장하고 원문은 `SFSafariViewController`로 원 사이트에서 보게 한다. 이건 원래 계획이 이미 맞게 잡은 부분이고, 유지하는 게 중요하다 (저작권 + 심사 4.5.2)
- **상표.** 앱 아이콘·스크린샷·앱 이름에 삼성/테슬라 등 로고나 워드마크를 쓰면 가이드라인 5.2 리젝. 앱 내 회사 표시는 텍스트만. 앱 설명에 "각 기업과 무관한 비공식 앱" 명시
- **가이드라인 4.2 (최소 기능).** 리스트 + 푸시만 있으면 "웹사이트 래퍼"로 리젝될 수 있다. 대응: 저장(북마크), 알림 히스토리, 키워드별 필터, 공유 — 이 정도는 MVP에 넣는다
- **구독(3.1.2).** 앱 내 구독 관리·복원 버튼, 개인정보처리방침 URL, EULA URL 필수
- **개인정보처리방침.** 푸시 토큰 수집을 명시. 그 외 개인정보는 수집하지 않는다고 쓸 수 있게 설계돼 있음 (로그인 없음)
- **크롤링 예의.** `robots.txt` 확인, 30분 주기 유지, User-Agent에 연락처 URL 명시. 회사가 차단 요청하면 즉시 제거

---

## 5. 운영 / 비용

- 8개사 × 48회/일 ≈ **384 요청/일**. Lambda·DynamoDB·SQS 프리티어 안. 예상 월 $1–3 (대부분 Secrets Manager $0.40 + CloudWatch)
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
| 2 | 어댑터 3개 + 로컬 검증 스크립트 + 오프라인 테스트 | ✅ 코드 완료 / 실엔드포인트 확정은 로컬에서 |
| **2.5** | **삼성·SK하이닉스 XHR 엔드포인트 확정** (`docs/ADAPTER-GUIDE.md`, 회사당 ~5분) | ⏳ **당신 차례** |
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
