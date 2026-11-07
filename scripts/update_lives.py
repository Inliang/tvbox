#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新项目直播源播放列表。

背景：影视仓（FongMi 系）不解析 APTV 私有的 #EXT-X-SUB-URL 扩展，
且 gh.aptv.app 代理已返回 403，因此 lives 指向的文件必须是「内联完整频道」的
自包含 m3u，不能只放一个远程订阅头。本脚本拉取上游 -> 全量并发探测流地址 ->
剔除明确死链 -> 写出自包含播放列表。

用法：
  python scripts/update_lives.py                  拉上游、探测死链、重建全部播放列表
  python scripts/update_lives.py --all-only       不联网，由仓库内成品重建总表
  python scripts/update_lives.py --refresh-scenery  重测风景慢直播线路并重建总表
  python scripts/update_lives.py --refresh-logo     重测台标并重建总表
可重复运行：无上游的本地源会在首次运行时生成 .bak 原始备份，之后始终从备份读取。
"""
import collections
import concurrent.futures as cf
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"
UA = "Mozilla/5.0 (Linux; Android 11) okHttp/Mod-1.5.0.0"
TIMEOUT = 6
WORKERS = 64
ROUNDS = 2  # 公网探测有抖动，多轮取并集，避免误杀间歇可达的源
EPG = "https://epg.112114.xyz/pp.xml"

# 原「直播中国」景区摄像头 CDN（gcalic / gctxyc / gccncc / gcksc 等 /gc/ 路径）
# 已整体停服：主列表仍可能返回 200，但子列表一律断连，播放器根本出不了流。
# 上游清单仍在下发这批地址，故在「探测」与「合并总表」两处都拦掉，防止死源回流。
DEAD_SCENERY_RE = re.compile(r"/gc/[^\s]*\.m3u8", re.I)
SCENERY_FILE = ROOT / "data" / "scenery.json"

RAW = "https://raw.githubusercontent.com"

# out: 输出文件名；upstream: 上游列表（None 表示用仓库内已有文件）
SOURCES = [
    {
        "label": "Kimentanm（原有·去死链）",
        "out": "iptv.m3u",
        "upstream": [f"{RAW}/Kimentanm/aptv/master/m3u/iptv.m3u"],
    },
    {
        "label": "develop202（原有·去死链）",
        "out": "interface.txt",
        "upstream": None,
    },
    {
        "label": "高清综合·vbskycn",
        "out": "live-vbskycn.m3u",
        "upstream": [f"{RAW}/vbskycn/iptv/master/tv/iptv4.m3u"],
    },
    {
        "label": "央视卫视HD·bestfan",
        "out": "live-bestfan.m3u",
        "upstream": [f"{RAW}/best-fan/iptv-sources/master/cn_all.m3u8"],
    },
    {
        "label": "全网聚合·高清（mzky + kaige 实测可达）",
        "out": "live-kaige.m3u",
        "upstream": [
            f"{RAW}/mzky/checklist/master/itvlist.m3u",
            f"{RAW}/kaige-cai/live/main/live.m3u",
        ],
    },
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def parse_m3u(text):
    """返回 [(extinf行, url)]，兼容每频道单线路与同名多线路。"""
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            cur = line
        elif line.startswith("#"):
            continue
        elif cur is not None:
            out.append((cur, line))
            cur = None
    return out


def normalize(url):
    """URL 含中文时按 RFC 编码，否则 urllib 会抛 UnicodeEncodeError。"""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path),
         urllib.parse.quote(p.query, safe="=&?"), "")
    )


def probe(url):
    """返回是否保留。403/405 保留（防盗链，播放器带 Referer 可播）。"""
    if DEAD_SCENERY_RE.search(url):
        return False  # 老景区 CDN 已停服，主列表能开也拿不到分片
    if not url.startswith(("http://", "https://")):
        return True  # rtp/igmp 等组播源，无法探测，保留
    try:
        req = urllib.request.Request(
            normalize(url), headers={"User-Agent": UA, "Range": "bytes=0-1024"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            r.read(256)
        return True
    except urllib.error.HTTPError as e:
        # 404/410/5xx 视为死链；403/405 常见于防盗链，播放器可带 Referer 播放
        return e.code not in (404, 410) and e.code < 500
    except Exception:
        return False  # 连接失败/超时/断开 -> 死链


def make_header(text):
    """沿用源文件的 #EXTM3U 属性（catchup / x-tvg-url 等），并确保 EPG 里含可用源。"""
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    if first.startswith("#EXTM3U"):
        if EPG not in first and 'x-tvg-url="' in first:
            first = first.replace('x-tvg-url="', f'x-tvg-url="{EPG},', 1)
        return first
    return f'#EXTM3U x-tvg-url="{EPG}"'


