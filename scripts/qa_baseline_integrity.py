#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查用户原有站点在合并过程中是否被"改动"（违反 merge.py 纪律 3/4）。

纪律要求：原有站点不删、不改 key、不重排、字段不动。
此脚本做纯只读比对。
"""
import json, os, sys

ROOT = r"E:\GitHub\tvbox"


def load(p):
    return json.load(open(p, encoding="utf-8-sig"))


def sig(s):
    return (str(s.get("api", "")).strip(), str(s.get("name", "")).strip())


def main():
    base_path = os.path.join(ROOT, "data", "backup", "zijian-20261019-1539.json")
    base = load(base_path)["sites"]
    print(f"基线（用户原始配置）：{base_path}")
    print(f"原始站点数：{len(base)}\n")

    for name in ("zijian.json", "zijian-full.json"):
        cur = load(os.path.join(ROOT, name))["sites"]
        print("=" * 74)
        print(f"【{name}】当前站点数 {len(cur)}")
        print("=" * 74)

        cur_by_sig = {}
        for i, s in enumerate(cur):
            cur_by_sig.setdefault(sig(s), []).append((i, s))
        cur_by_key = {}
        for i, s in enumerate(cur):
            cur_by_key.setdefault(str(s.get("key")), []).append(i)

        missing, keyrenamed, fieldmut, reordered = [], [], [], []

        for bpos, b in enumerate(base):
            k = sig(b)
            hits = cur_by_sig.get(k)
            if not hits:
                missing.append(b)
                continue
            pos, s = hits[0]
            if str(s.get("key")) != str(b.get("key")):
                keyrenamed.append((b, s))
            added = {kk: vv for kk, vv in s.items() if kk not in b}
            removed = {kk: vv for kk, vv in b.items() if kk not in s}
            changed = {}
            for kk in set(b) & set(s):
                if b[kk] != s[kk]:
                    changed[kk] = (b[kk], s[kk])
            if added or removed or changed:
                fieldmut.append((b, s, added, removed, changed))

        # 顺序检查：原始站点在现配置中的相对顺序是否保持不变
        order = []
        for bpos, b in enumerate(base):
            hits = cur_by_sig.get(sig(b))
            if hits:
                order.append(hits[0][0])
        is_subseq = order == sorted(order)

        print(f"  丢失的原始站点        : {len(missing)}")
        for b in missing:
            print(f"      - key={b.get('key')!r} name={b.get('name')!r}")
        print(f"  key 被改名的原始站点  : {len(keyrenamed)}")
        for b, s in keyrenamed:
            print(f"      - {b.get('key')!r} -> {s.get('key')!r}   (name={b.get('name')!r})")
        print(f"  字段被改动的原始站点  : {len(fieldmut)}")
        for b, s, a, r, c in fieldmut:
            print(f"      - key={b.get('key')!r} name={b.get('name')!r}")
            if a:
                print(f"          新增字段 {a}")
            if r:
                print(f"          删除字段 {r}")
            if c:
                print(f"          字段变化 {c}")
        print(f"  原始站点相对顺序保持  : {'是' if is_subseq else '否 —— 原始站点被重排了'}")
        # 新增站点是否全部追加在末尾
        nbase = len(base)
        tail_ok = all(sig(s) in {sig(b) for b in base} for s in cur[nbase:]) if len(cur) > nbase else True
        first_new_idx = None
        basesig = {sig(b) for b in base}
        for i, s in enumerate(cur):
            if sig(s) not in basesig:
                first_new_idx = i
                break
        print(f"  首个新站点位置        : {first_new_idx}（原始站点数 {nbase}）"
              f" → {'新站点全部追加在末尾，符合预期' if first_new_idx is None or first_new_idx >= nbase else '❌ 新站点插入到了原始站点中间'}")
        print()


if __name__ == "__main__":
    main()
