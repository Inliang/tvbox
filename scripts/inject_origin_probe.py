"""把镜像源站的预计算结果注入 data/exports/sites.json 的对应 item。

为什么必须是预计算、且必须在 build.py 之前跑：
  落在已失效镜像 host（ghp.ci / raw.kkgithub.com / gh-proxy.net）上的站点，
  前端要把它们显示成"镜像已失效、源站实测存活"，而不是"不可验证"或"可达"。
  源站实测耗时在 0.6s ~ 40.8s 之间剧烈波动（间歇性 stall），
  **前端不能实时探测这些地址**，否则会卡死。所以探测结果必须由本脚本
  预先算好写进数据。

运行顺序（不可交换）：
  fetch_sources.py → build_candidates.py → **本脚本** → build.py
  本脚本必须插在 build_candidates 之后、build.py 之前：
  build_candidates 每次都会重写 exports/sites.json，跑在它前面会被冲掉；
  build.py 读 exports 作为上游并透传 contentHash，跑在它后面会导致
  docs 与 exports 脱节。

contentHash 用与 build_candidates.py:229 完全相同的算法重算
（sha1，剔除 generatedAt/contentHash，取前 16 位）。两边必须一致，
否则下次跑 build_candidates 会得出不同的 contentHash，"两次构建恒定"的断言失效。
"""
import datetime
import hashlib
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(BASE, "data", "mirror_origin_probe.json")
SITES = os.path.join(BASE, "data", "exports", "sites.json")


def content_hash(doc):
    """与 build_candidates.py:229 保持一致，勿单独改动。"""
    body = {k: v for k, v in doc.items() if k not in ("generatedAt", "contentHash")}
    canon = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()[:16]


def main():
    probe = json.load(open(PROBE, encoding="utf-8"))
    doc = json.load(open(SITES, encoding="utf-8"))
    items = doc["items"]

    by_url = {}
    for r in probe["items"]:
        if r.get("origin_ok200"):
            by_url[r["probe_url"]] = {
                "url": r["origin_url"],
                "status": 200,
                "bytes": r.get("origin_bytes"),
                "md5": r.get("origin_md5"),
                "checkedAt": probe["generatedAt"],
                "rounds": len(r.get("rounds") or []),
                "source": "预计算（scripts/probe_mirror_origin.py），勿前端实时探测",
            }
        elif r.get("origin_status") is not None:
            by_url[r["probe_url"]] = {
                "url": r["origin_url"], "status": r["origin_status"],
                "bytes": r.get("origin_bytes"), "md5": r.get("origin_md5"),
                "checkedAt": probe["generatedAt"],
                "rounds": len(r.get("rounds") or []),
                "source": "预计算（scripts/probe_mirror_origin.py），勿前端实时探测",
            }
        else:
            # 多轮都拿不到响应：写 status null，不写假值
            by_url[r["probe_url"]] = {
                "url": r["origin_url"], "status": None, "bytes": None, "md5": None,
                "checkedAt": probe["generatedAt"],
                "rounds": len(r.get("rounds") or []),
                "source": "预计算（scripts/probe_mirror_origin.py），勿前端实时探测",
            }

    hit = 0
    for it in items:
        rec = by_url.get(it.get("probe_url"))
        if rec:
            it["originProbe"] = rec
            hit += 1

    doc["contentHash"] = content_hash(doc)
    json.dump(doc, open(SITES, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)

    print(f"注入 originProbe: {hit} / {len(by_url)} 条待注入（共 {len(items)} 站）")
    print(f"exports contentHash 重算为 {doc['contentHash']}")
    if hit != len(by_url):
        missing = set(by_url) - {it.get('probe_url') for it in items}
        print(f"[注意] {len(missing)} 条在 sites.json 里找不到对应 item：")
        for u in sorted(missing):
            print("   ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
