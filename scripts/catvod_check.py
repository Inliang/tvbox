#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CatVod 反序列化模拟器（A6 关卡）

目的：在把配置交给 TVBox 真机之前，静态区分三种问题——
  [BLOCKING] 整包加载失败，用户看到"获取配置失败"
  [SITE]     只死这一个站，其他站照常（用户几乎无感）
  [NOTE]     合法但值得知道

判定依据是真实客户端源码，不是猜的。FongMi/TV（蜂蜜影视）的 com.fongmi.android.tv.bean.Site：

    @SerializedName("ext")
    @JsonAdapter(ExtAdapter.class)
    private String ext;

ext 虽然声明成 String，但挂了 ExtAdapter，其实现是：
    if (json.isJsonPrimitive()) return ...getAsString();
    if (json.isJsonArray() || json.isJsonObject()) return json.toString();

**所以 ext 传对象或数组是合法的**，会被序列化成 JSON 字符串交给爬虫。

而且 Site.objectFrom() 整段包在 try/catch 里，异常时返回 new Site()，
再被 isEmpty() 过滤掉 —— 也就是**单个站点解析失败不会连累整包**。

因此本脚本的 BLOCKING 只保留真正会全盘失败的情况：
  - 文件带 BOM / 不是合法 JSON
  - 顶层字段容器类型错（sites 不是数组、spider 不是字符串）
  - spider 声明的 md5 与实际文件不符（type:3 站点会全部失效）

用法：
    python scripts/catvod_check.py zijian.json [更多文件...]
