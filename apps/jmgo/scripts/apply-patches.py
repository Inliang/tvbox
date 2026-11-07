#!/usr/bin/env python3
"""对克隆到 UPSTREAM_DIR 的 FongMi/TV 上游源码应用兼容性补丁。

补丁清单内联在 PATCHES 中（与 SPEC.md / build-contract.md 的 P-00/P-01/P-03 对应）。
设计原则：
- required=True 的补丁若未命中目标，则整个构建判失败（硬门禁）。
- required=False 的补丁若未命中，只记录 skipped，不阻断构建（best-effort）。
- 无论成功与否都写出 PATCHES_OUT（patches-applied.json）供产物溯源。
- 绝不使用 sed -i 直接改文件：所有替换走 Python 字符串/正则，且只改已确认存在的字面量。
"""
import os
import re
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATCHES = [
    {
        "id": "P-00",
        "title": "移除 MPV native AAR 校验任务（clean clone 无 lib-mpvplayer/lib-decoder-ffmpeg AAR，必然 F1 失败）",
        "file": "buildSrc/src/main/groovy/com/fongmi/gradle/AbiApkPackaging.groovy",
        "required": True,
        "type": "regex",
        "flags": re.DOTALL,
        "find": r"def validation = project\.tasks\.register\(\"verify\$\{variant\.name\.capitalize\(\)\}MpvNative\", VerifyMpvNativeTask\) \{ task ->.*?project\.tasks\.matching \{ it\.name == \"merge\$\{variant\.name\.capitalize\(\)\}NativeLibs\" \}\.configureEach \{ it\.dependsOn\(validation\) \}\s*",
        "replace": "",
    },
    {
        "id": "P-01",
        "title": "runtime catalog 默认置空：首启不向 GitHub 拉取模块目录，离线可用",
        "file": "app/build.gradle",
        "required": True,
        "type": "regex",
        "flags": 0,
        "find": r"manifestPlaceholders\.runtimeCatalog = providers\.gradleProperty\('tvRuntimeCatalog'\)\.getOrElse\('https://github\.com/FongMi/Release/releases/download/module/catalog\.json'\)",
        "replace": "manifestPlaceholders.runtimeCatalog = providers.gradleProperty('tvRuntimeCatalog').getOrElse('')",
    },
    {
        "id": "P-03",
        "title": "移除 BootReceiver：减少开机自启/后台驻留进程被 LMK 回收引发的连锁不稳定",
        "file": "app/src/leanback/AndroidManifest.xml",
        "required": False,
        "type": "multi",
        "edits": [
            {
                "find": '<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
                "replace": '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n    xmlns:tools="http://schemas.android.com/tools">',
            },
            {
                "find": '            android:priority="999">',
                "replace": '            android:priority="999"\n            tools:node="remove">',
            },
        ],
    },
]


def apply_one(up, p):
    path = os.path.join(up, p["file"])
    if not os.path.exists(path):
        return "file-missing", path
    content = open(path, encoding="utf-8").read()
    if p["type"] == "regex":
        new, n = re.subn(p["find"], p["replace"], content, count=1, flags=p.get("flags", 0))
    elif p["type"] == "multi":
        new = content
        n = 0
        for e in p["edits"]:
            if e["find"] not in new:
                n = -1
                break
            new = new.replace(e["find"], e["replace"], 1)
            n += 1
    else:
        raise SystemExit("unknown patch type: " + p.get("type"))
    if n <= 0:
        return "no-match", p["file"]
    open(path, "w", encoding="utf-8").write(new)
    return "applied", p["file"]


def main():
    up = os.environ.get("UPSTREAM_DIR", "")
    out = os.environ.get("PATCHES_OUT", "patches-applied.json")
    if not up:
        sys.exit("UPSTREAM_DIR 未设置")
    applied, skipped, failed = [], [], []
    for p in PATCHES:
        status, detail = apply_one(up, p)
        entry = {"id": p["id"], "title": p.get("title", ""), "file": detail}
        if status == "applied":
            applied.append(entry)
        elif status in ("file-missing", "no-match"):
            if p.get("required"):
                failed.append({**entry, "reason": status})
            else:
                skipped.append({**entry, "reason": status})
        else:
            failed.append({**entry, "reason": status})
    report = {"applied": applied, "skipped": skipped, "failed": failed}
    json.dump(report, open(out, "w"), indent=2, ensure_ascii=False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        sys.exit("REQUIRED PATCH FAILED: " + ",".join(f["id"] for f in failed))
    print("OK: applied=%d skipped=%d" % (len(applied), len(skipped)))


if __name__ == "__main__":
    main()
