#!/usr/bin/env python3
"""TestFlight 서명 준비 — 기기 등록 없이 App Store 배포 서명을 만든다.

입력은 배포 인증서용 RSA 비밀키 하나다(GitHub 시크릿). 나머지는 App Store Connect
API 로 처리한다:

  1. 이 비밀키에 맞는 Apple Distribution 인증서를 찾는다. 없으면 CSR 을 만들어 발급받는다
     (첫 실행 한 번만). 그래서 실행마다 인증서가 쌓이지 않는다.
  2. App ID 에 Push Notifications 가 꺼져 있으면 켠다.
  3. App Store 프로비저닝 프로파일을 새로 만든다 (같은 이름의 이전 것은 지운다).
     App Store 프로파일은 기기 목록이 필요 없다.

결과물 (OUT_DIR):
  dist.p12               키체인에 넣을 인증서+비밀키 (암호: P12_PASSWORD)
  <UUID>.mobileprovision 프로파일

표준 라이브러리와 openssl 명령만 쓴다 — 러너에 pip 설치가 필요 없다.

환경 변수:
  ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_PATH   App Store Connect API 키 (.p8)
  DIST_KEY_PATH                             배포 인증서 비밀키 (RSA 2048, PEM)
  BUNDLE_ID, PROFILE_NAME, OUT_DIR, P12_PASSWORD
  ASC_API_BASE                              테스트용. 기본은 Apple 서버
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = os.environ.get("ASC_API_BASE", "https://api.appstoreconnect.apple.com/v1")


class Fail(Exception):
    pass


def openssl(*args: str, data: bytes | None = None) -> bytes:
    r = subprocess.run(["openssl", *args], input=data, capture_output=True)
    if r.returncode != 0:
        raise Fail(f"openssl {args[0]} 실패: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


# ---- JWT (ES256) ---------------------------------------------------------------


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _der_to_raw(sig: bytes) -> bytes:
    """openssl 이 내는 DER ECDSA 서명을 JWT 가 쓰는 r||s (각 32바이트) 로 바꾼다."""

    def read_len(i: int) -> tuple[int, int]:
        n = sig[i]
        if n < 0x80:
            return n, i + 1
        k = n & 0x7F
        return int.from_bytes(sig[i + 1 : i + 1 + k], "big"), i + 1 + k

    if sig[0] != 0x30:
        raise Fail("ECDSA 서명 형식이 이상하다")
    _, i = read_len(1)
    out = b""
    for _ in range(2):
        if sig[i] != 0x02:
            raise Fail("ECDSA 서명 형식이 이상하다")
        n, i = read_len(i + 1)
        out += sig[i : i + n].lstrip(b"\x00").rjust(32, b"\x00")
        i += n
    return out


def make_token(key_id: str, issuer: str, key_path: str) -> str:
    now = int(time.time())
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    payload = {"iss": issuer, "iat": now, "exp": now + 15 * 60, "aud": "appstoreconnect-v1"}
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    der = openssl("dgst", "-sha256", "-sign", key_path, data=signing_input.encode())
    return signing_input + "." + _b64url(_der_to_raw(der))


# ---- API -------------------------------------------------------------------------


class Asc:
    def __init__(self, token: str):
        self.token = token

    def call(self, method: str, path: str, body: dict | None = None, query: dict | None = None):
        url = API + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, data=data, timeout=60) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            try:
                errs = json.loads(detail).get("errors", [])
                detail = " / ".join(f"{x.get('title', '')}: {x.get('detail', '')}" for x in errs) or detail
            except ValueError:
                pass
            raise ApiError(e.code, f"{method} {path} → {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise Fail(f"{method} {path} 연결 실패: {e.reason}") from None
        return json.loads(raw) if raw else None


class ApiError(Fail):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


# ---- 단계 --------------------------------------------------------------------------


def public_key_of_private(key_path: str) -> str:
    return openssl("pkey", "-in", key_path, "-pubout").decode().strip()


def public_key_of_cert(der: bytes) -> str:
    return openssl("x509", "-inform", "DER", "-noout", "-pubkey", data=der).decode().strip()


def check_rsa(key_path: str) -> None:
    text = openssl("pkey", "-in", key_path, "-noout", "-text").decode()
    if "modulus" not in text.lower():
        raise Fail(
            "DIST_CERT_PRIVATE_KEY 가 RSA 키가 아니다. APNs/API 키(.p8)를 넣은 것 같다 — "
            "docs/IOS.md 의 openssl genrsa 명령으로 만든 키를 넣는다"
        )


def find_or_create_certificate(asc: Asc, key_path: str) -> tuple[str, bytes]:
    mine = public_key_of_private(key_path)
    res = asc.call(
        "GET",
        "/certificates",
        query={"filter[certificateType]": "DISTRIBUTION,IOS_DISTRIBUTION", "limit": "200"},
    )
    existing = res.get("data", [])
    for c in existing:
        der = base64.b64decode(c["attributes"]["certificateContent"])
        if public_key_of_cert(der) == mine:
            print(f"인증서: 기존 것 사용 ({c['attributes'].get('name')}, 만료 {c['attributes'].get('expirationDate')})")
            return c["id"], der

    print("인증서: 이 비밀키로 발급된 게 없다 → 새로 발급 (첫 실행)")
    csr = openssl("req", "-new", "-key", key_path, "-subj", "/CN=JobPing CI/C=KR").decode()
    try:
        res = asc.call(
            "POST",
            "/certificates",
            body={"data": {"type": "certificates", "attributes": {"certificateType": "DISTRIBUTION", "csrContent": csr}}},
        )
    except ApiError as e:
        lines = [str(e), "", "배포 인증서를 더 만들 수 없다 (한도 3개). 지금 있는 배포 인증서:"]
        for c in existing:
            a = c["attributes"]
            lines.append(f"  - {a.get('name')} / {a.get('certificateType')} / 만료 {a.get('expirationDate')}")
        lines.append(
            "developer.apple.com ▸ Certificates 에서 CI 가 만든 것(만든 이 'API Key: …') 하나를 Revoke 하고 "
            "다시 실행한다. Distribution Managed 는 남긴다."
        )
        raise Fail("\n".join(lines)) from None
    c = res["data"]
    print(f"인증서: 발급됨 ({c['attributes'].get('name')}, 만료 {c['attributes'].get('expirationDate')})")
    return c["id"], base64.b64decode(c["attributes"]["certificateContent"])


def find_bundle_id(asc: Asc, identifier: str) -> str:
    res = asc.call("GET", "/bundleIds", query={"filter[identifier]": identifier, "limit": "200"})
    for b in res.get("data", []):
        if b["attributes"].get("identifier") == identifier:
            return b["id"]
    raise Fail(
        f"App ID '{identifier}' 가 없다. developer.apple.com ▸ Identifiers 에서 만들거나 ios/project.yml 의 Bundle ID 를 확인한다"
    )


def ensure_push(asc: Asc, bundle_id: str) -> None:
    # 관계 경로라 limit 를 받지 않는다 (넣으면 400).
    res = asc.call("GET", f"/bundleIds/{bundle_id}/bundleIdCapabilities")
    kinds = {c["attributes"].get("capabilityType") for c in res.get("data", [])}
    if "PUSH_NOTIFICATIONS" in kinds:
        print("App ID: Push Notifications 켜져 있음")
        return
    asc.call(
        "POST",
        "/bundleIdCapabilities",
        body={
            "data": {
                "type": "bundleIdCapabilities",
                "attributes": {"capabilityType": "PUSH_NOTIFICATIONS"},
                "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bundle_id}}},
            }
        },
    )
    print("App ID: Push Notifications 켰음")


def make_profile(asc: Asc, name: str, bundle_id: str, cert_id: str) -> tuple[str, bytes]:
    # 같은 이름의 이전 프로파일은 지운다 — 인증서·기능이 바뀌었을 수 있고, 이름이 겹치면
    # Xcode 가 어느 걸 쓸지 모른다.
    res = asc.call("GET", "/profiles", query={"filter[name]": name, "limit": "200"})
    for p in res.get("data", []):
        if p["attributes"].get("name") == name:
            asc.call("DELETE", f"/profiles/{p['id']}")
            print(f"프로파일: 이전 것 삭제 ({p['id']})")
    res = asc.call(
        "POST",
        "/profiles",
        body={
            "data": {
                "type": "profiles",
                "attributes": {"name": name, "profileType": "IOS_APP_STORE"},
                "relationships": {
                    "bundleId": {"data": {"type": "bundleIds", "id": bundle_id}},
                    "certificates": {"data": [{"type": "certificates", "id": cert_id}]},
                },
            }
        },
    )
    a = res["data"]["attributes"]
    print(f"프로파일: 생성 ({name}, {a['uuid']}, 만료 {a.get('expirationDate')})")
    return a["uuid"], base64.b64decode(a["profileContent"])


def write_p12(key_path: str, cert_der: bytes, out: Path, password: str) -> None:
    # macOS `security import` 는 OpenSSL 3 의 기본(AES) p12 를 못 읽는 경우가 있어
    # 예전 형식(3DES, SHA1 MAC)으로 만든다.
    with tempfile.TemporaryDirectory() as d:
        cert_pem = Path(d) / "cert.pem"
        cert_pem.write_bytes(openssl("x509", "-inform", "DER", "-outform", "PEM", data=cert_der))
        args = [
            "pkcs12", "-export", "-inkey", key_path, "-in", str(cert_pem),
            "-out", str(out), "-passout", f"pass:{password}",
            "-certpbe", "PBE-SHA1-3DES", "-keypbe", "PBE-SHA1-3DES",
        ]
        if not openssl("version").decode().startswith("LibreSSL"):
            args += ["-macalg", "sha1"]
        openssl(*args)


def main() -> int:
    env = os.environ
    try:
        out = Path(env["OUT_DIR"])
        out.mkdir(parents=True, exist_ok=True)
        check_rsa(env["DIST_KEY_PATH"])
        asc = Asc(make_token(env["ASC_KEY_ID"], env["ASC_ISSUER_ID"], env["ASC_KEY_PATH"]))
        cert_id, cert_der = find_or_create_certificate(asc, env["DIST_KEY_PATH"])
        bundle_id = find_bundle_id(asc, env["BUNDLE_ID"])
        ensure_push(asc, bundle_id)
        uuid, profile = make_profile(asc, env["PROFILE_NAME"], bundle_id, cert_id)
        (out / f"{uuid}.mobileprovision").write_bytes(profile)
        write_p12(env["DIST_KEY_PATH"], cert_der, out / "dist.p12", env["P12_PASSWORD"])
    except Fail as e:
        for line in str(e).splitlines():
            print(f"::error::{line}" if line.strip() else "")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
