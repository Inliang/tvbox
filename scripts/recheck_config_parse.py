"""复核 10 条非 ok 配置的真实解析失败原因。

只读 docs/data/configs.json 的 url，不写任何数据层文件。
结论写 data/config_parse_recheck.json。

目的：区分三种完全不同的失败——
  jsonc      有 // 注释 / BOM / 尾逗号，TVBox 能加载，我们太严
  truncated  declared 与实收不符，或末尾语法未闭（今天应为 0）
  not_config 真不是配置
"""
import json
import os
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "docs", "data", "configs.json")
OUT = os.path.join(BASE, "data", "config_parse_recheck.json")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=CTX),
)
UA = "okhttp/3.12.13"


def jsdelivr(u):
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", u)
    if not m:
        return None
    o, r, ref, path = m.groups()
    return f"https://cdn.jsdelivr.net/gh/{o}/{r}@{ref}/{path}"


def fetch(u, timeout=30):
    t0 = time.time()
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "*/*"})
    with OPENER.open(req, timeout=timeout) as r:
        body = r.read(2000000)
        return {
            "url": u, "status": r.status,
            "declared": r.headers.get("Content-Length"),
            "received": len(body),
            "ms": int((time.time() - t0) * 1000),
            "ctype": r.headers.get("Content-Type", ""),
            "body": body,
        }


def try_parse(body):
    """返回 (kind, detail, sites)"""
    bom = body.startswith(b"\xef\xbb\xbf")
    txt = body.decode("utf-8-sig", "ignore")
    try:
        j = json.loads(txt)
        n = len(j.get("sites") or []) if isinstance(j, dict) else 0
        return ("strict_ok", {"bom": bom}, n)
    except Exception as e:
        pos = getattr(e, "pos", None)
        msg = str(e)
    # 去掉 // 行注释与 /* */ 块注释（TVBox 的 JSONC 习惯）
    t2 = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    t2 = re.sub(r"^\s*//.*$", "", t2, flags=re.M)
    # 去掉尾逗号
    t3 = re.sub(r",(\s*[}\]])", r"\1", t2)
    try:
        j = json.loads(t3)
        n = len(j.get("sites") or []) if isinstance(j, dict) else 0
        return ("jsonc_ok", {"bom": bom, "err": msg, "pos": pos}, n)
    except Exception as e2:
        return ("still_fail", {"bom": bom, "err": msg, "pos": pos,
                              "err2": str(e2)[:120]}, 0)


def work(c):
    url = c.get("url", "")
    alt = jsdelivr(url)
    rec = {"id": c["id"], "name": c.get("name"), "url": url,
           "state": c.get("state"), "error": c.get("error"),
           "probeMs": c.get("probeMs")}
    for label, u in (("jsdelivr", alt), ("raw", url)):
        if not u:
            continue
        try:
            r = fetch(u)
        except Exception as e:
            rec[label] = {"fail": type(e).__name__ + ":" + str(e)[:80]}
            continue
        kind, detail, n = try_parse(r["body"])
        rec[label] = {
            "status": r["status"], "declared": r["declared"],
            "received": r["received"], "ms": r["ms"],
            "ctype": r["ctype"], "kind": kind,
            "sites": n, "detail": detail,
            "head": r["body"][:60].decode("utf-8", "ignore"),
        }
        # jsdelivr 成功拿到内容就够判性质，raw 只抽前 3 条核对
        if label == "jsdelivr" and kind in ("strict_ok", "jsonc_ok"):
            break
    return rec


def main():
    cfg = json.load(open(SRC, encoding="utf-8"))
    items = [c for c in cfg["items"] if c.get("state") != "ok"]
    print(f"复核 {len(items)} 条非 ok 配置…", flush=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(work, items))
    from collections import Counter
    kinds = Counter()
    for r in rows:
        d = r.get("jsdelivr") or r.get("raw") or {}
        k = d.get("kind") or d.get("fail") or "no_data"
        kinds[k] += 1
        print(f"  {r['id']:22s} {k:12s} "
              f"{d.get('declared')}/{d.get('received')} "
              f"sites={d.get('sites')} pos={(d.get('detail') or {}).get('pos')}", flush=True)
    out = {"method": "优先 jsdelivr 取同一内容做语法分析；raw 只在 jsdelivr 失败时使用",
           "count": len(rows), "kinds": dict(kinds), "items": rows}
    json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    print("wrote", OUT, dict(kinds), flush=True)


if __name__ == "__main__":
    main()
