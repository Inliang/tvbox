#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox / CatVod 公开配置接口采集脚本（仅用标准库，无需 pip 安装依赖）。

做什么：
  1. 读取 scripts/candidates.json 中的候选地址；
  2. 逐条 GET（带常见 TVBox UA、超时、有限重试）；
  3. 校验响应是否为合法 JSON、是否含 sites[] 或 urls[]（多仓）；
  4. 合法内容落盘到 data/raw/<序号-名称>.json；
  5. 汇总写入 data/sources.json。

不做：不破解、不绕过访问控制、不猜测地址、不分析视频内容。

运行环境要求（重要）：
  HTTP 403 不足以判定站点失效——本项目实测到**两套独立原因**都会让好源返回 403：

  1. **并发限流（证据较硬）**：8 路并发下多个源（含 肥猫.net）返回 403 或空响应，
     串行间隔重试即恢复。2026-10-23 实测：同一份 candidates.json 并发跑得 49 ok，
     串行补跑后 55 ok。因此本脚本的 HTTP 403 不提前 break，会走完重试；
     若可用数仍偏少，用 FETCH_WORKERS=1 重跑一遍对比。
  2. **沙箱网络拦截（未确证）**：曾观察到沙箱内跑肥猫返回 403，但同一次会话里
     未绕过沙箱的单发探测也拿到过 200——两条证据互相矛盾，无法据此断定沙箱是主因。
     保留此条只为提醒：看到可用数偏少时，先排除环境因素，不要直接判站点失效。

  不要把 403 当结论。它可能是限流、可能是拦截、也可能是站点真的拒绝，
  这三者从单次响应上分不开——所以才需要重试和串行对照。
