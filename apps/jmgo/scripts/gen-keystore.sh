#!/usr/bin/env bash
# 解码签名密钥并生成 local.properties（供上游 app/build.gradle 的 signingConfigs.release 读取）。
# 优先使用 Secrets 注入的 JMGO_KEYSTORE_B64；否则退化为仓库内置的 keystore/jmgo.p12.b64。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="$SCRIPT_DIR/../keystore"
mkdir -p "$KEYS_DIR"

PASS="${JMGO_KEYSTORE_PASS:-jmgo-compat-2026}"
ALIAS="${JMGO_KEY_ALIAS:-jmgo}"
P12="$KEYS_DIR/jmgo.p12"
JKS="$KEYS_DIR/jmgo.jks"
B64="$KEYS_DIR/jmgo.p12.b64"

if [[ -n "${JMGO_KEYSTORE_B64:-}" ]]; then
  echo "$JMGO_KEYSTORE_B64" | base64 -d > "$P12"
else
  base64 -d "$B64" > "$P12"
fi

# PKCS12 -> JKS：上游 signingConfigs 默认按 JKS 读取 storeType
keytool -importkeystore -noprompt \
  -srckeystore "$P12" -srcstoretype PKCS12 -srcstorepass "$PASS" -srcalias "$ALIAS" \
  -destkeystore "$JKS" -deststoretype JKS -deststorepass "$PASS" -destkeypass "$PASS" -destalias "$ALIAS"

cat > "$KEYS_DIR/local.properties" <<EOF
storeFile=$JKS
storePassword=$PASS
keyPassword=$PASS
keyAlias=$ALIAS
EOF

echo "wrote $KEYS_DIR/local.properties (storeFile=$JKS)"
