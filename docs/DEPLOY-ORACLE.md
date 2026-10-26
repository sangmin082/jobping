# 배포 — 오라클 클라우드 VM (무료)

오라클 Always Free VM 한 대에 서버 전체를 올린다. 월 비용 0원이다.
AWS 판(`docs/DEPLOY.md`)과 수집·매칭·알림 코드는 같고, 실행 방식만 다르다.

| AWS | 오라클 VM |
|---|---|
| DynamoDB | SQLite 파일 하나 (`/var/lib/jobping/jobping.db`) |
| EventBridge 30분 | systemd 타이머 30분 |
| SQS → notifier Lambda | 같은 프로세스에서 수집 직후 바로 발송 |
| API Gateway + Lambda | 파이썬 내장 HTTP 서버 + Caddy(HTTPS 자동) |
| SSM Parameter Store | `/etc/jobping/env` |

확인된 VM 사양(2026-10-26): Ubuntu 24.04, Python 3.12, 메모리 954MB, 공인 IP
`138.2.124.116`. 채용 사이트 접속 정상.

## 1. 설치 — 명령 한 줄

VS Code 에서 VM 에 SSH 로 붙은 터미널(`ubuntu@instance-…`)에 붙여넣는다.

```bash
curl -fsSL https://raw.githubusercontent.com/sangmin082/jobping/claude/jobping-ios-plan-lqbny6/deploy/oracle/install.sh | sudo bash
```

3~5분 걸린다. 하는 일:

1. 스왑 2GB 추가 — 1GB VM 에선 VS Code 원격 서버만으로 절반이 찬다
2. 패키지 설치 (python3-venv, caddy, sqlite3, iptables-persistent)
3. 서비스 계정 `jobping`, 코드 `/opt/jobping`, DB `/var/lib/jobping`
4. VM 안쪽 방화벽에서 80·443 열기
5. Caddy 로 HTTPS 설정 (`138-2-124-116.sslip.io`)
6. API 서버, 수집 타이머(30분), 발송 타이머(매일 08:00 KST) 시작
7. **첫 수집 = 시딩.** 공고 ~1,200건을 저장만 하고 알림은 안 보낸다

## 2. 오라클 콘솔에서 포트 열기 — 한 번만

VM 안쪽 방화벽은 스크립트가 열었지만, 오라클 네트워크 바깥쪽 방화벽은 콘솔에서만
열 수 있다. 이게 닫혀 있으면 인증서도 못 받고 앱도 서버에 못 붙는다.

1. https://cloud.oracle.com 로그인
2. 메뉴 ▸ **Networking** ▸ **Virtual cloud networks** ▸ VCN 클릭
3. **Subnets** ▸ 서브넷 클릭 ▸ **Security Lists** ▸ **Default Security List…** 클릭
4. **Add Ingress Rules** 를 눌러 두 줄 추가:

   | Source CIDR | IP Protocol | Destination Port Range |
   |---|---|---|
   | `0.0.0.0/0` | TCP | `80` |
   | `0.0.0.0/0` | TCP | `443` |

5. VM 터미널에서:

   ```bash
   sudo systemctl restart caddy
   sleep 30
   curl https://138-2-124-116.sslip.io/v1/health
   ```

   `{"ok": true}` 가 나오면 끝이다.

## 3. 앱에 주소 알려주기

GitHub ▸ 저장소 ▸ Settings ▸ Secrets and variables ▸ Actions ▸ **Variables** ▸
`API_BASE_URL` = `https://138-2-124-116.sslip.io`

이후 TestFlight 빌드가 이 주소로 붙는다 (`docs/IOS.md`).

## 인증서가 안 나올 때 — DuckDNS

`sslip.io` 는 공개 접미사 목록에 없어서 Let's Encrypt 발급 한도(도메인당 주 50개)를
전 세계 사용자가 나눠 쓴다. 대부분은 되지만 한도가 차 있으면 막힌다. 설치 스크립트가
`rateLimited` 를 감지하면 아래를 안내한다.

1. https://www.duckdns.org 에 GitHub 로 로그인
2. 서브도메인 하나 추가 (예: `jobping`). 화면 위쪽 **token** 복사
3. VM 에서 다시 실행:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/sangmin082/jobping/claude/jobping-ios-plan-lqbny6/deploy/oracle/install.sh \
     | sudo DUCKDNS_DOMAIN=jobping DUCKDNS_TOKEN=<복사한토큰> bash
   ```

   스크립트가 DuckDNS 에 VM IP 를 등록하고 `jobping.duckdns.org` 로 인증서를 받는다.
   DuckDNS 는 공개 접미사 목록에 있어서 서브도메인마다 한도가 따로다.
   이 경우 `API_BASE_URL` 은 `https://jobping.duckdns.org` 다.

## 운영

```bash
jobping status                          # 소스별 마지막 수집, 테이블 건수
journalctl -u jobping-collect -n 30     # 최근 수집 로그
journalctl -u jobping-api -f            # API 로그
systemctl list-timers 'jobping*'        # 다음 실행 시각
sudo systemctl start jobping-collect    # 지금 바로 한 번 수집
```

**업데이트**: 설치 명령을 그대로 다시 실행한다. 코드·의존성만 바뀌고 설정과 DB 는
그대로다. 지난번 도메인도 기억한다.

**설정**: `/etc/jobping/env`. 바꾼 뒤 `sudo systemctl restart jobping-api`.

- `SLACK_WEBHOOK_URL` — 수집 실패·폭증 같은 운영 알림. 비우면 로그로만 남는다
- `APNS_*` — Apple 세팅 후 채운다. 비어 있어도 수집·매칭은 돌고 발송만 건너뛴다.
  `.p8` 파일은 `/etc/jobping/apns.p8` 에 두고:
  ```bash
  sudo chown root:jobping /etc/jobping/apns.p8 && sudo chmod 640 /etc/jobping/apns.p8
  ```

**메모리**: 서비스마다 상한을 걸어뒀다(API 200MB, 수집 400MB). 넘으면 그 서비스만
재시작되고 VM 은 안전하다.

**백업**: DB 는 파일 하나다. `sudo -u jobping sqlite3 /var/lib/jobping/jobping.db ".backup /tmp/jobping.bak"`
