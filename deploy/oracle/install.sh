#!/usr/bin/env bash
# 잡핑 서버 설치/업데이트 — Ubuntu 22.04/24.04 (오라클 클라우드 Always Free 기준)
#
#   curl -fsSL https://raw.githubusercontent.com/sangmin082/jobping/claude/jobping-ios-plan-lqbny6/deploy/oracle/install.sh | sudo bash
#
# 다시 실행하면 업데이트다(코드 pull, 의존성 갱신, 서비스 재시작). 설정(/etc/jobping/env)과
# DB(/var/lib/jobping)는 건드리지 않는다.
#
# 환경 변수로 바꿀 수 있는 것:
#   JOBPING_BRANCH   받을 브랜치 (기본: 개발 브랜치. main 에 합쳐지면 main 으로 바꾼다)
#   JOBPING_DOMAIN   HTTPS 도메인을 직접 지정 (가진 도메인이 있으면)
#   DUCKDNS_DOMAIN   DuckDNS 서브도메인 (예: jobping → jobping.duckdns.org)
#   DUCKDNS_TOKEN    DuckDNS 토큰. 둘 다 주면 IP 를 이 VM 으로 맞추고 그 도메인을 쓴다
#
# 셋 다 없으면 <공인IP>.sslip.io 를 쓴다. 도메인 없이 인증서를 받는 방법인데,
# sslip.io 는 공개 접미사 목록에 없어서 Let's Encrypt 발급 한도(도메인당 주 50개)를
# 전 세계 사용자가 나눠 쓴다. 한도가 차 있으면 발급이 막힌다. 그때는 DuckDNS 로:
#   curl -fsSL …/install.sh | sudo DUCKDNS_DOMAIN=jobping DUCKDNS_TOKEN=xxxx bash
set -euo pipefail

REPO="https://github.com/sangmin082/jobping.git"
BRANCH="${JOBPING_BRANCH:-claude/jobping-ios-plan-lqbny6}"
APP=/opt/jobping
DATA=/var/lib/jobping
CONF=/etc/jobping
SVC_USER=jobping

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '    \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "sudo 로 실행해야 한다:  curl … | sudo bash"
command -v apt-get >/dev/null || die "apt 가 없다. Ubuntu 에서만 지원한다."

# ---------------------------------------------------------------- 1. 스왑
# 1GB VM 에선 VS Code 원격 서버만으로 절반이 찬다. 스왑이 없으면 pip 설치나
# 토스(6MB 응답) 파싱 중에 OOM 으로 죽을 수 있다.
say "스왑"
if swapon --show --noheadings | grep -q .; then
  ok "이미 있다: $(swapon --show --noheadings | awk '{print $1, $3}' | tr '\n' ' ')"
else
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ok "2GB 스왑 추가"
fi

# ---------------------------------------------------------------- 2. 패키지
say "패키지"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# iptables-persistent 설치 중 '현재 규칙 저장?' 질문을 미리 답해둔다.
echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections
echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections
apt-get install -y -qq python3 python3-venv git sqlite3 curl caddy iptables-persistent >/dev/null
ok "python3 $(python3 -c 'import sys;print(sys.version.split()[0])'), caddy $(caddy version | awk '{print $1}')"

# ---------------------------------------------------------------- 3. 사용자·디렉터리
say "서비스 계정과 디렉터리"
id "$SVC_USER" >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin "$SVC_USER"
install -d -o "$SVC_USER" -g "$SVC_USER" -m 750 "$DATA"
install -d -o root -g "$SVC_USER" -m 750 "$CONF"
ok "계정 $SVC_USER, DB $DATA, 설정 $CONF"

# ---------------------------------------------------------------- 4. 코드
say "코드 ($BRANCH)"
if [ -d "$APP/.git" ]; then
  # 얕은 클론이라 origin/<브랜치> 참조가 안 생길 수 있다. FETCH_HEAD 로 받는다.
  git -C "$APP" fetch -q --depth 1 origin "$BRANCH"
  git -C "$APP" checkout -q -B "$BRANCH" FETCH_HEAD
else
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$APP"
fi
ok "$(git -C "$APP" log -1 --format='%h %s' | cut -c1-70)"

