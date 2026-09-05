# 잡핑 (JobPing)

대기업 자체 채용 페이지를 주기적으로 확인해서, 등록한 키워드에 맞는 **새 경력직
공고**가 뜨면 iOS 푸시로 알려주는 앱.

플랫폼(사람인/원티드 등)은 소스로 쓰지 않는다. 회사 공식 채용 페이지만 쓴다.

- 계획 및 아키텍처: [`docs/PLAN.md`](docs/PLAN.md)
- 회사 추가하기: [`docs/ADAPTER-GUIDE.md`](docs/ADAPTER-GUIDE.md)
- 백엔드 배포: [`docs/DEPLOY.md`](docs/DEPLOY.md)
- iOS 빌드·TestFlight (맥 없이): [`docs/IOS.md`](docs/IOS.md)
- 개인정보 처리방침: [`docs/PRIVACY.md`](docs/PRIVACY.md)

## 지금 수집되는 것

`2026-09-05` 기준 **14개 소스 / 1,108건 / 회사 68곳** (등록 100곳).

| 소스 | 회사 | 경력 공고 |
|---|---|---|
| 쿠팡 (Greenhouse) | 1 | 359 |
| 토스 (+뱅크·증권·페이먼츠 등 9곳) | 9 | 282 |
| SK (`skcareers.com`) | 30 | 88 |
| LG (LG전자·CNS·에너지솔루션 등 16곳) | 16 | 73 |
| 현대자동차 | 1 | 71 |
| 테슬라 코리아 (MokaHR) | 1 | 61 |
| 우아한형제들 | 1 | 54 |
| 당근 (Greenhouse) | 1 | 42 |
| 네이버 (+웹툰·클라우드·랩스·SNOW) | 5 | 31 |
| 카카오 | 1 | 26 |
| 라인 (한국 법인 6곳) | 6 | 14 |
| 기아 | 1 | 5 |
| 삼성 (`samsungcareers.com`) | 26 | 2 |
| 야놀자 (Workday) | 1 | 0 |

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
                   자체 포털: samsung / skcareers / naver / kakao / lg / toss / line / woowahan
    collector.py   수집 실행: 신규 판정, 시딩, 폭증 차단, 소스 헬스
    notifier.py    매칭 → 알림 계획(티어·상한·묶음·조용한 시간) → APNs 발송
    store.py       DynamoDB + 인메모리 구현 (같은 인터페이스)
    apns.py        APNs HTTP/2 클라이언트 (토큰 인증)
    api.py         앱 API: /v1/companies, /v1/jobs, /v1/devices
    handlers/      Lambda 진입점
  template.yaml    SAM — DynamoDB 4개, SQS, Lambda 3개, HTTP API, EventBridge, 알람
  scripts/verify.py   어댑터를 실제 사이트에 붙여 확인
  scripts/dry_run.py  전체 파이프라인을 로컬에서, 아무것도 보내지 않고
  tests/              실제 응답 픽스처 기반 오프라인 테스트
ios/               SwiftUI 앱. .xcodeproj 없음 — project.yml 에서 XcodeGen 이 생성
  JobPing/         App / Models / Services / Views
.github/workflows/ backend(pytest+sam validate), ios(시뮬레이터 빌드·테스트, TestFlight 업로드)
docs/
```

## 백엔드 시작하기

```bash
cd backend
make install               # .venv 생성 + 의존성
make test                  # 오프라인 테스트 (네트워크 불필요)
make verify A=naver        # 어댑터 하나를 실제 사이트에 붙여 확인
make dry-run               # 수집→신규판정→매칭→알림계획까지, 발송 없이 (AWS 불필요)
make deploy STAGE=dev      # AWS 배포 — 처음이면 docs/DEPLOY.md
```

`make dry-run` 을 두 번 돌려보면 동작이 보인다. 첫 번째는 시딩(전부 저장, 알림 0),
두 번째는 그 사이 새로 뜬 공고만 신규로 잡혀 매칭된다.

## 진행 상황

| 단계 | 상태 |
|---|---|
| 1. 레포 구조 | ✅ |
| 2. 어댑터 + 검증 도구 | ✅ 소스 14개 / 라이브 1,108건 |
| 3. SAM 배포 | ✅ 템플릿·수집·알림 파이프라인 완성. 실제 배포는 AWS 계정에서 `make deploy` |
| 3.5. 앱 API | ✅ `/v1/companies` `/v1/jobs` `/v1/devices` |
| 4. iOS MVP | 🔶 코드 완료. **GitHub Actions 첫 빌드로 컴파일 확인 필요** (맥 없이 작성) |
| 5. StoreKit 구독 | |
