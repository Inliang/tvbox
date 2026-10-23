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

# 源站是间歇性 stall，不是恒定慢：好的时候 0.6 秒出头，坏的时候 40 秒级。
# 2026-10-23 实测两轮并集，11 条全部 598–836 ms 拿到 200；而 10-19 那次同批地址
# 单次耗时 7.9s ~ 40.8s。同一个地址两次测量差 60 倍，所以：
#   - 不能按"慢"下结论说它不可用（那一次恰好赶上好窗口）
#   - 更不能指望前端探测时正好撞上好的那次（撞上 40s 就直接超时）
# 两条都指向同一个动作：结果必须由采集端预计算后写死。
# 跑多轮取并集，避免"某一轮超时"被误读成"站点不存在"。
ROUNDS = int(os.environ.get("ORIGIN_ROUNDS", "2"))


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
    print(f"轮次: {ROUNDS}（源站极慢且不稳定，取并集）", flush=True)

    res, unmapped = [], []
    for x in bad:
        o = to_origin(x["probe_url"])
        if not o:
            unmapped.append(x)
            print(f"  [无法映射] {host_of(x['probe_url'])} {x['name']}", flush=True)
            continue
        rounds = []
        for r in range(ROUNDS):
            rounds.append(once(o))
            if rounds[-1].get("status") == 200:
                break        # 已拿到 200，后面的轮次没有意义
        any200 = any(r.get("status") == 200 for r in rounds)
        last_ok = next((r for r in rounds if r.get("status") == 200), rounds[-1])
        rec = {
            "name": x["name"], "id": x["id"], "tier": x["tier"],
            "probe_status_now": x.get("probe_status"),
            "mirror_host": host_of(x["probe_url"]),
            "probe_url": x["probe_url"], "origin_url": o,
            # 并集口径：任一轮 200 即算源站存活；只有 404 才是"文件真的没了"
            "origin_status": last_ok.get("status"),
            "origin_bytes": last_ok.get("bytes"),
            "origin_md5": last_ok.get("md5"),
            "origin_responded": any(r.get("status") is not None for r in rounds),
            "origin_ok200": any200,
            "suggested_landing": landing(last_ok.get("status")) if any200
                                 else landing(None),
            "rounds": rounds,
        }
        res.append(rec)
        tag = "200" if any200 else str(last_ok.get("status") or last_ok.get("err"))
        print(f"  [{tag:>10}] {rec['mirror_host']:<18} {x['name'][:22]:<24} "
              f"{last_ok.get('bytes', '-')}B {last_ok.get('ms')}ms "
              f"({len(rounds)} 轮)", flush=True)

    out = {
        "method": ("把落在已失效镜像 host 上的 probe_url 按 host 形态映射回 "
                   "raw.githubusercontent.com 源站并实拉，用于确定删除该 host 后的落点"),
        "generatedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "field_note": ("origin_status 取第一轮拿到 200 的结果；若多轮均无 200 则取最后一轮。"
                       "origin_ok200=任一轮 200；404 才算 dead，超时不算。"
                       "本文件是预计算结果，禁止前端实时探测：源站是间歇性 stall，"
                       "2026-10-23 两轮并集实测 598–836 ms 全 200，而 10-19 同批地址单次曾达 7.9–40.8 s，"
                       "撞上慢窗口前端探测必超时。"),
        "rounds": ROUNDS,
        "mirrorHostCount": len(on_mirror),
        "badHostCount": len(bad),
        "mappedCount": len(res),
        "unmappedCount": len(unmapped),
        "confirmedCount": sum(1 for r in res if r["origin_ok200"]),
        "deadCount": sum(1 for r in res if r["origin_status"] == 404),
        "unresolvedCount": sum(1 for r in res if not r["origin_ok200"]
                               and r["origin_status"] != 404),
        "items": res,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    print(f"\n源站 200（任一轮）: {out['confirmedCount']} / 404: {out['deadCount']} / "
          f"仍未取到: {out['unresolvedCount']}，共 {len(res)}", flush=True)
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
