#!/usr/bin/env python3
"""Collect, validate and package the two jmgo leanback APKs produced by Gradle.

Locates leanback-arm64_v8a.apk / leanback-armeabi_v7a.apk under --apk-dir,
renames them to the contract artifact names, runs aapt2/apksigner static
checks (best-effort), and writes build-info.json + SHA256SUMS.txt into --out-dir.
"""

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_build_tools(android_home: str):
    if not android_home:
        return None
    cands = sorted(glob.glob(os.path.join(android_home, "build-tools", "*")), reverse=True)
    return cands[0] if cands else None


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as e:  # noqa
        class R:  # minimal stub
            returncode = -1
            stdout = ""
            stderr = str(e)
        return R()


def aapt_badging(aapt2: str, apk: Path) -> dict:
    r = run([aapt2, "dump", "badging", str(apk)])
    out = r.stdout or ""
    info = {"raw": out[:4000]}
    m = re.search(r"package: name='([^']+)'", out)
    if m:
        info["package"] = m.group(1)
    m = re.search(r"versionName='([^']*)'", out)
    if m:
        info["versionName"] = m.group(1)
    m = re.search(r"targetSdkVersion:'([^']*)'", out)
    if m:
        info["targetSdkVersion"] = m.group(1)
    info["nativeCode"] = re.findall(r"native-code: '([^']+)'", out)
    info["leanbackLauncher"] = "LEANBACK_LAUNCHER" in out
    return info


def apksigner_verify(apksigner: str, apk: Path) -> dict:
    r = run(["java", "-jar", apksigner, "verify", "--print-certs", str(apk)])
    out = (r.stdout or "") + (r.stderr or "")
    return {
        "signed": "Signed" in out or r.returncode == 0,
        "certSha256": re.findall(r"SHA-256 digest: ([0-9A-Fa-f:]+)", out),
        "returncode": r.returncode,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--android-home", default=os.environ.get("ANDROID_HOME", ""))
    ap.add_argument("--upstream-sha", default="")
    ap.add_argument("--repo-sha", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--patches-json", default="")
    ap.add_argument("--version", default="5.8.7")
    args = ap.parse_args()

    apk_dir = Path(args.apk_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # locate the two APKs by filename marker
    abi_map = {"arm64_v8a": "arm64_v8a", "armeabi_v7a": "armeabi_v7a"}
    found = {}
    for p in sorted(glob.glob(str(apk_dir / "leanback-*.apk"))):
        name = Path(p).name
        for marker, abi in abi_map.items():
            if marker in name and abi not in found:
                found[abi] = Path(p)
    missing = [a for a in ("arm64_v8a", "armeabi_v7a") if a not in found]
    if missing:
        print(f"[collect_apk] MISSING abi(s): {missing} in {apk_dir}", file=sys.stderr)
        print(f"[collect_apk] available: {[Path(p).name for p in glob.glob(str(apk_dir / '*.apk'))]}",
              file=sys.stderr)
        sys.exit(1)

    bt = find_build_tools(args.android_home)
    aapt2 = os.path.join(bt, "aapt2") if bt else None
    apksigner = os.path.join(bt, "lib", "apksigner.jar") if bt else None

    repo_short = (args.repo_sha or "unknown")[:8]
    apks = []
    sums = []
    for abi, src in found.items():
        dst_name = f"tvbox-jmgo-leanback-{abi}-{args.version}-{repo_short}.apk"
        dst = out_dir / dst_name
        shutil.copyfile(src, dst)
        digest = sha256_of(dst)
        sums.append(f"{digest}  {dst_name}")
        entry = {"abi": abi, "file": dst_name, "sha256": digest}
        if aapt2 and Path(aapt2).exists():
            entry["badging"] = aapt_badging(aapt2, dst)
        if apksigner and Path(apksigner).exists():
            entry["sign"] = apksigner_verify(apksigner, dst)
        apks.append(entry)
        print(f"[collect_apk] {abi}: {dst_name} ({digest[:16]}...)")

    # soft validation
    problems = []
    for e in apks:
        b = e.get("badging")
        if b:
            if b.get("package") and b["package"] != "com.fongmi.android.tv":
                problems.append(f"{e['abi']}: package={b['package']} (expected com.fongmi.android.tv)")
            if not b.get("leanbackLauncher"):
                problems.append(f"{e['abi']}: missing LEANBACK_LAUNCHER")
            nc = b.get("nativeCode", [])
            if e["abi"] == "arm64_v8a" and "arm64-v8a" not in nc:
                problems.append(f"{e['abi']}: native-code missing arm64-v8a ({nc})")
            if e["abi"] == "armeabi_v7a" and "armeabi-v7a" not in nc:
                problems.append(f"{e['abi']}: native-code missing armeabi-v7a ({nc})")
        s = e.get("sign")
        if s and not s.get("signed"):
            problems.append(f"{e['abi']}: apksigner verify failed")

    patches = {}
    if args.patches_json and Path(args.patches_json).is_file():
        try:
            patches = json.loads(Path(args.patches_json).read_text(encoding="utf-8"))
        except Exception:  # noqa
            patches = {}

    (out_dir / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    build_info = {
        "product": "tvbox-jmgo",
        "device": "JMGO N1S 4K (J31-8K2, Android 11)",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "githubRunId": args.run_id,
        "repoSha": args.repo_sha,
        "upstreamRepo": "FongMi/TV",
        "upstreamSha": args.upstream_sha,
        "versionName": args.version,
        "apks": apks,
        "patches": patches,
        "validation": {
            "problems": problems,
            "ok": len(problems) == 0,
            "note": "soft checks; aapt2/apksigner absent => checks skipped, not failed",
        },
    }
    (out_dir / "build-info.json").write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[collect_apk] SHA256SUMS.txt + build-info.json written")
    if problems:
        print("[collect_apk] VALIDATION PROBLEMS:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
    else:
        print("[collect_apk] validation: OK")


if __name__ == "__main__":
    main()
