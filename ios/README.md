# 잡핑 iOS 앱

SwiftUI, iOS 17+. `.xcodeproj` 는 없고 `project.yml` 에서 XcodeGen 이 만든다.
빌드·배포는 GitHub Actions 에서 — 절차는 [`../docs/IOS.md`](../docs/IOS.md).

```
JobPing/
  App/          진입점, AppDelegate(푸시 등록·알림 탭), AppModel(상태)
  Models/       서버 응답 Codable
  Services/     APIClient, InstallID(Keychain), Bookmarks
  Views/        Onboarding → Jobs / Bookmarks / Settings
  Resources/    Info.plist(자리표시자), entitlements, 에셋
JobPingTests/   모델 디코딩 테스트
```

설계 메모:

- 식별자는 Keychain 의 UUID(`InstallID`). APNs 토큰은 바뀌므로 식별자로 쓰지 않는다
- 푸시 권한은 온보딩 **마지막**에, 이유를 보여준 뒤 묻는다
- 공고 원문은 `SFSafariViewController` 로 회사 사이트에서 연다. 본문을 앱에 담지 않는다
- 북마크는 기기에만 저장한다
- 회사 로고·워드마크는 어디에도 쓰지 않는다(심사 5.2). 앱 아이콘은 단색 자리표시자다
