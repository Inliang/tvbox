#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract.py —— 从采集回来的公开配置中拆解站点源，按 A/B/C/D/E 五档分级、去重。

五档定义（全部可复现，不依赖主观判断）：

  A  远程单源   : type==1 且 api 为绝对 http(s) URL。自包含，可实测返回合法 JSON。
  B  参数化源   : type==3 且 api 的类名属于"站点类"白名单，且 ext 里含公网绝对 URL。
                  ext 才是真正的目标地址，跨配置迁移后仍然有效；且该 URL 可用于前端探测。
  C  自包含源   : type==3 且类名合法，但无 ext（类内部自带目标，不依赖第三方域名存活）。
                  最稳的一类，但无可探 URL，页面只能标"未测"。
  D  本地依赖   : ext 指向 ./lib/ 相对文件，或 host 是 127.0.0.1 / localhost / 0.0.0.0。
                  跨配置迁移必然失效；且浏览器探 127.0.0.1 可能"探通"，是假绿来源。
  E  拒绝       : 类名不存在于 spider dex；或 api 是相对路径；或类名属于非站点类；或 type 非标。

非站点类（不可当站点合并）：Init 初始化入口、Proxy 代理工具、Push 推送、JSDemo 示例、Market 应用市场。
可用站点类上界 = 42 − 5 = 37。

用法：
    python extract.py            # 拆解并输出 data/candidates.json
    python extract.py --probe    # 额外对 A 档做网络实测（慢）
