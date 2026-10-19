#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py —— 构建站点数据并注入页面。

做四件事：
  1. 对配置地址做服务端预探测（不走浏览器，不受 CORS 限制），写入 state / confidence / checkedAt
  2. 反查站点是否已收录进 zijian.json / zijian-full.json，把 included 二值升级为 includedIn 三值
  3. 统一写入时间戳（数据里的 generatedAt 由本脚本覆盖，避免上游时钟漂移）
  4. 把数据内联进 docs/index.html 的 DATA_FALLBACK 区块，保证 file:// 双击也能看

## 注入契约（与前端约定的硬约束，不要改）
本脚本写 docs/index.html 时**只替换**下面两个标记之间的内容，禁止整文件重写、
禁止模板整页重渲染，否则会覆盖手写代码：

    <!--DATA_FALLBACK_START-->
    <script>window.__TVBOX_FALLBACK__ = {...};</script>
    <!--DATA_FALLBACK_END-->

替换必须用 `re.subn(..., lambda _m: block, html, flags=re.S)` 的函数式替换。
直接传字符串会被 re 当成转义模板，破坏 JSON 里的 `\\` 序列（曾导致注入后无法解析）。

## 数据契约
- 上游权威数据在 data/exports/（采集层产出），本脚本只读不写
- 输出 docs/data/*.json + 内联，schema 版本见 SCHEMA_VERSION
- 字段：totalSites / staticPass / probeConfirmed / encryptedSites / curatedSites
  （注意：不存在 probeOk，旧字段已废弃）

用法：
    python build.py            # 全量构建
    python build.py --no-probe # 跳过网络探测（离线构建）
"""
import sys
import os
import re
import json
import time
import hashlib
import datetime
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
DATA_JSON = os.path.join(DOCS, "data")
# 采集层权威产出（由采集脚本维护），构建层只读不写
EXPORTS = os.path.join(ROOT, "data", "exports")
# 输出的数据结构版本。上下游对不上时先看这个数字，别再靠字段名猜。
SCHEMA_VERSION = 3
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def dump(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


TVBOX_UA = "okhttp/3.12.13"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 这套此站只认 python-urllib 也会吃 UA 黑名单；只用一个 UA 等于单点故障。
UA_CHAIN = [TVBOX_UA, BROWSER_UA]


def probe(url, timeout=15):
    """对外入口：拿不到**确定结论**时再采一次样。

    为什么重试：实测 raw.githubusercontent.com 对我们是**间歇性 stall**，
    约 1/4 的请求会卡到超时（同一 UA 既 200 也超时，说明不是指纹问题）。
    单次采样不足以支撑任何结论，所以再试一次，两次都拿不到才认。

    第二次顺带换了 UA —— 不是为了"装成浏览器"，而是让两次采样尽量独立：
    如果两条通道都僵死，那更像是对方真的不通，而不是我们运气差。

    **只在"没有明确答复"时重试**：404 是对方明确回答，重试只会浪费时间，
    还可能把确定的失效洗成"可达"。
    """
    best = _probe_once(url, timeout, UA_CHAIN[0])
    # 有确定的 HTTP 答复（尤其 404）就不再折腾
    if best.get("state") in ("ok", "reachable", "fail") and best.get("httpStatus"):
        return best
    if best.get("state") == "ok":
        return best

    for ua in UA_CHAIN[1:]:
        alt = _probe_once(url, timeout, ua)
        if alt.get("state") == "ok":
            return alt
        if alt.get("state") == "reachable" and best.get("state") != "ok":
            return alt
    return best


def _probe_once(url, timeout, ua):
    """单次服务端探测。

    核心原则：**误判"死"的代价远大于漏判"活"**。
    用户看到"失效"会直接放弃，看到"未测"还会自己点开试。
    所以只有 404 / 连接拒绝 / 超时 才判定 dead，其余一律 uncertain。

    返回 state（页面四态）：
        ok         → 可用：返回合法 JSON 且含 sites
        reachable  → 可达：HTTP 通了但内容不是可用配置
        untestable → 未测：403/TLS/编码/代理等探针自身能力问题
        fail       → 失效：明确的 404 / 连接拒绝 / 超时
    返回 confidence：confirmed / uncertain / dead
    """
    # 中文域名必须先 IDNA 编码，否则 urllib 抛 UnicodeEncodeError（请求根本没发出去）
    try:
        p = urlparse(url)
        if p.hostname:
            host = p.hostname.encode("idna").decode("ascii")
            netloc = host + (f":{p.port}" if p.port else "")
            url = url.replace(p.netloc, netloc, 1)
    except Exception:
        return {"state": "untestable", "confidence": "uncertain",
                "error": "idna_failed", "httpStatus": None, "probeMs": 0}

    # 先用 TVBox 同款客户端 UA；被拦时由外层 probe() 换浏览器 UA 再来一次
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "*/*",
        "Connection": "close",
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(800000)
            code = r.status
            declared = r.headers.get("Content-Length")
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        # 403/401/451 是风控与地域封锁，不代表站点没了
        if e.code in (401, 403, 451, 429):
            return {"state": "untestable", "confidence": "uncertain",
                    "httpStatus": e.code, "probeMs": ms, "error": "blocked"}
        # 5xx 是服务端临时故障
        if 500 <= e.code < 600:
            return {"state": "untestable", "confidence": "uncertain",
                    "httpStatus": e.code, "probeMs": ms, "error": "server_error"}
        return {"state": "fail", "confidence": "dead",
                "httpStatus": e.code, "probeMs": ms, "error": "http_" + str(e.code)}
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        name = type(e).__name__
        msg = str(e).lower()
        if "timed out" in msg or "timeout" in name.lower():
            # 超时 ≠ 失效。10s 是我们自己的耐心，不是对方的存在与否。
            # GitHub raw 走大陆出口经常要十几秒，把这种标红，等于
            # 把我们自己的网络状况宣布成对方的死亡证明。
            return {"state": "untestable", "confidence": "uncertain",
                    "httpStatus": None, "probeMs": ms, "error": "timeout"}
        if "refused" in msg or "reset" in msg:
            return {"state": "fail", "confidence": "dead",
                    "httpStatus": None, "probeMs": ms, "error": "conn_refused"}
        if "ssl" in msg or "certificate" in msg or "tls" in msg:
            return {"state": "untestable", "confidence": "uncertain",
                    "httpStatus": None, "probeMs": ms, "error": "tls_issue"}
        if "name or service" in msg or "getaddrinfo" in msg:
            # 解析不出发不出请求 = 我们这边没到达对方，不是对方不存在。
            # 大陆 DNS 污染会让完全正常的域名解析失败，判成"失效"是冤枉。
            return {"state": "untestable", "confidence": "uncertain",
                    "httpStatus": None, "probeMs": ms, "error": "dns_fail"}
        return {"state": "untestable", "confidence": "uncertain",
                "httpStatus": None, "probeMs": ms, "error": name}

    ms = int((time.time() - t0) * 1000)
    # 连接被中途截断时 body 会不完整，表现为"内容不是 JSON"。
    # 这是并发下的伪故障，必须识别出来，否则会把好接口判成不可用。
    if declared and declared.isdigit() and int(declared) != len(body):
        return {"state": "untestable", "confidence": "uncertain",
                "httpStatus": code, "probeMs": ms, "error": "truncated"}
    try:
        j = json.loads(body.decode("utf-8", "ignore"))
    except Exception:
        # 200 但不是 JSON：服务器活着，只是这个路径不吐配置（很常见，需要带参数）
        return {"state": "reachable", "confidence": "uncertain",
                "httpStatus": code, "probeMs": ms, "error": "not_json"}

    if not isinstance(j, dict):
        return {"state": "reachable", "confidence": "uncertain",
                "httpStatus": code, "probeMs": ms, "error": "not_config_object"}

    n = 0
    if isinstance(j.get("sites"), list):
        n = len(j["sites"])
    elif isinstance(j.get("urls"), list):
        n = len(j["urls"])
    if n:
        return {"state": "ok", "confidence": "confirmed", "httpStatus": code,
                "probeMs": ms, "probeSiteCount": n}
    # 结构是 JSON 但没有站点（多仓/空配置），算可达不算可用
    return {"state": "reachable", "confidence": "uncertain",
            "httpStatus": code, "probeMs": ms, "probeSiteCount": 0,
            "error": "no_sites"}


