# 어댑터 추가 / 엔드포인트 확정 가이드

회사 하나를 붙이는 데 드는 시간은 대개 **엔드포인트 찾기 10분, 코드 작성 20분**이다.
찾는 쪽이 진짜 일이므로 실제로 통했던 절차를 그대로 적어둔다.

---

## 0. 이 사이트는 HTML인가 SPA인가

```bash
curl -s -A "Mozilla/5.0" https://recruit.example.com/ | grep -ci "공고\|job"
```

0이 나오면 SPA다. HTML 파싱은 시도할 가치가 없다.
(`samsungcareers.com`이 정확히 이 경우 — 52KB 응답에 "job"이 0회)

---

## 1. 브라우저 없이 엔드포인트 찾기

DevTools를 열 수 있으면 그게 제일 빠르다(Network → Fetch/XHR → 공고 제목이
들어 있는 응답). 그럴 수 없을 때는 **JS 번들을 직접 읽는다.** 세 소스 모두
이 방법으로 찾았다.

```bash
# 1) 페이지가 어떤 스크립트를 부르는지
curl -s "$URL" | grep -o '<script[^>]*src="[^"]*"' 

# 2) 목록을 그리는 번들을 받아서 API 경로를 뽑는다
curl -s "$BUNDLE_URL" -o app.js
grep -oE '"(/[A-Za-z0-9_/.-]{4,60})"' app.js | sort -u | grep -Ei 'job|list|recruit|api'

# 3) 후보 경로 주변을 읽어 파라미터 이름을 확인한다
grep -o '.\{900\}/api/your/path.\{400\}' app.js
```

인라인 스크립트에 그냥 있는 경우도 많다:

```bash
curl -s "$URL" | grep -oE '(url:|\$\.(get|post)\(|fetch\()\s*"[^"]+"'
```

---

## 2. 파라미터를 이등분해서 찾기

엔드포인트를 알아도 파라미터가 틀리면 실패한다. **틀렸을 때 돌아오는 응답이
에러가 아닌 경우가 많아서** 이 단계가 제일 헷갈린다:

| 실제로 겪은 응답 | 진짜 원인 |
|---|---|
| `{"code":500,"message":"Internal server error"}` | 삼성 — 9개 파라미터 중 일부 누락 |
| **404 HTML 페이지** | SK — 7개 파라미터 중 일부 누락 (ASP.NET 모델 바인딩 실패) |
| 302 리다이렉트 루프 | MokaHR — 세션 쿠키 없음 |
| **HTTP 500 + 채용 사이트 HTML** | 현대차 — 파라미터 누락 |
| **200 + 빈 목록** | 현대차 — `hgrCd` 오답. 제일 찾기 어렵다 |
| **200 + `alert('접근권한이 없습니다')`** | 네이버 — GET인데 POST로 부름 |
| 기술 직군 8건만 (전체는 26건) | 카카오 — `part` 기본값이 TECHNOLOGY |

그러니 **하나씩 빼면서 이등분하라.** 대조군(다른 POST 엔드포인트)을 하나
같이 때려보면 "라우팅이 문제인가 파라미터가 문제인가"가 바로 갈린다.

```bash
P(){ curl -sS -X POST "$EP" -H "Referer: $PAGE" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     --data "$1" -o /dev/null -w "%{http_code}\n"; }
P ""                          # 빈 바디
P "sort=0"                    # 하나씩
P "sort=0&searchText=&..."    # 전부
```

---

## 3. 함정: 로케일에 따라 값이 바뀐다

**이게 가장 위험한 종류의 버그다.** SK의 `recruitType`은 요청 언어에 따라
`"Experienced"`(영어) 또는 `"경력"`(한국어)으로 온다. 영어 기준으로 필터를
짜고 한국어로 요청하면 **필터가 전부 걸러내 0건이 되는데, 예외가 안 난다.**
사용자에게는 "채용이 없구나"로 보이고, 앱이 고장난 걸 아무도 모른다.

규칙 두 개:

1. 로케일에 따라 달라지는 값은 **모든 표기를 등록한다** (`companies.py`의
   `aliases`, `skcareers.py`의 `EXPERIENCED_TYPES`)
2. **모르는 값이 오면 예외를 던진다.** 조용히 걸러내면 안 된다

같은 이유로 회사명도 두 표기를 다 등록한다 (`SK하이닉스` / `SK hynix`).

---

## 4. URL 두 가지를 구분한다

`models.py`에 함수가 둘인 이유:

- `clean_url()` — **저장하고 사용자가 누를 URL.** 추적 파라미터만 떼고
  경로와 프래그먼트는 그대로 둔다
- `identity_url()` — **`job_id` 해시용.** 쿼리 정렬, 끝 슬래시 제거

프래그먼트를 지우면 해시 라우팅 SPA에서 링크가 전부 홈으로 간다
(MokaHR 공고 주소는 `.../100000166#/job/{id}` 라 `#` 뒤가 곧 공고다).
끝 슬래시를 지우면 `/hr/?no=1` 을 `/hr?no=1` 로 바꿔버린다 — 서버에 따라
다르게 동작한다.

---

## 4.5. 먼저 공용 ATS인지 본다

