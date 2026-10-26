# iOS 앱 — 맥 없이 빌드하고 배포하기

이 저장소에는 `.xcodeproj` 가 없다. `ios/project.yml` 에서 XcodeGen 이 매번
만든다. 빌드는 전부 GitHub Actions 의 macOS 러너에서 돈다.

## 흐름

```
git push  ──►  build 잡 (자동)       시뮬레이터용 컴파일 + 유닛 테스트. 서명 없음.
                                     여기서 통과해야 코드가 "컴파일된다"는 뜻이다.

Actions ▸ iOS ▸ Run workflow
  upload = true  ──►  testflight 잡   서명 → 아카이브 → App Store Connect 업로드
                                     → 10~30분 뒤 아이폰 TestFlight 앱에 뜬다
```

**시뮬레이터에서 앱을 눌러볼 방법은 없다.** 맥이 없으면 실행은 TestFlight 를 거쳐
실제 아이폰에서만 된다. 푸시 알림도 실제 기기에서만 온다.

## 한 번만 하는 준비

### 1. Apple Developer Program (연 $99)

TestFlight 와 푸시 알림 둘 다 이게 필요하다. 가입 후:

- **Team ID** 적어두기 (Membership 페이지, 10자리)
- **App ID 만들기** — Certificates, Identifiers & Profiles ▸ Identifiers ▸ `+`
  - Bundle ID: `com.sangmin082.jobping` (바꾸려면 `ios/project.yml` 도 같이)
  - Capabilities: **Push Notifications** 체크
- **APNs 키 만들기** — Keys ▸ `+` ▸ Apple Push Notifications service. `.p8` 다운로드
  (**한 번만 받을 수 있다**). Key ID 적어두기. 이건 백엔드 SSM 에 넣는다 (`docs/DEPLOY.md`)

### 2. App Store Connect

- **앱 등록** — My Apps ▸ `+` ▸ 이름 `잡핑`, 위 Bundle ID 선택
- **API 키 만들기** — Users and Access ▸ Integrations ▸ App Store Connect API ▸ `+`
  - Access: **Admin** — CI 가 배포 인증서와 프로비저닝 프로파일을 자동으로 만든다.
    그보다 낮은 권한이면 아카이브 단계에서 인증서를 못 만들어 실패할 수 있다
  - `.p8` 다운로드, **Key ID** 와 **Issuer ID** 적어두기

이 키 하나로 CI 가 배포 인증서와 프로비저닝 프로파일을 알아서 만든다
(`xcodebuild -allowProvisioningUpdates`). `.p12` 인증서를 손으로 뽑아 올릴 필요가 없다.

### 3. GitHub 저장소 설정

Settings ▸ Environments ▸ **New environment** ▸ 이름 `testflight`

거기에 시크릿:

| Secret | 값 |
|---|---|
| `APPLE_TEAM_ID` | Team ID |
| `APPSTORE_API_KEY_ID` | App Store Connect API Key ID |
| `APPSTORE_API_ISSUER_ID` | Issuer ID |
| `APPSTORE_API_PRIVATE_KEY` | `.p8` 파일 **내용 전체** (`-----BEGIN PRIVATE KEY-----` 부터) |

그리고 Settings ▸ Secrets and variables ▸ Actions ▸ **Variables**:

| Variable | 값 |
|---|---|
| `API_BASE_URL` | 서버 주소. 오라클 VM 이면 `https://138-2-124-116.sslip.io` (또는 DuckDNS 주소). AWS 면 배포 출력의 `ApiUrl` |

Secret 으로 넣어도 된다. 둘 다 없으면 워크플로가 오라클 서버 주소(`https://138-2-124-116.sslip.io`)를 쓴다.

## 배포하기

1. 워크플로 실행 (`upload` = true). 방법은 둘 중 하나:
   - **Claude 에게 "업로드 돌려줘"** — API 로 실행한다. 지금은 이게 기본이다
   - Actions ▸ **iOS** ▸ Run workflow ▸ 브랜치 선택 ▸ `upload` 체크 ▸ Run. 단 이 버튼은
     워크플로가 **기본 브랜치(main)에 있을 때만** 보인다. 작업 브랜치를 main 에 합치기
     전에는 안 보인다
2. 30분쯤 뒤 App Store Connect ▸ TestFlight 에 빌드가 뜬다. 처음엔 "규정 준수" 질문이 뜰 수 있다 — 암호화 없음(`ITSAppUsesNonExemptEncryption=false` 로 이미 답해뒀다)
3. Internal Testing 그룹에 본인 Apple ID 추가 → 아이폰 TestFlight 앱에서 설치

빌드 번호는 워크플로 실행 번호(`github.run_number`)라 자동으로 올라간다.

## 백엔드와 맞추기

TestFlight 빌드는 `aps-environment: production` 이다. 서버의 APNs 환경도
**`production`** 이어야 푸시가 간다 (오라클 VM: `/etc/jobping/env` 의 `APNS_ENVIRONMENT`,
이미 production 이 기본값이다. AWS: `ApnsEnvironment` 파라미터). `sandbox` 로 두면 APNs 가
`BadDeviceToken` 을 돌려주고 notifier 가 그 기기를 삭제해버린다.

```bash
cd backend && make deploy STAGE=dev   # samconfig.toml 의 parameter_overrides 에 ApnsEnvironment=production
```

## 자주 막히는 곳

| 증상 | 원인 |
|---|---|
| build 잡에서 컴파일 에러 | 코드 문제. 맥 없이 쓴 코드라 첫 실행에서 몇 개 날 수 있다. 로그의 파일:줄 보고 고친다 |
| `No profiles for 'com.sangmin082.jobping'` | App ID 를 안 만들었거나 Bundle ID 가 다르다 |
| `Authentication credentials are invalid` | API 키 역할이 Developer 미만이거나 Issuer ID 가 틀렸다 |
| 업로드는 됐는데 TestFlight 에 안 뜸 | 처리 중(최대 30분). 그 이상이면 App Store Connect 이메일 확인 |
| 앱은 뜨는데 공고가 안 옴 | `API_BASE_URL` 변수를 안 넣었거나 백엔드가 아직 시딩 중 |
| Archive/Export 에서 인증서 한도 오류. Developer 사이트 인증서 추가 화면에 "Maximum number of certificates generated" | 배포 인증서가 한도(3개)까지 찼다. CI 가 만든 인증서(만든 이 `API Key: …`)는 러너와 함께 비밀키가 사라져 쓸모없으니 오래된 것부터 Revoke. **Distribution Managed 는 남긴다** — 클라우드 서명이 쓴다. 다시 쌓이는 건 API 키가 Admin 이 아니어서 클라우드 서명을 못 쓸 때다 |
| Prepare 단계에서 `::error::` | 시크릿 값 문제. 메시지가 어느 값이 어떻게 틀렸는지 말해준다 (공백·끝 슬래시는 자동으로 지운다) |
| 푸시가 안 옴 | 백엔드 `ApnsEnvironment=production` 인지, SSM 에 APNs 키가 있는지 |

## 로컬에서 Xcode 로 열고 싶을 때

```bash
brew install xcodegen
cd ios && cp Config.xcconfig.example Config.xcconfig   # 값 채우기
API_BASE_URL=... DEVELOPMENT_TEAM=... xcodegen generate && open JobPing.xcodeproj
```
