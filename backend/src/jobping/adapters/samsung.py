"""삼성 그룹 통합 채용 포털 — www.samsungcareers.com.

목록 페이지는 SPA라 HTML을 받아도 공고가 없다. 대신 브라우저가 부르는
`POST /hr/list.data`를 직접 호출한다. 응답은 JSON이 아니라 **HTML 조각**이다.

파라미터 두 개가 이 앱에 특히 중요하다:

* `strType=B` — 서버가 경력 공고만 걸러준다. 클라이언트에서 거를 필요가 없다
* `strCompany` — 계열사 코드. 비우면 26개사 전체

공고 하나가 세부 직무 여러 개를 묶고 있다("R&D분야 경력사원 채용" 안에
"[Big Data센터] SW개발 (데이터 엔지니어링)" 등이 10여 개). 사용자가 찾는
키워드는 제목이 아니라 이 세부 직무에 있으므로 `roles`로 함께 가져온다.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..companies import SAMSUNG, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, parse_date

BASE = "https://www.samsungcareers.com"
LIST_URL = f"{BASE}/hr/list.data"
JOB_URL = f"{BASE}/hr/?no={{no}}"

EXPERIENCED = "B"  # A=신입, B=경력, C=인턴

MAX_PAGES = 30

#: 이 아홉 개를 다 보내야 한다. 하나라도 빠지면 서버가 500을 준다.
BASE_PARAMS = {
    "currentPageNo": "1",
    "intNo": "0",
    "strVal": "",
    "strTxt": "",
    "strKey": "",
    "strCompany": "",
    "strType": "",
    "strOrderBy": "",
    "strEntity": "",
}

_PERIOD = re.compile(r"(\d{4}\.\d{2}\.\d{2})\s*~\s*(\d{4}\.\d{2}\.\d{2})")


class SamsungAdapter(Adapter):
    key = "samsung"
    display_name = "삼성"
    site_url = f"{BASE}/hr/?ty=B"
    companies = SAMSUNG
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        jobs: list[Job] = []
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            params = {**BASE_PARAMS, "currentPageNo": str(page),
                      "strType": EXPERIENCED}
            html = client.post_text(
                LIST_URL,
                data=params,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                    "Referer": self.site_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            page_jobs, last_page = self._parse(html)
            if not page_jobs:
                break
            for job in page_jobs:
                if job.job_id not in seen:
                    seen.add(job.job_id)
                    jobs.append(job)
            if last_page is not None and page >= last_page:
                break
        return jobs

    def _parse(self, html: str) -> tuple[list[Job], int | None]:
        soup = BeautifulSoup(html, "html.parser")

        last_page = None
        counter = soup.select_one("input.divCnt")
        if counter is not None and counter.get("data-max"):
            try:
                last_page = int(str(counter["data-max"]))
            except ValueError:
                last_page = None

        items = soup.select("li")
        if not items:
            # 빈 목록과 구조 변경은 다르다. 목록이 비면 컨테이너는 남는다.
            if counter is None:
                raise AdapterError(
                    "samsung: 응답에 li 도 input.divCnt 도 없다. "
                    "list.data 응답 형식이 바뀌었을 수 있다."
                )
            return [], last_page

        jobs = []
        for item in items:
            job = self._parse_item(item)
            if job is not None:
                jobs.append(job)
        if items and not jobs:
            raise AdapterError(
                f"samsung: li {len(items)}개를 받았지만 한 건도 파싱하지 못했다. "
                "마크업이 바뀌었다."
            )
        return jobs, last_page

    def _parse_item(self, item) -> Job | None:
        share = item.select_one("button.btnShare[data-value]")
        title_el = item.select_one("h3.title")
        if share is None or title_el is None:
            return None

        # data-value 는 "22,878" 처럼 천 단위 구분자가 들어 있다.
        no = str(share["data-value"]).replace(",", "").strip()
        if not no.isdigit():
            raise AdapterError(f"samsung: 공고 번호가 숫자가 아니다 — {no!r}")

        company_el = item.select_one("p.company")
        company_name = company_el.get_text(strip=True) if company_el else ""

        posted = None
        period_el = item.select_one(".period")
        if period_el is not None:
            matched = _PERIOD.search(period_el.get_text(" ", strip=True))
            if matched:
                posted = parse_date(matched.group(1))

        roles = tuple(
            el.get_text(" ", strip=True) for el in item.select(".flagWrap .flag.grey")
        )

        return Job.make(
            company=resolve(self.key, company_name, company_name),
            title=title_el.get_text(" ", strip=True),
            url=JOB_URL.format(no=no),
            source_id=no,
            posted_at=posted,
            department=company_name or None,
            employment_type="경력",
            roles=roles,
        )