"""

import hashlib
import json
import os
import sys
from collections import Counter

# CatVod / FongMi Site 的字段类型。int 允许数字或可转数字的字符串（Gson 会强转）。
SITE_TYPES = {
    "key": "str", "name": "str", "api": "str", "jar": "str",
    "type": "int", "searchable": "int", "quickSearch": "int",
    "changeable": "int", "hide": "int", "indexs": "int",
    "timeout": "int", "danmaku": "int", "playerType": "int",
    "ext": "ext",           # 标量/对象/数组都合法（ExtAdapter）
    "categories": "list",   # List<String>，传字符串会被丢站
    "header": "dict",       # Map<String,String>
    "style": "dict",
}

TOP_LEVEL = {
    "spider": "str", "wallpaper": "str", "logo": "str",
    "sites": "list", "parses": "list", "lives": "list", "doh": "list",
    "headers": "list", "proxy": "list", "hosts": "list",
    "ads": "list", "rules": "list", "flags": "list",
}

TYPE_CN = {"str": "字符串", "int": "整数", "list": "数组", "dict": "对象"}


def kind(v):
    if isinstance(v, dict):
        return "dict"
    if isinstance(v, list):
        return "list"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, str):
        return "str"
    return "null" if v is None else type(v).__name__


def check_spider(doc, basedir, blocking, site_level, note):
    """spider 的 md5 是唯一会让全部 type:3 站点集体失效的东西，权重要给足。"""
    sp = doc.get("spider")
    if not isinstance(sp, str) or not sp:
        note.append("没有 spider 字段：所有 type:3 的站点都无法运行"
                    "（若配置里几乎没有 type:3，可忽略）")
        return
    parts = sp.split(";")
    rel, declared = parts[0], None
    if len(parts) >= 3 and parts[1].strip().lower() == "md5":
        declared = parts[2].strip()
    print(f"  spider   = {rel}")
    if not declared:
        note.append("spider 未声明 md5：客户端每次都会重新下载 spider，"
                    "行为因版本而异，建议补上 md5")
        return
    print(f"  md5 声明 = {declared}")

    # 只校验本地相对路径；远程 URL 无法在此校验
    if rel.startswith(("http://", "https://", "clan://")):
        note.append("spider 是远程地址，md5 需真机首次加载后确认，脚本无法离线校验")
        return
    path = os.path.normpath(os.path.join(basedir, rel))
    if not os.path.isfile(path):
        blocking.append(f"spider 指向的本地文件不存在：{path}"
                        f" —— 客户端取不到 spider，所有 type:3 站点全灭")
        return
    actual = hashlib.md5(open(path, "rb").read()).hexdigest()
    if actual != declared:
        blocking.append(f"spider md5 不符：声明 {declared}，实际 {actual}"
                        f" —— 客户端会拒绝加载 spider，所有 type:3 站点全灭")
    else:
        print(f"  md5 实测 = {actual}  ✓ 一致")


def check_sites(doc, blocking, site_level, note):
    sites = doc.get("sites")
    if not isinstance(sites, list):
        blocking.append(f"顶层 sites 是 {kind(sites)}，应为数组 —— 整包加载失败")
        return

    keys = Counter()
    ext_kinds = Counter()

    for i, s in enumerate(sites):
        if not isinstance(s, dict):
            site_level.append((f"sites[{i}] 不是对象", None))
            continue
        name = s.get("name") or s.get("key") or f"#{i}"

        for f, t in SITE_TYPES.items():
            if f not in s:
                continue
            v = s[f]
            k = kind(v)
            if t == "ext":
                ext_kinds[k] += 1
                if k == "dict" and not v:
                    note.append(f"[{name}] ext 是空对象 {{}}，等价于没有配置")
                continue
            if t == "int":
                if k == "int":
                    continue
                if k == "str" and v.strip().lstrip("-").isdigit():
                    continue
                site_level.append((f"{f} 是 {k}={v!r}，无法转整数", name))
                continue
            if k != t and not (t == "str" and k == "int"):
                site_level.append(
                    (f"{f} 应为{TYPE_CN.get(t, t)}，实际是 {k} —— 该站会被客户端丢弃", name))

        k = s.get("key")
        if not k:
            site_level.append(("缺少 key，无法建立站点索引", name))
        else:
            keys[k] += 1

        if s.get("type") == 3 and not s.get("api"):
            site_level.append(("type:3 但缺少 api（爬虫类名），该站必然不可用", name))

    dup = [k for k, c in keys.items() if c > 1]
    if dup:
        site_level.append((f"key 重复 {len(dup)} 组（{', '.join(dup[:5])}）"
                           f"—— Room 主键冲突，后写入的会覆盖前者", None))

    print(f"  ext 形态 = {dict(ext_kinds)}  （对象/数组均合法，ExtAdapter 会转成 JSON 字符串）")

    # parses / lives 顺带看一眼，都是站点级问题
    for field in ("parses", "lives"):
        arr = doc.get(field) or []
        if not isinstance(arr, list):
            blocking.append(f"顶层 {field} 不是数组 —— 整包加载失败")
            continue
        for i, it in enumerate(arr):
            if not isinstance(it, dict):
                site_level.append((f"{field}[{i}] 不是对象", None))


def check(path):
    raw = open(path, "rb").read()
    print(f"\n{'='*66}\n{path}  ({len(raw)} 字节)\n{'='*66}")
    blocking, site_level, note = [], [], []

    if raw[:3] == b"\xef\xbb\xbf":
        blocking.append("文件带 UTF-8 BOM（EF BB BF）—— Gson 非宽松模式直接抛 "
                        "JsonSyntaxException，整包加载失败")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as e:
        blocking.append(f"不是合法 JSON：{e}")
        doc = None

    if doc is not None:
        if not isinstance(doc, dict):
            blocking.append("顶层不是对象 —— 整包加载失败")
        else:
            for k, t in TOP_LEVEL.items():
                if k not in doc:
                    continue
                kk = kind(doc[k])
                if t == "str" and kk not in ("str", "null"):
                    blocking.append(f"顶层 {k} 是 {kk}，应为字符串 —— 整包加载失败")
                if t == "list" and kk != "list":
                    blocking.append(f"顶层 {k} 是 {kk}，应为数组 —— 整包加载失败")
            check_spider(doc, os.path.dirname(os.path.abspath(path)),
                         blocking, site_level, note)
            check_sites(doc, blocking, site_level, note)
            print(f"\n  sites={len(doc.get('sites') or [])}  "
                  f"parses={len(doc.get('parses') or [])}  "
                  f"lives={len(doc.get('lives') or [])}")

    if blocking:
        print(f"\n[BLOCKING] {len(blocking)} 项 —— 整包加载失败：")
        for m in blocking:
            print(f"  ✕ {m}")
    else:
        print("\n[BLOCKING] 0 项 —— 没有任何会导致整包加载失败的问题")

    if site_level:
        print(f"\n[SITE] {len(site_level)} 项 —— 只影响单个站点，其他站正常：")
        for m, n in site_level[:20]:
            print(f"  · {'['+n+'] ' if n else ''}{m}")
        if len(site_level) > 20:
            print(f"  … 其余 {len(site_level)-20} 项省略")

    if note:
        print(f"\n[NOTE] {len(note)} 项：")
        for m in note:
            print(f"  · {m}")

    return not blocking


def main():
    targets = sys.argv[1:] or ["zijian.json"]
    ok = True
    for t in targets:
        ok = check(t) and ok
    print(f"\n{'='*66}")
    print("结论：" + ("可以交给真机导入" if ok else "存在阻塞级问题，禁止交付"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
