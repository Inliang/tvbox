"""给落在『已失效镜像 host』上的站点找真实落点。

背景：docs 前端的 isMirrorUrl() 判的是 probe_url 的 host。落在 mirrorHosts 里的
站点会被豁免（不判青、不进探测队列），显示为「⊘ 镜像当前不可用，源站未验证」。
若 v2 简单地把坏 host 从清单里删掉，这些站会静默掉进「青=可达」——把一个诚实的
「不可验证」换成一句假的「主机有响应」。

所以删之前必须先给落点。本脚本做的事：按 host 形态把镜像 URL 映射回
raw.githubusercontent.com 源站并实拉，让这些站落到真实的 confirmed / dead，
而不是掉进「可达」或停在「不可验证」。

只读 data/exports/sites.json，只写 data/mirror_origin_probe.json。
"""
import datetime
import hashlib
import json
import os
import ssl
import time
import urllib.request
from urllib.parse import quote, urlsplit, urlunsplit

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "data", "exports", "sites.json")
OUT = os.path.join(BASE, "data", "mirror_origin_probe.json")

MIRROR_HOSTS = {"ghp.ci", "gh-proxy.com", "gh-proxy.org", "gh-proxy.net",
                "ghproxy.net", "ghproxy.cc", "ghfast.top", "raw.kkgithub.com"}
# 2026-10-19 实测：ghp.ci 对端 RST、gh-proxy.net 已劫持、raw.kkgithub.com 域名停放
BAD_HOSTS = {"ghp.ci", "gh-proxy.net", "raw.kkgithub.com"}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=CTX))
UA = "okhttp/3.12.13"


def host_of(u):
    try:
        return urlsplit(u or "").hostname or ""
    except Exception:
        return ""


def encode(url):
    """IDNA + 百分号编码。缺后者会让含中文路径的 URL 抛 UnicodeEncodeError——
    那是探针自身的缺陷，不是站点死。"""
    p = urlsplit(url)
    keep = "/%:=&?+~#"
    return urlunsplit((p.scheme, p.netloc, quote(p.path, safe=keep),
                       quote(p.query, safe=keep), p.fragment))


def to_origin(url):
    """镜像 URL -> raw.githubusercontent.com 源站 URL；映射不了返回 None。"""
    p = urlsplit(url)
    h = (p.hostname or "")
    if h == "raw.kkgithub.com":          # 与 raw.githubusercontent.com 同路径
        return "https://raw.githubusercontent.com" + p.path
    rest = p.path.lstrip("/")
    if rest.startswith("raw.githubusercontent.com/"):   # ghp.ci 的无 scheme 形态
        return "https://" + rest
    if rest.startswith("https://raw.githubusercontent.com/"):
        return rest
    if rest.startswith("http://raw.githubusercontent.com/"):
        return "https://" + rest[len("http://"):]
    return None


def once(url, timeout=10):
    t0 = time.time()
    try:
        req = urllib.request.Request(encode(url),
                                     headers={"User-Agent": UA, "Accept": "*/*"})
        with OPENER.open(req, timeout=timeout) as r:
            b = r.read()
            return {"status": r.status, "ms": int((time.time() - t0) * 1000),
                    "bytes": len(b), "md5": hashlib.md5(b).hexdigest(),
                    "ctype": (r.headers.get("Content-Type") or "")[:40],
                    "head": b[:70].decode("utf-8", "ignore").replace("\n", " ")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "ms": int((time.time() - t0) * 1000),
                "err": "http_%d" % e.code}
    except Exception as e:
        return {"status": None, "ms": int((time.time() - t0) * 1000),
                "err": type(e).__name__}


def landing(status):
    """把源站实测结果翻译成建议落点。"""
    if status == 200:
        return "confirmed（源站返回 200，可判定为真实可用）"
    if status == 404:
        return "dead（源站 404，文件确实不存在）"
    if status is None:
        return "uncertain（源站也没拿到响应，维持不可验证）"
    return "uncertain（源站返回 %s，维持不可验证）" % status


def main():
    doc = json.load(open(SRC, encoding="utf-8"))
    items = doc["items"]
    on_mirror = [x for x in items if host_of(x.get("probe_url")) in MIRROR_HOSTS]
    bad = [x for x in items if host_of(x.get("probe_url")) in BAD_HOSTS]
    print(f"517 中 probe_url 落在 8 个镜像 host 上: {len(on_mirror)}", flush=True)
    print(f"其中落在 3 个已失效 host 上: {len(bad)}", flush=True)

    res, unmapped = [], []
    for x in bad:
        o = to_origin(x["probe_url"])
        if not o:
            unmapped.append(x)
            print(f"  [无法映射] {host_of(x['probe_url'])} {x['name']}", flush=True)
            continue
        r = once(o)
        r.update({"name": x["name"], "id": x["id"], "tier": x["tier"],
                  "probe_status_now": x.get("probe_status"),
                  "mirror_host": host_of(x["probe_url"]),
                  "probe_url": x["probe_url"], "origin_url": o,
                  "suggested_landing": landing(r.get("status"))})
        res.append(r)
        print(f"  [{str(r.get('status') or r.get('err')):>10}] "
              f"{r['mirror_host']:<18} {x['name'][:22]:<24} "
              f"{r.get('bytes', '-')}B {r.get('ms')}ms", flush=True)
        if r.get("head"):
            print(f"               head: {r['head']}", flush=True)

    out = {
        "method": ("把落在已失效镜像 host 上的 probe_url 按 host 形态映射回 "
                   "raw.githubusercontent.com 源站并实拉，用于确定删除该 host 后的落点"),
        "generatedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "field_note": ("suggested_landing 是建议落点，不是已生效的判定；"
                       "数据层冻结期间本文件只作 v2 决策依据"),
        "mirrorHostCount": len(on_mirror),
        "badHostCount": len(bad),
        "mappedCount": len(res),
        "unmappedCount": len(unmapped),
        "confirmedCount": sum(1 for r in res if r.get("status") == 200),
        "deadCount": sum(1 for r in res if r.get("status") == 404),
        "items": res,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    print(f"\n源站 200: {out['confirmedCount']} / 404: {out['deadCount']} / "
          f"其他: {len(res) - out['confirmedCount'] - out['deadCount']}", flush=True)
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
