#!/usr/bin/env bash
# VM 에 80/443 을 연다 — 오라클 Cloud Shell 에서 실행한다.
#
#   curl -fsSL https://raw.githubusercontent.com/sangmin082/jobping/claude/jobping-ios-plan-lqbny6/deploy/oracle/open-ports.sh | bash -s 138.2.124.116
#
# Cloud Shell = 오라클 웹 콘솔 오른쪽 위 ">_" 아이콘. 로그인된 oci CLI 가 들어 있다.
#
# 하는 일:
#   1. 공인 IP 로 VM 과 그 VNIC 을 찾는다 (구독한 모든 리전에서)
#   2. 그 VCN 에 네트워크 보안 그룹 "jobping-web" 을 만든다 (있으면 재사용)
#   3. 거기에 TCP 80, 443 인바운드 규칙을 추가한다 (있으면 건너뜀)
#   4. VM 의 VNIC 에 그 그룹을 붙인다 (기존에 붙은 그룹은 유지)
#
# 서브넷의 보안 목록(Security List)은 건드리지 않는다. 그 API 는 규칙 전체를
# 덮어쓰는 방식이라, 잘못되면 22번(SSH)까지 날아간다. NSG 규칙 추가는 기존
# 규칙을 건드리지 않고, 오라클은 보안 목록과 NSG 중 하나만 허용해도 통과시킨다.
# 다시 실행해도 안전하다.
set -euo pipefail

IP="${1:-}"
NSG_NAME="jobping-web"
PORTS=(80 443)

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()  { printf '    \033[32m✓\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -n "$IP" ] || die "VM 공인 IP 를 넘겨야 한다:  … | bash -s 138.2.124.116"
command -v oci >/dev/null || die "oci 명령이 없다. 오라클 웹 콘솔의 Cloud Shell(>_) 에서 실행할 것."
command -v python3 >/dev/null || die "python3 가 없다."

# oci 출력(JSON)에서 값을 뽑는다. jq 대신 python3 — Cloud Shell 에 확실히 있다.
# oci 는 목록이 비면 아무것도 출력하지 않는다(빈 JSON 도 아니다). 빈 입력은 {} 로 본다.
pj() { python3 -c "import json,sys; d=json.loads(sys.stdin.read() or '{}'); $1"; }

TENANCY_ARGS=()
[ -n "${OCI_TENANCY:-}" ] && TENANCY_ARGS=(--tenancy-id "$OCI_TENANCY")

# ---------------------------------------------------------------- 1. VM 찾기
say "공인 IP $IP 인 VM 찾기"
REGIONS=$(oci iam region-subscription list "${TENANCY_ARGS[@]}" \
  | pj 'print("\n".join(r["region-name"] for r in d.get("data", [])))')
FOUND=""
for region in $REGIONS; do
  instances=$(oci search resource structured-search --region "$region" \
    --query-text "query instance resources where lifecycleState = 'RUNNING'" --limit 1000 \
    | pj 'print("\n".join(i["identifier"]+" "+i["compartment-id"] for i in (d.get("data") or {}).get("items", [])))')
  while read -r inst comp; do
    [ -n "$inst" ] || continue
    hit=$(oci compute instance list-vnics --region "$region" --instance-id "$inst" \
      | pj "
v=[x for x in d.get('data', []) if x.get('public-ip')=='$IP']
print(' '.join([v[0]['id'], v[0]['subnet-id'], json.dumps(v[0].get('nsg-ids') or [])]) if v else '')")
    if [ -n "$hit" ]; then
      FOUND="$region $comp $hit"
      break 2
    fi
  done <<< "$instances"
done
[ -n "$FOUND" ] || die "공인 IP $IP 인 실행 중 VM 을 못 찾았다. IP 를 확인할 것 (VM 에서: curl -4 ifconfig.me)"
read -r REGION COMP VNIC SUBNET NSGS <<< "$FOUND"
ok "리전 $REGION"
ok "VNIC ${VNIC:0:40}…"

VCN=$(oci network subnet get --region "$REGION" --subnet-id "$SUBNET" | pj 'print(d["data"]["vcn-id"])')

# ---------------------------------------------------------------- 2. NSG
say "네트워크 보안 그룹 $NSG_NAME"
NSG=$(oci network nsg list --region "$REGION" --compartment-id "$COMP" --vcn-id "$VCN" \
  --display-name "$NSG_NAME" --lifecycle-state AVAILABLE \
  | pj 'print(d["data"][0]["id"] if d.get("data") else "")')
if [ -n "$NSG" ]; then
  ok "이미 있다 — 재사용"
else
  NSG=$(oci network nsg create --region "$REGION" --compartment-id "$COMP" --vcn-id "$VCN" \
    --display-name "$NSG_NAME" --wait-for-state AVAILABLE | pj 'print(d["data"]["id"])')
  ok "만들었다"
fi

# ---------------------------------------------------------------- 3. 규칙
say "인바운드 규칙"
EXISTING=$(oci network nsg rules list --region "$REGION" --nsg-id "$NSG" --direction INGRESS --all \
  | pj '
ports=set()
for r in d.get("data", []):
    rng=(r.get("tcp-options") or {}).get("destination-port-range") or {}
    if r.get("protocol")=="6" and r.get("source")=="0.0.0.0/0" and rng.get("min")==rng.get("max"):
        ports.add(rng["min"])
print(" ".join(map(str, sorted(ports))))')
TO_ADD=()
for p in "${PORTS[@]}"; do
  if [[ " $EXISTING " == *" $p "* ]]; then ok "TCP $p 이미 열림"; else TO_ADD+=("$p"); fi
done
if [ ${#TO_ADD[@]} -gt 0 ]; then
  RULES=$(python3 -c "
import json,sys
print(json.dumps([{'description': 'jobping https' if p==443 else 'jobping http (인증서 발급)',
  'direction':'INGRESS','protocol':'6','source':'0.0.0.0/0','sourceType':'CIDR_BLOCK',
  'isStateless':False,'tcpOptions':{'destinationPortRange':{'min':p,'max':p}}}
  for p in map(int, sys.argv[1:])]))" "${TO_ADD[@]}")
  oci network nsg rules add --region "$REGION" --nsg-id "$NSG" --security-rules "$RULES" >/dev/null
  ok "TCP ${TO_ADD[*]} 열었다"
fi

# ---------------------------------------------------------------- 4. VNIC 에 붙이기
say "VM 에 연결"
if python3 -c "import json,sys; sys.exit(0 if sys.argv[2] in json.loads(sys.argv[1]) else 1)" "$NSGS" "$NSG"; then
  ok "이미 연결돼 있다"
else
  NEW_NSGS=$(python3 -c "import json,sys; print(json.dumps(json.loads(sys.argv[1])+[sys.argv[2]]))" "$NSGS" "$NSG")
  oci network vnic update --region "$REGION" --vnic-id "$VNIC" --nsg-ids "$NEW_NSGS" --force >/dev/null
  ok "연결했다 (기존 그룹 유지)"
fi

DOMAIN="${IP//./-}.sslip.io"
echo
echo "──────────────────────────────────────────────────────────────"
echo " 바깥쪽 80/443 이 열렸다. 이제 VM 터미널(VS Code)에서:"
echo
echo "   sudo systemctl restart caddy"
echo "   sleep 30"
echo "   curl https://$DOMAIN/v1/health"
echo
echo " {\"ok\": true} 가 나오면 서버 끝."
echo "──────────────────────────────────────────────────────────────"
