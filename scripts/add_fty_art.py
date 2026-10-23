#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量把饭太硬 .art 图片载体配置登记进 data/sources.json + data/raw/。

不重跑 fetch_sources.py 全量，避免网络抖动把已有的 55 个可用源冲掉。
复用 fetch_sources 的解析/修复函数，保证与全量采集产出同构。
"""
import sys, os, json, datetime, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_sources as fs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(ROOT, "data", "sources.json")
RAW = os.path.join(ROOT, "data", "raw", "84-fty-art.json")
NAME = "fty-art"
URL = "http://www.饭太硬.art/tv"
NOTE = "饭太硬主接口；图片尾部内嵌配置（bCCtSiKQ** + base64），spider md5 与 qist 镜像一致"

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
opener.addheaders = [("User-Agent", fs.UA if isinstance(fs.UA, str) else "Mozilla/5.0")]

nu = fs.normalize_url(URL)
with opener.open(nu, timeout=25) as r:
    body = r.read()
    ctype = r.headers.get("Content-Type", "")
print("fetched", len(body), "bytes, ctype=", ctype)

payload, kind = fs.extract_gif_payload(body, ctype)
assert payload, "未解出图片载荷"
print("payload kind =", kind, "bytes =", len(payload))
text = payload.decode("utf-8", "replace")
text = fs.repair_json_text(text)
cfg = json.loads(text)
print("sites =", len(cfg.get("sites", [])), "lives =", len(cfg.get("lives", [])),
      "spider =", str(cfg.get("spider", ""))[:80])

with open(RAW, "w", encoding="utf-8", newline="\n") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
print("wrote", RAW)

doc = json.load(open(SOURCES, encoding="utf-8"))
cfgs = doc["configs"]
assert not any(c.get("name") == NAME for c in cfgs), "已存在 fty-art"
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
stamp = now.replace(microsecond=0).isoformat()
entry = {
    "name": NAME,
    "url": URL,
    "category": "综合",
    "note": NOTE,
    "status": "ok",
    "checkedAt": stamp,
    "httpStatus": 200,
    "respBytes": len(body),
    "sitesCount": len(cfg.get("sites", [])),
    "urlsCount": 0,
    "kind": "single",
    "error": None,
    "elapsedMs": 0,
    "rawFile": "data/raw/84-fty-art.json",
    "payloadKind": kind,
}
cfgs.append(entry)
doc["summary"]["total"] = len(cfgs)
doc["summary"]["ok"] = sum(1 for c in cfgs if c.get("status") == "ok")
doc["summary"]["fail"] = sum(1 for c in cfgs if c.get("status") == "fail")
doc["summary"]["single"] = sum(1 for c in cfgs if c.get("kind") == "single")
doc["summary"]["multi"] = sum(1 for c in cfgs if c.get("kind") == "multi")
doc["generatedAt"] = stamp
json.dump(doc, open(SOURCES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("sources.json updated: total =", doc["summary"]["total"],
      "ok =", doc["summary"]["ok"])
