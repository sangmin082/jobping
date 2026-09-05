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

**신규 = 알림이 아니다.** 세 가지를 거쳐야 알림 대상이 된다 (`collector.py`):

| 방어 | 조건 | 이유 |
|---|---|---|
| 시딩 | 소스의 헬스 레코드가 없음(첫 실행) | 첫 배포 때 1,108건이 전부 신규다. 그걸 보내면 그날로 앱은 삭제된다 |
| 폭증 차단 | 한 소스 신규 > `max(30, 수집의 50%)` | job_id 체계 변경·사이트 개편이면 기존 공고가 전부 신규로 잡힌다 |
| 0건 판정 | 연속 3회 0건에만 알림 | 새벽·주말은 진짜 0건이다 |

SQS 메시지는 **실행당 하나**(신규 키 목록). 공고마다 하나면 notifier 가 디바이스별 상한·묶음을 계산할 수 없다.

**조용한 시간(23–08 KST)**: 매칭은 하되 `deliveries` 에 `pending` 으로 두고, 08:00 KST 크론이 디바이스별로 묶어 보낸다. 밤에 온 공고가 아침 실행의 "신규"에는 없기 때문에 보류를 저장해야 한다.

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

## 2. 수집 소스

전부 실제 응답으로 검증했다. `2026-09-05` 기준 **14개 소스 / 1,108건 / 회사 68곳**.

| 소스 | 엔드포인트 | 형식 | 회사 | 건수 |
|---|---|---|---|---|
| `coupang` | Greenhouse `boards-api.greenhouse.io/v1/boards/coupang/jobs` | JSON | 1 | 359 |
| `toss` | `GET api-public.toss.im/api/v3/ipd-eggnog/career/job-groups` | JSON(6MB) | 9 | 282 |
| `skcareers` | `POST skcareers.com/Recruit/GetRecruitList` | JSON | 30 | 88 |
| `lg` | `POST api.careers.lg.com/rmk/job/retrieveJobNoticesList` | JSON | 16 | 73 |
| `hyundai` | `GET talent.hyundai.com/api/rec/AP-HM-FO-02700` | JSON | 1 | 71 |
| `tesla_kr` | MokaHR `hire-r1.mokahr.com/api/outer/ats-apply/website/jobs/v2` | JSON | 1 | 61 |
| `woowahan` | `GET career.woowahan.com/w1/recruits` + 코드표 | JSON | 1 | 54 |
| `daangn` | Greenhouse `.../boards/daangn/jobs` | JSON | 1 | 42 |
| `naver` | `GET recruit.navercorp.com/rcrt/loadJobList.do` | JSON | 5 | 31 |
| `kakao` | `GET careers.kakao.com/public/api/job-list` | JSON | 1 | 26 |
| `line` | Gatsby `careers.linecorp.com/page-data/ko/jobs/page-data.json` | JSON | 6 | 14 |
| `kia` | `GET career.kia.com/api/rec/AP-KM-FO-02700` | JSON | 1 | 5 |
| `samsung` | `POST samsungcareers.com/hr/list.data` | HTML 조각 | 26 | 2 |
| `yanolja` | Workday `yanolja.wd102.myworkdayjobs.com/wday/cxs/...` | JSON | 1 | 0 |

### 공용 ATS 어댑터가 확장의 핵심

회사별로 어댑터를 쓰는 게 아니라 **채용 시스템별로** 쓴다. 상속해서 설정 두세
줄만 바꾸면 새 회사가 붙는다.

| 어댑터 | 붙이는 데 필요한 것 | 현재 |
|---|---|---|
| `GreenhouseAdapter` | 보드 토큰 1개 | 당근, 쿠팡 |
| `WorkdayAdapter` | tenant / wd호스트 / site | 야놀자 |
| `MokaHRAdapter` | orgId / siteId | 테슬라 코리아 |
| `HMGAdapter` | 호스트 / API번호 / hgrCd | 현대차, 기아 |

