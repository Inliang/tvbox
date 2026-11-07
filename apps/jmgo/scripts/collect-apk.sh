#!/usr/bin/env bash
# 收集并静态校验构建产物：重命名为统一命名、计算 sha256、写 build-info.json 与 SHA256SUMS.txt。
# 用法：collect-apk.sh <上游目录> <输出目录> [commit短哈希]
set -euo pipefail

UP="$1"
OUT="$2"
SHORT="${3:-${GITHUB_SHA:-$(git rev-parse --short HEAD)}}"
BT="${BUILD_TOOLS:-37.0.0}"

mkdir -p "$OUT"

for abi in arm64_v8a armeabi_v7a; do
  # AbiApkPackaging 把产物导出到 Release/apk/；个别版本可能留在 gradle 输出目录，做兜底。
  src="$UP/Release/apk/leanback-${abi}.apk"
  if [[ ! -f "$src" ]]; then
    src="$UP/app/build/outputs/apk/leanback/release/leanback-${abi}.apk"
  fi
  if [[ ! -f "$src" ]]; then
    echo "MISSING: leanback-${abi}.apk (tried Release/apk and gradle outputs)" >&2
    exit 1
  fi
  cp "$src" "$OUT/tvbox-jmgo-leanback-${abi}-5.8.7-${SHORT}.apk"
done

cd "$OUT"
sha256sum tvbox-jmgo-leanback-*.apk > SHA256SUMS.txt

APK="$ANDROID_HOME/build-tools/$BT/apksigner"
AAPT="$ANDROID_HOME/build-tools/$BT/aapt"
for f in tvbox-jmgo-leanback-*.apk; do
  echo "== verify $f =="
  if [[ -x "$APK" ]]; then "$APK" verify --verbose "$f" || true; fi
  if [[ -x "$AAPT" ]]; then "$AAPT" dump badging "$f" | grep -E "package:|native-code|launchable-activity|uses-permission:.*INTERNET" || true; fi
done

python3 - "$OUT" "$SHORT" "$BT" <<'PY'
import json, sys, os, hashlib, glob
out, short, bt = sys.argv[1], sys.argv[2], sys.argv[3]
info = {"project": "tvbox-jmgo", "versionName": "5.8.7", "commitShort": short,
        "buildTools": bt, "abis": ["arm64_v8a", "armeabi_v7a"], "artifacts": []}
for f in sorted(glob.glob(os.path.join(out, "tvbox-jmgo-leanback-*.apk"))):
    h = hashlib.sha256(open(f, "rb").read()).hexdigest()
    info["artifacts"].append({
        "file": os.path.basename(f), "sha256": h,
        "abi": "arm64_v8a" if "arm64" in f else "armeabi_v7a",
    })
json.dump(info, open(os.path.join(out, "build-info.json"), "w"), indent=2, ensure_ascii=False)
print(json.dumps(info, ensure_ascii=False, indent=2))
PY

echo "collected to $OUT"