def collect(src):
    target = LIB / src["out"]
    if src["upstream"]:
        texts = [fetch(u) for u in src["upstream"]]
        text = "\n".join(texts)
        header = make_header(texts[0])
    else:
        bak = LIB / (src["out"] + ".bak")
        if not bak.exists():
            shutil.copy(target, bak)
        text = bak.read_text(encoding="utf-8", errors="ignore")
        header = make_header(text)

    channels = parse_m3u(text)
    # 去重：(extinf, url) 完全一致才丢，同名不同线路保留作为备用
    seen, uniq = set(), []
    for item in channels:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return target, header, uniq


def probe_many(urls, rounds=ROUNDS, workers=None):
    """多轮探测取并集：任一轮可达即保留，降低网络抖动造成的误杀。"""
    workers = workers or WORKERS
    urls = sorted(set(urls))
    verdict = {u: False for u in urls}
    for i in range(rounds):
        pending = [u for u, ok in verdict.items() if not ok]
        if not pending:
            break
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            res = dict(zip(pending, ex.map(probe, pending)))
        for u, ok in res.items():
            verdict[u] = verdict[u] or ok
        print(f"  第 {i + 1} 轮：本轮可达 {sum(res.values())}/{len(pending)}，"
              f"累计可达 {sum(verdict.values())}/{len(urls)}")
    return verdict


