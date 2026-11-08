#!/usr/bin/env python3
"""官方包聚合流水线的机械校验与产物打包。

纯 Python 实现，便于在开发者本机复现（不依赖 Gradle / NDK / 源码树）。

子命令：
  verify       逐包校验 4 个官方 5.8.7 asset，写出 upstream-verify.json（默认）
  package      校验通过后统一重命名、生成 SHA256SUMS.txt 与 build-info.json
  list-assets  逐行输出 4 个官方 asset 文件名
  self-test    用伪造包证明「任一断言失败即非零退出」

设计约束：
  - 任一断言失败 -> 写出含失败明细的 upstream-verify.json、stderr 打印
    "FAIL <assetName>: <reason>"、非零退出。绝不静默继续。
  - 只认固定 tag 5.8.7 的 4 个固定文件名，禁止 fallback 到其它版本。
  - 不实现任何二进制改造，compatPatchStatus 恒为 "not-applied"。
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

UPSTREAM_REPO = "FongMi/Release"
UPSTREAM_TAG = "5.8.7"
SOURCE_URL_PREFIX = "https://github.com/FongMi/Release/releases/download/5.8.7/"
EXPECTED_PACKAGE = "com.fongmi.android.tv"
EXPECTED_VERSION_NAME = "5.8.7"
MIN_SIZE_BYTES = 30 * 1024 * 1024
BUILD_TOOLS_VERSION = "34.0.0"

# (flavor, abi_token, native_abi, 官方 asset 精确字节数)
# 精确大小来自已核实事实，用于「零偏差」核验：大小不符即判定下错版本或
# 官方 asset 被替换，直接终止，不静默放过。
ASSETS = [
    ("leanback", "arm64_v8a",   "arm64-v8a",   51412139),
    ("leanback", "armeabi_v7a", "armeabi-v7a", 44768123),
    ("mobile",   "arm64_v8a",   "arm64-v8a",   51326563),
    ("mobile",   "armeabi_v7a", "armeabi-v7a", 44682547),
]


def asset_name(flavor: str, abi_token: str) -> str:
    return f"{flavor}-{abi_token}.apk"


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_tool(name, build_tools_dir=None, android_home=None):
    """按 显式 build-tools 目录 -> ANDROID_HOME -> PATH 的顺序定位工具。"""
    candidates = []
    if build_tools_dir:
        candidates.append(os.path.join(build_tools_dir, name))
    if android_home:
        candidates.append(os.path.join(android_home, "build-tools", BUILD_TOOLS_VERSION, name))
        bt_root = os.path.join(android_home, "build-tools")
        if os.path.isdir(bt_root):
            for ver in sorted(os.listdir(bt_root), reverse=True):
                candidates.append(os.path.join(bt_root, ver, name))
    on_path = shutil.which(name)
    if on_path:
        candidates.append(on_path)
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def resolve_tools(android_home, build_tools_dir):
    aapt_tools = [p for p in (
        find_tool("aapt2", build_tools_dir, android_home),
        find_tool("aapt", build_tools_dir, android_home),
    ) if p]
    return {
        "aapt": aapt_tools,
        "apksigner": find_tool("apksigner", build_tools_dir, android_home),
    }


def parse_badging(text):
    """兼容 aapt / aapt2 输出中单引号或双引号包裹的字段值。"""
    package = version = target_sdk = None
    native_code = []
    quote = r"['\"]"
    for line in text.splitlines():
        if line.startswith("package:"):
            m = re.search(r"name=" + quote + r"([^'\"]+)" + quote, line)
            if m:
                package = m.group(1)
            m = re.search(r"versionName=" + quote + r"([^'\"]+)" + quote, line)
            if m:
                version = m.group(1)
            m = re.search(r"targetSdkVersion:" + quote + r"([^'\"]+)" + quote, line)
            if m:
                target_sdk = m.group(1)
        elif line.startswith("native-code:"):
            native_code = re.findall(quote + r"([^'\"]+)" + quote, line)
    return {
        "package": package,
        "versionName": version,
        "targetSdkVersion": target_sdk,
        "nativeCode": native_code,
    }


def badging_info(apk, aapt_tools):
    """优先 aapt2 dump badging；输出格式不兼容时回退 aapt dump badging。"""
    for tool in aapt_tools:
        try:
            proc = subprocess.run(
                [tool, "dump", "badging", apk],
                capture_output=True, text=True, timeout=180,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0 or "package:" not in proc.stdout:
            continue
        info = parse_badging(proc.stdout)
        if info["package"] and info["versionName"]:
            return info, os.path.basename(tool)
    return None, None


def zip_integrity(apk):
    """unzip -t 完整性；无 unzip 时回退纯 Python zipfile.testzip。"""
    unzip = shutil.which("unzip")
    if unzip:
        try:
            proc = subprocess.run(
                [unzip, "-t", apk], capture_output=True, text=True, timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"unzip -t 执行异常: {exc}", "unzip -t"
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip()[-500:]
            return False, f"unzip -t 失败 (exit={proc.returncode}): {tail}", "unzip -t"
        return True, "", "unzip -t"
    try:
        with zipfile.ZipFile(apk) as zf:
            bad = zf.testzip()
        if bad is not None:
            return False, f"zipfile.testzip 发现损坏条目: {bad}", "zipfile.testzip"
        return True, "", "zipfile.testzip"
    except Exception as exc:
        return False, f"ZIP 完整性检查异常: {exc}", "zipfile.testzip"


def detect_zip_abis(apk):
    """从 APK 内 lib/<abi>/ 目录直接读取 ABI，不依赖 aapt 是否输出 native-code 行。"""
    try:
        with zipfile.ZipFile(apk) as zf:
            names = zf.namelist()
    except Exception:
        return []
    abis = set()
    for name in names:
        parts = name.split("/")
        if len(parts) >= 2 and parts[0] == "lib" and parts[1]:
            abis.add(parts[1])
    return sorted(abis)


def signing_info(apk, apksigner):
    if not apksigner:
        return None, "未找到 apksigner（需 build-tools;34.0.0）"
    try:
        proc = subprocess.run(
            [apksigner, "verify", "--verbose", "--print-certs", apk],
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"apksigner 执行异常: {exc}"
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        return None, f"apksigner verify 失败 (exit={proc.returncode}): {out.strip()[-500:]}"
    digest = None
    for line in out.splitlines():
        if "SHA-256 digest" in line:
            m = re.search(r"SHA-256 digest:\s*([0-9a-fA-F:]+)", line)
            if m:
                digest = m.group(1).replace(":", "").lower()
                break
    if not digest or len(digest) != 64:
        return None, f"未能解析签名证书 SHA-256 指纹（输出片段：{out.strip()[-400:]}）"
    schemes = {}
    for line in out.splitlines():
        m = re.search(r"Verified using (v[\d.]+) scheme[^\n]*?:\s*(true|false)", line, re.I)
        if m:
            schemes[m.group(1)] = m.group(2).lower() == "true"
    return {"signingCertificateSha256": digest, "signatureSchemes": schemes}, None


def verify_one(apk_dir, item, tools):
    flavor, abi_token, native_abi, expected_size = item
    name = asset_name(flavor, abi_token)
    path = os.path.join(apk_dir, name)
    rec = {
        "assetName": name,
        "sourceUrl": SOURCE_URL_PREFIX + name,
        "flavor": flavor,
        "abi": abi_token,
        "nativeAbi": native_abi,
        "expectedSizeBytes": expected_size,
        "checks": {},
        "failures": [],
        "status": "pending",
    }

    def ok(check):
        rec["checks"][check] = True

    def fail(check, reason):
        rec["checks"][check] = False
        rec["failures"].append(f"{check}: {reason}")

    if not os.path.isfile(path):
        fail("exists", f"文件不存在: {path}")
        rec["status"] = "fail"
        return rec
    ok("exists")

    size = os.path.getsize(path)
    rec["sizeBytes"] = size
    rec["sha256"] = sha256_file(path)
    if size > MIN_SIZE_BYTES:
        ok("sizeMin")
    else:
        fail("sizeMin", f"大小 {size} B 未超过下限 {MIN_SIZE_BYTES} B (>30MB)")
    if size == expected_size:
        ok("sizeExact")
    else:
        fail("sizeExact",
             f"大小 {size} B 与已核实官方 asset {expected_size} B 不一致（禁止下错版本 / asset 被替换）")

    zok, zreason, zmethod = zip_integrity(path)
    rec["zipIntegrityMethod"] = zmethod
    if zok:
        ok("zip")
    else:
        fail("zip", zreason)

    info, tool_used = badging_info(path, tools["aapt"])
    rec["badgingTool"] = tool_used
    # ABI 取 badging 的 native-code 与 APK 内 lib/ 目录的并集：
    # 个别 aapt2 版本可能不输出 native-code 行，lib/ 目录是更本质的证据。
    zip_abis = detect_zip_abis(path)
    rec["libAbis"] = zip_abis
    badging_abis = info["nativeCode"] if info else []
    observed = list(dict.fromkeys(list(badging_abis) + zip_abis))
    rec["nativeCodeObserved"] = observed

    if info is None:
        fail("badging", "aapt2 / aapt 均无法读取 badging（缺 build-tools 或 APK 损坏）")
    else:
        ok("badging")
        rec["package"] = info["package"]
        rec["versionName"] = info["versionName"]
        rec["nativeCode"] = info["nativeCode"]
        rec["targetSdkVersion"] = info["targetSdkVersion"]
        if info["package"] == EXPECTED_PACKAGE:
            ok("package")
        else:
            fail("package", f"包名 {info['package']!r} != {EXPECTED_PACKAGE!r}")
        if info["versionName"] == EXPECTED_VERSION_NAME:
            ok("versionName")
        else:
            fail("versionName", f"versionName {info['versionName']!r} != {EXPECTED_VERSION_NAME!r}")

    if native_abi in observed:
        ok("abi")
    else:
        fail("abi", f"文件名声明 {native_abi}，badging native-code={badging_abis}，"
                    f"APK 内 lib/ 目录={zip_abis}")

    sig, serr = signing_info(path, tools["apksigner"])
    if serr or sig is None:
        fail("signature", serr or "签名信息解析失败")
    else:
        rec["signingCertificateSha256"] = sig["signingCertificateSha256"]
        rec["signatureSchemes"] = sig["signatureSchemes"]
        ok("signature")

    rec["status"] = "pass" if not rec["failures"] else "fail"
    return rec


def build_report(apk_dir, android_home, build_tools_dir):
    tools = resolve_tools(android_home, build_tools_dir)
    records = [verify_one(apk_dir, item, tools) for item in ASSETS]

    fingerprints = [r.get("signingCertificateSha256") for r in records]
    consistent = all(f is not None for f in fingerprints) and len(set(fingerprints)) == 1
    common = fingerprints[0] if consistent else None
    for r in records:
        if consistent:
            r["checks"]["signingConsistency"] = True
        else:
            r["checks"]["signingConsistency"] = False
            detail = ", ".join(
                f"{x['assetName']}={x.get('signingCertificateSha256') or 'missing'}"
                for x in records
            )
            r["failures"].append(f"signingConsistency: 四包签名证书 SHA-256 指纹不一致: {detail}")
            r["status"] = "fail"

    return {
        "schemaVersion": 1,
        "generatedAt": utcnow(),
        "upstreamRepo": UPSTREAM_REPO,
        "upstreamTag": UPSTREAM_TAG,
        "sourceUrlPrefix": SOURCE_URL_PREFIX,
        "expectedPackage": EXPECTED_PACKAGE,
        "expectedVersionName": EXPECTED_VERSION_NAME,
        "minSizeBytes": MIN_SIZE_BYTES,
        "buildToolsVersion": BUILD_TOOLS_VERSION,
        "tools": {
            "aapt": [os.path.basename(p) for p in tools["aapt"]],
            "apksigner": os.path.basename(tools["apksigner"]) if tools["apksigner"] else None,
        },
        "signingCertificateSha256Consistent": consistent,
        "signingCertificateSha256": common,
        "packageCount": len(records),
        "packages": records,
        "allPassed": all(r["status"] == "pass" for r in records) and consistent,
    }


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def cmd_verify(args):
    out = args.out or os.path.join(args.out_dir, "upstream-verify.json")
    report = build_report(args.apk_dir, args.android_home, args.build_tools)
    write_json(out, report)
    for r in report["packages"]:
        for reason in r["failures"]:
            print(f"FAIL {r['assetName']}: {reason}", file=sys.stderr)
    if not report["allPassed"]:
        print(
            f"VERIFY FAILED: {report['packageCount']} 个官方包中有断言失败，"
            f"明细见 {out}；构建终止。",
            file=sys.stderr,
        )
        return 1
    print(f"VERIFY OK: {report['packageCount']} packages, "
          f"signing sha256={report['signingCertificateSha256']}")
    print(f"report: {out}")
    return 0


def cmd_package(args):
    verify_path = args.verify_json or os.path.join(args.out_dir, "upstream-verify.json")
    if not os.path.isfile(verify_path):
        print(f"FAIL package: 缺少 {verify_path}，必须先跑 verify", file=sys.stderr)
        return 1
    with open(verify_path, encoding="utf-8") as f:
        report = json.load(f)
    if not report.get("allPassed"):
        print(f"FAIL package: {verify_path} 显示校验未通过，拒绝打包", file=sys.stderr)
        return 1

    os.makedirs(args.out_dir, exist_ok=True)
    packages, sums = [], []
    for rec in report["packages"]:
        src = os.path.join(args.apk_dir, rec["assetName"])
        if not os.path.isfile(src):
            print(f"FAIL package: 源包缺失 {src}", file=sys.stderr)
            return 1
        fname = f"tvbox-jmgo-{rec['flavor']}-{rec['abi']}-{args.tag}-{args.short}.apk"
        dst = os.path.join(args.out_dir, fname)
        shutil.copyfile(src, dst)
        digest = sha256_file(dst)
        if digest != rec.get("sha256"):
            print(f"FAIL {fname}: 复制后 sha256 与校验阶段不一致", file=sys.stderr)
            return 1
        sums.append((digest, fname))
        packages.append({
            "fileName": fname,
            "assetName": rec["assetName"],
            "sourceUrl": rec["sourceUrl"],
            "flavor": rec["flavor"],
            "abi": rec["abi"],
            "nativeAbi": rec["nativeAbi"],
            "sizeBytes": rec["sizeBytes"],
            "sha256": digest,
            "signingCertificateSha256": rec.get("signingCertificateSha256"),
        })

    sums_path = os.path.join(args.out_dir, "SHA256SUMS.txt")
    # 不写注释行：sha256sum -c 对注释行会报 "improperly formatted" 噪声。
    with open(sums_path, "w", encoding="utf-8", newline="\n") as f:
        for digest, fname in sums:
            f.write(f"{digest}  {fname}\n")

    build_info = {
        "schemaVersion": 1,
        "product": "tvbox-jmgo",
        "deliveryMode": "upstream-aggregate",
        "upstreamRepo": report["upstreamRepo"],
        "upstreamTag": report["upstreamTag"],
        "sourceUrlPrefix": report["sourceUrlPrefix"],
        "sourceUrl": report["sourceUrlPrefix"],
        "runId": args.run_id,
        "commitSha": args.commit_sha,
        "shortSha": args.short,
        "builtAt": utcnow(),
        "compatPatchStatus": "not-applied",
        "signingMode": "upstream-original",
        "signingCertificateSha256": report.get("signingCertificateSha256"),
        "signingCertificateSha256Consistent": report.get("signingCertificateSha256Consistent"),
        "upstreamVerify": os.path.basename(verify_path),
        "packages": packages,
    }
    info_path = os.path.join(args.out_dir, "build-info.json")
    write_json(info_path, build_info)
    print(f"PACKAGE OK: {len(packages)} apks -> {args.out_dir}")
    print(f"  {sums_path}")
    print(f"  {info_path}")
    return 0


def cmd_list_assets(args):
    for flavor, abi_token, _native, _size in ASSETS:
        print(asset_name(flavor, abi_token))
    return 0


def cmd_self_test(args):
    """真跑：用伪造包证明任一断言失败都会让 verify 非零退出且写出诊断。"""
    import tempfile

    script = os.path.abspath(__file__)
    scenarios = [
        ("all-missing", None),
        ("tiny-fake-apk", 2048),
        ("exact-size-non-zip", ASSETS[0][3]),
    ]
    with tempfile.TemporaryDirectory(prefix="jmgo-verify-selftest-") as d:
        for label, size in scenarios:
            case_dir = os.path.join(d, label)
            case_apks = os.path.join(case_dir, "apks")
            os.makedirs(case_apks)
            if size is not None:
                fake = os.path.join(case_apks, asset_name(ASSETS[0][0], ASSETS[0][1]))
                with open(fake, "wb") as f:
                    if size > 1024:
                        f.truncate(size)  # 稀疏文件，不占实际磁盘
                    else:
                        f.write(b"not-a-zip" * (size // 9 + 1))
            out = os.path.join(case_dir, "upstream-verify.json")
            proc = subprocess.run(
                [sys.executable, script, "verify", "--apk-dir", case_apks, "--out", out],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                print(f"SELF-TEST FAIL [{label}]: verify 意外返回 0", file=sys.stderr)
                return 1
            if "FAIL " not in proc.stderr:
                print(f"SELF-TEST FAIL [{label}]: stderr 缺少 FAIL <包名> 诊断", file=sys.stderr)
                return 1
            if not os.path.isfile(out):
                print(f"SELF-TEST FAIL [{label}]: 未写出诊断 JSON", file=sys.stderr)
                return 1
            with open(out, encoding="utf-8") as f:
                report = json.load(f)
            if report.get("allPassed") is not False:
                print(f"SELF-TEST FAIL [{label}]: allPassed 未置为 false", file=sys.stderr)
                return 1
            print(f"  scenario {label}: exit={proc.returncode}, allPassed=false, report written")
    print("SELF-TEST PASS: 3 scenarios, 断言失败均终止且写出诊断")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="verify",
                        choices=["verify", "package", "list-assets", "self-test"])
    parser.add_argument("--apk-dir", default=os.environ.get("APK_DIR", "."))
    parser.add_argument("--out-dir", default=os.environ.get("OUT_DIR", "jmgo-out"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--verify-json", default=None)
    parser.add_argument("--android-home",
                        default=os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT"))
    parser.add_argument("--build-tools", default=os.environ.get("BUILD_TOOLS_DIR"))
    parser.add_argument("--short", default=os.environ.get("SHORT_SHA", "local"))
    parser.add_argument("--tag", default=UPSTREAM_TAG)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--commit-sha", default=os.environ.get("GITHUB_SHA", ""))
    args = parser.parse_args()

    handlers = {
        "verify": cmd_verify,
        "package": cmd_package,
        "list-assets": cmd_list_assets,
        "self-test": cmd_self_test,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