"""

import base64
import concurrent.futures
import datetime
import gzip
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
import zlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATES_FILE = os.path.join(BASE_DIR, "scripts", "candidates.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
OUT_FILE = os.path.join(DATA_DIR, "sources.json")

TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "15"))
RETRIES = int(os.environ.get("FETCH_RETRIES", "2"))
WORKERS = int(os.environ.get("FETCH_WORKERS", "8"))

UA = ("Mozilla/5.0 (Linux; Android 11; TVBox) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

TZ = datetime.timezone(datetime.timedelta(hours=8))
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def now_iso() -> str:
    return datetime.datetime.now(TZ).replace(microsecond=0).isoformat()


def slug(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z._-]+", "-", name).strip("-")
    return s or "unnamed"


def normalize_url(url: str) -> str:
    """把中文域名/中文路径转成可请求的 ASCII URL（IDNA + percent-encoding）。"""
    parts = urllib.parse.urlsplit(url.strip())
    host = parts.hostname or ""
    try:
        host_ascii = host.encode("idna").decode("ascii")
    except Exception:
        host_ascii = host
    netloc = host_ascii
    if parts.port:
        netloc = f"{host_ascii}:{parts.port}"
    if parts.username:
        auth = parts.username + (":" + parts.password if parts.password else "")
        netloc = f"{auth}@{netloc}"
    path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(parts.query, safe="=&%:@!$'()*+,;/?-._~")
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, ""))


def decode_body(body: bytes, content_encoding: str) -> bytes:
    enc = (content_encoding or "").lower()
    if "gzip" in enc or body[:2] == b"\x1f\x8b":  # 有些源发 gzip 但不带响应头
        try:
            return gzip.decompress(body)
        except Exception:
            return body
    if "deflate" in enc or body[:1] == b"\x78":
        try:
            return zlib.decompress(body)
        except Exception:
            try:
                return zlib.decompress(body, -zlib.MAX_WBITS)
            except Exception:
                return body
    return body


# 有些配置藏在图片尾部：Content-Type 是 image/*，GIF 正常结束后再拖一段载荷。
# 载荷格式（已实测）：[8B]"feimaomm" [2B]"**" [N B]base64 → 解码得明文 JSON。
# 只在能找到魔法串时启用；找不到或解码失败一律按"非 JSON"处理，不猜、不截断。
GIF_PAYLOAD_MAGIC = b"feimaomm**"


def extract_gif_payload(body: bytes, content_type: str):
    """从图片响应尾部取出内嵌配置。返回 (字节, 标记)；不适用时返回 (None, None)。

    解码失败抛 ValueError，由调用方转成干净的错误文案。
    """
    if not (content_type or "").lower().startswith("image/"):
        return None, None
    idx = body.find(GIF_PAYLOAD_MAGIC)
    if idx < 0:
        return None, None
    tail = body[idx + len(GIF_PAYLOAD_MAGIC):]
    if not tail:
        raise ValueError("魔法串后无载荷")
    # 只保留 base64 字母表，滤掉可能混入的换行/补齐字节
    b64 = re.sub(rb"[^A-Za-z0-9+/=]", b"", tail)
    if not b64:
        raise ValueError("魔法串后无有效 base64 字符")
    try:
        data = base64.b64decode(b64, validate=False)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"base64 解码失败: {e}")
    if not data:
        raise ValueError("base64 解码结果为空")
    return data, "gif-embedded"


def guess_encoding(body: bytes, content_type: str) -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        return m.group(1)
    for enc in ("utf-8", "gb18030"):
        try:
            body.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def repair_json_text(text: str) -> str:
    """针对常见的手写配置瑕疵做最小修复（仅用于校验/落盘，不改变语义）。"""
    t = text.lstrip("\ufeff").strip()
    # 块注释
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    # 行注释：只处理 // 前是空白、逗号、大括号或分号的情况，避免误伤 http://
    t = re.sub(r"(?<=[\s,{};])//[^\r\n]*", "", t)
    # 行首注释
    t = re.sub(r"(?m)^\s*//[^\r\n]*$", "", t)
    # 尾逗号
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    # 未加引号的 "key": 中文值（如 "key":爱迪V2）
    t = re.sub(r'("key"\s*:\s*)([^"\s,{\[\r\n][^,}\r\n]*)', r'\1"\2"', t)
    return t


def lenient_json(text: str):
    """尽力解析 JSON：原文 → 截取对象 → 修复注释/尾逗号/裸值。返回 (obj, repaired)。"""
    text = text.lstrip("\ufeff").strip()
    if not text:
        return None, False
    for candidate in (text, text[text.find("{"):text.rfind("}") + 1] if "{" in text else ""):
        if not candidate:
            continue
        try:
            return json.loads(candidate), False
        except Exception:
            continue
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(repair_json_text(text[start:end + 1])), True
        except Exception:
            return None, False
    return None, False


def classify(obj):
    """返回 (kind, sites_count, urls_count, spider)。"""
    if not isinstance(obj, dict):
        return "unknown", 0, 0, None
    sites = obj.get("sites")
    urls = obj.get("urls")
    spider = obj.get("spider")
    sites_count = len(sites) if isinstance(sites, list) else 0
    urls_count = len(urls) if isinstance(urls, list) else 0
    if urls_count and not sites_count:
        kind = "multi"
    elif sites_count:
        kind = "single"
    elif obj.get("storeHouse"):
        kind = "multi"      # 影视仓 storeHouse 多仓入口
        urls_count = len(obj["storeHouse"]) if isinstance(obj["storeHouse"], list) else 1
    elif obj.get("规则名"):
        kind = "unknown"    # 海阔视界规则，不是 TVBox 配置
    elif obj.get("key") and obj.get("name") and obj.get("type") is not None:
        kind = "site"       # 单站片段，需包进 sites[] 才能作为配置使用
        sites_count = 1
    else:
        kind = "unknown"
    return kind, sites_count, urls_count, spider


def fetch_one(item, idx):
    name = item.get("name") or f"config-{idx}"
    url = item["url"]
    result = {
        "name": name,
        "url": url,
        "category": item.get("category", "综合"),
        "note": item.get("note", ""),
        "status": "fail",
        "checkedAt": now_iso(),
        "httpStatus": None,
        "respBytes": 0,
        "sitesCount": 0,
        "urlsCount": 0,
        "kind": "unknown",
        "error": None,
        "elapsedMs": None,
        "rawFile": None,
        "repaired": False,
    }
    started = time.time()
    last_err = None
    final_url = None

    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(normalize_url(url), headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as resp:
                result["httpStatus"] = resp.status
                final_url = resp.geturl()
                result["finalUrl"] = final_url
                body = decode_body(resp.read(), resp.headers.get("Content-Encoding", ""))
                ctype = resp.headers.get("Content-Type", "")
            result["respBytes"] = len(body)
            if not body:
                last_err = "空响应"
                continue

            # 图片尾部内嵌配置：先尝试解码，解码出来的字节才是真正的配置文本
            try:
                embedded, payload_kind = extract_gif_payload(body, ctype)
            except ValueError as e:
                last_err = f"图片载荷解码失败: {e}"
                result["error"] = last_err
                break
            if embedded is not None:
                body = embedded
                result["respBytes"] = len(body)
                result["payload"] = payload_kind
                ctype = "application/json"   # 后续按 JSON 处理

            enc = guess_encoding(body, ctype)
            text = body.decode(enc, errors="replace")
            obj, repaired = lenient_json(text)
            if obj is None:
                last_err = "非 JSON 内容"
                snippet = text.strip()[:80].replace("\n", " ")
                result["error"] = f"非 JSON（开头：{snippet}）"
                continue
            result["repaired"] = bool(repaired)

            kind, sites_count, urls_count, spider = classify(obj)
            result["kind"] = kind
            result["sitesCount"] = sites_count
            result["urlsCount"] = urls_count
            if kind == "unknown":
                last_err = "JSON 中无 sites/urls 字段"
                result["error"] = last_err
                continue

            fname = f"{idx:02d}-{slug(name)}.json"
            fpath = os.path.join(RAW_DIR, fname)
            with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            result["rawFile"] = f"data/raw/{fname}"
            result["status"] = "ok"
            result["error"] = None
            if isinstance(spider, str):
                result["spider"] = spider
            break
        except urllib.error.HTTPError as e:
            result["httpStatus"] = e.code
            last_err = f"HTTP {e.code}"
            # 403 不提前退出：实测多个源在 8 路并发下返回 403/空响应，串行重试即恢复
            # （同一份清单，并发跑 49 ok，串行补跑后 55 ok）。403 也可能是真 WAF，
            # 但多花一次重试的代价远小于把可用源误判成死站。
            # 401 是需要鉴权，重试无意义；404/410 是文件确实没了。
            if e.code in (401, 404, 410):
                break
        except (socket.timeout, TimeoutError):
            last_err = f"超时(>{TIMEOUT}s)"
        except urllib.error.URLError as e:
            reason = e.reason
            if isinstance(reason, (socket.timeout, TimeoutError)):
                last_err = f"超时(>{TIMEOUT}s)"
            elif isinstance(reason, socket.gaierror):
                last_err = "DNS 解析失败"
            elif isinstance(reason, ConnectionRefusedError):
                last_err = "连接被拒绝"
            elif isinstance(reason, ssl.SSLError):
                last_err = f"TLS 失败: {reason}"
            else:
                last_err = f"连接失败: {reason}"
        except ssl.SSLError as e:
            last_err = f"TLS 失败: {e}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(0.8 * (attempt + 1))

    result["elapsedMs"] = int((time.time() - started) * 1000)
    if result["status"] != "ok":
        result["error"] = result["error"] or last_err
    return result


def hint_for(r):
    """给失败项补一句人话解释，避免把网络限制误判成地址失效。"""
    if r["status"] == "ok":
        return None
    err = r.get("error") or ""
    code = r.get("httpStatus")
    if code == 403:
        return "本机出口返回 403（WAF/网络限制），地址本身未必失效，需代理复验"
    if code == 401:
        return "需要鉴权（401），不符合公开可访问要求"
    if code == 404:
        return "文件不存在（404），可能已改名或删除"
    if "超时" in err:
        return "请求超时，可能被墙或站点响应慢"
    if "DNS" in err:
        return "DNS 解析失败，域名可能已停用或被污染"
    if "非 JSON" in err:
        return "返回内容不是明文 JSON（可能是 HTML/图片/加密内容）"
    return None


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    # 清理上次生成的 raw 文件，避免序号变化后残留
    for fn in os.listdir(RAW_DIR):
        if fn.lower().endswith(".json"):
            os.remove(os.path.join(RAW_DIR, fn))

    with open(CANDIDATES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    candidates = data["candidates"]

    print(f"候选地址 {len(candidates)} 个，超时 {TIMEOUT}s，重试 {RETRIES} 次，并发 {WORKERS}")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_one, c, i + 1): c for i, c in enumerate(candidates)}
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            flag = "OK  " if r["status"] == "ok" else "FAIL"
            detail = (f"sites={r['sitesCount']} urls={r['urlsCount']} kind={r['kind']}"
                      if r["status"] == "ok" else (r["error"] or ""))
            print(f"[{flag}] {r['name']:<20} {str(r.get('httpStatus')):<4} "
                  f"{r['respBytes']:>7}B {detail}")

    order = {c["url"]: i for i, c in enumerate(candidates)}
    results.sort(key=lambda r: order.get(r["url"], 999))

    for r in results:
        h = hint_for(r)
        if h:
            r["hint"] = h
            if h not in (r.get("note") or ""):
                r["note"] = f"{r['note']}｜{h}" if r.get("note") else h
        if r["status"] == "ok" and r.get("kind") == "site":
            r["note"] = f"单站片段（需包进 sites[]）｜{r['note']}" if r.get("note") else "单站片段（需包进 sites[]）"

    ok = [r for r in results if r["status"] == "ok"]
    fail = [r for r in results if r["status"] != "ok"]

    payload = {
        "updated": datetime.datetime.now(TZ).strftime("%Y-%m-%d"),
        "generatedAt": now_iso(),
        "summary": {
            "total": len(results),
            "ok": len(ok),
            "fail": len(fail),
            "single": sum(1 for r in ok if r["kind"] == "single"),
            "multi": sum(1 for r in ok if r["kind"] == "multi"),
            "site": sum(1 for r in ok if r["kind"] == "site"),
            "totalSites": sum(r["sitesCount"] for r in ok),
        },
        "configs": results,
    }
    with open(OUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("-" * 60)
    print(f"可用 {len(ok)} / 候选 {len(results)}，失败 {len(fail)}")
    print(f"单仓 {payload['summary']['single']}，多仓 {payload['summary']['multi']}，"
          f"可拆解站点合计 {payload['summary']['totalSites']}")
    print(f"清单：{OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
