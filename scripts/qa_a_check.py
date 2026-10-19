#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox 配置验收脚本 —— A 组：配置文件能否被 TVBox 正确加载

不修改任何业务数据，只做只读校验并输出结果。
"""
import os, io, sys, json, re, hashlib, collections

ROOT = r"E:\GitHub\tvbox"
PY = sys.executable

MISSING_TOP = ["spider","wallpaper","logo","sites","parses","doh",
               "lives","headers","proxy","hosts","ads","rules"]

def rd(p):
    with open(p, "rb") as f:
        return f.read()

def rep(items):
    for it in items:
        print("   ", it)

print("=" * 78)
print("A 组：TVBox 配置加载正确性")
print("=" * 78)

TARGETS = {
    "zijian.json": "data/backup/zijian-20261019-1539.json",
    "zijian-full.json": "data/backup/zijian-20261019-1539.json",
}

for name, base_rel in TARGETS.items():
    print()
    print("-" * 78)
    print(f"【目标】{name}")
    print("-" * 78)
    path = os.path.join(ROOT, name)
    bpath = os.path.join(ROOT, base_rel)
    raw = rd(path)

    # A1 严格 JSON / 编码 / BOM
    print("\n[A1] 严格 JSON 与编码")
    print("     文件字节数        :", len(raw))
    print("     是否为 UTF-8 BOM  :", raw.startswith(b"\xef\xbb\xbf"))
    try:
        txt = raw.decode("utf-8")
        print("     UTF-8 解码        : OK")
    except UnicodeDecodeError as e:
        print("     UTF-8 解码        : FAIL ->", e)
        continue
    # 注释 / 尾逗号检测（严格模式下 load 会报出来）
    strict_err = None
    try:
        doc = json.loads(txt)
        dec = json.JSONDecoder()
        dec.decode(txt)
        print("     json.loads        : OK（无注释/无尾逗号/无多余内容）")
    except json.JSONDecodeError as e:
        strict_err = e
        print("     json.loads        : FAIL ->", e)

    # A2 顶层字段
    print("\n[A2] 顶层字段完整性")
    keys = list(doc.keys())
    print("     顶层字段顺序/数量 :", len(keys), keys)
    miss = [k for k in MISSING_TOP if k not in doc]
    extra = [k for k in keys if k not in MISSING_TOP]
    print("     缺失标准字段      :", miss or "无")
    print("     非标准字段        :", extra or "无")

    # A2b 非 sites 字段与备份是否完全一致
    print("\n[A2b] 非 sites 字段 vs 备份一致性")
    braw = rd(bpath)
    bdoc = json.loads(braw.decode("utf-8-sig"))
    diffs = []
    for k in keys:
        if k == "sites":
            continue
        if k not in bdoc:
            diffs.append(f"{k}: 备份中不存在")
        elif json.dumps(bdoc[k], ensure_ascii=False, sort_keys=True) != \
             json.dumps(doc[k], ensure_ascii=False, sort_keys=True):
            diffs.append(f"{k}: 内容被改动")
    for k in bdoc:
        if k != "sites" and k not in doc:
            diffs.append(f"{k}: 备份里有但新配置丢失")
    print("     差异              :", diffs or "无（完全一致）")
    print(f"     sites 数量        : 备份 {len(bdoc.get('sites',[]))} -> 现 {len(doc.get('sites',[]))}")

    # A3 spider md5
    print("\n[A3] spider md5")
    spider = doc.get("spider", "")
    print("     spider 值         :", spider)
    parts = spider.split(";")
    if len(parts) >= 3 and parts[1].strip().lower() == "md5":
        rel = parts[0].strip()
        fp = os.path.join(ROOT, rel[2:].replace("/", os.sep)) if rel.startswith("./") else None
        if fp and os.path.exists(fp):
            actual = hashlib.md5(rd(fp)).hexdigest()
            expect = parts[2].strip().lower()
            print(f"     期望 md5          : {expect}")
            print(f"     实际 md5          : {actual}")
            print("     结论              :", "OK" if expect == actual else "FAIL（TVBox 拒绝加载整个配置）")
        else:
            print("     结论              : FAIL spider 文件不存在", rel)
    else:
        print("     结论              : 无 md5 段（TVBox 不强校验，但每次联网拉最新的 spider）")

    # A4 key 唯一 / type 数值
    print("\n[A4] key 唯一性与 type 类型")
    sites = doc.get("sites", [])
    counter = collections.Counter()
    bad = []
    for i, s in enumerate(sites):
        if not isinstance(s, dict):
            bad.append(f"sites[{i}] 不是对象: {type(s).__name__}")
            continue
        k = s.get("key")
        counter[k] += 1
        t = s.get("type")
        if isinstance(t, bool) or not isinstance(t, int):
            bad.append(f"sites[{i}] key={k!r} type={t!r} ({type(t).__name__})")
    dups = [(k, c) for k, c in counter.items() if c > 1]
    print("     sites 总数        :", len(sites))
    print("     唯一 key 数       :", len(counter))
    print("     重复 key          :", dups or "无")
    print("     type 非整型       :", bad or "无")

    # A5 ext 本地依赖
    print("\n[A5] 新站点 ext 本地依赖（./lib/ 127.0.0.1 localhost）")
    base_sigs = {(str(s.get("key")), str(s.get("api"))) for s in bdoc.get("sites", []) if isinstance(s, dict)}
    LOCAL = re.compile(r"//(127\.0\.0\.1|localhost|0\.0\.0\.0)")
    hits = []
    newcnt = 0
    for s in sites:
        if not isinstance(s, dict):
            continue
        sig = (str(s.get("key")), str(s.get("api")))
        if sig in base_sigs:
            continue
        newcnt += 1
        blob = json.dumps(s.get("ext"), ensure_ascii=False) if s.get("ext") is not None else ""
        for tok in ("./lib/", "../"):
            if tok in blob:
                hits.append(f"[{s.get('key')}] ext 含 {tok}")
        if LOCAL.search(blob):
            hits.append(f"[{s.get('key')}] ext 指向本机地址")
    print("     新增站点数        :", newcnt)
    print("     违规              :", hits or "无")

print()
print("=" * 78)
print("A 组脚本执行完毕")
print("=" * 78)
