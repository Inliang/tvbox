#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C 组：数据准确性抽查（只读，不修改任何数据）

C1  从 docs/data/sites.json 抽 5 条，去对应 configId 的配置里核对站点是否真实存在、api 是否一致
C2  includedIn 三值（main/full/false）与 zijian.json / zijian-full.json 实际内容对得上
C3  snippet 必须是能直接粘进 TVBox 配置的合法 JSON 片段
"""
import os, sys, json, random, re, urllib.request, urllib.error

ROOT = r"E:\GitHub\tvbox"
random.seed(20261019)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8-sig") as f:
        return json.load(f)


def sig(x):
    return (str(x.get("api", "")).strip(), str(x.get("name", "")).strip())


sites_doc = load("docs/data/sites.json")
cfgs_doc = load("docs/data/configs.json")
sites = sites_doc["items"]
cfgs = cfgs_doc["items"]
cfg_by_id = {c["id"]: c for c in cfgs}

main_cfg = load("zijian.json")
full_cfg = load("zijian-full.json")
main_set = {sig(s) for s in main_cfg["sites"]}
full_set = {sig(s) for s in full_cfg["sites"]}

problems = []

print("=" * 78)
print("C2  includedIn 三值 vs 实际配置内容")
print("=" * 78)
from collections import Counter
dist = Counter()
mismatch = []
for it in sites:
    k = sig(it)
    expect = "main" if k in main_set else ("full" if k in full_set else False)
    got = it.get("includedIn")
    dist[got if got is not False else "false"] += 1
    okflag = (expect is False and got in (False, None)) or (expect is not False and got == expect)
    if not okflag:
        mismatch.append((it.get("name"), it.get("api", "")[:56], got, expect))
print(f"页面记录分布：{dict(dist)}")
print(f"与 zijian.json / zijian-full.json 实际内容不符：{len(mismatch)} 条")
for m in mismatch[:12]:
    print(f"   - {m[0]!r} api={m[1]} 记录={m[2]!r} 实际={m[3]!r}")

# 反向检查：配置里的站点是否都出现在 sites.json 里
site_sigs = {sig(s) for s in sites}
main_orphan = [s for s in main_cfg["sites"] if sig(s) not in site_sigs]
print(f"\n反向核对：zijian.json 中 {len(main_cfg['sites'])} 个站点，"
      f"有 {len(main_orphan)} 个在 sites.json 里找不到（页面上查不到）")
for s in main_orphan[:10]:
    print(f"   - {s.get('key')!r} {s.get('name')!r} api={str(s.get('api'))[:50]}")

if len(mismatch) or len(main_orphan):
    problems.append(f"C2: includedIn 不符 {len(mismatch)} 条，配置站点未进页面 {len(main_orphan)} 条")

print()
print("=" * 78)
print("C3  snippet 是否为可直接粘贴的合法 JSON")
print("=" * 78)
bad_snippet = []
frag_mismatch = []
for it in sites:
    sn = it.get("snippet")
    if not isinstance(sn, str) or not sn.strip():
        bad_snippet.append((it.get("name"), "缺失或非字符串"))
        continue
    try:
        obj = json.loads(sn)
    except Exception as e:
        bad_snippet.append((it.get("name"), f"JSON 解析失败: {e}"))
        continue
    if not isinstance(obj, dict):
        bad_snippet.append((it.get("name"), f"不是对象而是 {type(obj).__name__}"))
        continue
    for fld in ("key", "name", "type", "api"):
        if fld not in obj:
            bad_snippet.append((it.get("name"), f"缺字段 {fld}"))
    if str(obj.get("api", "")).strip() != str(it.get("api", "")).strip():
        frag_mismatch.append((it.get("name"), obj.get("api"), it.get("api")))

print(f"总条数 {len(sites)}，snippet 不合法 {len(bad_snippet)} 条")
for x in bad_snippet[:10]:
    print(f"   - {x[0]!r}: {x[1]}")
print(f"snippet.api 与列表 api 不一致 {len(frag_mismatch)} 条")
for x in frag_mismatch[:6]:
    print(f"   - {x[0]!r}: snippet={x[1]!r} vs item={x[2]!r}")

print("\n--- 抽 3 条展示 snippet 原文 ---")
for it in random.sample(sites, 3):
    print(f"  [{it.get('name')}] -> {it.get('snippet')}")

if bad_snippet:
    problems.append(f"C3: snippet 不合法 {len(bad_snippet)} 条")

print()
print("=" * 78)
print("C1  抽 5 条站点，回源核对该配置里是否真有这个站点")
print("=" * 78)


def fetch(url, timeout=20):
    """先直连，失败则用 jsdelivr 镜像重试（raw.githubusercontent 在国内常被 TLS 干扰）。"""
    def _try(u):
        try:
            req = urllib.request.Request(u, headers={
                "User-Agent": "okhttp/3.12.13", "Accept": "*/*", "Connection": "close"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(2_000_000), u
        except Exception as e:
            return None, str(e).encode(), u

    st, body, used = _try(url)
    if st is not None:
        return st, body, used
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", url)
    if m:
        owner, repo, ref, path = m.groups()
        alt = f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{ref}/{path}"
        st2, body2, _ = _try(alt)
        if st2 is not None:
            return st2, body2, alt + "  (jsdelivr 镜像)"
    return None, body, url


sample = random.sample(sites, 8)
print(f"抽样 {len(sample)} 条：{[s.get('name') for s in sample]}\n")
unverified = 0
verified = 0
for it in sample:
    cid = it.get("configId")
    c = cfg_by_id.get(cid)
    print(f"--- [{it.get('name')}]  configId={cid}  api={it.get('api')}")
    if not c:
        print("    ✗ 找不到该 configId 对应的配置")
        unverified += 1
        continue
    if "github-inliang" == cid:
        local = main_cfg if sig(it) in main_set else full_cfg
        hit = [s for s in local["sites"] if sig(s) == sig(it)]
        print(f"    本地核对（自建配置）：{'在配置中，api 一致' if hit else '不在配置中'}")
        if hit:
            verified += 1
        else:
            problems.append(f"C1: {it.get('name')} 不在自建配置中")
        continue
    url = c.get("url", "")
    st, body, used = fetch(url)
    if st is None:
        print(f"    ⚠ 拉取失败（{body[:60].decode('utf-8', 'ignore')}），无法核对 -> {url}")
        unverified += 1
        continue
    try:
        cfg = json.loads(body.decode("utf-8", "ignore"))
    except Exception as e:
        print(f"    ⚠ 返回 {st} 但不是合法 JSON（{e}），无法核对（经 {used}）")
        unverified += 1
        continue
    cfg = cfg or {}
    raw_sites = cfg.get("sites") if isinstance(cfg, dict) else None
    if not isinstance(raw_sites, list):
        print(f"    ⚠ 返回 {st} 但结构不是 {{sites:[...]}}，无法核对")
        unverified += 1
        continue
    hit = [s for s in raw_sites if isinstance(s, dict) and sig(s) == sig(it)]
    if hit:
        verified += 1
        print(f"    ✓ HTTP {st}（经 {used}），该配置共 {len(raw_sites)} 站点，找到目标且 api 完全一致")
    else:
        api_hit = [s for s in raw_sites if isinstance(s, dict) and
                   str(s.get("api", "")).strip() == str(it.get("api", "")).strip()]
        print(f"    ✗ HTTP {st}（经 {used}），该配置共 {len(raw_sites)} 站点，未找到该站点"
              f"（同 api 命中 {len(api_hit)} 条）")
        problems.append(f"C1: {it.get('name')} 在其来源配置 {cid} 中不存在")

print()
print("=" * 78)
print("结论")
print("=" * 78)
print(f"成功核对 {verified} 条，无法核对 {unverified} 条")
if problems:
    print("发现问题：")
    for p in problems:
        print("  - " + p)
else:
    print("C 组未发现数据准确性问题")