한국 대기업은 그룹 통합 포털을, 스타트업·외국계는 공용 ATS를 쓴다. 어느
쪽이든 **소스 하나가 회사 여럿**이라 회사 수보다 소스 수가 훨씬 적다.

### 소스별로 확인된 사실

**삼성** — `strType=B`로 서버가 경력만 걸러준다. 8/28에 16건이던 게 9/2에 전부
마감돼 지금 2건이다. 공고 회전이 빠르다는 뜻이고, 이 앱이 필요한 이유다.

**SK** — `recruit.skhynix.com`이 아니라 그룹 포털이 소스다. 8/28 이후 계열사
4곳(SK핀크스·SK인텔릭스·SK에코엔지니어링·나래에너지서비스)이 새로 나타났다.
슬러그 폴백 덕에 수집은 안 끊겼고, 등록만 추가했다.

**네이버** — **GET이어야 한다.** POST로 부르면 HTTP 200과 함께
`alert('접근권한이 없습니다')` HTML이 온다. 응답이 `jobDetailLink`로 공고
주소를 직접 주는 유일한 소스다.

**카카오** — 파라미터 없이 부르면 기술 직군만 온다(8건). 응답의
`jobTypeCountDtoList`가 직군 목록을 알려주므로 그걸 읽어 순회한다(26건).
이 API는 **공고 본문 전문까지 내려주는데, 저장하지 않는다**(4절).

**현대차** — 파라미터를 빼면 HTTP 500 + 채용 사이트 HTML이 온다. `hgrCd`가
틀리면 200 + 빈 목록이라 더 고약하다(정답은 `1`, 페이지의 `common.constant.js`
에 있다). `channelCodeNm`으로 경력/계약직만 남긴다.

**쿠팡** — 웹사이트는 403이지만 Greenhouse 보드 API는 열려 있다. 전 세계
689건이 한 보드에 올라오므로 근무지로 국내만 추린다(359건).

**야놀자** — 엔드포인트는 맞다. 잘못된 site는 404, 여기는 200 + 빈 배열이라
**지금 공고가 실제로 0건**이다. 둘을 구분할 수 있으므로 오류로 오해하지 않는다.

**기아** — 현대차와 같은 플랫폼, 같은 어댑터. 처음엔 `/api/*`가 전부 400이라
IP 차단으로 판단했는데 **틀렸다.** 브라우저의 axios가 로그인 전 sessionStorage
값(null)을 헤더에 그대로 실어 `X-HKMC-TOKEN: null`(문자열)로 보내고, 서버는 이
헤더가 없으면 400, `"null"`이면 통과시킨다. 빈 문자열도 400이다.

**LG** — 목록 API가 별도 호스트(`api.careers.lg.com/rmk`)에 있다. 페이지는
847바이트 셸이라 번들의 axios `baseURL`에서 찾았다. 계열사 16곳이 섞여 나오고
`careerTypeCode` B(경력)·D(신입/경력)만 남긴다. `noticeStatus=SAVE`는 임시저장이라
링크가 안 열려 제외.

**토스** — 속은 Greenhouse(`gh_jid`)인데 공개 보드 토큰이 없고 자체 API로 감싸
내보낸다. 응답이 **그룹** 단위("Product Designer" 그룹에 변형 공고 여럿)라
그룹당 1건으로 낸다 — 같은 제목 넷을 알림 넷으로 보내면 스팸이다. 자회사·
고용형태가 고정 필드가 아니라 `metadata[]`에 **한국어 질문 문구를 이름으로**
들어 있어 부분 문자열로 찾고, 하나도 못 찾으면 예외. 응답이 6MB다(본문 전문
포함 — 저장 안 함).

**라인** — Gatsby 정적 사이트. API가 아니라 빌드된 `page-data.json`을 읽는다.
전 세계 378건 중 한국 도시(분당·서울) 54건, 그중 `publish=True` 14건.
`publish=False`인 한국 공고 40건은 대부분 마감이 지난 것이라 이 플래그가
"현재 노출 중"이다.

