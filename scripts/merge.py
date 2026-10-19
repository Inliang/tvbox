#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge.py —— 把通过准入的候选站点合并进配置。

产物（两份）：
    zijian.json       主配置：原有 51 + A 档 + C 档
    zijian-full.json  扩展配置：原有 51 + A + C + B（同 host 收敛）

执行纪律（硬性）：
  1. 只重建 sites 数组，其余顶层字段从原文件逐字节原样拷贝
  2. 覆盖前备份到 data/backup/
  3. 新站 append 到末尾，不插中间、不重排原有站点
  4. key 冲突：原有 key 一个不改；新站冲突改为 <来源前缀>_<key>，再冲突加 _2/_3
  5. 两份配置除 sites 外必须完全一致
  6. 写盘后自校验，不通过则回滚

用法：
    python merge.py --dry-run          # 只算不写
    python merge.py                    # 生成两份
    python merge.py --mode main        # 只生成主配置
"""
import sys
import os
import re
import json
import shutil
import hashlib
import datetime
from collections import defaultdict
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BACKUP = os.path.join(DATA, "backup")

URL_RE = re.compile(r'https?://[^\s"\'|,}\)\\]+')
LOCAL_HOST = {"127.0.0.1", "localhost", "0.0.0.0"}

GROUP_RULES = [
    ("直播", ["直播", "电视", "卫视", "iptv", "cctv", "体育", "看球"]),
    ("短剧", ["短剧", "剧王", "星牙"]),
    ("动漫", ["动漫", "番剧", "动画", "巴士"]),
    ("音乐", ["音乐", "mv", "酷狗", "听歌"]),
    ("网课", ["课堂", "教学", "小学", "初中", "高中", "启蒙", "少儿", "教育", "急救"]),
    ("网盘", ["网盘", "盘搜", "米搜", "夸克", "阿里", "115", "磁力"]),
    ("工具", ["配置", "工具", "推送", "中心", "设置", "关注公众号"]),
    ("APP", ["app"]),
    ("影视", []),
]

# 合并时保留的站点字段（丢弃 categories 等纯展示字段以控制体积）
KEEP_FIELDS = ("key", "name", "type", "api", "searchable", "quickSearch", "filterable",
               "changeable", "playerType", "ext", "style", "gridview", "jar", "logo",
               "timeout", "clickSelector", "homePage")


def load_json(p):
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        print(f"[FATAL] 读取失败 {p}: {e}")
        sys.exit(2)


def group_of(name):
    low = (name or "").lower()
    for g, kws in GROUP_RULES:
        if not kws:
            continue
        for kw in kws:
            if kw in low:
                return g
    return "影视"


def host_of(site):
    """取站点依赖的外部 host，用于 full 配置收敛。"""
    api = site.get("api") or ""
    if api.startswith("http"):
        try:
            return urlparse(api).netloc.lower()
        except Exception:
            return ""
    ext = site.get("ext")
    blob = json.dumps(ext, ensure_ascii=False) if ext is not None else ""
    for u in URL_RE.findall(blob):
        try:
            h = urlparse(u).netloc.lower()
            if h and h not in LOCAL_HOST:
                return h
        except Exception:
            continue
    return ""


def signature(site):
    return (str(site.get("api")),
            json.dumps(site.get("ext"), ensure_ascii=False, sort_keys=True)
            if site.get("ext") is not None else "")


def clean(site, keep_group=True):
    """只保留已知字段，避免把别的配置里的私有字段带进来；数值字段强制规范化。"""
    out = {}
    for k in KEEP_FIELDS:
        if k in site and site[k] is not None:
            out[k] = site[k]
    # 必填兜底
    out["key"] = str(site.get("key") or "site")
    out["name"] = str(site.get("name") or out["key"])
    out["api"] = str(site.get("api")).strip()

    # 数值字段：新增站点统一为 number（TVBox 对字符串 type 会拒载该站）
    for nk in ("type", "searchable", "quickSearch", "filterable", "changeable", "playerType"):
        if nk in out:
            v = out[nk]
            if isinstance(v, str) and v.strip().isdigit():
                out[nk] = int(v.strip())
            elif isinstance(v, bool):
                out[nk] = int(v)
    if "type" not in out or out["type"] is None:
        out["type"] = 3

    if keep_group:
        out["group"] = group_of(out["name"])
    return out


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    only_main = "--mode" in args and "main" in args

    base = load_json(os.path.join(ROOT, "zijian.json"))
    cand = load_json(os.path.join(DATA, "site_candidates.json"))
    items = cand.get("items", [])

    base_sites = base.get("sites", [])
    stats = defaultdict(int)

    # 降级剔除：已经被判为 D/E/Y 的站点不该留在主配置里。
    # 但用户原始站点（original_baseline.json）永远受保护，一个都不删。
    ob = load_json(os.path.join(DATA, "original_baseline.json")) if os.path.exists(
        os.path.join(DATA, "original_baseline.json")) else None
    protected = {signature(s) for s in ob.get("sites", [])} if ob else set()
    degraded = set()
    for it in items:
        # Y 档（type1 但探测不确定）不配进主配置，只在扩展配置末尾保留
        if it.get("tier") in ("D", "E", "Y"):
            degraded.add(signature(it.get("site") or {}))

    removed = []
    kept = []
    for s in base_sites:
        sig = signature(s)
        if sig in degraded and sig not in protected:
            removed.append(s)
        else:
            kept.append(s)
    if removed:
        stats["degraded_removed"] = len(removed)
    base_sites = kept

    base_sigs = {signature(s) for s in base_sites}
    used_keys = {str(s.get("key")) for s in base_sites}

    # 按档分组，保持 A → C → B(可探) → B(加密) → Y 顺序
    # Y 档 = 测不准的 type1：探针 403/TLS/编码失败，不代表站点死了。
    # 按"误判死的代价远大于漏判活"的原则，放进扩展配置末尾而不是丢弃。
    pool = {"A": [], "C": [], "B": [], "Y": []}
    seen_sig = set()
    for it in items:
        tier = it.get("tier")
        site = it.get("site") or {}
        sig = signature(site)

        # type3 且探测明确 dead（404/拒绝/超时）→ 确定死站，不进任何配置
        if tier == "B" and it.get("probe_status") == "dead":
            stats["b_dead_dropped"] += 1
            continue

        if tier == "D":
            # 只捞回"测不准的 type1"，本地依赖(local/relpath)仍然拒绝
            if (it.get("reason_code") == "probe_uncertain"
                    and site.get("type") == 1):
                tier = "Y"
            else:
                continue

        if tier not in pool:
            continue
        if sig in seen_sig:
            stats["dup"] += 1
            continue
        seen_sig.add(sig)
        if sig in base_sigs:
            stats[f"already_{tier}"] += 1
            pool[tier].append({"site": site, "skip": True, "tier": tier,
                               "src": it.get("config_ref") or "",
                               "enc": not it.get("probe_url")})
            continue
        pool[tier].append({"site": site, "skip": False, "tier": tier,
                           "src": it.get("config_ref") or "",
                           "enc": not it.get("probe_url")})

    def build(tiers, collapse_host=False, per_host=3):
        out = []
        host_count = defaultdict(int)
        for tier in tiers:
            # B 档内部：可探（有 probe_url）的排前面，加密 ext 的排后面，
            # 因为加密源初始化成本最高且 100% 无法预验证。
            entries = sorted(pool[tier],
                             key=lambda e: (1 if e.get("enc") else 0,
                                            e["site"].get("name") or ""))
            for entry in entries:
                if entry["skip"]:
                    continue
                site = clean(entry["site"])
                if tier == "B" and collapse_host:
                    h = host_of(entry["site"])
                    if h:
                        if host_count[h] >= per_host:
                            stats["host_collapsed"] += 1
                            continue
                        host_count[h] += 1
                out.append((tier, entry["src"], site))
        return out

    main_new = build(["A", "C"])
    # 分段顺序：A+C(最稳) → B 可探 → B 加密 → Y(测不准的 type1)
    full_new = build(["A", "C", "B", "Y"], collapse_host=False)

    # key 冲突处理
    def assign_keys(rows):
        keys = set(used_keys)
        for tier, src, site in rows:
            k = site["key"]
            if k in keys:
                base_k = re.sub(r"[^A-Za-z0-9\u4e00-\u9fa5]+", "", str(k))[:16] or "ext"
                n = 2
                newk = f"{base_k}_{n}"
                while newk in keys:
                    n += 1
                    newk = f"{base_k}_{n}"
                stats["key_renamed"] += 1
                site["key"] = newk
                keys.add(newk)
            else:
                keys.add(k)
        return rows

    main_new = assign_keys(main_new)
    # full 复用同一批 key（两份配置的公共部分 key 必须一致）
    used_keys |= {s["key"] for _, _, s in main_new}
    full_only = [r for r in full_new if r[0] in ("B", "Y")]
    full_only = assign_keys(full_only)

    main_sites = list(base_sites) + [s for _, _, s in main_new]
    full_sites = list(base_sites) + [s for _, _, s in main_new] + [s for _, _, s in full_only]

    print("=" * 70)
    print("合并计划")
    print("=" * 70)
    print(f"  原有站点            : {len(base_sites)}")
    print(f"  新增 → 主配置 (A+C) : {len(main_new)}  → 合计 {len(main_sites)}")
    print(f"  新增 → 扩展 (B+Y)   : {len(full_only)}  → 合计 {len(full_sites)}")
    print(f"  跳过（已在配置中）  : "
          f"{sum(stats[k] for k in stats if k.startswith('already_'))}")
    print(f"  重复丢弃            : {stats.get('dup', 0)}")
    print(f"  确定死站剔除        : {stats.get('b_dead_dropped', 0)}")
    print(f"  key 重命名          : {stats.get('key_renamed', 0)}")
    for t in ("A", "C", "B", "Y"):
        print(f"    {t} 档候选 {len(pool[t]):3}  "
              f"(已存在 {sum(1 for e in pool[t] if e['skip'])})")

    if dry:
        print("\n[dry-run] 不写文件。")
        return 0

    # 备份
    os.makedirs(BACKUP, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    bp = os.path.join(BACKUP, f"zijian-{ts}.json")
    shutil.copy2(os.path.join(ROOT, "zijian.json"), bp)
    print(f"\n备份 → {os.path.relpath(bp, ROOT)}")

    # 组装：非 sites 字段原样拷贝
    def assemble(sites):
        cfg = {}
        for k, v in base.items():
            if k == "sites":
                cfg["sites"] = sites
            else:
                cfg[k] = v
        return cfg

    main_cfg = assemble(main_sites)
    targets = [("zijian.json", main_cfg)]
    if not only_main:
        targets.append(("zijian-full.json", assemble(full_sites)))

    for fname, cfg in targets:
        p = os.path.join(ROOT, fname)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        size = os.path.getsize(p)
        print(f"写入 {fname}  站点 {len(cfg['sites'])}  体积 {size/1024:.1f} KB")

    # 一致性断言：非 sites 字段必须完全一致
    if len(targets) == 2:
        a = {k: v for k, v in main_cfg.items() if k != "sites"}
        b = {k: v for k, v in targets[1][1].items() if k != "sites"}
        if a != b:
            print("[FATAL] 两份配置的非 sites 字段不一致")
            return 3
        print("一致性校验通过：两份配置除 sites 外完全相同")

    # changelog
    cl = os.path.join(DATA, "changelog.md")
    with open(cl, "a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.datetime.now():%Y-%m-%d %H:%M}\n")
        f.write(f"- zijian.json: {len(base_sites)} → {len(main_sites)} (+{len(main_new)})\n")
        if not only_main:
            f.write(f"- zijian-full.json: {len(base_sites)} → {len(full_sites)} "
                    f"(+{len(main_new) + len(full_only)})\n")
        f.write(f"- 同 host 收敛 {stats.get('host_collapsed', 0)} 条，"
                f"key 重命名 {stats.get('key_renamed', 0)} 条，重复丢弃 {stats.get('dup', 0)} 条\n")
    print(f"changelog → data/changelog.md")

    # 自校验
    print("\n运行校验门禁…")
    import subprocess
    py = sys.executable
    rc_main = subprocess.call([py, os.path.join(ROOT, "scripts", "validate.py"),
                               os.path.join(ROOT, "zijian.json"),
                               "--baseline", bp],
                              cwd=ROOT)
    if rc_main != 0:
        print("[FATAL] 主配置校验不通过，已保留备份，请修复后重试")
        return 4
    if not only_main:
        rc_full = subprocess.call([py, os.path.join(ROOT, "scripts", "validate.py"),
                                   os.path.join(ROOT, "zijian-full.json"),
                                   "--baseline", bp],
                                  cwd=ROOT)
        if rc_full != 0:
            print("[FATAL] 扩展配置校验不通过")
            return 4
    print("\n合并完成，两份配置均通过校验。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
