# 잡핑 iOS 앱

4단계에서 구현한다. 계획은 [`../docs/PLAN.md`](../docs/PLAN.md) 7절 참고.

먼저 확정돼야 하는 것:

- 3.5단계의 읽기 API 계약 (`GET /v1/jobs`, `POST /v1/devices`)
- 최소 한 개 이상의 `verified=True` 어댑터 — 실제 공고가 흐르지 않으면
  온보딩에서 고를 회사가 없다

기술 선택:

- SwiftUI, iOS 17+, `@Observable`
- `install_id`: Keychain UUID (재설치해도 유지). APNs 토큰은 별도 속성
- 공고 열기: `SFSafariViewController`
- 로컬 캐시는 오프라인 표시용 JSON이면 충분 (SwiftData는 과함)