**우아한형제들** — 채용구분·고용형태·직무군이 코드(`BA003002`)로만 오고 코드표는
`/w1/common/common-item/all`(844항목)에 따로 있다. **매 수집마다 코드표를 먼저
받아 해석한다.** 하드코딩하면 항목이 추가됐을 때 조용히 걸러진다.

### 소스가 조용히 틀리는 방식 (전부 실제로 겪음)

이 앱의 최악의 실패 모드는 **0건과 "채용 없음"이 구분되지 않는 것**이다.
사용자는 앱이 고장난 줄 모르고 오지 않는 알림을 기다린다. 그래서:

- 로케일에 따라 값이 바뀌는 필드는 **모든 표기를 등록**하고, **모르는 값이
  오면 예외를 던진다** (SK `recruitType`: `Experienced` ↔ `경력`)
- 필터가 전부 걸러내면 예외를 던진다 (쿠팡 근무지 필터)
- 목록을 나누는 축이 응답에 있으면 그걸 읽는다. 없으면 예외 (카카오 직군)
- 페이지네이션이 없다고 알고 있는 소스는 `totalCount`와 실제 건수를 비교
- 어댑터는 `verified` 플래그를 갖고, 미검증 소스의 회사는 앱에 노출하지 않는다

## 3. 키워드 매칭

"제목에 키워드가 포함되면"을 그대로 쓰면 한국어에서도 영어에서도 망가진다.

- **정규화 두 가지.** `normalize_text`는 구분자를 지우고(`Dev Ops`→`devops`),
  `spaced_text`는 공백 하나로 바꾼다. 둘 다 필요하다
- **동의어**: `인프라 ↔ infra ↔ infrastructure`, `반도체 ↔ semiconductor`
- **매칭 대상**: 제목 + 부서 + **세부 직무(`roles`)**. 본문은 저장하지 않는다(4절)
  - `roles`가 매칭의 상당 부분을 만든다. 삼성 공고 제목은 "R&D분야 경력사원
    채용(DX부문)"처럼 뭉뚱그려져 있고 "데이터 엔지니어링"은 그 안의 직무
    태그에만 있다. 카카오 `skillSetList`, 현대차 `fldCodeNm`도 마찬가지
  - 다만 **직무처럼 생긴 게 다 직무는 아니다.** 현대차 `hashTag`는
    "9월 신입채용" 같은 캠페인 라벨이라 뺐다. 넣으면 키워드 '경력'이 전부에
    걸리고 경력 공고의 `roles`에 '신입채용'이 섞인다

### 영문 키워드는 알파벳/숫자 경계를 지킨다

한국어는 "반도체공정엔지니어"처럼 붙여 쓰므로 부분문자열 매칭이 **필요하다.**
영어에 같은 규칙을 쓰면 엉뚱한 데 걸린다. 라이브 데이터에서 나온 것들:

| 키워드 | 잘못 걸린 곳 | 원인 |
|---|---|---|
| `SRE` | Sr. Employee Relation Specialist | `Sr.`+`Employee` → `sre` |
| `ML` | HTML 퍼블리셔 | `HT`**`ML`** |
| `intern` (제외어) | **Internal** Tools Engineer | 공고가 통째로 사라짐 |

마지막 것이 제일 나쁘다. 오탐은 알림 하나로 끝나지만 **잘못된 제외는 공고가
조용히 사라져서 아무도 눈치채지 못한다.**

규칙: 영숫자로만 된 키워드는 앞뒤가 영숫자가 아닐 것을 요구한다. 경계는 `\b`가
아니라 직접 정의한다 — 파이썬에서 한글은 `\w`라서 `\b`를 쓰면 "AI개발자"의
`AI`를 못 잡는다. 대신 흔한 어미(`s`, `ing`, `er`, `ment`, `ship` …)는 허용해서
`engineer`가 `Engineering`을 잡게 한다. `al`은 목록에 없다 — 넣으면 `intern`이
`Internal`을 다시 잡는다.

