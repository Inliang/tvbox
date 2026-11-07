#!/usr/bin/env bash
# 重新生成固定签名密钥（PKCS12），并写入 keystore/jmgo.p12.b64。
# 注意：一旦用某个密钥签名并安装到设备，之后每次构建都必须用同一个密钥，
#       否则旧 APK 无法覆盖安装（签名不一致）。轮换密钥前请先在设备上卸载旧版。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$HERE/keystore/jmgo.p12.b64"

ALIAS="${KEY_ALIAS:-jmgo}"
PASSWORD="${KEY_PASSWORD:-jmgo-compat-2026}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

openssl req -x509 -newkey rsa:2048 -sha256 -days 36500 -nodes \
  -keyout "$TMP/k.pem" -out "$TMP/c.pem" \
  -subj "/C=CN/O=JMGO Compat/CN=JMGO Compat Signing" 2>/dev/null

openssl pkcs12 -export -out "$TMP/jmgo.p12" -inkey "$TMP/k.pem" -in "$TMP/c.pem" \
  -name "$ALIAS" -passout "pass:$PASSWORD" 2>/dev/null

python - <<PY
import base64, pathlib
data = pathlib.Path("$TMP/jmgo.p12").read_bytes()
pathlib.Path("$OUT").write_text(base64.b64encode(data).decode())
print("wrote", "$OUT", len(data), "bytes")
PY

echo "Done. alias=$ALIAS  (keep KEY_ALIAS/KEY_PASSWORD in sync with the workflow env)"