def main():
    print(f"直播源更新  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"探测并发={WORKERS} 超时={TIMEOUT}s 轮次={ROUNDS}  EPG={EPG}\n")

    # 汇总所有 URL 一次性探测，跨源复用结果
    data = []
    for src in SOURCES:
        try:
            target, header, channels = collect(src)
            data.append((src, target, header, channels))
            print(f"[拉取] {src['label']:38s} 原始 {len(channels):4d} 条")
        except Exception as e:
            print(f"[失败] {src['label']}: {type(e).__name__} {e}")

    all_urls = [u for _, _, _, chs in data for _, u in chs]
    print(f"\n开始探测 {len(set(all_urls))} 个唯一流地址 ...")
    results = probe_many(all_urls)
    print(f"探测完成：可达 {sum(results.values())} / {len(results)}\n")

    # 4K/8K 精选：从所有源里挑出标注超清的频道，单独多轮复测，只留实测可达的
    uhd = [(inf, u) for _, _, _, chs in data for inf, u in chs
           if re.search(r"4K|8K|UHD|2160", inf, re.I)]
    uhd_urls = [u for _, u in uhd]
    print(f"4K/8K 频道候选 {len(uhd)} 条，单独复测 ...")
    uhd_res = probe_many(uhd_urls, rounds=3)
    seen, uhd_kept = set(), []
    for inf, u in uhd:
        if uhd_res.get(u) and (inf, u) not in seen:
            seen.add((inf, u))
            uhd_kept.append((inf, u))
    data.append((
        {"label": "4K8K超清精选（实测可达）"},
        LIB / "live-4k.m3u",
        f'#EXTM3U x-tvg-url="{EPG}"',
        uhd_kept,
    ))
    for _, u in uhd_kept:
        results[u] = True

    written = []
    for src, target, header, channels in data:
        kept = [(inf, u) for inf, u in channels if results.get(u, True)]
        lines = [header]
        for inf, u in kept:
            lines.append(inf)
            lines.append(u)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append((target, kept))
        print(f"[写出] {str(target.relative_to(ROOT)):28s} "
              f"{len(channels):4d} -> {len(kept):4d} 条"
              f"（剔除 {len(channels) - len(kept)} 死链）")

    build_all(written)
    print("\n完成。播放列表已是自包含 m3u，不再依赖 #EXT-X-SUB-URL / gh.aptv.app 代理。")


# 部分精简版 TVBox 只加载 lives[0]，因此把全部可用频道合并成一张总表放在首位。
# 同名频道保留多条线路（播放器显示「线路 1/N」，可手动/自动换源），但限制上限避免刷屏。
MAX_LINES = 6
# 点播噪声 / 上游临时频道，不进直播列表
SKIP_NAME = ("春晚", "支持作者", "更新时间", "更新日期", "测试")

# 上游 6 个源对同一套频道有 6 套命名习惯（CCTV1 / CCTV1综合 / CCTV-1 (720p) /
# CCTV13新闻 / CCTV-4 中文国际 ...）。只按字面去重会把它们当成不同频道，
# 所以合并前必须先归一化成同一个名字，TVBox 才会收成「线路 1/N」。
CCTV_RE = re.compile(r"(?:CCTV|央视|中央)[\s\-_]*(\d{1,2})\s*([+＋])?", re.I)
UHD_RE = re.compile(r"4K|8K|UHD|2160", re.I)
# 画质/清晰度后缀（4K/8K 除外，它们是独立频道，不剥）
NOISE_RE = re.compile(
    r"[\s\-_()（）\[\]]*(?:超清|高清|标清|蓝光|流畅|频道|HD|FHD|\d{3,4}[PIpi])"
    r"[\s\-_()（）\[\]]*$", re.I
)
ALIAS = {
    "福建东南卫视": "东南卫视",
    "凤凰卫视中文": "凤凰卫视中文台",
}
# 上游会把构建时间戳也写成一条「频道」
DATE_RE = re.compile(r"^[\d\s\-:./]+$")


def normalize_name(name):
    """把同一频道的上游别名收成规范名，并去掉画质后缀。"""
    # 上游偶尔把两个台名用竖线拼在一起（CBS News | CBSN Pittsburgh），取第一段
    n = re.split(r"\s*\|\s*", name.strip())[0].strip()
    m = CCTV_RE.search(n)
    if m:
        # 央视统一成 CCTV1..CCTV17 / CCTV5+ / CCTV4K 这类编号名
        uhd = ""
        u = UHD_RE.search(n)
        if u:
            uhd = "4K" if u.group(0).upper() in ("UHD", "2160") else u.group(0).upper()
        return f"CCTV{int(m.group(1))}{'+' if m.group(2) else ''}{uhd}"
    if UHD_RE.search(n):
        return n  # 4K/8K 是独立频道，别和同名的普通频道并掉
    while True:
        stripped = NOISE_RE.sub("", n).strip()
        if stripped == n:
            break
        n = stripped
    return ALIAS.get(n, n) or name.strip()


def channel_sort_key(item):
    """分组内排序：CCTV 按数字自然序（CCTV1, CCTV2 ... 而不是 CCTV1, CCTV10）。"""
    name, group = item
    gi = GROUP_ORDER.index(group)
    m = re.fullmatch(r"CCTV(\d{1,2})(\+)?(4K|8K)?", name)
    if m:
        return (gi, 0, int(m.group(1)), m.group(2) or "", m.group(3) or "")
    return (gi, 1, 0, "", name)

# 只重建总表时读取的成品播放列表（顺序即线路优先级）
ALL_INPUTS = [
    "iptv.m3u",
    "interface.txt",
    "live-vbskycn.m3u",
    "live-bestfan.m3u",
    "live-kaige.m3u",
    "live-4k.m3u",
]

GROUP_RULES = [
    # 只认明确的 4K/8K，避免「XX超清」这类仅高清的频道混进来
    ("4K超清", r"4K|8K|UHD|2160|4K8K"),
    ("央视频道", r"CCTV|CGTN|央视|央视频道"),
    ("卫视频道", r"卫视"),
    ("体育频道", r"体育|足球|篮球"),
    ("少儿频道", r"少儿|卡通|动画"),
    ("影视频道", r"电影|影视|剧场"),
    ("纪录频道", r"纪录|科教"),
    ("音乐频道", r"音乐"),
    # 地方台常叫「XX新闻综合」，不能按「新闻」归类，故只认明确的地区/地方字样
    ("地方频道", r"地区|地方|新闻综合|广播电视台"),
]
GROUP_ORDER = [g for g, _ in GROUP_RULES] + [
    "港澳台频道", "国外频道", "风景慢直播", "其他频道",
]

# 「其他频道」原本塞了 188 个来路各异的台，按地域二次归类。
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# 中国香港 / 中国澳门 / 中国台湾地区频道，单独成组，不并入「国外频道」
HMT_RE = re.compile(
    r"凤凰|TVB|翡翠|明珠|亚视|亚洲电视|香港|澳门|台湾|台视|中视|华视|中天|"
    r"东森|三立|民视|非凡|壹电视|TVBS|纬来|年代|澳亚|ViuTV|HOY|星河|无线|"
    r"人间卫视|BLTV", re.I
)
FOREIGN_RE = re.compile(
    r"^(?:俄|韩|日|美|英|法|德|泰|新|印|意|半岛|阿拉伯)[·・:：]|"
    r"^(?:日本|韩国|美国|俄罗斯|泰国|半岛|亚洲新闻)", re.I
)
FOREIGN_HOST_RE = re.compile(r"\.kr$|\.jp$|cloudfront\.net|ebs\.co\.kr", re.I)
# 防御：万一上游又混入 /gc/ 景区源（现已在 build_all 中统一剔除），仍单列不淹没地方台。
# 当前「风景慢直播」分组由 data/scenery.json 注入，见 load_scenery()。
SCENERY_URL_RE = re.compile(r"/gc/.*contentid=2820180516001", re.I)


def refine_group(name, url):
    """把散落在「其他频道」的条目按地域二次归类。"""
    if SCENERY_URL_RE.search(url):
        return "风景慢直播"
    if HMT_RE.search(name):
        return "港澳台频道"
    host = urllib.parse.urlsplit(url).netloc
    if (FOREIGN_RE.search(name) or FOREIGN_HOST_RE.search(host)
            or not CJK_RE.search(name)):
        return "国外频道"
    # 剩下的中文台名都是国内地方台 / 专业频道
    return "地方频道"


def classify(inf, name):
    # 4K/8K 一律归到「4K超清」，不受上游 group-title 影响
    # （否则「北京卫视4K」会被上游标成卫视频道，和另外几个 4K 分开）
    if UHD_RE.search(name):
        return "4K超清"
    # 港澳台地区频道全局归组，不受上游 group-title 影响；且不并入「国外频道」
    if HMT_RE.search(name):
        return "港澳台频道"
    # 优先沿用上游 group-title，映射不到再按频道名判断
    m = re.search(r'group-title="([^"]*)"', inf)
    original = m.group(1) if m else ""
    for text in (original, name):
        for group, pattern in GROUP_RULES:
            if re.search(pattern, text, re.I):
                return group
    return "其他频道"


# 同一条流在不同上游被标成点播/占位内容（春晚录像、构建时间戳）时，
# 它根本不是这个频道的直播，放进正规频道就表现为「串台」。
NOISE_MARK_RE = re.compile(r"春晚|更新日期|更新时间|支持作者|测试|^\d{4}[-/.]\d", re.I)
CCTV_URL_RE = re.compile(r"cctv[-_ ]?(\d{1,2})", re.I)
LOGO_BASE = "https://epg.112114.xyz/logo/"
LOGO_NAMES = LIB / "logo-names.json"


def build_votes(written):
    """url -> Counter(归一化频道名)：看同一条流在各上游被标成什么，用于裁决串台。"""
    votes = collections.defaultdict(collections.Counter)
    for _, kept in written:
        for inf, url in kept:
            votes[url][normalize_name(inf.rsplit(",", 1)[-1].strip())] += 1
    return votes


def build_id_votes(written):
    """IPTV 数字编号 -> Counter(频道名)，用于识别编号被上游标错的流。

    例如 1030_1 在多数上游是「重庆卫视」、只有一处被标成 CCTV5+，
    那条流就不该进 CCTV5+ 的线路。
    """
    votes = collections.defaultdict(collections.Counter)
    for _, kept in written:
        for inf, url in kept:
            m = re.search(r"/tsfile/live/(\d{4})_\d+\.m3u8", url)
            if m:
                votes[m.group(1)][normalize_name(inf.rsplit(",", 1)[-1].strip())] += 1
    return votes


def line_trust(name, url, votes, id_votes):
    """线路裁决：噪声流、上游标注分歧、URL 台号不符、编号标错，一律不采用。"""
    v = votes.get(url, {})
    if any(NOISE_MARK_RE.search(k) for k in v):
        return False
    real = {k: c for k, c in v.items() if not NOISE_MARK_RE.search(k)}
    if real:
        top = max(real.values())
        tops = [k for k, c in real.items() if c == top]
        # 只在「当前标注严格少于唯一多数票」时剔除。平票时保留两边归属：
        # 地方台常有同流异名，若平票也全剔，会把整条频道的唯一线路抹掉。
        if len(tops) == 1 and real.get(name, 0) < top:
            return False
    # URL 里写死的 cctvN 必须和目标频道号一致
    m = re.fullmatch(r"CCTV(\d{1,2})(\+)?(4K|8K)?", name)
    if m:
        num = int(m.group(1))
        for hit in CCTV_URL_RE.finditer(url):
            if int(hit.group(1)) != num:
                return False
        # CCTV5+ 里不能混入纯 CCTV5 的流地址
        if m.group(2) and re.search(r"cctv5(?!plus|p\b|\+)", url, re.I):
            return False
    # 流编号在多个上游被一致地标成另一个频道，当前标注只是少数票 -> 剔除。
    # 仅对央视系列生效：地方台共用同一批 IPTV 编号，各运营商含义完全不同，
    # 全局裁决会把大量地方频道的唯一线路误删。
    mid = re.search(r"/tsfile/live/(\d{4})_\d+\.m3u8", url)
    if mid and name.startswith("CCTV"):
        iv = id_votes.get(mid.group(1), {})
        if iv:
            top = max(iv.values())
            tops = [k for k, c in iv.items() if c == top]
            if len(tops) == 1 and top >= 2 and iv.get(name, 0) < top:
                return False
    return True


def load_logo_names():
    """读取已探测过的台标名单（lib/logo-names.json），避免每次重建都打网络。"""
    if not LOGO_NAMES.exists():
        return set()
    try:
        return set(json.loads(LOGO_NAMES.read_text(encoding="utf-8")))
    except Exception:
        return set()


def probe_logo_names(names):
    """探测 epg.112114.xyz 台标库里真实存在哪些频道的 logo。"""
    hdr = {"User-Agent": "Mozilla/5.0 (Linux; Android 11) okHttp/Mod-1.5.0.0"}

    def chk(n):
        u = LOGO_BASE + urllib.parse.quote(n, safe="") + ".png"
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=8)
            r.read(32)
            return n, (r.status == 200
                       and r.headers.get("Content-Type", "").startswith("image/"))
        except Exception:
            return n, False

    names = sorted(set(names))
    res = {}
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for n, ok in ex.map(chk, names):
            res[n] = ok
    # 失败的重试一轮，避免网络抖动误判
    miss = [n for n, ok in res.items() if not ok]
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for n, ok in ex.map(chk, miss):
            res[n] = ok
    return sorted(n for n, ok in res.items() if ok)


