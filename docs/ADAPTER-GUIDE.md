# 어댑터 추가 / 엔드포인트 확정 가이드

회사 하나를 붙이는 데 드는 시간은 대개 **코드 작성 5분, 엔드포인트 찾기 5분**이다.
찾는 쪽이 진짜 일이므로 그 절차를 여기 적어둔다.

---

## 0. 먼저: 이 사이트는 HTML인가 SPA인가

```bash
curl -s -A "Mozilla/5.0" https://recruit.example.com/ | grep -ci "공고\|job"
```

- **0이 나오면 SPA다.** HTML 파싱은 시도할 가치가 없다. 1번으로 간다.
  (삼성 `samsungcareers.com`이 정확히 이 경우다 — 52KB 응답에 "job"이 0회)
- 공고 제목이 실제로 보이면 서버 렌더링이다. BeautifulSoup으로 파싱하는
  어댑터를 써도 된다. 다만 HTML 파싱은 마크업이 바뀔 때마다 깨지므로,
  그 사이트에도 JSON API가 있는지 1번으로 한 번은 확인하는 게 낫다.

---

## 1. XHR 엔드포인트 찾기 (5분)

1. 크롬에서 회사 채용 **목록** 페이지를 연다
2. DevTools → **Network** → **Fetch/XHR** 필터
3. 페이지를 새로고침하거나 "더보기"/2페이지를 누른다
4. 응답에 공고 제목이 들어 있는 요청을 찾는다 (Preview 탭에서 눈으로 확인)
5. 그 요청에서 **네 가지**를 적어둔다:
   - 메서드 + URL
   - Request Payload (POST면) 또는 Query String
   - 응답에서 공고 배열까지 가는 **경로** (예: `data.list`, `result.items`)
   - 배열 원소의 **키 이름들** (제목/ID/근무지/게시일)

> 팁: 요청에 우클릭 → **Copy as cURL**로 떠서 터미널에 붙여보면
> 어떤 헤더가 실제로 필요한지(Referer, X-Requested-With 등) 바로 갈린다.
> 대개 `Referer`만 있으면 통과한다.

---

## 2. 코드에 채우기

`adapters/samsung.py` 같은 미설정 어댑터는 상수 세 개만 채우면 된다.

```python
ENDPOINT = ("POST", f"{BASE}/rest/job/list")   # 1번에서 적은 메서드+URL

REQUEST = {"json": {"pageIndex": 1, "pageSize": 100}}   # POST 바디
# GET이면: REQUEST = {"params": {"page": 1, "size": 100}}

SPEC = JsonListSpec(
    company="samsung",
    list_path="data.list",           # 배열까지 가는 경로
    title_key="jobTitle",
    id_key="jobId",
    location_key="workPlace",
    department_key="jobField",
    posted_at_key="regDate",
    url=lambda row: f"{BASE}/job/detail/{row['jobId']}",
)
```

경로나 키 이름이 틀리면 `AdapterError`가 **응답에 실제로 있던 키 목록을
같이 알려준다.** 추측하지 말고 그 메시지를 보고 고치면 된다.

---

## 3. 확인

```bash
cd backend
python scripts/verify.py samsung                  # 결과 눈으로 확인
python scripts/verify.py samsung --save-fixture   # 응답을 tests/fixtures/ 에 저장
python scripts/verify.py samsung --json --limit 3 # DynamoDB 에 들어갈 형태로
```

확인할 것:

- 건수가 사이트에 표시된 총 공고 수와 맞는가 (페이지네이션 누락 여부)
- `job_id 중복` 경고가 없는가 — 뜨면 `id_key` 선택이 잘못된 것이다
- URL을 브라우저에 붙여넣으면 그 공고가 열리는가

다 맞으면 어댑터 클래스의 **`verified = True`로 바꾼다.** 이 플래그가
False인 회사는 앱의 회사 목록에 노출되지 않는다 — 동작하지 않는 회사가
목록에 보이면 사용자는 "앱이 고장났다"가 아니라 "채용이 없구나"로
오해하기 때문이다.

마지막으로 픽스처 기반 테스트를 추가한다 (`tests/test_adapters.py` 참고).
이게 있으면 이후 사이트가 바뀌었을 때 파싱 코드 회귀와 사이트 변경을
구분할 수 있다.

---

## 4. 페이지네이션

`JsonListSpec`은 단일 응답만 다룬다. 페이지를 넘겨야 하면 `workday.py`의
루프를 참고해서 어댑터에 직접 쓴다. 그때 반드시 지킬 것:

- **상한(`MAX_PAGES`)을 둔다.** 종료 조건이 틀렸을 때 무한 루프로 상대
  서버를 때리는 사고를 막는다
- **`source_id`로 중복을 거른다.** offset 페이징 중에 목록이 갱신되면
  같은 공고가 두 페이지에 걸쳐 나온다

---

## 5. Workday를 쓰는 회사라면

채용 URL이 `https://{tenant}.wd{N}.myworkdayjobs.com/{site}` 형태면
어댑터를 새로 쓸 필요가 없다:

```python
class AcmeAdapter(WorkdayAdapter):
    key, display_name = "acme", "Acme"
    site_url = "https://acme.wd3.myworkdayjobs.com/Acme_Careers"
    tenant, wd_host, site = "acme", "wd3", "Acme_Careers"
    verified = True
```

Greenhouse(`boards-api.greenhouse.io/v1/boards/{token}/jobs`)와
Lever(`api.lever.co/v0/postings/{token}?mode=json`)도 같은 식으로
공용 어댑터를 만들 수 있다. 필요해지면 그때 추가한다.

---

## 6. 예의

- `robots.txt`를 확인한다
- 수집 주기 30분을 유지한다. 더 자주 돌 이유가 없다
- User-Agent에 연락처를 남긴다 (`http.py`의 `CONTACT_URL`)
- 회사가 차단을 요청하면 즉시 어댑터를 제거한다
- 공고 **본문은 저장하지 않는다.** 제목/URL/게시일/근무지/부서까지만.
  원문은 앱에서 `SFSafariViewController`로 원 사이트를 연다
