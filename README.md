# 잡핑 (JobPing)

대기업 자체 채용 페이지를 주기적으로 확인해서, 등록한 키워드에 맞는 **새 경력직
공고**가 뜨면 iOS 푸시로 알려주는 앱.

플랫폼(사람인/원티드 등)은 소스로 쓰지 않는다. 회사 공식 채용 페이지만 쓴다.

- 계획 및 아키텍처: [`docs/PLAN.md`](docs/PLAN.md)
- 회사 추가하기: [`docs/ADAPTER-GUIDE.md`](docs/ADAPTER-GUIDE.md)

## 지금 수집되는 것

`2026-09-05` 기준 **680건 / 회사 37곳**.

| 소스 | 회사 | 경력 공고 |
|---|---|---|
| SK (`skcareers.com`) | 30 | 88 |
| 삼성 (`samsungcareers.com`) | 26 | 2 |
| 네이버 (+웹툰·클라우드·랩스·SNOW) | 5 | 31 |
| 쿠팡 (Greenhouse) | 1 | 359 |
| 현대자동차 | 1 | 71 |
| 테슬라 코리아 (MokaHR) | 1 | 61 |
| 당근 (Greenhouse) | 1 | 42 |
| 카카오 | 1 | 26 |
| 야놀자 (Workday) | 1 | 0 |

미구현: 기아(코드는 있으나 미검증), LG전자, 라인, 우아한형제들, 토스 —
앱의 회사 목록에는 노출되지 않는다.

회사별이 아니라 **채용 시스템별**로 어댑터를 쓴다. `GreenhouseAdapter`,
`WorkdayAdapter`, `MokaHRAdapter`, `HMGAdapter`를 상속하면 설정 두세 줄로
새 회사가 붙는다.

## 구조

```
backend/
  src/jobping/
    models.py      Job 모델, URL 정규화, job_id 계산
    companies.py   계열사 레지스트리 (소스 코드/이름 → 안정적인 키)
    http.py        공용 HTTP 클라이언트
    matching.py    키워드 매칭 (정규화 + 동의어 + 제외어)
    registry.py    어댑터 레지스트리
    adapters/      공용 ATS: greenhouse / workday / mokahr / hmg
                   자체 포털: samsung / skcareers / naver / kakao
  scripts/verify.py  어댑터를 실제 사이트에 붙여 확인하는 도구
  tests/             실제 응답 픽스처 기반 오프라인 테스트
ios/               SwiftUI 앱 (4단계)
docs/
```

## 백엔드 시작하기

```bash
cd backend
make install               # .venv 생성 + 의존성
make test                  # 오프라인 테스트 (네트워크 불필요)
make verify A=naver        # 실제 사이트에 붙여 확인
python scripts/verify.py --all --limit 1
```

## 진행 상황

| 단계 | 상태 |
|---|---|
| 1. 레포 구조 | ✅ |
| 2. 어댑터 + 검증 도구 | ✅ 소스 9개 / 라이브 680건 |
| 3. SAM 배포 | |
| 3.5. 읽기 API | |
| 4. iOS MVP | |
| 5. StoreKit 구독 | |
