#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直播线路「流畅度」测速：给 update_lives.py 的线路排序提供依据。

背景：update_lives.py 原有的 probe() 只判断 HTTP 能否返回 2xx / 读 256 字节，
只能筛掉「死链」，筛不掉「能连上但一直转圈」的慢源 —— 这正是卡顿的主因。
本脚本对每个流地址实测两件事：
  1) TTFB / 播放列表响应耗时  -> 决定起播快慢
  2) 实际分片下载吞吐(kbps)   -> 决定播放中是否持续缓冲

产出 data/live_speed.json（本机网络快照，不入库），供
`python scripts/update_lives.py --with-speed` 重排线路、生成流畅优选列表。

用法：
  python scripts/probe_live_speed.py
  python scripts/probe_live_speed.py --extra-dir /tmp/iptv_up --workers 64
  python scripts/probe_live_speed.py --limit 200          # 小样本试跑
"""
import argparse
import concurrent.futures as cf
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"
OUT = ROOT / "data" / "live_speed.json"
UA = "Mozilla/5.0 (Linux; Android 11) okHttp/Mod-1.5.0.0"
TIMEOUT = 6
# 并发过高会被大量源站当成刷流而返回 403（实测 64 并发时 88% 的"可达"其实是限流），
# 单独复测同一批地址即恢复正常。宁可慢一点，也要拿到真实的可播性数据。
WORKERS = 16
READ_BYTES = 128 * 1024

# 不少直播源用自签/过期证书，播放器一般不做严格校验；这里与播放器行为对齐
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def normalize(url):
    """URL 含中文时按 RFC 编码，否则 urllib 抛 UnicodeEncodeError。"""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path),
         urllib.parse.quote(p.query, safe="=&?"), "")
    )


def parse_m3u(path):
    """返回 [(extinf 行, url)]，跳过注释掉的备用线路。"""
    out, cur = [], None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            cur = line
        elif line.startswith("#"):
            continue
        elif cur is not None and line.startswith(("http://", "https://")):
            out.append((cur, line))
            cur = None
    return out


def collect_urls(extra_dirs):
    urls = {}
    paths = sorted(LIB.glob("*.m3u")) + sorted(LIB.glob("*.txt"))
    for d in extra_dirs:
        paths += sorted(Path(d).glob("*.m3u"))
    for p in paths:
        for inf, url in parse_m3u(p):
            urls.setdefault(url, inf.rsplit(",", 1)[-1].strip())
    return urls


def _open(url, rng=None, timeout=TIMEOUT):
    headers = {"User-Agent": UA, "Accept": "*/*", "Connection": "close"}
    if rng:
        headers["Range"] = rng
    req = urllib.request.Request(normalize(url), headers=headers)
    return urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)


def _read_some(resp, limit=READ_BYTES):
    buf = bytearray()
    while len(buf) < limit:
        chunk = resp.read(min(16384, limit - len(buf)))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


def _is_playlist(body, url):
    head = body.lstrip()[:64]
    return head.startswith(b"#EXTM3U") or url.split("?")[0].lower().endswith(".m3u8")


def _segment_urls(text, base):
    """分片候选：直播列表末尾那个分片常常尚未生成（404），故多备几个。"""
    lines = [l.strip() for l in text.splitlines()
             if l.strip() and not l.startswith("#")]
    if not lines:
        return []
    picks = []
    for idx in (len(lines) - 1, max(0, len(lines) - 2), 0):
        u = urllib.parse.urljoin(base, lines[idx])
        if u not in picks:
            picks.append(u)
    return picks[:3]


def measure(url):
    res = {"ok": False, "ttfb_ms": None, "kbps": None, "http": None,
           "kind": "", "score": 0.0, "reason": ""}
    try:
        t0 = time.perf_counter()
        # 播放列表不带 Range：不少源站对带 Range 的 m3u8 请求直接拒绝
        r = _open(url)
        res["http"] = r.status
        res["ttfb_ms"] = round((time.perf_counter() - t0) * 1000)
        t_read = time.perf_counter()
        body = _read_some(r)
        read_dt = time.perf_counter() - t_read
        r.close()
        if not body:
            res["reason"] = "empty body"
            return res
        res["ok"] = True

        if _is_playlist(body, url):
            res["kind"] = "hls"
            # 最多下钻三层：master -> media playlist -> ts 分片
            base, cur_body = url, body
            for _ in range(3):
                segs = _segment_urls(cur_body.decode("utf-8", "ignore"), base)
                if not segs:
                    break
                descended = False
                for seg in segs:
                    try:
                        t1 = time.perf_counter()
                        r2 = _open(seg, None)  # 不给分片送 Range，部分源站会回 416
                        chunk = _read_some(r2)
                        dt = time.perf_counter() - t1
                        r2.close()
                        if _is_playlist(chunk, seg):
                            cur_body, base, descended = chunk, seg, True
                            break
                        if dt > 0 and chunk:
                            res["kbps"] = round(len(chunk) * 8 / dt / 1000)
                            res["seg_ms"] = round(dt * 1000)
                            break
                    except Exception as e:
                        res["reason"] = "seg:" + type(e).__name__
                if res["kbps"] is not None or not descended:
                    break
        else:
            res["kind"] = "stream"
            # 直连流：body 本身就是媒体数据，读满一块即可估吞吐
            if read_dt > 0 and len(body) >= 32768:
                res["kbps"] = round(len(body) * 8 / read_dt / 1000)
    except urllib.error.HTTPError as e:
        res["http"] = e.code
        # 防盗链源播放器带 Referer 可播，保留但给低分；明确死链剔除
        if e.code in (403, 405, 401):
            res["ok"] = True
            res["reason"] = "anti-leech (kept, low priority)"
        else:
            res["reason"] = f"http {e.code}"
    except Exception as e:
        res["reason"] = type(e).__name__
    return finalize(res)


def finalize(res):
    if not res["ok"]:
        res["score"] = 0.0
        return res
    ttfb = res["ttfb_ms"] if res["ttfb_ms"] is not None else 3000
    # 起播：<=300ms 满分，>=3000ms 0 分
    s_start = max(0.0, min(1.0, (3000 - ttfb) / 2700))
    kbps = res["kbps"] or 0
    # 吞吐：>=4000kbps 满分（1080p 常见 4~8M，取相对分即可）
    s_rate = max(0.0, min(1.0, kbps / 4000))
    score = 100 * (0.45 * s_start + 0.55 * s_rate)
    # 只拿到播放列表、取不到分片速度的，不能给高分：那正是「能开但没流」的源
    if res["kbps"] is None:
        score = min(score, 22.0)
    if res["reason"].startswith("anti-leech"):
        score = min(score, 12.0)
    res["score"] = round(score, 1)
    return res


def main():
    global TIMEOUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-dir", action="append", default=[],
                    help="额外的上游 m3u 目录，可重复指定")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--timeout", type=int, default=TIMEOUT)
    ap.add_argument("--limit", type=int, default=0, help="只测前 N 条（试跑用）")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    TIMEOUT = args.timeout

    urls = collect_urls(args.extra_dir)
    targets = sorted(urls)
    if args.limit:
        targets = targets[:args.limit]
    print(f"直播线路测速  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"候选 {len(targets)} 条唯一流地址，并发={args.workers} 超时={TIMEOUT}s\n")

    results = {}
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(measure, u): u for u in targets}
        done = 0
        for fut in cf.as_completed(futs):
            u = futs[fut]
            try:
                results[u] = fut.result()
            except Exception as e:
                results[u] = {"ok": False, "score": 0.0, "reason": type(e).__name__}
            done += 1
            if done % 200 == 0:
                print(f"  进度 {done}/{len(targets)}  可达 "
                      f"{sum(1 for v in results.values() if v['ok'])}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "note": "本机网络实测快照，仅代表该网络；score 越高越流畅",
        "total": len(results),
        "results": results,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = [v for v in results.values() if v["ok"]]
    fast = [v for v in ok if v["score"] >= 50]
    measured = [v for v in ok if v["kbps"]]
    print(f"\n耗时 {time.perf_counter() - t0:.0f}s  可达 {len(ok)}/{len(results)}  "
          f"高分(>=50) {len(fast)}  取到分片速度 {len(measured)}")
    if measured:
        ks = sorted(v["kbps"] for v in measured)
        ts = sorted(v["ttfb_ms"] for v in ok if v["ttfb_ms"] is not None)
        print(f"分片吞吐 kbps  p10={ks[len(ks)//10]}  p50={ks[len(ks)//2]}  "
              f"p90={ks[len(ks)*9//10]}")
        print(f"响应耗时 ms    p10={ts[len(ts)//10]}  p50={ts[len(ts)//2]}  "
              f"p90={ts[len(ts)*9//10]}")
    print(f"结果 -> {out}")


if __name__ == "__main__":
    sys.exit(main())