def refresh_logos():
    """重新探测台标覆盖，写回 lib/logo-names.json。"""
    path = LIB / "live-all.m3u"
    if not path.exists():
        print("[跳过] 尚无 lib/live-all.m3u，请先重建总表")
        return
    names = {l.rsplit(",", 1)[-1].strip()
             for l in path.read_text(encoding="utf-8", errors="ignore").splitlines()
             if l.startswith("#EXTINF")}
    hits = probe_logo_names(names)
    LOGO_NAMES.write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[台标] 探测 {len(names)} 个频道，{len(hits)} 个有台标 -> {LOGO_NAMES.name}")


def load_scenery():
    """读取实测可播的风景慢直播频道；文件缺失时不影响其余频道生成。"""
    if not SCENERY_FILE.exists():
        print(f"[跳过] 缺少 {SCENERY_FILE.relative_to(ROOT)}，风景慢直播分组为空")
        return []
    try:
        data = json.loads(SCENERY_FILE.read_text(encoding="utf-8"))
        return [c for c in data.get("channels", [])
                if c.get("name") and c.get("urls")]
    except Exception as e:
        print(f"[警告] 读取风景源失败：{e}")
        return []


def refresh_scenery():
    """重新探测风景源线路（房间下播/代理调整会 404），写回 data/scenery.json。

    代理对高并发会限流，故低并发 + 两轮取并集，避免把好线路误杀。
    """
    if not SCENERY_FILE.exists():
        print("[跳过] 缺少 data/scenery.json")
        return
    data = json.loads(SCENERY_FILE.read_text(encoding="utf-8"))
    channels = data.get("channels", [])
    urls = sorted({u for c in channels for u in c.get("urls", [])})
    print(f"[风景源] 低并发探测 {len(urls)} 条线路 ...")
    verdict = probe_many(urls, rounds=2, workers=8)
    kept_channels, dead = [], 0
    for c in channels:
        kept = [u for u in c.get("urls", []) if verdict.get(u)]
        dead += len(c.get("urls", [])) - len(kept)
        if kept:
            kept_channels.append({"name": c["name"], "urls": kept})
    data["channels"] = kept_channels
    data["updated"] = datetime.now().strftime("%Y-%m-%d")
    SCENERY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[风景源] 保留 {len(kept_channels)} 个频道 / "
          f"{sum(len(c['urls']) for c in kept_channels)} 条线路，剔除 {dead} 条失效线路")


