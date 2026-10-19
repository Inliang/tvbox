#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冻结版最终结构核对（G3）：把报告里要引用的数字一次性算准。"""
import json, os, re, hashlib, collections

ROOT = r"E:\GitHub\tvbox"
TOP = ["spider", "wallpaper", "logo", "sites", "parses", "doh",
       "lives", "headers", "proxy", "hosts", "ads", "rules"]
BASE = os.path.join(ROOT, "data", "backup", "zijian-20261019-1539.json")


def rd(p):
    with open(p, "rb") as f:
        return f.read()


def sig(s):
    return (str(s.get("api", "")).strip(), str(s.get("name", "")).strip())


base_doc = json.loads(rd(BASE).decode("utf-8-sig"))
base_sites = base_doc["sites"]

for name in ("zijian.json", "zijian-full.json"):
    print("=" * 74)
    print(f"【{name}】")
    print("=" * 74)
    raw = rd(os.path.join(ROOT, name))
    print(f"  字节 {len(raw)}   md5 {hashlib.md5(raw).hexdigest()}")
    print(f"  BOM: {raw.startswith(b'\xef\xbb\xbf')}")
    txt = raw.decode("utf-8")            # 非 UTF-8 会在这里抛
    doc = json.loads(txt)                 # 严格解析：有注释/尾逗号会抛
    print(f"  严格 JSON 解析: OK（解析成功即证明不存在 // 注释、尾逗号、// * 块注释）")

    # 防御性再扫一次裸 //（先把字符串内容抹掉）
    stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', txt)
    bare = [i for i, ln in enumerate(stripped.split("\n"), 1) if "//" in ln]
    print(f"  字符串外出现 // 的行: {bare or '无'}")

    miss = [k for k in TOP if k not in doc]
    print(f"  顶层 12 字段齐全: {'是' if not miss else '缺 ' + str(miss)}   实际字段数 {len(doc)}")

    diffs = []
    for k in doc:
        if k == "sites":
            continue
        if k not in base_doc:
            diffs.append(f"{k} 备份中不存在")
        elif json.dumps(base_doc[k], ensure_ascii=False, sort_keys=True) != \
             json.dumps(doc[k], ensure_ascii=False, sort_keys=True):
            diffs.append(k)
    print(f"  非 sites 字段与备份差异: {diffs or '无'}")

    spider = doc["spider"]
    rel, tag, md5 = spider.split(";")
    fp = os.path.join(ROOT, rel[2:].replace("/", os.sep))
    actual = hashlib.md5(rd(fp)).hexdigest()
    print(f"  spider md5: 声明 {md5} / 实际 {actual} -> {'一致' if md5.lower() == actual else '不一致'}")

    sites = doc["sites"]
    print(f"  sites 数量: {len(sites)}")
    keys = [str(s.get("key")) for s in sites]
    dups = [k for k, v in collections.Counter(keys).items() if v > 1]
    print(f"  key 唯一: {'是' if not dups else '重复 ' + str(dups)}")
    bad_type = [s.get("key") for s in sites if not isinstance(s.get("type"), int) or isinstance(s.get("type"), bool)]
    print(f"  type 全为 int: {'是' if not bad_type else bad_type}")
    ext_null = [s.get("key") for s in sites if "ext" in s and s["ext"] is None]
    print(f"  ext 为 null 的站点: {ext_null or '无'}")
    ext_kind = collections.Counter(type(s["ext"]).__name__ for s in sites if "ext" in s)
    print(f"  ext 类型分布: {dict(ext_kind)}")

    cur = {sig(s): s for s in sites}
    lost = [s for s in base_sites if sig(s) not in cur]
    renamed = [(s.get("key"), cur[sig(s)].get("key")) for s in base_sites
               if sig(s) in cur and str(cur[sig(s)].get("key")) != str(s.get("key"))]
    print(f"  原始 51 站丢失: {len(lost)}   key 被改名: {renamed or '无'}")
    print()

# ---------- includedIn ----------
print("=" * 74)
print("includedIn 三值 vs 两份配置实际内容")
print("=" * 74)
main_cfg = json.loads(rd(os.path.join(ROOT, "zijian.json")).decode("utf-8"))
full_cfg = json.loads(rd(os.path.join(ROOT, "zijian-full.json")).decode("utf-8"))
main_set = {sig(s) for s in main_cfg["sites"]}
full_set = {sig(s) for s in full_cfg["sites"]}
sj = json.loads(rd(os.path.join(ROOT, "docs", "data", "sites.json")).decode("utf-8"))
items = sj["items"]
dist = collections.Counter(x.get("includedIn") for x in items)
bad = []
for it in items:
    k = sig(it)
    exp = "main" if k in main_set else ("full" if k in full_set else False)
    got = it.get("includedIn")
    if (exp is False and got not in (False, None)) or (exp is not False and got != exp):
        bad.append((it.get("name"), got, exp))
print(f"  页面记录分布: {dict(dist)}")
print(f"  与配置实际内容不符: {len(bad)} 条 {bad[:5]}")
print(f"  main 集合里是否都真在 zijian.json: {all(sig(x) in main_set for x in items if x.get('includedIn') == 'main')}")
print(f"  full 集合里是否都真在 zijian-full.json: {all(sig(x) in full_set for x in items if x.get('includedIn') == 'full')}")

# ---------- 页面口径 ----------
print()
print("=" * 74)
print("页面数据口径")
print("=" * 74)
cf = json.loads(rd(os.path.join(ROOT, "docs", "data", "configs.json")).decode("utf-8"))
print(f"  sites.json total = {sj.get('total')} / items = {len(items)} / schema = {sj.get('schema')}")
print(f"  configs.json total = {cf.get('total')} / items = {len(cf['items'])} / schema = {cf.get('schema')}")
nulls = [c["id"] for c in cf["items"] if c.get("totalSites") is None]
print(f"  totalSites 为 null 的配置 {len(nulls)} 个: {nulls}")
print(f"  其中 isMulti=True 的 {sum(1 for c in cf['items'] if c.get('totalSites') is None and c.get('isMulti'))} 个")
inv = [(c["id"], c.get("totalSites"), c.get("staticPass"), c.get("probeConfirmed"))
       for c in cf["items"] if c.get("totalSites") and c.get("staticPass") is not None
       and (c["staticPass"] > c["totalSites"] or (c.get("probeConfirmed") or 0) > c["staticPass"])]
print(f"  指标倒挂（staticPass>totalSites 或 probeConfirmed>staticPass）: {inv or '无'}")
print(f"  segment 分布: {dict(collections.Counter(str(x.get('segment')) for x in items))}")
print(f"  tier 分布: {dict(collections.Counter(str(x.get('tier')) for x in items))}")
