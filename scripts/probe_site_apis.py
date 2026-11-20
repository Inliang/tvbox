#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实测 zijian.json 里 http 直链 API 站点是否真能返回视频数据。

判定依据（贴近 TVBox 实际使用）：用 okhttp UA 请求 API 的 list 接口，
- HTTP 2xx 且响应是 JSON、含非空 list 数组（CMS 类接口标准响应）→ alive
- 返回 HTML/空/403/超时/连接失败 → dead（但区分原因，便于人工复核）
不探测 csp_ 自建接口（依赖本地 spider/JS，URL 请求不适用）。

只读 zijian.json，只写 data/site_api_probe.json。
"""
import concurrent.futures as cf
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "site_api_probe.json"
UA = "okhttp/3.12.13"
TIMEOUT = 10
WORKERS = 16
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=CTX),
)


def normalize(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path),
         urllib.parse.quote(p.query, safe="=&?"), ""))


def probe(site):
    api = site["api"]
    t0 = time.perf_counter()
    rec = {"key": site.get("key"), "name": site.get("name"), "api": api}
    try:
        req = urllib.request.Request(
            normalize(api),
            headers={"User-Agent": UA, "Accept": "*/*", "Connection": "close"})
        with OPENER.open(req, timeout=TIMEOUT) as resp:
            status = resp.status
            raw = resp.read(256 * 1024)
        rec["status"] = status
        rec["ms"] = int((time.perf_counter() - t0) * 1000)
        text = raw.decode("utf-8", errors="ignore").lstrip()
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                lst = obj.get("list")
                total = obj.get("total")
                rec["has_list"] = isinstance(lst, list) and len(lst) > 0
                rec["list_len"] = len(lst) if isinstance(lst, list) else 0
                rec["total"] = total
                # 视频列表接口：有非空 list 即视为可用；total>0 但 list 空也可接受
                rec["alive"] = rec["has_list"] or (isinstance(total, (int, str)) and str(total).isdigit() and int(total) > 0)
            else:
                rec["alive"] = False
            rec["json"] = True
        except (ValueError, json.JSONDecodeError):
            rec["json"] = False
            rec["alive"] = False
            rec["head"] = text[:60]
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["ms"] = int((time.perf_counter() - t0) * 1000)
        rec["alive"] = False
        rec["reason"] = f"http {e.code}"
    except Exception as e:
        rec["ms"] = int((time.perf_counter() - t0) * 1000)
        rec["alive"] = False
        rec["reason"] = type(e).__name__
    return rec


def main():
    z = json.loads((ROOT / "zijian.json").read_text(encoding="utf-8"))
    targets = [s for s in z.get("sites", []) if str(s.get("api", "")).startswith("http")]
    print(f"站点 API 实测  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"探测 {len(targets)} 个 http 直链 API（csp_ 自建接口不测），并发={WORKERS}\n")
    results = []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for rec in ex.map(probe, targets):
            results.append(rec)
    results.sort(key=lambda r: (r.get("alive", False), r.get("name") or ""))
    alive = sum(1 for r in results if r.get("alive"))
    dead = [r for r in results if not r.get("alive")]
    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "alive": alive,
        "dead": len(dead),
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"结果：alive {alive}/{len(results)}，dead {len(dead)}")
    print("\n=== 判死站点 ===")
    for r in dead:
        why = r.get("reason") or ("html" if not r.get("json") else "no-list")
        print(f"  [{why:>16}] {str(r.get('name'))[:22]:24s} {str(r.get('api'))[:58]}")
    print(f"\n结果 -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