def build_all(written):
    """合并各源、归一化频道名、统一分组，生成 lib/live-all.m3u。

    归一化后的「频道名」是唯一键：同一套频道的不同上游别名会收成一个频道，
    多路流地址变成该频道的「线路 1/N」；https 线路优先，最多 MAX_LINES 条。
    """
    votes = build_votes(written)
    id_votes = build_id_votes(written)
    logo_names = load_logo_names()
    dropped = collections.Counter()
    buckets = {}
    for _, kept in written:
        for inf, url in kept:
            # 手机/盒子端放不了 rtmp/组播，这类地址又无法探测，直接丢弃
            if not url.startswith(("http://", "https://")):
                continue
            # 上游清单仍在下发已停服的「直播中国」景区摄像头地址
            if DEAD_SCENERY_RE.search(url):
                dropped["老景区停服源"] += 1
                continue
            raw = inf.rsplit(",", 1)[-1].strip()
            if not raw or DATE_RE.fullmatch(raw) or any(k in raw for k in SKIP_NAME):
                continue
            name = normalize_name(raw)
            if not name:
                continue
            # 上游标错、点播占位流、URL 台号不符 -> 不进这个频道的线路
            if not line_trust(name, url, votes, id_votes):
                dropped["串台/歧义流"] += 1
                continue
            if name not in buckets:
                group = classify(inf, name)
                if group == "其他频道":
                    group = refine_group(name, url)
                buckets[name] = {"group": group, "urls": []}
            item = buckets[name]
            if url not in item["urls"]:
                item["urls"].append(url)

    # 清洗后可能整条频道都没有可信线路了，去掉避免出现空频道
    buckets = {n: v for n, v in buckets.items() if v["urls"]}
    # 注入实测可播的风景慢直播频道：多条代理地址就是 TVBox 的「线路 1/N」
    scenery = load_scenery()
    for ch in scenery:
        buckets[ch["name"]] = {"group": "风景慢直播", "urls": list(ch["urls"])}
    # 收尾：上游标注越一致越靠前，其次 https 优先（Android 9+ 默认禁明文）
    for name, item in buckets.items():
        item["urls"].sort(key=lambda u: (
            -votes.get(u, {}).get(name, 0),
            0 if u.startswith("https://") else 1,
        ))
        del item["urls"][MAX_LINES:]

    lines = [f'#EXTM3U x-tvg-url="{EPG}"']
    total = logo_count = 0
    for name, item in sorted(
        ((n, v) for n, v in buckets.items()),
        key=lambda pair: channel_sort_key((pair[0], pair[1]["group"])),
    ):
        group = item["group"]
        # 只为台标库里确实存在的频道写 tvg-logo，其余交给 lives 的 logo 模板兜底
        logo = ""
        if name in logo_names:
            logo = f' tvg-logo="{LOGO_BASE}{urllib.parse.quote(name, safe="")}.png"'
            logo_count += 1
        # 同名频道保持"名字完全一致"，TVBox 会自动合并成「线路1/N」供换源；
        # 若在此加线路后缀，反而会拆成 N 个独立频道刷屏。
        for url in item["urls"]:
            lines.append(f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" '
                         f'group-title="{group}"{logo},{name}')
            lines.append(url)
            total += 1
    target = LIB / "live-all.m3u"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    groups = collections.Counter(v["group"] for v in buckets.values())
    print(f"[总表] {str(target.relative_to(ROOT)):28s} "
          f"{total:4d} 条 / {len(buckets)} 个频道 / {len(groups)} 个分组")
    print("        " + "  ".join(f"{g}:{n}" for g, n in
                                sorted(groups.items(), key=lambda x: GROUP_ORDER.index(x[0]))))
    print(f"[台标] {logo_count}/{len(buckets)} 个频道写入 tvg-logo")
    if dropped:
        print(f"[清洗] {dict(dropped)}")
    return total


def rebuild_all():
    """不跑网络探测，直接由仓库内已有的成品播放列表重建总表。"""
    written = []
    for name in ALL_INPUTS:
        path = LIB / name
        if not path.exists():
            print(f"[跳过] 缺少 {name}")
            continue
        kept = parse_m3u(path.read_text(encoding="utf-8", errors="ignore"))
        written.append((path, kept))
        print(f"[读取] {name:26s} {len(kept):4d} 条")
    build_all(written)
    print("完成。若需重新探测上游死链，请不带参数运行本脚本。")


if __name__ == "__main__":
    if "--refresh-scenery" in sys.argv:
        refresh_scenery()
        sys.exit(rebuild_all())
    if "--refresh-logo" in sys.argv:
        refresh_logos()
    if "--all-only" in sys.argv or "--refresh-logo" in sys.argv:
        sys.exit(rebuild_all())
    sys.exit(main())