say "파이썬 의존성"
[ -x "$APP/venv/bin/python" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/backend/src/requirements.txt"
PYTHONPATH="$APP/backend/src" "$APP/venv/bin/python" -c "import jobping.selfhost" \
  || die "패키지 import 실패. 위 pip 출력을 확인할 것."
ok "venv $APP/venv"

# ---------------------------------------------------------------- 5. 설정
say "설정 ($CONF/env)"
if [ -f "$CONF/env" ]; then
  ok "이미 있다 — 건드리지 않는다"
else
  install -o root -g "$SVC_USER" -m 640 "$APP/deploy/oracle/env.example" "$CONF/env"
  ok "새로 만들었다. Slack/APNs 값은 나중에 채운다"
fi

# 편하게 쓰라고:  jobping status / jobping collect
# 설정 파일은 root:jobping 640 이라 ubuntu 계정은 못 읽는다. 서비스 계정으로 바꾼 뒤 읽는다.
cat > /usr/local/bin/jobping <<EOF
#!/usr/bin/env bash
exec sudo -u $SVC_USER bash -c 'set -a; . $CONF/env; set +a; cd $APP/backend; exec env PYTHONPATH=$APP/backend/src $APP/venv/bin/python -m jobping.selfhost "\$@"' _ "\$@"
EOF
chmod 755 /usr/local/bin/jobping
ok "명령 'jobping' 설치 (status / collect / flush)"

# ---------------------------------------------------------------- 6. 방화벽 (VM 안쪽)
# 오라클 Ubuntu 이미지는 22번 외 전부 REJECT 하는 iptables 규칙을 갖고 나온다.
# 80(인증서 발급) 과 443(앱 API) 을 그 REJECT 앞에 끼워 넣는다.
say "방화벽 80/443 (VM 안쪽 iptables)"
for port in 80 443; do
  if iptables -C INPUT -p tcp -m state --state NEW --dport "$port" -j ACCEPT 2>/dev/null; then
    ok "$port 이미 열림"
  else
    pos=$(iptables -L INPUT --line-numbers -n | awk '/REJECT/ {print $1; exit}')
    iptables -I INPUT "${pos:-1}" -p tcp -m state --state NEW --dport "$port" -j ACCEPT
    ok "$port 열었다"
  fi
done
netfilter-persistent save >/dev/null 2>&1 && ok "재부팅 후에도 유지되게 저장"

# ---------------------------------------------------------------- 7. HTTPS (Caddy)
say "HTTPS"
PUBLIC_IP=$(curl -s -4 --max-time 10 ifconfig.me || true)
SAVED_DOMAIN=$(cat "$CONF/domain" 2>/dev/null || true)
if [ -n "${JOBPING_DOMAIN:-}" ]; then
  DOMAIN="$JOBPING_DOMAIN"
elif [ -n "${DUCKDNS_DOMAIN:-}" ] && [ -n "${DUCKDNS_TOKEN:-}" ]; then
  [ -n "$PUBLIC_IP" ] || die "공인 IP 를 못 알아냈다"
  sub="${DUCKDNS_DOMAIN%.duckdns.org}"
  resp=$(curl -s --max-time 15 "https://www.duckdns.org/update?domains=$sub&token=$DUCKDNS_TOKEN&ip=$PUBLIC_IP")
  [ "$resp" = "OK" ] || die "DuckDNS 갱신 실패($resp). 서브도메인과 토큰을 확인할 것."
  DOMAIN="$sub.duckdns.org"
  ok "DuckDNS $DOMAIN → $PUBLIC_IP"
elif [ -n "$SAVED_DOMAIN" ]; then
  # 업데이트하려고 그냥 다시 실행한 경우. 지난번 도메인을 그대로 쓴다.
  DOMAIN="$SAVED_DOMAIN"
else
  [ -n "$PUBLIC_IP" ] || die "공인 IP 를 못 알아냈다. JOBPING_DOMAIN 을 지정해서 다시 실행할 것."
  DOMAIN="${PUBLIC_IP//./-}.sslip.io"
fi
# 다음에 다시 실행할 때 같은 도메인을 쓰도록 남겨둔다.
echo "$DOMAIN" > "$CONF/domain"
cat > /etc/caddy/jobping.caddy <<EOF
# install.sh 가 쓴다. 다시 실행하면 덮어쓴다.
$DOMAIN {
	encode gzip
	reverse_proxy 127.0.0.1:8080
}
EOF
# 기존 Caddyfile 을 함부로 덮지 않는다. 패키지 기본 파일일 때만 바꾸고,
# 직접 쓴 설정이 있으면 import 한 줄만 덧붙인다.
if [ ! -f /etc/caddy/Caddyfile ] || grep -q 'The Caddyfile is an easy way' /etc/caddy/Caddyfile; then
  printf 'import /etc/caddy/jobping.caddy\n' > /etc/caddy/Caddyfile
elif ! grep -q 'import /etc/caddy/jobping.caddy' /etc/caddy/Caddyfile; then
  cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%s)"
  printf '\nimport /etc/caddy/jobping.caddy\n' >> /etc/caddy/Caddyfile
  warn "기존 Caddyfile 이 있어 import 한 줄만 추가했다 (백업 남김)"
