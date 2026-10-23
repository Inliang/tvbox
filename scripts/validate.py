#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zijian.json 校验门禁

在 merge.py 覆盖 zijian.json 之前做硬校验。任何 ERROR 都会让进程非 0 退出，从而阻止写盘。

关键设计：--baseline 基线机制。
    用户原有配置里存在历史遗留问题（如 csp_Living 类不存在、playerType 写成字符串）。
    这些不该阻塞"新增站点"的合并，所以我们拿基线文件比对：
      - 站点在基线里已存在且 api 未变  → 其问题降级为 [KNOWN]，不阻塞
      - 站点是新引入的 / api 被改过    → 问题记为 [ERROR]，阻塞写盘

用法：
    python validate.py [目标文件] [--baseline 原文件] [--json]

退出码：0 = 无 ERROR；1 = 有 ERROR（禁止写盘）
"""
import sys
import os
import re
import json
import hashlib

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPECTED_TOP_KEYS = [
    "spider", "wallpaper", "logo", "sites", "parses", "doh",
    "lives", "headers", "proxy", "hosts", "ads", "rules",
]
VALID_TYPES = {0, 1, 3, 4}

# 非站点类：可作为工具入口存在，但不应被当成影视站点合并进来
NON_SITE = {"Init", "Proxy", "Push", "JSDemo", "Market"}
# 存量配置中允许存在的非标数值写法（只警告）
NUM_FIELDS = ("playerType", "searchable", "quickSearch", "filterable", "changeable")

LOCAL_RE = re.compile(r"//(127\.0\.0\.1|localhost|0\.0\.0\.0)")

errors = []
knowns = []
warns = []
infos = []


def err(code, msg):
    errors.append((code, msg))


def known(code, msg):
    knowns.append((code, msg))


def warn(code, msg):
    warns.append((code, msg))


def info(msg):
    infos.append(msg)


def load_json(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def check_encoding(path):
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        err("BOM", "文件带 UTF-8 BOM，部分 TVBox 版本解析失败，请存为无 BOM 的 UTF-8")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        err("ENCODING", f"不是合法 UTF-8：{e}")
        return None


def check_spider(cfg):
    spider = cfg.get("spider")
    if not isinstance(spider, str) or not spider.strip():
        warn("SPIDER_EMPTY", "spider 为空，所有依赖 spider 的站点都会失效")
        return
    parts = spider.split(";")
    rel = parts[0].strip()
    if rel.startswith("http"):
        info(f"spider 为远程地址：{rel}")
        return
    if not rel.startswith("./"):
        warn("SPIDER_FORMAT", f"spider 首段不是 './' 相对路径：{rel}")
        return
    fp = os.path.join(ROOT, rel[2:].replace("/", os.sep))
    if not os.path.exists(fp):
        err("SPIDER_MISSING", f"spider 指向的文件不存在：{rel}")
        return
    if len(parts) >= 3 and parts[1].strip().lower() == "md5":
        expect = parts[2].strip().lower()
        actual = hashlib.md5(open(fp, "rb").read()).hexdigest()
        if expect != actual:
            err("SPIDER_MD5", f"spider md5 不匹配：配置写 {expect}，实际 {actual}，"
                              f"TVBox 会拒绝加载整个配置")
        else:
            info(f"spider md5 校验通过（{actual}）")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    baseline_path = None
    if "--baseline" in sys.argv:
        i = sys.argv.index("--baseline")
        if i + 1 < len(sys.argv):
            baseline_path = sys.argv[i + 1]
            if baseline_path in args:
                args.remove(baseline_path)

    path = args[0] if args else os.path.join(ROOT, "zijian.json")
    if not os.path.exists(path):
        print(f"文件不存在：{path}")
        return 1

    # 基线签名集合
    base_sigs = set()
    if baseline_path and os.path.exists(baseline_path):
        bcfg = load_json(baseline_path) or {}
        for s in bcfg.get("sites", []) or []:
            if isinstance(s, dict):
                base_sigs.add((str(s.get("key")), str(s.get("api"))))
        info(f"基线：{os.path.basename(baseline_path)}，{len(base_sigs)} 个站点")

    text = check_encoding(path)
    if text is None:
        return finish(path, as_json, 0, 0)
    try:
        cfg = json.loads(text)
    except json.JSONDecodeError as e:
        err("JSON_INVALID", f"第 {e.lineno} 行第 {e.colno} 列：{e.msg}")
        return finish(path, as_json, 0, 0)
    if not isinstance(cfg, dict):
        err("ROOT_TYPE", "顶层不是对象")
        return finish(path, as_json, 0, 0)

    missing = [k for k in EXPECTED_TOP_KEYS if k not in cfg]
    if missing:
        err("TOP_MISSING", f"缺少顶层字段：{', '.join(missing)}")
    extra = [k for k in cfg if k not in EXPECTED_TOP_KEYS]
    if extra:
        warn("TOP_EXTRA", f"非标准顶层字段：{', '.join(extra)}")

    check_spider(cfg)

    # 用户显式配置项必须保留（脚本曾把 wallpaper 换成默认值，这类必须拦）
    for k in ("wallpaper", "logo"):
        v = cfg.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            warn(f"{k.upper()}_EMPTY", f"{k} 为空，会退回客户端默认外观")

    # 合并进来的人造站点必须带 group，否则主配置全是新站、用户无从筛选
    SITE_ALLOWED = {
        "key", "name", "type", "api", "searchable", "quickSearch", "filterable",
        "changeable", "playerType", "ext", "style", "gridview", "jar", "logo",
        "timeout", "clickSelector", "homePage", "group", "categories",
        "spider", "playerUrl", "header", "click", "hide", "timeout",
    }

    sites = cfg.get("sites")
    if not isinstance(sites, list) or not sites:
        err("SITES", "sites 缺失或为空数组")
        return finish(path, as_json, 0, 0)

    dex = (load_json(os.path.join(ROOT, "data", "dex_classes.json")) or {}).get("classes")
    classes = set(dex) if dex else None
    if classes is None:
        warn("DEX_MISSING", "未找到 data/dex_classes.json，跳过类名存在性校验")

    keys = {}
    for idx, s in enumerate(sites):
        loc = f"sites[{idx}]"
        if not isinstance(s, dict):
            err("SITE_TYPE", f"{loc} 不是对象")
            continue

        key = s.get("key")
        api = s.get("api")
        sig = (str(key), str(api))
        is_base = sig in base_sigs

        def flag(code, msg):
            (known if is_base else err)(code, msg)

        for rk in ("key", "name", "api"):
            if rk not in s or (isinstance(s.get(rk), str) and not s[rk].strip()):
                flag("SITE_FIELD", f"{loc} 缺少必填字段 {rk}")

        label = key if isinstance(key, str) and key.strip() else loc

        if isinstance(key, str):
            if key in keys:
                flag("KEY_DUP", f"key '{key}' 重复（sites[{keys[key]}] 与 {loc}），"
                                f"TVBox 只认其中一个")
            else:
                keys[key] = idx

        t = s.get("type")
        if t is not None and t not in VALID_TYPES:
            flag("SITE_TYPE_VAL", f"[{label}] type={t!r} 非标准值")

        for nk in NUM_FIELDS:
            if nk in s and isinstance(s[nk], str):
                warn("SITE_NUM_STR", f"[{label}] {nk} 是字符串 {s[nk]!r}")

        # 字段白名单：合并带来的站点只应有已知字段，避免把别人的私有字段塞进配置
        unknown = [k for k in s if k not in SITE_ALLOWED]
        if unknown:
            warn("SITE_FIELD_UNKNOWN", f"[{label}] 未知字段 {unknown}（可能是别家私有字段）")

        # 非原始站点应有 group，便于在客户端分类浏览
        if s.get("group") is None and not is_base:
            warn("SITE_NO_GROUP", f"[{label}] 缺少 group 字段")

        if not isinstance(api, str) or not api.strip():
            continue
        api = api.strip()

        blob = json.dumps(s.get("ext"), ensure_ascii=False) if s.get("ext") is not None else ""

        # 相对路径资源
        if api.startswith("./"):
            fp = os.path.join(ROOT, api[2:].replace("/", os.sep))
            if not os.path.exists(fp):
                flag("REL_MISSING", f"[{label}] 相对资源不存在：{api}")
            else:
                head = open(fp, "rb").read(80).lstrip()
                if head[:1] == b"<":
                    flag("REL_HTML", f"[{label}] {api} 实际是 HTML 页面而非 JS，"
                                     f"TVBox 解析失败，该站会一直转圈")
            continue

        # ext 本地依赖
        # 只在引用的文件确实不存在时判 ERROR。本仓库的场景是 zijian.json 与 lib/ 同在根目录，
        # TVBox 把 ./lib/ 解析为相对配置文件所在目录，路径有效、站点可用——此时不该阻塞。
        # （csp_Bili 曾被这条规则误判为失效，实际 lib/0075389dca9afadd4614e9713765ff17.txt
        #   在仓库内、47,957 B，站点可正常加载。）
        if "./lib/" in blob or "../" in blob:
            rels = re.findall(r"(?:\./lib/|\.\./)[^\s\"']+", blob)
            missing = [r for r in rels
                       if not os.path.exists(os.path.join(
                           ROOT, r[2:].replace("/", os.sep)))]
            if missing:
                err("EXT_REL",
                    f"[{label}] ext 依赖的本地文件不存在：{missing[0]}")
            else:
                known("EXT_REL",
                      f"[{label}] ext 依赖本仓库 lib 文件（{len(rels)} 个均在仓库内，"
                      f"相对路径有效）")
        if LOCAL_RE.search(blob):
            flag("EXT_LOCAL", f"[{label}] ext 指向本机服务（127.0.0.1/localhost），"
                              f"仅本机可用，换设备失效")

        # csp_XXX 类名
        m = re.match(r"^csp_([A-Za-z0-9_]+)$", api)
        if m and classes is not None:
            cls = m.group(1)
            if cls not in classes:
                flag("CSP_CLASS", f"[{label}] 类 com.github.catvod.spider.{cls} "
                                  f"不在 spider dex 中，必然失效且不报错")
            elif cls in NON_SITE:
                flag("CSP_NONSITE", f"[{label}] {cls} 是非站点类，不应作为影视站点")

    return finish(path, as_json, len(sites), len(keys))


def finish(path, as_json, total, unique):
    ok = not errors
    if as_json:
        print(json.dumps({
            "file": path, "sites": total, "uniqueKeys": unique,
            "errors": [{"code": c, "message": m} for c, m in errors],
            "known": [{"code": c, "message": m} for c, m in knowns],
            "warns": [{"code": c, "message": m} for c, m in warns],
            "ok": ok,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    print("=" * 70)
    print(f"校验：{path}")
    print(f"站点 {total}   唯一 key {unique}")
    print("=" * 70)
    for m in infos:
        print(f"  [OK]    {m}")
    if errors:
        print(f"\n[ERROR] {len(errors)} 项 —— 新引入的问题，必须修复，禁止写盘：")
        for c, m in errors:
            print(f"  - ({c}) {m}")
    if knowns:
        print(f"\n[KNOWN] {len(knowns)} 项 —— 存量问题，不阻塞（建议后续修复）：")
        for c, m in knowns:
            print(f"  - ({c}) {m}")
    if warns:
        print(f"\n[WARN] {len(warns)} 项 —— 建议关注：")
        for c, m in warns:
            print(f"  - ({c}) {m}")
    print("-" * 70)
    print("结论：" + ("通过" if ok else "不通过，禁止写盘"))
    print("-" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
