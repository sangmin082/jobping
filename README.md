# 잡핑 (JobPing)

대기업 자체 채용 페이지를 주기적으로 확인해서, 등록한 키워드에 맞는 **새 경력직
공고**가 뜨면 iOS 푸시로 알려주는 앱.

플랫폼(사람인/원티드 등)은 소스로 쓰지 않는다. 회사 공식 채용 페이지만 쓴다.

- 계획 및 아키텍처: [`docs/PLAN.md`](docs/PLAN.md)
- 회사 추가하기: [`docs/ADAPTER-GUIDE.md`](docs/ADAPTER-GUIDE.md)

## 지금 수집되는 것

| 소스 | 계열사 | 경력 공고 |
|---|---|---|
| 삼성 (`samsungcareers.com`) | 26곳 | 16건 |
| SK (`skcareers.com`) | 27곳 | 96건 |
| 테슬라 코리아 (MokaHR) | 1곳 | 65건 |

삼성·SK는 **그룹 통합 포털**이라 소스 하나가 계열사 수십 곳을 내보낸다.
사용자가 구독하는 단위는 그룹이 아니라 계열사(`samsung_ds`, `sk_hynix`)다.

## 구조

```
backend/
  src/jobping/
    models.py      Job 모델, URL 정규화, job_id 계산
    companies.py   계열사 레지스트리 (소스 코드/이름 → 안정적인 키)
    http.py        공용 HTTP 클라이언트
    matching.py    키워드 매칭 (정규화 + 동의어 + 제외어)
    registry.py    어댑터 레지스트리
    adapters/      samsung / skcareers / mokahr(tesla_kr) + 스켈레톤
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
make verify A=samsung      # 실제 사이트에 붙여 확인
python scripts/verify.py --all --limit 1
```

## 진행 상황

| 단계 | 상태 |
|---|---|
| 1. 레포 구조 | ✅ |
| 2. 어댑터 3개 + 검증 도구 | ✅ 라이브 177건 수집 확인 |
| 3. SAM 배포 | |
| 3.5. 읽기 API | |
| 4. iOS MVP | |
| 5. StoreKit 구독 | |