fi
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1 || die "Caddyfile 검증 실패"
ok "도메인 $DOMAIN"

# ---------------------------------------------------------------- 8. 서비스
say "서비스"
install -m 644 "$APP"/deploy/oracle/systemd/*.service "$APP"/deploy/oracle/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q --now jobping-api.service jobping-collect.timer jobping-flush.timer
systemctl restart jobping-api.service
systemctl reload-or-restart caddy
ok "jobping-api, 수집 타이머(30분), 발송 타이머(08:00 KST)"

# API 가 뜰 때까지 기다린다. DB 파일도 이때 서비스 계정 소유로 만들어진다.
for _ in $(seq 1 15); do
  curl -fsS --max-time 2 http://127.0.0.1:8080/v1/health >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS --max-time 5 http://127.0.0.1:8080/v1/health >/dev/null \
  || die "API 가 안 뜬다:  journalctl -u jobping-api -n 50"
ok "API (VM 안쪽) 정상"

# 첫 수집 = 시딩. 공고를 전부 저장만 하고 알림은 보내지 않는다(collector.py).
# root 로 sqlite3 를 열면 WAL 파일이 root 소유로 생겨 서비스가 못 쓴다. 반드시 서비스 계정으로.
seeded=$(sudo -u "$SVC_USER" sqlite3 "$DATA/jobping.db" 'SELECT COUNT(*) FROM health' 2>/dev/null || echo 0)
if [ "$seeded" = "0" ]; then
  say "첫 수집 (시딩, 30초~1분)"
  systemctl start jobping-collect.service || warn "첫 수집 실패 — journalctl -u jobping-collect 로 확인"
  journalctl -u jobping-collect -n 5 --no-pager -o cat | grep -E 'collect' | cut -c1-200 || true
fi

# ---------------------------------------------------------------- 9. 확인
say "확인"
if curl -fsS --max-time 20 "https://$DOMAIN/v1/health" >/dev/null 2>&1; then
  ok "HTTPS 바깥에서 접속 정상"
  HTTPS_OK=1
else
  HTTPS_OK=0
fi

echo
echo "──────────────────────────────────────────────────────────────"
if [ "$HTTPS_OK" = 1 ]; then
  echo " 설치 완료."
  echo
  echo "   앱에 넣을 주소 (GitHub ▸ Settings ▸ Variables ▸ API_BASE_URL):"
  echo
  echo "     https://$DOMAIN"
elif journalctl -u caddy --since "-10min" --no-pager -o cat 2>/dev/null | grep -qiE 'rateLimited|too many certificates'; then
  echo " 인증서 발급 한도에 걸렸다 (sslip.io 를 전 세계가 나눠 쓴다)."
  echo
  echo " DuckDNS 로 바꾸면 된다 (무료, 2분):"
  echo "   1) https://www.duckdns.org 에 GitHub 로 로그인"
  echo "   2) 서브도메인 하나 추가 (예: jobping)  — 화면 위쪽 token 을 복사"
  echo "   3) 이 VM 에서:"
  echo "      curl -fsSL https://raw.githubusercontent.com/sangmin082/jobping/$BRANCH/deploy/oracle/install.sh \\"
  echo "        | sudo DUCKDNS_DOMAIN=jobping DUCKDNS_TOKEN=<복사한토큰> bash"
else
  echo " 거의 다 됐다. 바깥에서 HTTPS 가 아직 안 열린다."
  echo
  echo " 오라클 바깥쪽 방화벽에서 80/443 을 열어야 한다 (VM 안쪽은 이미 열었다)."
  echo " 오라클 웹 콘솔 오른쪽 위 '>_' (Cloud Shell) 을 열고 붙여넣는다:"
  echo
  echo "   curl -fsSL https://raw.githubusercontent.com/sangmin082/jobping/$BRANCH/deploy/oracle/open-ports.sh | bash -s $PUBLIC_IP"
  echo
  echo " 연 다음 Caddy 를 재시작하면 1분 안에 인증서를 받는다:"
  echo "   sudo systemctl restart caddy"
  echo "   curl https://$DOMAIN/v1/health      # {\"ok\": true} 가 나오면 끝"
  echo
  echo " 그 주소가 앱에 넣을 API_BASE_URL 이다:  https://$DOMAIN"
fi
echo
echo " 상태 보기:  jobping status"
echo " 로그 보기:  journalctl -u jobping-collect -n 30"
echo "──────────────────────────────────────────────────────────────"