def main():
    no_probe = "--no-probe" in sys.argv

    sites_doc = load(os.path.join(EXPORTS, "sites.json"))
    cfgs_doc = load(os.path.join(EXPORTS, "configs.json"))
    sites = sites_doc.get("items") or sites_doc.get("sites") or []
    cfgs = cfgs_doc.get("items") or cfgs_doc.get("configs") or []

    # ---------- 1) 服务端预探测 ----------
    if not no_probe:
        def jsdelivr(u):
            """raw.githubusercontent.com/x/y/main/z.json → jsdelivr CDN 镜像"""
            m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", u)
            if not m:
                return None
            owner, repo, ref, path = m.groups()
            return f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{ref}/{path}"

        def work(c):
            url = c.get("url", "")
            # probe() 内部已经做过"拿不到确定结论就再采一次"，
            # 这里不要再叠一层重试，否则最坏情况会打 4 次，把构建拖成龟速。
            r = probe(url)
            # raw 直连不通时，用 jsdelivr 侧证一下"这份配置本身是好的"。
            # 但**只写 note，不改 state**：用户复制走的是 raw 地址，
            # 卡片上那个绿点必须由 raw 自己挣来。让镜像替源站背书，
            # 就是今天修了一整天的"假可用"（ghp.ci 那 6 条、dep 站的 5 条）。
            if r["state"] == "fail" and "raw.githubusercontent.com" in url:
                alt = jsdelivr(url)
                if alt:
                    r3 = probe(alt)
                    if r3["state"] == "ok":
                        r["checkedVia"] = alt
                        r["note"] = (c.get("note") or "") + \
                            " · 直连失败，经 jsdelivr 侧证内容正常（卡片状态仍以直连为准）"
            c.update(r)
            c["checkedAt"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            return c

            c["checkedAt"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            return c

        print(f"预探测 {len(cfgs)} 个配置地址…", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(work, cfgs))
        from collections import Counter
        dist = Counter(c.get("state") for c in cfgs)
        print(f"  可用 {dist.get('ok',0)} / 可达 {dist.get('reachable',0)} / "
              f"未测 {dist.get('untestable',0)} / 失效 {dist.get('fail',0)}", file=sys.stderr)

    # 为未探测的补默认值
    for c in cfgs:
        c.setdefault("state", "unknown")
        c.setdefault("checkedAt", "")

    # ---------- 2) recommend ----------
    # 采集层已按"同域名保留状态最好的 2 条"算好 recommend，优先沿用，
    # 只有完全缺失时才用本地探测结果补算。
    if not any("recommend" in c for c in cfgs):
        by_host = {}
        for c in cfgs:
            try:
                h = urlparse(c.get("url", "")).netloc.lower()
            except Exception:
                h = ""
            c["_host"] = h
            by_host.setdefault(h, []).append(c)
        state_rank = {"ok": 0, "reachable": 1, "unknown": 2, "fail": 3}
        for h, group in by_host.items():
            group.sort(key=lambda c: (state_rank.get(c.get("state"), 9),
                                      -(c.get("siteCount") or 0)))
            for i, c in enumerate(group):
                c["recommend"] = (i < 2 and c.get("state") in ("ok", "reachable"))
        for c in cfgs:
            c.pop("_host", None)

    # ---------- 3) includedIn 三值 ----------
    def sig_set(path):
        if not os.path.exists(path):
            return set()
        cfg = load(path)
        out = set()
        for s in cfg.get("sites", []) or []:
            out.add((str(s.get("api", "")).strip(), str(s.get("name", "")).strip()))
        return out

    main_set = sig_set(os.path.join(ROOT, "zijian.json"))
    full_set = sig_set(os.path.join(ROOT, "zijian-full.json"))

    cnt = {"main": 0, "full": 0, "none": 0}
    for s in sites:
        # 数值字段归一化：源配置里常见 "searchable": "0" 这种手写习惯，
        # 而 JS 里 "0" 是真值，卡片会显示「可搜索 是」——实际是不能搜。
        # 同一个坑今天已经在 type 上踩过一次，在这里统一收口。
        for nk in ("type", "searchable", "quickSearch", "filterable",
                   "changeable", "playerType"):
            v = s.get(nk)
            if isinstance(v, str) and v.strip().lstrip("-").isdigit():
                s[nk] = int(v.strip())

        key = (str(s.get("api", "")).strip(), str(s.get("name", "")).strip())
        if key in main_set:
            s["includedIn"] = "main"
            cnt["main"] += 1
        elif key in full_set:
            s["includedIn"] = "full"
            cnt["full"] += 1
        else:
            s["includedIn"] = False
            cnt["none"] += 1
        s.pop("included", None)

    # ---------- 4) 写回 ----------
    now = datetime.datetime.now().astimezone()
    stamp = now.isoformat(timespec="seconds")
    sites_doc["schema"] = SCHEMA_VERSION
    # 镜像清单必须透传。前端要靠它把"镜像活着"降级为「无法预验证」；
    # 如果在页面里再写一份，两处清单必然漂移——今天已经因为双份定义返工四次。
    exports_sites = load(os.path.join(EXPORTS, "sites.json")) or {}
    if "mirrorHosts" in exports_sites:
        sites_doc["mirrorHosts"] = exports_sites["mirrorHosts"]
    cfgs_doc["schema"] = SCHEMA_VERSION

    # contentHash：只对"内容"取指纹，**不含每次构建都会变的量**。
    # 实测两次构建漂移的元凶是 checkedAt（探测时刻）和 probeMs（耗时），
    # 它们描述的是"某次测量的瞬间"，不是内容本身。genratedAt/contentHash 同理。
    # 剥掉这些之后，同一份 exports 两次构建得到的 contentHash 必然相同，
    # 可以直接回答"这轮到底变了什么"——generatedAt 每轮都变，它做不了这件事。
    # 注意：state / httpStatus 属于真实结论，**保留**。网络确实变了时
    # contentHash 就该变，那不是噪声，是信息。
    VOLATILE = {"generatedAt", "checkedAt", "contentHash", "probeMs", "builtAt"}

    def _scrub(o):
        if isinstance(o, dict):
            return {k: _scrub(v) for k, v in o.items() if k not in VOLATILE}
        if isinstance(o, list):
            return [_scrub(v) for v in o]
        return o

    content_payload = json.dumps(
        _scrub({"sites": sites_doc, "configs": cfgs_doc}),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha1(content_payload.encode("utf-8")).hexdigest()[:12]
    sites_doc["contentHash"] = content_hash
    cfgs_doc["contentHash"] = content_hash

    # 上游血缘：记录本次构建读的是哪一版 exports。
    # 没有这个，构建就会静默吃过期上游、并产出一个"看起来正常"的结果——
    # 今天已经栽过一次（docs 比 exports 早两分钟，丢了 mirrorHosts 与 13 个站）。
    # 校验只能比 hash，不能比时间戳：时间戳会因为时区、秒级截断、机器时钟而骗人。
    sites_doc["sourceContentHash"] = exports_sites.get("contentHash", "")
    cfgs_doc["sourceContentHash"] = (load(os.path.join(EXPORTS, "configs.json")) or {}).get("contentHash", "")

    sites_doc["generatedAt"] = stamp
    cfgs_doc["generatedAt"] = stamp

    # 关键字段缺失就拒绝写盘。宁可构建失败，也不要产出"字段不见了但界面照常"的假正常。
    REQUIRED_TOP = ("generatedAt", "total", "mirrorHosts", "items", "contentHash")
    missing = [k for k in REQUIRED_TOP if k not in sites_doc]
    if missing:
        print(f"[FATAL] sites_doc 缺关键字段 {missing}，拒绝写盘。"
              f"通常是上游 exports 版本不对或字段被改名。")
        return 3

    dump(os.path.join(DATA_JSON, "sites.json"), sites_doc)
    dump(os.path.join(DATA_JSON, "configs.json"), cfgs_doc)
    print(f"[build] contentHash = {content_hash}"
          f"（同一份 exports 应恒定，与 generatedAt 无关）")
    print(f"[build] 上游 exports.contentHash = {sites_doc['sourceContentHash']}"
          f"（与 docs 的 contentHash 不同是正常的：前者是数据层，后者含构建期加工）")

    # ---------- 5) 内联兜底 ----------
    fb = {"configs": cfgs_doc, "sites": sites_doc, "builtAt": stamp}
    html_path = os.path.join(DOCS, "index.html")
    html = open(html_path, encoding="utf-8").read()
    payload = json.dumps(fb, ensure_ascii=False, separators=(",", ":"))
    # 防止 JSON 里的 </script> 截断标签
    payload = payload.replace("</", "<\\/")
    block = (f"<!--DATA_FALLBACK_START-->\n"
             f"<script>window.__TVBOX_FALLBACK__ = {payload};</script>\n"
             f"<!--DATA_FALLBACK_END-->")
    # 注意：必须用 lambda 作为替换值。直接传字符串会被 re 当成转义模板，
    # 把 payload 里的 \ 序列破坏掉（曾导致注入后的 JSON 无法解析）。
    new_html, n = re.subn(
        r"<!--DATA_FALLBACK_START-->.*?<!--DATA_FALLBACK_END-->",
        lambda _m: block, html, flags=re.S)
    if n != 1:
        print(f"[FATAL] 未找到 DATA_FALLBACK 注入点（匹配 {n} 次）")
        return 2
    # 注入后立刻自检：确保页面里的 JSON 能被解析
    m = re.search(r"window\.__TVBOX_FALLBACK__ = (.*?);</script>", new_html, re.S)
    if not m:
        print("[FATAL] 注入后找不到 fallback 数据")
        return 3
    try:
        chk = json.loads(m.group(1))
        if len(chk["sites"]["items"]) != len(sites):
            print(f"[FATAL] 注入站点数不符：{len(chk['sites']['items'])} != {len(sites)}")
            return 3
    except Exception as e:
        print(f"[FATAL] 注入后的 JSON 无法解析：{e}")
        return 3
    open(html_path, "w", encoding="utf-8", newline="\n").write(new_html)

    print("=" * 66)
    print("构建完成")
    print("=" * 66)
    print(f"  配置 {len(cfgs)} 条   站点 {len(sites)} 条")
    print(f"  已收录：主配置 {cnt['main']} / 扩展配置 {cnt['full']} / 未收录 {cnt['none']}")
    if not no_probe:
        from collections import Counter
        print(f"  配置状态：{dict(Counter(c.get('state') for c in cfgs))}")
        print(f"  推荐标记：{sum(1 for c in cfgs if c.get('recommend'))} 条")
    print(f"  index.html {os.path.getsize(html_path)/1024:.1f} KB")
    print(f"  sites.json {os.path.getsize(os.path.join(DATA_JSON,'sites.json'))/1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
