# 배포 — AWS 서버리스 (SAM)

한 번 세팅하면 이후 배포는 `make deploy` 한 줄이다. 처음엔 아래 순서대로.

## 0. 준비물

| 것 | 어디서 | 비고 |
|---|---|---|
| AWS 계정 + CLI 자격 증명 | `aws configure` | 리전은 `ap-northeast-2`(서울) 권장 — 채용 사이트가 전부 한국이라 지연이 가장 적다 |
| Docker | 로컬 | `sam build --use-container` 가 쓴다. 없으면 `cryptography` 휠이 Mac 용으로 들어가 Lambda 에서 import 가 실패한다 |
| APNs 인증 키 (.p8) | Apple Developer → Keys → APNs | Key ID, Team ID 같이 적어둔다. **한 번만 다운로드된다** |
| Slack Incoming Webhook URL | Slack 앱 설정 | 없어도 배포는 된다. 알림이 로그로만 남을 뿐 |

APNs 는 4단계(iOS 앱)에서 필요하다. **지금 없어도 배포된다** — notifier 가
"APNs 미설정" 로그를 남기고 발송만 건너뛴다. 수집·신규 판정·매칭까지는 다 돈다.

## 1. 비밀값을 SSM Parameter Store 에 넣는다

CloudFormation 파라미터에 넣지 않는다. 스택 이벤트와 콘솔에 값이 남기 때문이다.
SSM 표준 티어 SecureString 은 **무료**다.

```bash
STAGE=dev
aws ssm put-parameter --name /jobping/$STAGE/slack-webhook --type SecureString \
  --value "https://hooks.slack.com/services/XXX/YYY/ZZZ"

# APNs 키가 준비되면 (4단계)
aws ssm put-parameter --name /jobping/$STAGE/apns-key --type SecureString \
  --value "$(cat AuthKey_ABC123.p8)"
```

## 2. 첫 배포

```bash
cd backend
make install                 # .venv + sam cli
make test                    # 231개, 네트워크 불필요
make validate                # 템플릿 lint
make build                   # Docker 안에서 arm64 휠로 빌드
make deploy-first STAGE=dev  # sam deploy --guided
```

`--guided` 가 묻는 것:

- Stack Name: `jobping-dev`
- Region: `ap-northeast-2`
- Parameter `ApnsKeyId` / `ApnsTeamId` / `ApnsBundleId`: 4단계 전이면 비워둔다
- Confirm changes / Allow IAM role creation: Y
- Save arguments to configuration file: Y → `samconfig.toml` 생성 (gitignore 됨)

끝나면 30분마다 collector 가 돈다. 첫 실행은 **시딩**이라 전체 공고를 저장만
하고 알림은 보내지 않는다(`collector.py` 참고). 두 번째 실행부터 신규가 잡힌다.

## 3. 확인

```bash
make invoke STAGE=dev        # 지금 바로 한 번 수집
make logs STAGE=dev          # collector 로그 tail
```

로그에 `collector: coupang:359/359 SEED skcareers:88/88 SEED …` 처럼 한 줄
요약이 남는다. `SEED` 가 사라지고 `naver:31/2` 같은 줄이 보이면 신규 2건이
notifier 로 넘어간 것이다.

DynamoDB 콘솔에서 `jobping-dev-adapter-health` 를 보면 소스별 마지막 성공
시각·건수·연속 실패 횟수가 있다.

## 4. 이후 배포

```bash
make deploy STAGE=dev        # build + deploy, 확인 없이
```

## 5. 비용 (예상)

| 항목 | 월 |
|---|---|
| Lambda (collector 48회/일 × ~15초 × 1GB) | ~$0.30 |
| DynamoDB on-demand (수천 건 규모) | ~$0.10 |
| SQS, EventBridge, CloudWatch 기본 | 프리티어 안 |
| SSM 표준 파라미터 | $0 |
| **합계** | **$1 미만** |

전송량은 토스 응답(6MB × 48회 = ~300MB/일)이 대부분인데, Lambda 인바운드는
과금되지 않는다.

## 6. 운영 알림이 오는 경우

| Slack 메시지 | 뜻 | 할 일 |
|---|---|---|
| `:x: naver 수집 실패 (N회 연속)` | 어댑터 예외 | `make verify A=naver` 로 로컬 재현. 사이트 구조 변경이면 어댑터 수정 |
| `:thinking_face: … 3회 연속 0건` | 1시간 반 동안 0건 | 진짜 0건인지(야놀자처럼) 필터가 다 걸러내는지 확인 |
| `:warning: … 신규 N/M건 — 폭증` | job_id 체계나 사이트 개편 의심 | 알림은 자동으로 보류됐다. 원인 확인 후 다음 실행부터 정상 |
| `:x: APNs 발송 실패 N건` | Apple 쪽 오류 | 로그의 reason 확인. `BadDeviceToken` 은 sandbox/production 불일치가 대부분 |

## 7. 프로덕션

`STAGE=prod` 로 같은 절차. 스택·테이블·큐 이름이 전부 `jobping-prod-*` 로 갈리고
SSM 경로도 `/jobping/prod/*` 다. APNs 는 `ApnsEnvironment=production`.
