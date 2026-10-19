#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按五档规则（A/B/C/D/E）给采集到的站点分档，并生成前端数据文件。

输入：
  data/sources.json        采集清单
  data/raw/*.json          原始配置
  data/dex_classes.json    反编译得到的 spider 类清单
  zijian.json              本仓库配置（用于 included 判定）

输出：
  data/site_candidates.json   全量证据（含原始站点 JSON、档位、理由、probe_url）
  docs/data/configs.json      整包配置（前端 Tab 1）
  docs/data/sites.json        站点源 A/B/C 档（前端 Tab 2）

A 档需要实测 type:1 的 api 是否可访问，结果缓存在 data/probe_cache.json。
用法：python scripts/build_candidates.py [--no-probe]
"""

import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
SOURCES_FILE = os.path.join(DATA_DIR, "sources.json")
DEX_FILE = os.path.join(DATA_DIR, "dex_classes.json")
ZIJIAN_FILE = os.path.join(BASE_DIR, "zijian.json")
OUT_CANDIDATES = os.path.join(DATA_DIR, "site_candidates.json")
OUT_CONFIGS = os.path.join(DATA_DIR, "exports", "configs.json")
OUT_SITES = os.path.join(DATA_DIR, "exports", "sites.json")
PROBE_CACHE = os.path.join(DATA_DIR, "probe_cache.json")

TZ = datetime.timezone(datetime.timedelta(hours=8))
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Linux; Android 11; TVBox) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36")

NON_SITE_CLASSES = {"Init", "Proxy", "Push", "JSDemo", "Market"}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}
URL_RE = re.compile(r'https?://[^\s"\'|,}\)]+')

CATEGORIES = ["综合", "多仓", "短剧", "影视", "采集", "自建"]
CATEGORY_MAP = {
    "综合": "综合", "多仓": "多仓", "短剧": "短剧", "采集": "采集", "自建": "自建",
    "动漫": "影视", "4K": "影视", "JS源": "综合", "CatVod": "综合", "单站": "影视",
}

DISPLAY_NAMES = {
    "qist-jsm": "自建综合接口 qist",
    "qist-0821": "qist 全量配置 0821",
    "qist-0825": "qist 精简配置 0825",
    "qist-0826": "qist 饭太硬系 0826",
    "qist-0827": "qist 蜂蜜系 0827",
    "qist-js": "qist JS 源合集",
    "qist-xyq": "qist 香雅情源",
    "qist-fty": "qist 饭太硬源",
    "qist-xiaosa": "qist 潇洒接口",
    "qist-pages-jsm": "qist 镜像接口",
    "gao-js": "高天流云 JS 源",
    "gao-0821": "高天流云 0821",
    "gao-0826": "高天流云 0826",
    "gao-0827": "高天流云 0827",
    "gao-xyq": "高天流云 香雅情",
    "2hacc-oktv": "2hacc OK影视配置",
    "2hacc-jsdelivr": "2hacc 镜像接口",
    "xyq-tvbox": "香雅情主接口",
    "guot55-vip2": "宝盒 VIP 接口",
    "maoystv-000": "分享源 000",
    "chitue-dongli": "东篱线路",
    "hccx-tvbox": "荷城茶秀",
    "guot55-ygmax": "月光 Max",
    "9280-kstore": "放牛娃新接口",
    "yingm-dm": "动漫城",
    "dxawi": "dxawi 接口",
    "252035-fongmi": "真心 FongMi",
    "9763-aowu": "嗷呜线路",
    "lushunming": "L 佬线路",
    "szyyds-x": "小马接口",
    "liucn-m": "老刘备接口",
    "qist-0707": "qist 0707 多仓",
    "qist-367": "qist 367",
    "qist-9918": "qist 9918",
    "qist-99188": "qist 99188",
    "qist-dianshi": "qist 电视自用",
    "fish2018-ol-all": "fish2018 去重合集",
    "fish2018-ol-tvbox": "fish2018 抓取结果",
    "github-inliang": "自建综合配置",
    "noimank-muti": "noimank 多仓",
    "noimank-jsdelivr": "noimank 多仓镜像",
    "niubihu-1": "niubihu 主配置",
    "niubihu-tv8": "niubihu 多仓",
    "tushen6-tvbox": "tushen6 主配置",
    "tushen6-lmw": "tushen6 多仓",
    "tushen6-caiji": "tushen6 采集源",
}

PROBE_TYPES = {"type1_api"}


def now_iso():
    return datetime.datetime.now(TZ).replace(microsecond=0).isoformat()


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_abs_url(v):
    return isinstance(v, str) and re.match(r"^https?://", v.strip(), re.I)


def host_of(u):
    try:
        return (urllib.parse.urlsplit(u).hostname or "").lower()
    except Exception:
        return ""


def normalize_type(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return -1


def is_template_url(u):
    """未展开的模板占位符（{cateId}、%s）不是可请求目标；%XX 是百分号编码，属于正常 URL。"""
    return bool(u) and bool(re.search(r"[{}]|%[sdv]", u))


STATIC_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".css", ".svg")


def is_static_asset(u):
    """图片/样式表返回 200 只能说明文件在，回答不了"这个源能不能用"。"""
    return bool(u) and urllib.parse.urlsplit(u).path.lower().endswith(STATIC_EXT)


def extract_probe_url(ext):
    """从 ext 里取第一个可探的绝对 URL，跳过本机地址、模板串和静态资源。"""
    if ext is None:
        return None
    raw = json.dumps(ext, ensure_ascii=False) if not isinstance(ext, str) else ext
    for u in URL_RE.findall(raw):
        u = u.rstrip("\\'\"")
        if host_of(u) in LOCAL_HOSTS or is_template_url(u) or is_static_asset(u):
            continue
        return u
    return None


def probe_kind(site):
    """probe_url 为 null 时区分原因，前端据此给不同文案。"""
    t = normalize_type(site.get("type"))
    api = site.get("api") if isinstance(site.get("api"), str) else ""
    ext = site.get("ext")
    if t == 1:
        return "url" if is_abs_url(api) else "none"
    if ext is None or (isinstance(ext, dict) and not ext) or (isinstance(ext, str) and not ext.strip()):
        return "no_ext"
    etext = ext_text(ext)
    raw_urls = URL_RE.findall(etext)
    urls = [u for u in raw_urls if not is_template_url(u) and not is_static_asset(u)]
    if urls:
        return "local_only" if all(host_of(u) in LOCAL_HOSTS for u in urls) else "url"
    if raw_urls:
        # 有 URL 但全是模板串或图片资源，同样没有可直接请求的地址
        return "no_url"
    if isinstance(ext, str):
        return "encrypted_ext"
    return "no_url"


def probe_target(site):
    """返回该站点真正要探测的 URL（type1 探 api，type3 探 ext 首个绝对地址）。"""
    t = normalize_type(site.get("type"))
    if t == 1:
        api = site.get("api")
        return api if is_abs_url(api) else None
    return extract_probe_url(site.get("ext"))


def ext_text(ext):
    if ext is None:
        return ""
    return json.dumps(ext, ensure_ascii=False, sort_keys=True) if not isinstance(ext, str) else ext


def site_signature(s):
    t = normalize_type(s.get("type"))
    ext = s.get("ext")
    e = ext if isinstance(ext, str) else json.dumps(ext, ensure_ascii=False, sort_keys=True)
    return (t, str(s.get("api")), e)


def site_id(s):
    """站点自身签名派生，与收录来源无关：换归属/换顺序 id 不变，内容变了才换。"""
    ext = s.get("ext", "")
    if not isinstance(ext, str):
        # 对象/数组必须规范化，否则键序不同会算出不同 id
        ext = json.dumps(ext, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    raw = "|".join([
        str(normalize_type(s.get("type"))),
        str(s.get("api", "")),
        ext,
        str(s.get("key", "")),   # 兜底防碰撞：同 api+ext 但 key 不同的条目
    ])
    return "s_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def content_hash(doc):
    """去掉时间戳后的内容指纹：判断"这轮到底改了什么"用这个，不用文件字节。"""
    body = {k: v for k, v in doc.items() if k not in ("generatedAt", "contentHash")}
    canon = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()[:16]


UA_CLIENT = "okhttp/3.12.13"
UA_BROWSER = ("Mozilla/5.0 (Linux; Android 11; TVBox) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36")
BLOCKED_CODES = {403, 405, 418, 423, 429}

# 关键：绕过环境代理直连。环境里的 127.0.0.1:9188 代理会拦 http 目标并返回 502/403，
# 曾导致 136 个 http 目标全部误判为失效。
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=SSL_CTX),
)


def idna_url(url):
    """中文域名/中文路径转 ASCII，否则 http.client 会抛 UnicodeEncodeError。"""
    if all(ord(c) < 128 for c in url):
        return url
    p = urllib.parse.urlsplit(url)
    try:
        host = (p.hostname or "").encode("idna").decode("ascii")
    except Exception:
        host = p.hostname or ""
    netloc = f"{host}:{p.port}" if p.port else host
    path = urllib.parse.quote(p.path, safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(p.query, safe="=&%:@!$'()*+,;/?-._~")
    return urllib.parse.urlunsplit((p.scheme, netloc, path, query, ""))


def swap_scheme(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(("http" if p.scheme == "https" else "https",
                                    p.netloc, p.path, p.query, ""))


def _get(url, ua, timeout, opener=None):
    """返回 (code, body, ctype, err)。err 为 'ssl' 表示 TLS 层失败。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip",
        "Connection": "close",
    })
    try:
        with (opener or OPENER).open(req, timeout=timeout) as r:
            return r.status, r.read(200000), r.headers.get("Content-Type", ""), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read(4096)
        except Exception:
            body = b""
        return e.code, body, e.headers.get("Content-Type", "") if e.headers else "", None
    except (socket.timeout, TimeoutError):
        return None, b"", "", "timeout"
    except urllib.error.URLError as e:
        r = e.reason
        if isinstance(r, ssl.SSLError) or "SSL" in type(r).__name__:
            return None, b"", "", "ssl"
        if isinstance(r, socket.gaierror):
            return None, b"", "", "dns"
        if isinstance(r, ConnectionRefusedError):
            return None, b"", "", "refused"
        return None, b"", "", f"conn:{r}"
    except ssl.SSLError:
        return None, b"", "", "ssl"
    except Exception as e:  # noqa: BLE001
        name = type(e).__name__
        if "RemoteDisconnected" in name or "IncompleteRead" in name:
            return None, b"", "", "timeout"
        return None, b"", "", f"exc:{name}"


def parse_json_body(body):
    if body[:2] == b"\x1f\x8b":
        try:
            import gzip
            body = gzip.decompress(body)
        except Exception:
            pass
    text = body.decode("utf-8", errors="replace").lstrip("\ufeff").strip()
    try:
        return json.loads(text), text
    except Exception:
        m = re.search(r"[\{\[]", text)
        if m:
            tail = text.rfind("}" if text[m.start()] == "{" else "]")
            if tail > m.start():
                try:
                    return json.loads(text[m.start():tail + 1]), text
                except Exception:
                    pass
    return None, text


def probe_once(url, kind="api", timeout=8, opener=None):
    """
    探测一个地址，返回带 confidence 的结构化结果。
    confidence: confirmed / dead / uncertain —— 只有 confirmed 才算「探明可用」，
    其余一律视为「探针没能力判断」，不允许当成失效对外展示。
    """
    base = {"ver": 3, "kind": kind, "status": None, "confidence": "uncertain",
            "httpStatus": None, "reason": None, "url": url}

    def classify(code, body, ctype, err):
        if err == "ssl":
            return "tls_issue", "uncertain", None, "TLS 握手失败"
        if err == "dns":
            return "dead", "dead", None, "DNS 解析失败"
        if err in ("refused", "timeout"):
            return "dead", "dead", None, "连接拒绝/超时"
        if err:
            return "uncertain_network", "uncertain", None, f"网络错误 {err}"
        if code is None:
            return "uncertain_network", "uncertain", None, "无响应"
        if code in BLOCKED_CODES:
            return "blocked", "uncertain", code, f"HTTP {code}（UA/IP 拦截）"
        if code in (404, 410):
            return "dead", "dead", code, f"HTTP {code}"
        if 500 <= code < 600:
            return "uncertain_temporary", "uncertain", code, f"HTTP {code}"
        if 200 <= code < 300:
            obj, text = parse_json_body(body)
            if obj is not None:
                return "confirmed_ok", "confirmed", code, None
            return "uncertain_non_json", "uncertain", code, "2xx 但非 JSON"
        return "uncertain_http", "uncertain", code, f"HTTP {code}"

    candidates = [url]
    if kind == "api" and "?" not in url:
        candidates.append(url + "?ac=list")

    last = None
    for idx, target in enumerate(candidates):
        u = idna_url(target)
        code, body, ctype, err = _get(u, UA_CLIENT, timeout, opener)
        # TLS 失败常见于 scheme 写错（https 端口跑 http 服务），换 scheme 再试一次
        if err == "ssl":
            code, body, ctype, err = _get(idna_url(swap_scheme(target)), UA_CLIENT, timeout, opener)
        # 被 UA 拦截时用浏览器 UA 复验一次
        if err is None and code in BLOCKED_CODES:
            code, body, ctype, err = _get(u, UA_BROWSER, timeout, opener)

        status, conf, hcode, reason = classify(code, body, ctype, err)
        last = {"status": status, "confidence": conf, "httpStatus": hcode, "reason": reason}
        base.update(last)
        base["bytes"] = len(body)
        base["contentType"] = (ctype or "")[:80]
        base["tried"] = target
        if status == "confirmed_ok":
            obj, text = parse_json_body(body)
            base["shape"] = type(obj).__name__
            base["keys"] = list(obj)[:6] if isinstance(obj, dict) else None
            base["snippet"] = text[:80]
            return base
        if status == "dead":
            return base
    # 非 JSON 时给前端一点判据
    if last and last["status"] == "uncertain_non_json":
        base["snippet"] = parse_json_body(body)[1][:100].replace("\n", " ")
    return base


# 备用通道：环境代理。直连失败（DNS/超时/TLS）时才用，避免代理把 http 目标全判死。
PROXY_OPENER = urllib.request.build_opener(urllib.request.HTTPSHandler(context=SSL_CTX))
RANK = {"confirmed": 3, "uncertain": 2, "dead": 1}


def probe_json(url, kind="api", timeout=8):
    """双通道探测：直连优先，网络类失败再走代理，取更可信的结果。"""
    r = probe_once(url, kind, timeout, OPENER)
    r["via"] = "direct"
    reason = str(r.get("reason") or "")
    need_proxy = r["status"] in ("tls_issue", "uncertain_network") or (
        r["status"] == "dead" and not reason.startswith("HTTP"))
    if need_proxy:
        r2 = probe_once(url, kind, timeout, PROXY_OPENER)
        r2["via"] = "proxy"
        if RANK.get(r2["confidence"], 0) > RANK.get(r["confidence"], 0):
            return r2
    return r


# GitHub 加速/转发站：它们挂了不代表源站挂了，dead 只能说明这一跳不可用。
# 不含 cdn.jsdelivr.net：它是 CDN，直接返回仓库文件本身，404 说明文件真没了，属于真 dead。
# 这份清单必须与 docs/index.html 的 MIRROR_HOSTS 完全一致（前端用它决定不判青/不进探测队列）。
MIRROR_HOSTS = {"ghp.ci", "gh-proxy.com", "gh-proxy.org", "gh-proxy.net",
                "ghproxy.net", "ghproxy.cc", "ghfast.top", "raw.kkgithub.com"}


def apply_probe_guards(url, res):
    """把"这个地址失败"和"这个站点失效"分开，避免镜像/代理故障生成假死链。"""
    if res.get("confidence") != "dead":
        return res
    h = host_of(url)
    if h in MIRROR_HOSTS:
        out = dict(res)
        out["confidence"] = "uncertain"
        out["status"] = "mirror_down"
        out["reason"] = f"镜像 {h} 不可用，源站未验证"
        return out
    return res


def classify_site(site, site_classes, probe=None):
    """返回 (tier, reason, reason_code)。"""
    t = normalize_type(site.get("type"))
    api = site.get("api")
    api_s = api if isinstance(api, str) else ""
    ext = site.get("ext")
    etext = ext_text(ext)
    cls = api_s[4:] if api_s.startswith("csp_") else None

    if t == 1:
        if not is_abs_url(api_s):
            return "E", "type1 但 api 不是绝对 http(s) 地址", "api_not_class"
        st = (probe or {}).get("status")
        if st == "confirmed_ok":
            return "A", "type1 远程单源，实测返回合法 JSON", "probe_ok"
        if st == "dead":
            return "D", "type1 远程单源，实测确认失效", "probe_dead"
        return "Y", "type1 远程单源，探针无法判断（拦截/非 JSON/TLS），保守收进 full 末尾", "probe_uncertain"

    if t == 3:
        if api_s.startswith("./lib/") or api_s.startswith("lib/"):
            return "E", "api 依赖 ./lib 相对路径脚本", "relpath_api"
        if cls is None:
            if re.match(r"^https?://", api_s, re.I):
                return "E", "api 为远程 JS 地址（js 源，MVP 不合并）", "remote_js"
            return "E", "type3 但 api 既非 csp_ 类名也非绝对地址", "api_not_class"
        if cls in NON_SITE_CLASSES:
            return "E", f"csp_{cls} 是工具类，不是可播放站点", "non_site_class"
        if cls not in site_classes:
            return "E", f"类名 {cls} 不在本仓库 dex 中", "class_missing"
        if "./lib/" in etext or "../" in etext:
            return "D", "ext 依赖 ./lib 相对路径资源", "dep_relpath"
        if any(host_of(u) in LOCAL_HOSTS for u in URL_RE.findall(etext)):
            return "D", "ext 指向本机文件服务（127.0.0.1/localhost）", "dep_local"
        # ext 是唯一数据源，确认失效即整站不可用，与 type1 的 dead 同等处理
        if (probe or {}).get("status") == "dead":
            return "D", "ext 实测确认失效（404/连接拒绝/超时）", "probe_dead"
        if ext is None or (isinstance(ext, dict) and not ext) or (isinstance(ext, str) and not ext.strip()):
            return "C", "type3 自包含源，无外部依赖", "self_contained"
        if re.search(r"https?://", etext):
            return "B", "type3 类名可用，ext 含绝对 URL", "ext_abs_url"
        return "B", "type3 类名可用，ext 非明文（加密串），无外部依赖可探", "ext_encrypted"

    return "E", f"type {t} 不是可合并的站点类型", "type_unsupported"


def build_snippet(site):
    """生成可直接粘贴的紧凑 JSON，字段顺序 key/name/type/api + 约定可选字段。"""
    order = ["key", "name", "type", "api", "ext", "playerType", "searchable", "filterable"]
    out = {}
    for k in order:
        if k in site and site[k] not in (None, ""):
            out[k] = site[k]
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def type_label(site):
    t = normalize_type(site.get("type"))
    api = site.get("api") if isinstance(site.get("api"), str) else ""
    if t == 1:
        return "type1 远程"
    if t == 3:
        if api.lower().endswith(".py"):
            return "py"
        if api.lower().endswith(".js") or api.lower().startswith("./lib/"):
            return "js"
        return "type3 爬虫"
    return "other"


def source_repo(url):
    h = host_of(url)
    if "githubusercontent" in h or h == "github.com":
        parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    if "jsdelivr" in h:
        m = re.search(r"/gh/([^/]+/[^/@]+)", urllib.parse.urlsplit(url).path)
        if m:
            return m.group(1)
    return h or "unknown"


def main():
    probe_enabled = "--no-probe" not in sys.argv
    created = now_iso()
    sources = load_json(SOURCES_FILE)
    dex = load_json(DEX_FILE) or {"classes": []}
    zijian = load_json(ZIJIAN_FILE) or {}

    all_classes = set(dex.get("classes") or [])
    site_classes = all_classes - NON_SITE_CLASSES
    print(f"dex 类 {len(all_classes)} 个，可用站点类 {len(site_classes)} 个")

    inc_sigs = {site_signature(s) for s in (zijian.get("sites") or []) if isinstance(s, dict)}

    configs = [c for c in sources["configs"] if c["status"] == "ok"]
    order_map = {c["url"]: i for i, c in enumerate(sources["configs"])}
    # 保持候选清单的采集顺序，自建接口置顶（决定去重时谁保留原始 JSON）
    configs.sort(key=lambda c: (0 if c["name"] == "github-inliang" else 1, order_map.get(c["url"], 999)))

    # 内容完全相同的配置视为镜像，合并成一张卡片
    digest_of = {}
    for cfg in configs:
        with open(os.path.join(BASE_DIR, cfg["rawFile"]), "rb") as f:
            digest_of[cfg["name"]] = hashlib.md5(f.read()).hexdigest()
    primary_by_digest, mirrors = {}, {}
    for cfg in configs:
        dg = digest_of[cfg["name"]]
        if dg in primary_by_digest:
            mirrors.setdefault(primary_by_digest[dg], []).append(cfg["url"])
        else:
            primary_by_digest[dg] = cfg["name"]
    mirror_names = {n for n in digest_of if primary_by_digest[digest_of[n]] != n}
    print(f"镜像配置 {len(mirror_names)} 个，主配置 {len(set(primary_by_digest.values()))} 个")

    # 先收集所有站点，保留出现顺序（本仓库自己的配置读实时文件，避免快照过期）
    raw_sites = []   # (config, site)
    cfg_total = {}
    for cfg in configs:
        path = ZIJIAN_FILE if cfg["name"] == "github-inliang" else os.path.join(BASE_DIR, cfg["rawFile"])
        obj = load_json(path)
        sites = [s for s in (obj.get("sites") or []) if isinstance(s, dict)]
        cfg_total[cfg["name"]] = len(sites)
        for s in sites:
            raw_sites.append((cfg, s))

    # 实测：type1 探 api（可加 ?ac=list 重试），type3 探 ext 首个绝对地址
    probe_map = {}
    cache = load_json(PROBE_CACHE, {}) or {}
    target_kind = {}
    for _, s in raw_sites:
        t = probe_target(s)
        if not t:
            continue
        k = "api" if normalize_type(s.get("type")) == 1 else "ext"
        # 同一 URL 如果既是 api 又是 ext，按 api 处理（可触发 ?ac=list 重试）
        if target_kind.get(t) != "api":
            target_kind[t] = k

    to_probe = sorted(target_kind)
    old_ver = [u for u in to_probe if cache.get(u, {}).get("ver") != 3]
    if old_ver:
        cache = {u: v for u, v in cache.items() if v.get("ver") == 3}
    if probe_enabled:
        todo = [u for u in to_probe if u not in cache]
        print(f"待实测 {len(todo)} 个（v2 缓存 {len(to_probe) - len(todo)} 个，作废旧结果 {len(old_ver)} 个）")
        if todo:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
                futs = {pool.submit(probe_json, u, target_kind[u]): u for u in todo}
                for i, fut in enumerate(concurrent.futures.as_completed(futs), 1):
                    u = futs[fut]
                    cache[u] = fut.result()
                    cache[u]["probedAt"] = created
                    if i % 50 == 0:
                        print(f"  已测 {i}/{len(todo)}")
            with open(PROBE_CACHE, "w", encoding="utf-8", newline="\n") as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)
    for u in to_probe:
        probe_map[u] = apply_probe_guards(
            u, cache.get(u, {"status": "untested", "confidence": "uncertain"}))

    conf_stat = {}
    for v in probe_map.values():
        conf_stat[v.get("confidence", "uncertain")] = conf_stat.get(v.get("confidence", "uncertain"), 0) + 1
    print(f"实测完成：confirmed {conf_stat.get('confirmed', 0)} / dead {conf_stat.get('dead', 0)} "
          f"/ uncertain {conf_stat.get('uncertain', 0)}，共 {len(probe_map)}")

    # 分档 + 去重（同一签名保留最早出现，来源汇总到 sources）
    items = []
    seen = {}
    cfg_tier = {}
    cfg_probe_ok = {}
    cfg_encrypted = {}
    for cfg, site in raw_sites:
        target = probe_target(site)
        pr = probe_map.get(target) if target else None
        tier, reason, code = classify_site(site, site_classes, pr)
        cfg_tier.setdefault(cfg["name"], {}).setdefault(tier, 0)
        cfg_tier[cfg["name"]][tier] += 1
        if pr and pr.get("confidence") == "confirmed" and tier in ("A", "B", "C"):
            cfg_probe_ok[cfg["name"]] = cfg_probe_ok.get(cfg["name"], 0) + 1
        if tier == "B" and probe_kind(site) == "encrypted_ext":
            cfg_encrypted[cfg["name"]] = cfg_encrypted.get(cfg["name"], 0) + 1

        sig = site_signature(site)
        if sig in seen:
            seen[sig]["sources"].append(cfg["name"])
            continue
        key = site.get("key")
        api = str(site.get("api"))
        pconf = (pr or {}).get("confidence")
        pstatus = "none" if not target else ("confirmed" if pconf == "confirmed"
                                             else "dead" if pconf == "dead" else "uncertain")
        rec = {
            "key": key,
            "name": site.get("name"),
            "type": normalize_type(site.get("type")),
            "api": api,
            "tier": tier,
            "reason": reason,
            "reason_code": code,
            "probe_url": extract_probe_url(site.get("ext")),
            "probe_kind": probe_kind(site),
            "probe_target": target,
            "probe_status": pstatus,
            "probe_detail": (pr or {}).get("status"),
            "probe_reason": (pr or {}).get("reason"),
            "included": sig in inc_sigs,
            "config_ref": cfg["name"],
            "config_url": cfg["url"],
            "source_url": cfg["url"],
            "fetchedAt": cfg.get("checkedAt"),
            "sources": [cfg["name"]],
            "site": site,
        }
        seen[sig] = rec
        items.append(rec)

    # 粗筛：A 全收、C 全收，B 按 probe 域名每域最多 2 条，首屏控制在 150 条内
    RECOMMEND_LIMIT = 150
    rank = {"A": 0, "C": 1, "B": 2}
    ordered = sorted(items, key=lambda r: (rank.get(r["tier"], 9),
                                           0 if r.get("probe_status") == "ok" else 1,
                                           -len(r["sources"]), r["name"] or ""))
    picked = 0
    domain_used = {}
    for r in ordered:
        r["recommend"] = False
        if r["tier"] in ("A", "C"):
            r["recommend"] = True
            picked += 1
    for r in ordered:
        if r["tier"] != "B" or picked >= RECOMMEND_LIMIT:
            continue
        d = host_of(r["probe_url"] or "")
        if domain_used.get(d, 0) >= 2:
            continue
        domain_used[d] = domain_used.get(d, 0) + 1
        r["recommend"] = True
        picked += 1
    print(f"首屏推荐 {picked} 条（A/C 全收，B 每域名≤2）")

    # 统计
    tiers = {t: 0 for t in "ABCDEY"}
    for r in items:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    total_raw = len(raw_sites)
    unique = len(items)
    print(f"站点原始 {total_raw} 条，去重后 {unique} 条；档位 A{tiers['A']} B{tiers['B']} "
          f"C{tiers['C']} D{tiers['D']} E{tiers['E']}；E 档占比 {tiers['E'] / unique * 100:.1f}%")

    code_stats = {}
    for r in items:
        code_stats[r["reason_code"]] = code_stats.get(r["reason_code"], 0) + 1
    # 未上架站点的排除原因聚合（key 名冻结，前端直接用）
    REJECTION_KEYS = ("class_missing", "relpath_api", "remote_js", "api_not_class",
                      "type_unsupported", "non_site_class", "dep_local", "dep_relpath",
                      "probe_dead")
    rejections = {k: code_stats.get(k, 0) for k in REJECTION_KEYS}
    pk_stats = {}
    for r in items:
        pk_stats[r["probe_kind"]] = pk_stats.get(r["probe_kind"], 0) + 1

    candidates_doc = {
        "generatedAt": created,
        "rules": {
            "A": "type1 + api 为绝对 URL + 实测返回合法 JSON",
            "B": "type3 + 类名在 dex 站点类中 + ext 含绝对 URL",
            "C": "type3 + 类名在 dex 站点类中 + 无 ext（自包含）",
            "Y": "type1 + api 绝对 URL + 实测无法判断（拦截/非 JSON/TLS）：只进 full 末尾",
            "D": "确定不可用：实测 dead（type1/type3 一致）或依赖 ./lib/本机文件",
            "E": "类名不在 dex、工具类、./lib 脚本、type0/4",
        },
        "reasonCodes": {
            "probe_ok": "A 档：实测确认通过",
            "probe_dead": "D 档：实测确认失效（404/DNS/拒绝/超时）",
            "probe_uncertain": "D 档：探针无法判断（拦截/非 JSON/TLS）",
            "ext_abs_url": "B 档：ext 含绝对 URL",
            "ext_encrypted": "B 档：ext 为加密串，无外部依赖",
            "self_contained": "C 档：无 ext",
            "relpath_api": "E 档：api 依赖 ./lib 相对路径",
            "dep_relpath": "D 档：ext 依赖 ./lib 相对路径",
            "dep_local": "D 档：ext 只指向本机文件服务",
            "remote_js": "E 档：api 为远程 JS 地址",
            "class_missing": "E 档：类名不在本仓库 dex",
            "non_site_class": "E 档：工具类（Init/Proxy/Push/JSDemo/Market）",
            "api_not_class": "E 档：api 既非 csp_ 类名也非绝对地址",
            "type_unsupported": "E 档：type 0/4 等",
        },
        "probeKinds": {
            "url": "有可探地址",
            "no_ext": "无 ext，无需探测",
            "encrypted_ext": "ext 为加密串，无需探测",
            "local_only": "ext 仅本机地址，探测会产生假绿",
            "no_url": "ext 存在但不含 URL",
            "none": "无 ext 且非 type1",
        },
        "confidence": {
            "confirmed": "探针确认可用（2xx + 合法 JSON）",
            "dead": "确定失效（404/DNS/连接拒绝/超时）",
            "uncertain": "探针无法判断（403/429/非 JSON/TLS/临时故障），不得当失效看",
        },
        "dexClasses": len(all_classes),
        "siteClasses": sorted(site_classes),
        "stats": {
            "configs": len(configs),
            "rawSites": total_raw,
            "uniqueSites": unique,
            "duplicates": total_raw - unique,
            "tiers": tiers,
            "tierERatio": round(tiers["E"] / unique * 100, 1) if unique else 0,
            "recommend": picked,
            "reasonCodes": code_stats,
            "probeKinds": pk_stats,
            "probe": {
                "total": len(probe_map),
                "confirmed": conf_stat.get("confirmed", 0),
                "dead": conf_stat.get("dead", 0),
                "uncertain": conf_stat.get("uncertain", 0),
                "rateConfirmed": round(conf_stat.get("confirmed", 0) / len(probe_map) * 100, 1) if probe_map else 0,
            },
        },
        "items": items,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_CANDIDATES, "w", encoding="utf-8", newline="\n") as f:
        json.dump(candidates_doc, f, ensure_ascii=False, indent=1)
    print(f"证据：{OUT_CANDIDATES}")

    # 已确认可用、但还没进 zijian.json 的站点，供 team-lead 直接合并
    pending = [r for r in items if r["tier"] == "A" and not r["included"]]
    pending_doc = {
        "generatedAt": created,
        "note": "A 档（type1 实测确认）且未出现在当前 zijian.json 中的站点，按来源配置去重",
        "count": len(pending),
        "items": [{
            "key": r["key"],
            "name": r["name"],
            "api": r["api"],
            "type": r["type"],
            "snippet": build_snippet(r["site"]),
            "site": r["site"],
            "config_ref": r["config_ref"],
            "source_url": r["source_url"],
        } for r in pending],
    }
    os.makedirs(os.path.join(DATA_DIR, "exports"), exist_ok=True)
    with open(os.path.join(DATA_DIR, "exports", "pending-main.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(pending_doc, f, ensure_ascii=False, indent=1)
    print(f"待并入主配置：{len(pending)} 条 -> data/exports/pending-main.json")

    # ---------------- 前端数据 ----------------
    os.makedirs(os.path.dirname(OUT_CONFIGS), exist_ok=True)
    site_items = []
    for r in items:
        if r["tier"] not in ("A", "B", "C", "Y"):
            continue
        cid = r["config_ref"]
        sid = site_id(r["site"])
        rec_item = {
            "id": sid,
            "name": r["name"],
            "configId": cid,
            "type": r["type"],
            "typeLabel": type_label(r["site"]),
            "api": r["api"],
            "searchable": r["site"].get("searchable"),
            "snippet": build_snippet(r["site"]),
            "probe_url": r["probe_url"],
            "probe_kind": r["probe_kind"],
            "probe_status": r["probe_status"],
            "included": r["included"],
            "tier": r["tier"],
            "segment": (4 if r["tier"] == "Y"
                        else 1 if r["tier"] in ("A", "C")
                        else 3 if (r["tier"] == "B" and r["probe_kind"] == "encrypted_ext")
                        else 2),
            "recommend": r["recommend"],
        }
        ext = r["site"].get("ext")
        if isinstance(ext, dict):
            su = ext.get("site_urls") or ext.get("site")
            if isinstance(su, list) and len(su) > 1:
                rec_item["note"] = f"含 {len(su)} 个镜像地址"
        site_items.append(rec_item)

    # id 是页面锚点的对外契约：签名派生一旦碰撞，DOM id 会撞、scrollIntoView 会跳错卡
    ids = [s["id"] for s in site_items]
    if len(ids) != len(set(ids)):
        from collections import Counter
        dup = [k for k, v in Counter(ids).items() if v > 1]
        raise SystemExit(f"站点 id 碰撞 {len(dup)} 组：{dup[:5]}")

    # 同一配置在 sites.json 的条数，必须与 configs.json siteCount 一致
    count_by_config = {}
    for s in site_items:
        count_by_config[s["configId"]] = count_by_config.get(s["configId"], 0) + 1

    # 站点集合与其它配置完全重合的，折叠为对方的镜像卡片，保留 URL 不丢
    owner = {sig: rec["config_ref"] for sig, rec in seen.items()}
    cfg_sigs = {}
    for cfg, site in raw_sites:
        cfg_sigs.setdefault(cfg["name"], set()).add(site_signature(site))
    for cfg in configs:
        cid = cfg["name"]
        if cfg.get("kind") == "multi" or cid in mirror_names:
            continue
        sigs = cfg_sigs.get(cid) or set()
        if not sigs:
            continue
        self_owned = sum(1 for sg in sigs if owner.get(sg) == cid)
        if self_owned == 0:
            from collections import Counter
            others = Counter(owner.get(sg) for sg in sigs if owner.get(sg) and owner.get(sg) != cid)
            if others:
                target = others.most_common(1)[0][0]
                mirrors.setdefault(target, []).append(cfg["url"])
                mirror_names.add(cid)
    if mirror_names:
        print(f"站点全重合、折叠为镜像：{len(mirror_names)} 个")

    cfg_items = []
    for cfg in configs:
        cid = cfg["name"]
        if cid in mirror_names:
            continue
        kind = cfg.get("kind")
        cat = CATEGORY_MAP.get(cfg.get("category"), "综合")
        tags = ["CatVod"] if kind != "multi" else ["多仓", "CatVod"]
        if cid == "github-inliang":
            tags = ["自建", "CatVod"]
        elif cfg.get("category") == "短剧":
            tags = ["短剧"]
        elif cfg.get("category") == "采集":
            tags = ["采集"]
        note = (cfg.get("note") or "").split("｜")[0][:48]
        if cid == "github-inliang":
            note = "本站维护，含自建影视与直播源"
        if kind == "multi":
            note = f"多仓入口（{cfg.get('urlsCount', 0)} 条子配置），站点需二级展开"
        tiers_of_cfg = cfg_tier.get(cid, {})
        static_pass = sum(v for k, v in tiers_of_cfg.items() if k in ("A", "B", "C"))
        is_multi = kind == "multi"
        cfg_items.append({
            "id": cid,
            "name": DISPLAY_NAMES.get(cid, cfg.get("name"))[:24],
            "url": cfg["url"],
            "format": "pluto" if is_multi else "catvod",
            "isMulti": is_multi,
            "category": cat,
            # 多仓配置里是子配置 URL 而不是 sites[]，站点数概念不适用，给 null 不显示 0
            "totalSites": None if is_multi else cfg_total.get(cid, cfg.get("sitesCount", 0)),
            "staticPass": None if is_multi else static_pass,
            "probeConfirmed": None if is_multi else cfg_probe_ok.get(cid, 0),
            "encryptedSites": None if is_multi else cfg_encrypted.get(cid, 0),
            "curatedSites": count_by_config.get(cid, 0),
            "recommend": cid in ("github-inliang", "qist-jsm", "liucn-m"),
            "tags": tags[:3],
            "note": note,
            "updatedAt": (cfg.get("checkedAt") or created)[:10],
            "innerUrls": cfg.get("urlsCount", 0) if is_multi else 0,
            "mirrors": sorted(set(mirrors.get(cid, []))),
            "source": source_repo(cfg["url"]),
        })

    def cfg_sort_key(x):
        return (not x["recommend"],
                -1 if x["probeConfirmed"] is None else -x["probeConfirmed"],
                -1 if x["staticPass"] is None else -x["staticPass"],
                -1 if x["totalSites"] is None else -x["totalSites"],
                x["name"], x["id"])

    cfg_items.sort(key=cfg_sort_key)
    cat_present = [c for c in CATEGORIES if any(x["category"] == c for x in cfg_items)]

    cfg_doc = {"generatedAt": created, "total": len(cfg_items),
               "categories": cat_present, "rejections": rejections,
               "items": cfg_items}
    cfg_doc["contentHash"] = content_hash(cfg_doc)

    with open(OUT_CONFIGS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg_doc, f, ensure_ascii=False, separators=(",", ":"))

    type_order = {"type1 远程": 0, "type3 爬虫": 1, "py": 2, "js": 3, "other": 4}
    # 末位用 id 兜底：同名同类型同推荐时不能依赖上游遍历顺序
    site_items.sort(key=lambda s: (s["segment"], not s["recommend"],
                                   type_order.get(s["typeLabel"], 9), s["name"] or "", s["id"]))
    sites_doc = {"generatedAt": created, "total": len(site_items),
                 "mirrorHosts": sorted(MIRROR_HOSTS), "items": site_items}
    sites_doc["contentHash"] = content_hash(sites_doc)
    with open(OUT_SITES, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sites_doc, f, ensure_ascii=False, separators=(",", ":"))

    print(f"configs.json: {len(cfg_items)} 条，分类 {cat_present}")
    print(f"sites.json: {len(site_items)} 条，"
          f"{os.path.getsize(OUT_SITES) / 1024:.0f}KB")
    bad = [c for c in cfg_items if c["curatedSites"] != count_by_config.get(c["id"], 0)]
    print("curatedSites 一致性:", "全部一致" if not bad else f"{len(bad)} 条不一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