- 제외 키워드: `신입`, `인턴`, `intern` 등 (경력직 앱이므로 기본 제외)
- **1회 실행당 디바이스별 푸시 상한 5건.** 넘으면 "새 공고 12건" 묶음 1건으로.
  상한 없이 보내면 채용 시즌에 알림 20개가 한꺼번에 터지고 그날로 알림이 꺼진다

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

- 소스 14개 × 48회/일 + 페이지네이션 ≈ **1,000~1,300 요청/일**. 토스 응답이 6MB라 전송량은 토스가 대부분. Lambda·DynamoDB·SQS 프리티어 안. 예상 월 $1–3 (대부분 Secrets Manager $0.40 + CloudWatch)
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
| 2 | 어댑터 + 로컬 검증 스크립트 + 오프라인 테스트 | ✅ 완료 — 14소스 / 라이브 1,108건 |
| **2.5** | **삼성전자 국내 경력 공고가 어디 올라오는지 확인** | ⏳ 2절 참고 |
| 3 | SAM 템플릿: DynamoDB + collector + notifier + APNs | ✅ 코드·템플릿 완료, 테스트 231개. 실제 배포는 `docs/DEPLOY.md` |
| **3.5** | **앱 API** (v2에서 추가) | ✅ HTTP API + `api.py`, 테스트 19개 |
| 4 | iOS MVP: 온보딩 → 리스트 → 푸시 수신 | 🔶 코드 완료. CI(macOS 러너)에서 컴파일·TestFlight. `docs/IOS.md` |
| 5 | StoreKit 2 구독 + 서버 검증 + App Store Server Notifications | |

### 순서에 대한 제안
StoreKit(5단계)은 **사용자가 붙고 나서** 하는 걸 권한다. 구독 서버 검증 + Apple 웹훅은 체감상 3~4단계를 합친 것만큼 일이 큰데, 알림 품질이 검증되기 전에는 아무도 결제하지 않는다. 4단계까지 만들어서 본인이 2주 써보고 "푸시가 실제로 쓸모 있다"가 확인된 다음에 5단계로 가는 게 낫다. (물론 이건 제안이고, 순서는 그대로 가도 된다.)

---

## 7. iOS 앱

맥이 없으므로 **`.xcodeproj` 를 저장소에 두지 않고 `ios/project.yml`(XcodeGen)에서
CI 가 생성**한다. 빌드·테스트·TestFlight 업로드가 전부 GitHub Actions macOS 러너에서
돈다. 서명은 App Store Connect API 키 하나로 Xcode 가 자동 관리(cloud-managed
signing)해서 `.p12` 를 다룰 일이 없다. 절차는 `docs/IOS.md`.

제약: 시뮬레이터에서 눌러볼 수 없다. 실행 확인은 TestFlight → 실제 아이폰뿐이다.
그래서 build 잡이 푸시마다 시뮬레이터용 컴파일 + 유닛 테스트를 돌려 "컴파일은
된다"를 보장하고, 화면 확인은 TestFlight 에서 한다.

- SwiftUI, iOS 17+, `@Observable`, async/await `URLSession`
- `install_id`: Keychain (`kSecAttrAccessibleAfterFirstUnlock`) — 재설치 후에도 유지
- 푸시 권한: 온보딩 **마지막**에, "왜 필요한지" 화면을 한 번 보여준 뒤 요청 (선요청하면 거부율이 크게 오름)
- 캐시: 서버가 원본. 로컬은 오프라인 표시용 JSON 캐시면 충분 (SwiftData는 과함)
- 공고 열기: `SFSafariViewController` (`UIViewControllerRepresentable`)
- 푸시 페이로드에 `job_id` → 탭 시 해당 공고로 딥링크