새 어댑터를 쓰기 전에 **채용 URL만 보고** 판별되는 것들이 있다. 맞으면
설정 두세 줄로 끝난다.

| URL 모양 | 어댑터 | 설정 |
|---|---|---|
| `boards.greenhouse.io/{token}` 또는 지원 링크에 `gh_jid=` | `GreenhouseAdapter` | `board_token` |
| `{tenant}.wd{N}.myworkdayjobs.com/{locale}/{site}` | `WorkdayAdapter` | `tenant`, `wd_host`, `site` |
| `hire-r1.mokahr.com/social-recruitment/{org}/{site}` | `MokaHRAdapter` | `org_id`, `site_id` |

Greenhouse 토큰은 회사명 그대로인 경우가 많아서 그냥 찔러보면 된다:

```bash
for t in acme acme-inc acmecorp; do
  printf "%-12s" "$t"
  curl -sS -o /dev/null -w "%{http_code}\n" \
    "https://boards-api.greenhouse.io/v1/boards/$t/jobs?content=false"
done
```

쿠팡을 이렇게 찾았다. 쿠팡 채용 **웹사이트**는 403을 주는데 Greenhouse 보드
API는 열려 있다 — 사이트가 막혔다고 포기하기 전에 ATS를 확인할 것.

Lever(`api.lever.co/v0/postings/{token}?mode=json`)도 같은 식으로 확인한다.

---

## 5. 공고 하나에 직무가 여럿인 경우

삼성 공고 하나("R&D분야 경력사원 채용")에는 세부 직무가 10여 개 붙어 있고,
사용자가 찾는 "데이터 엔지니어링"은 **제목이 아니라 거기에** 있다. 제목만
매칭하면 거의 아무것도 안 걸린다. 그래서 `Job.roles`로 함께 가져오고
`matching.haystack()`이 이걸 본다. 새 어댑터를 쓸 때 꼭 채워라.
카카오 `skillSetList`, 현대차 `fldCodeNm`, SK `jobRole`, 네이버 `subJobCdNm`이
같은 역할을 한다.

**다만 직무처럼 생긴 게 다 직무는 아니다.** 현대차 `hashTag`는
"9월 신입채용" 같은 캠페인 라벨이라 뺐다. 넣었더니 키워드 '경력'이 모든 공고에
걸리고, 우리가 남긴 경력 공고의 `roles`에 '신입채용'이 섞여 들어갔다. 필드를
`roles`에 넣기 전에 **값 분포를 한 번 찍어보고** 판단해라:

```bash
python scripts/verify.py <adapter> --json --limit 50 | grep -o '"roles".*'
```

---

## 6. 계열사 매핑

삼성·SK는 그룹 통합 포털이라 소스 하나가 계열사 26~27곳을 내보낸다.
`Job.company`는 **그룹이 아니라 계열사** 키다. 반도체 공고를 원하는 사람에게
삼성생명 공고를 보내면 안 되기 때문이다.

`companies.py`에 계열사를 등록하고 어댑터에서 `resolve(source, 이름_또는_코드)`
를 부른다. 등록되지 않은 계열사는 슬러그로 대체되어 **수집은 계속되지만 앱의
회사 목록에는 안 뜬다.** `verify.py`가 미등록 계열사를 경고로 알려준다.

---

## 7. 확인

```bash
cd backend
python scripts/verify.py samsung                  # 결과 눈으로 확인
python scripts/verify.py samsung --save-fixture   # 응답을 tests/fixtures/ 에 저장
python scripts/verify.py --all --limit 1          # 전체 상태 한눈에
```

확인할 것:

- 건수가 사이트에 표시된 총 공고 수와 맞는가 (페이지네이션 누락 여부)
- `job_id 중복` / `URL 중복` / `미등록 계열사` 경고가 없는가
- **URL을 브라우저에 붙여넣으면 그 공고가 실제로 열리는가**

다 맞으면 어댑터의 `verified = True`로 바꾼다. 이 플래그가 False인 소스의
회사는 앱 목록에 노출되지 않는다.

마지막으로 저장한 픽스처로 테스트를 추가한다. 픽스처는 통과하는데 라이브가
실패하면 사이트가 바뀐 것이고, 둘 다 실패하면 우리 코드가 깨진 것이다.

---

## 8. 페이지네이션

- **상한(`MAX_PAGES`)을 반드시 둔다.** 종료 조건이 틀렸을 때 무한 루프로
  상대 서버를 때리는 사고를 막는다
- **`source_id`로 중복을 거른다.** offset 페이징 중 목록이 갱신되면 같은
  공고가 두 페이지에 걸쳐 나온다
- 페이지네이션이 없는 소스(SK)는 `totalCount`와 실제 건수를 비교해서
  나중에 생겼는지 감지한다

---

## 9. 예의

- `robots.txt`를 확인한다
- 수집 주기 30분을 유지한다. 더 자주 돌 이유가 없다
- User-Agent에 연락처를 남긴다 (`http.py`의 `CONTACT_URL`)
- 회사가 차단을 요청하면 즉시 어댑터를 제거한다
- 공고 **본문은 저장하지 않는다.** 제목/URL/게시일/근무지/직무까지만.
  원문은 앱에서 `SFSafariViewController`로 원 사이트를 연다
