"""独立重探 reason_code=='probe_dead' 的候选，验证"一次没响应"是否等于"确定死"。

只读 data/site_candidates.json，只写 data/probe_dead_raw.json。
人工整理的解释层在 data/probe_dead_recheck.json，本脚本永不写入（见 CURATED 守卫）。

测量规则（2026-10-19 收敛）：
  1. 先用 TVBox 同款 UA 请求
  2. 失败且耗时 < 3s（RST / refused）→ UA 层拒绝，立刻换浏览器 UA 重试，不 sleep
  3. 失败且耗时 > 3s（stall / timeout）→ 通道问题，换 UA 无用，同 UA 间隔 1s 重试
  4. 两条路径都记 ua / ms / status，使"为什么判它没响应"可复查
  5. http_responded 只表示拿到 HTTP 响应，不表示站点可用
"""
import datetime
import json
import os
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "data", "site_candidates.json")
# 测量与解释分开：本脚本只写原始测量结果，每次重跑覆盖。
OUT = os.path.join(BASE, "data", "probe_dead_raw.json")
CURATED = os.path.join(BASE, "data", "probe_dead_recheck.json")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=CTX),
)

UA_CLIENT = "okhttp/3.12.13"
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

FAST_FAIL_MS = 3000


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


def classify_err(e):
    """把异常归成可判读的种类。rst 表示对端主动断开，不是超时。"""
    name = type(e).__name__
    msg = str(e).lower()
    if "timed out" in msg or "timeout" in name.lower():
        return "timeout"
    if isinstance(e, urllib.error.HTTPError):
        return "http"
    if "remote end closed" in msg or "reset" in msg or "refused" in msg:
        return "rst"
    if "getaddrinfo" in msg or "name or service" in msg:
        return "dns"
    if "ssl" in msg or "certificate" in msg:
        return "tls"
    return name


def once(url, ua, timeout=8):
    t0 = time.time()
    try:
        req = urllib.request.Request(idna(url), headers={
            "User-Agent": ua, "Accept": "*/*", "Connection": "close"})
        with OPENER.open(req, timeout=timeout) as r:
            body = r.read(4000)
            return {"ua": "client" if ua == UA_CLIENT else "browser",
                    "ok": True, "status": r.status,
                    "ms": int((time.time() - t0) * 1000),
                    "bytes": len(body),
                    "ctype": r.headers.get("Content-Type", ""),
                    "head": body[:60].decode("utf-8", "ignore")}
    except urllib.error.HTTPError as e:
        return {"ua": "client" if ua == UA_CLIENT else "browser",
                "ok": False, "status": e.code,
                "ms": int((time.time() - t0) * 1000), "err": "http_" + str(e.code)}
    except Exception as e:
        return {"ua": "client" if ua == UA_CLIENT else "browser",
                "ok": False, "status": None,
                "ms": int((time.time() - t0) * 1000),
                "err": classify_err(e), "err_detail": type(e).__name__}


def probe(url):
    """返回 (attempts, http_responded, path)"""
    a = once(url, UA_CLIENT)
    if a.get("ok"):
        return [a], True, "client_ok"

    err = a.get("err") or ""
    fast = (a.get("ms") or 0) < FAST_FAIL_MS
    if fast and err in ("rst", "http_403", "http_429"):
        # UA 层拒绝：同一指纹重试必然重复失败，换指纹且不等待
        b = once(url, UA_BROWSER)
        return [a, b], bool(b.get("ok")), "ua_blocked_retry"

    # 通道 stall / 超时：换 UA 无用，同 UA 隔 1s 再测一次
    time.sleep(1.0)
    b = once(url, UA_CLIENT)
    return [a, b], bool(b.get("ok")), "stall_retry"


def work(item):
    url = item.get("probe_target") or ""
    if not url:
        return None
    attempts, responded, path = probe(url)
    return {
        "name": (item.get("site") or {}).get("name"),
        "tier": item.get("tier"),
        "included": item.get("included"),
        "url": url,
        "http_responded": responded,
        "path": path,
        "attempts": attempts,
    }


def main():
    doc = json.load(open(SRC, encoding="utf-8"))
    items = doc["items"] if isinstance(doc, dict) else doc
    dead = [x for x in items if x.get("reason_code") == "probe_dead"]
    print(f"重探 {len(dead)} 条 probe_dead …", flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = [r for r in ex.map(work, dead) if r]
    responded = [r for r in res if r["http_responded"]]
    print(f"HTTP 有响应 {len(responded)} / {len(res)}（不等价于可用）", flush=True)
    for r in responded:
        t = next((a for a in r["attempts"] if a.get("ok")), {})
        print(f"  + {r['tier']} {r['name']} [{r['path']}] "
              f"{t.get('status')} {t.get('ms')}ms {t.get('ctype','')}", flush=True)

    out = {
        "method": "双 UA 策略：快速失败(＜3s RST)换浏览器 UA 立即重试；慢失败(＞3s)同 UA 隔 1s 重试",
        "generatedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "count": len(res),
        "httpRespondedCount": len(responded),
        "pathCounts": {p: sum(1 for r in res if r["path"] == p)
                       for p in sorted({r["path"] for r in res})},
        "field_note": "http_responded 只表示拿到 HTTP 响应，不表示站点可用",
        "items": res,
    }

    # 守卫：解释层是人工整理出来的，脚本永远不碰它。
    if os.path.exists(CURATED):
        old = json.load(open(CURATED, encoding="utf-8"))
        curated_keys = {"config_parse", "rejections_breakdown",
                        "reclassify_preview", "field_notes", "classification"}
        if curated_keys & set(old) and os.path.abspath(OUT) == os.path.abspath(CURATED):
            raise SystemExit(f"[拒绝覆盖] {CURATED} 含人工整理字段 "
                             f"{curated_keys & set(old)}")

    json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    print("wrote", OUT, out["pathCounts"], flush=True)


if __name__ == "__main__":
    main()
