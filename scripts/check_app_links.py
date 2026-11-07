#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 README「APP 推荐」里的 APK 下载直链是否仍能下载。

从 README.md 提取所有 GitHub Releases 的 .apk 链接，并发请求开头 256 字节，
只认 200/206 + application/vnd.android.package-archive（避免把 HTML 错误页当好链接）。

用法：python scripts/check_app_links.py
退出码：0 = 全部可用；1 = 有失效链接或未找到链接。
"""
import concurrent.futures as cf
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
APK_RE = re.compile(r"https://github\.com/[^\s)]+/releases/[^\s)]+\.apk")
UA = {"User-Agent": "Mozilla/5.0", "Range": "bytes=0-255"}


def check(url):
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=20
        ) as r:
            r.read(16)
            ct = r.headers.get("Content-Type", "")
            ok = r.status in (200, 206) and "android.package-archive" in ct
            return url, ok, f"HTTP {r.status} {ct.split(';')[0]}"
    except urllib.error.HTTPError as e:
        return url, False, f"HTTP {e.code}"
    except Exception as e:
        return url, False, type(e).__name__


def main():
    urls = sorted(set(APK_RE.findall(README.read_text(encoding="utf-8"))))
    print(f"README 里的 APK 直链：{len(urls)} 条")
    if not urls:
        print("未找到 .apk 直链，请检查 README 的「APP 推荐 → 下载直链」章节")
        return 1
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(check, urls))
    bad = [(u, m) for u, ok, m in results if not ok]
    for url, ok, msg in results:
        print(f"  {'OK  ' if ok else 'FAIL'} {msg[:38]:38s} {url.split('/')[-1]}")
    print(f"\n可用 {len(urls) - len(bad)}/{len(urls)}")
    if bad:
        print("失效链接（需更新 README）：")
        for url, msg in bad:
            print(f"  {msg}  {url}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