"""
import sys
import os
import re
import json
import time
import urllib.request
import urllib.error
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
DATA_DIR = os.path.join(ROOT, "data")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 这些类不是"站点"，不能作为 site 合并
NON_SITE = {"Init", "Proxy", "Push", "JSDemo", "Market"}

GROUP_RULES = [
    ("直播", ["直播", "电视", "卫视", "iptv", "cctv", "体育", "看球"]),
    ("短剧", ["短剧", "剧王", "星牙"]),
    ("动漫", ["动漫", "番剧", "动画", "巴士"]),
    ("音乐", ["音乐", "MV", "酷狗", "听歌"]),
    ("网课", ["课堂", "教学", "小学", "初中", "高中", "启蒙", "少儿", "教育", "急救"]),
    ("网盘", ["网盘", "盘搜", "米搜", "夸克", "阿里", "115", "磁力"]),
    ("工具", ["配置", "工具", "推送", "中心", "设置", "关注公众号"]),
    ("APP", ["app"]),
    ("影视", []),
]

URL_RE = re.compile(r'https?://[^\s"\'|,}\)\\]+')
LOCAL_RE = re.compile(r'//(127\.0\.0\.1|localhost|0\.0\.0\.0)')


def load_json(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def dex_classes():
    d = load_json(os.path.join(DATA_DIR, "dex_classes.json")) or {}
    return set(d.get("classes", []))


def group_of(name):
    low = (name or "").lower()
    for g, kws in GROUP_RULES:
        if not kws:
            continue
        for kw in kws:
            if kw.lower() in low:
                return g
    return "影视"


def is_abs_url(s):
    return isinstance(s, str) and re.match(r"^https?://[^\s]+$", s.strip()) is not None


def judge(site, classes):
    """五档判定。返回 (档位, 理由, 可探 URL 列表)"""
    api = site.get("api", "")
    ext = site.get("ext")
    t = site.get("type")

    if not isinstance(api, str) or not api.strip():
        return "E", "api 为空", []
    api = api.strip()

    # A 档：type1 远程自包含
    if api.startswith("http"):
        if t == 1:
            return "A", "type1 远程 json 源，可实测", [api]
        return "E", f"绝对 URL 但 type={t}，非标准用法", []

    # 相对路径
    if api.startswith("./") or api.startswith("../"):
        return "E", "api 是相对路径，跨配置迁移必然失效", []

    name = api[4:] if api.startswith("csp_") else api
    if not re.match(r"^[A-Za-z0-9_]+$", name):
        return "E", f"无法识别的 api：{api}", []
    if name not in classes:
        return "E", f"类 com.github.catvod.spider.{name} 不在 spider dex 中，必然死站", []
    if name in NON_SITE:
        return "E", f"{name} 是非站点类（非影视站点）", []

    blob = json.dumps(ext, ensure_ascii=False) if ext is not None else ""
    urls = [u.rstrip(".,;") for u in URL_RE.findall(blob)]

    # D 档：本地依赖
    if "./lib/" in blob or "../" in blob:
        return "D", "ext 依赖本仓库 lib 文件，迁移后失效", urls
    if any(LOCAL_RE.search(u) for u in urls):
        return "D", "ext 依赖本机文件服务（127.0.0.1），浏览器探测会假绿", urls

    # B 档：有公网 URL 可探
    if urls:
        return "B", f"参数化源，可探 {urls[0]}", urls

    # C 档：自包含
    return "C", "自包含源，无可探 URL", []


def probe_url(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(600000)
            code = r.status
    except urllib.error.HTTPError as e:
        return {"ok": False, "httpStatus": e.code, "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "httpStatus": None, "error": type(e).__name__,
                "ms": int((time.time() - t0) * 1000)}
    ms = int((time.time() - t0) * 1000)
    try:
        j = json.loads(body.decode("utf-8", "ignore"))
    except Exception:
        return {"ok": False, "httpStatus": code, "error": "not_json", "ms": ms}
    return {"ok": True, "httpStatus": code, "ms": ms, "json": j}


def match_raw(cfg, raw_files):
    """把 sources.json 的条目对应到 data/raw 里的快照文件。"""
    slug = re.sub(r"[^a-z0-9]+", "-", (cfg.get("name") or "").lower()).strip("-")
    if not slug:
        return None
    for rf in raw_files:
        base = os.path.basename(rf).lower()
        if slug in base:
            return rf
    return None


def main():
    do_probe = "--probe" in sys.argv
    classes = dex_classes()
    sources = load_json(os.path.join(DATA_DIR, "sources.json")) or {}
    configs = sources.get("configs", [])

    raw_files = []
    if os.path.isdir(RAW_DIR):
        raw_files = [os.path.join(RAW_DIR, f) for f in sorted(os.listdir(RAW_DIR))
                     if f.endswith(".json")]

    buckets = defaultdict(list)
    seen = {}
    stats = defaultdict(int)

    # ---- 1) 本项目自身配置 ----
    own = load_json(os.path.join(ROOT, "zijian.json")) or {}
    for s in own.get("sites", []):
        b, reason, urls = judge(s, classes)
        item = {k: v for k, v in s.items() if not k.startswith("_")}
        item.update({"_bucket": b, "_reason": reason, "_probeUrls": urls,
                     "_source": "本项目 zijian.json", "_group": group_of(s.get("name")),
                     "_inZijian": True})
        stats["own_" + b] += 1
        if b in ("A", "B", "C", "D"):
            buckets[b].append(item)
        else:
            buckets["E"].append(item)
        sig = (item.get("api"), json.dumps(item.get("ext"), ensure_ascii=False, sort_keys=True)
               if item.get("ext") is not None else "")
        seen[sig] = True

    # ---- 2) 外部配置 ----
    for cfg in configs:
        if cfg.get("status") != "ok":
            continue
        url = cfg.get("url")
        data = None
        rf = match_raw(cfg, raw_files)
        if rf:
            data = load_json(rf)
        if not isinstance(data, dict):
            pr = probe_url(url)
            data = pr.get("json")
        if not isinstance(data, dict):
            stats["cfg_unparsed"] += 1
            continue

        for s in (data.get("sites") or []):
            if not isinstance(s, dict):
                continue
            b, reason, urls = judge(s, classes)
            item = {k: v for k, v in s.items() if not k.startswith("_")}
            item.update({"_bucket": b, "_reason": reason, "_probeUrls": urls,
                         "_source": cfg.get("name"), "_sourceUrl": url,
                         "_group": group_of(s.get("name")), "_inZijian": False})

            if b == "E":
                stats["E"] += 1
                buckets["E"].append(item)
                continue

            # 去重：A/B/C 三档按 api+ext 判同一源；同一源优先保留"本项目已有"的那条
            sig = (item.get("api"),
                   json.dumps(item.get("ext"), ensure_ascii=False, sort_keys=True)
                   if item.get("ext") is not None else "")
            if sig in seen:
                stats["dup_" + b] += 1
                continue
            seen[sig] = True

            buckets[b].append(item)
            stats[b] += 1

    if do_probe:
        from concurrent.futures import ThreadPoolExecutor

        def check(item):
            urls = item.get("_probeUrls") or []
            if not urls:
                return
            target = urls[0]
            pr = probe_url(target, timeout=8)
            item["_probe"] = {
                "url": target,
                "httpStatus": pr.get("httpStatus"),
                "ms": pr.get("ms"),
                "ok": bool(pr.get("ok")) or pr.get("httpStatus") == 200,
                "json": pr.get("ok", False),
                "error": pr.get("error"),
            }

        targets = [it for k in ("A", "B") for it in buckets.get(k, [])
                   if it.get("_probeUrls")]
        print(f"实测 {len(targets)} 个目标（并发 12）…", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=12) as ex:
            list(ex.map(check, targets))

        for k in ("A", "B"):
            live = sum(1 for it in buckets.get(k, []) if (it.get("_probe") or {}).get("ok"))
            dead = sum(1 for it in buckets.get(k, []) if it.get("_probe")
                       and not it["_probe"].get("ok"))
            none = sum(1 for it in buckets.get(k, []) if not it.get("_probe"))
            stats[f"probe_{k}_live"] = live
            stats[f"probe_{k}_dead"] = dead
            stats[f"probe_{k}_nourl"] = none

    out = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dexClassCount": len(classes),
        "siteClassCount": len(classes - NON_SITE),
        "stats": dict(stats),
        "counts": {k: len(v) for k, v in buckets.items()},
        "buckets": dict(buckets),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("=" * 66)
    print(f"spider dex 类总数 {len(classes)}，其中可用站点类 {len(classes - NON_SITE)}")
    print("=" * 66)
    label = {
        "A": "A 远程单源（最稳，可实测）",
        "B": "B 参数化源（可迁移，URL 可探）",
        "C": "C 自包含源（可迁移，无可探URL）",
        "D": "D 本地依赖（不合并）",
        "E": "E 拒绝（必然失效）",
    }
    for k in "ABCDE":
        print(f"  {label[k]:30} {len(buckets.get(k, []))}")
    for k in sorted(stats):
        if k.startswith(("own_", "dup_", "cfg_")):
            print(f"    · {k:16} {stats[k]}")

    mergeable = sum(len(buckets.get(k, [])) for k in "ABC")
    new_merge = sum(1 for k in "ABC" for it in buckets.get(k, []) if not it.get("_inZijian"))
    print("-" * 66)
    print(f"  可合并总量（含本已有）: {mergeable}")
    print(f"  其中新增（不在 zijian 中）: {new_merge}")
    print(f"  输出: data/candidates.json")


if __name__ == "__main__":
    main()
