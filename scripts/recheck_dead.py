"""独立重探 reason_code=='probe_dead' 的候选，验证"一次没响应"是否等于"确定死"。

只读 site_candidates.json，只写 data/probe_dead_recheck.json。
不碰 exports / probe_cache，不改变已冻结的数据层。
"""
import json
import os
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "data", "site_candidates.json")
OUT = os.path.join(BASE, "data", "probe_dead_recheck.json")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=CTX),
)
UA = "okhttp/3.12.13"


def idna(url):
    try:
        p = urlsplit(url)
        if p.hostname:
            host = p.hostname.encode("idna").decode("ascii")
            netloc = host + (f":{p.port}" if p.port else "")
            return url.replace(p.netloc, netloc, 1)
    except Exception:
        pass
    return url


def once(url, timeout=8):
    t0 = time.time()
    try:
        req = urllib.request.Request(idna(url), headers={
            "User-Agent": UA, "Accept": "*/*", "Connection": "close"})
        with OPENER.open(req, timeout=timeout) as r:
            body = r.read(4000)
            return {"ok": True, "status": r.status,
                    "ms": int((time.time() - t0) * 1000),
                    "bytes": len(body),
                    "head": body[:60].decode("utf-8", "ignore"),
                    "ctype": r.headers.get("Content-Type", "")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code,
                "ms": int((time.time() - t0) * 1000),
                "err": "http_" + str(e.code)}
    except Exception as e:
        return {"ok": False, "status": None,
                "ms": int((time.time() - t0) * 1000),
                "err": type(e).__name__ + ":" + str(e)[:60]}


def work(item):
    url = item.get("probe_target") or ""
    if not url:
        return None
    a = once(url)
    b = {"ok": False, "skipped": True}
    if not a.get("ok"):
        time.sleep(1.0)
        b = once(url)
    alive = bool(a.get("ok") or b.get("ok"))
    return {
        "name": (item.get("site") or {}).get("name"),
        "tier": item.get("tier"),
        "included": item.get("included"),
        "url": url,
        "alive": alive,
        "try1": a,
        "try2": b,
    }


def main():
    doc = json.load(open(SRC, encoding="utf-8"))
    items = doc["items"] if isinstance(doc, dict) else doc
    dead = [x for x in items if x.get("reason_code") == "probe_dead"]
    print(f"重探 {len(dead)} 条 probe_dead …", flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = [r for r in ex.map(work, dead) if r]
    alive = [r for r in res if r["alive"]]
    print(f"复活 {len(alive)} / {len(res)}", flush=True)
    for r in alive:
        t = r["try1"] if r["try1"].get("ok") else r["try2"]
        print(f"  + {r['tier']} {r['name']} -> {t.get('status')} "
              f"{t.get('ms')}ms {t.get('bytes')}B {t.get('ctype','')}", flush=True)
    out = {"method": "同一 URL 连试两次，间隔 1s；任一成功记为 alive",
           "count": len(res), "aliveCount": len(alive),
           "items": res}
    json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
