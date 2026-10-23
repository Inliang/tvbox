"""恢复被误移出的 csp_Bili 到 zijian.json，并同步 data/removed-from-main.json。

背景：validate 报 csp_Bili 的 EXT_REL「ext 依赖本仓库 lib 文件」。但
lib/0075389dca9afadd4614e9713765ff17.txt 真实存在（47,957 B，git ls-files 有记录）。
TVBox 把 ./lib/ 解析为相对配置文件所在目录，zijian.json 与 lib/ 同在仓库根，
路径有效，该站可用——属过度移除，恢复。
"""
import collections
import json

KEEP = "csp_Bili"

ev = json.load(open("data/removed-from-main.json", encoding="utf-8"))
z = json.load(open("zijian.json", encoding="utf-8"))

bili = next((it for it in ev["items"] if it["key"] == KEEP), None)
if bili is None:
    raise SystemExit("removed-from-main.json 里没有 csp_Bili")
if any(s.get("key") == KEEP for s in z["sites"]):
    raise SystemExit("zijian.json 里已经有 csp_Bili，无需恢复")

z["sites"].append(bili["site"])
json.dump(z, open("zijian.json", "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=2)

ev["items"] = [it for it in ev["items"] if it["key"] != KEEP]
ev["removedCount"] = len(ev["items"])
ev["sitesAfter"] = len(z["sites"])
kept = collections.OrderedDict([
    ("key", KEEP),
    ("reason", ("validate 报 EXT_REL「ext 依赖本仓库 lib 文件」，但 "
                "lib/0075389dca9afadd4614e9713765ff17.txt 真实存在（47,957 B，"
                "git ls-files 有记录）。TVBox 把 ./lib/ 解析为相对配置文件所在目录，"
                "zijian.json 与 lib/ 同在仓库根，路径有效，该站可用，属过度移除，已恢复。")),
    ("recoverableFrom", "zijian-full.json"),
])
ev["keptBack"] = kept
json.dump(ev, open("data/removed-from-main.json", "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=2)

print("zijian.json sites %s -> %s" % (ev["sitesBefore"], ev["sitesAfter"]))
print("removed-from-main items: %d（原 8，csp_Bili 已恢复）" % ev["removedCount"])
print("keptBack:", ev["keptBack"]["key"])
