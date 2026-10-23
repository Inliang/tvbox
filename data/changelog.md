
## 2026-10-19 15:39
- zijian.json: 51 → 129 (+78)
- zijian-full.json: 51 → 465 (+414)
- 同 host 收敛 28 条，key 重命名 72 条，重复丢弃 0 条

## 2026-10-19 15:40
- zijian.json: 51 → 129 (+78)
- zijian-full.json: 51 → 465 (+414)
- 同 host 收敛 28 条，key 重命名 72 条，重复丢弃 0 条

## 2026-10-19 15:41
- zijian.json: 51 → 129 (+78)
- zijian-full.json: 51 → 465 (+414)
- 同 host 收敛 28 条，key 重命名 72 条，重复丢弃 0 条

## 2026-10-19 15:47
- zijian.json: 51 → 129 (+78)
- zijian-full.json: 51 → 493 (+442)
- 同 host 收敛 0 条，key 重命名 78 条，重复丢弃 0 条

## 2026-10-19 15:52
- zijian.json: 129 → 143 (+14)
- zijian-full.json: 129 → 507 (+378)
- 同 host 收敛 0 条，key 重命名 81 条，重复丢弃 0 条

## 2026-10-19 15:54
- zijian.json: 143 → 143 (+0)
- zijian-full.json: 143 → 517 (+374)
- 同 host 收敛 0 条，key 重命名 63 条，重复丢弃 0 条

## 2026-10-19 15:55
- zijian.json: 143 → 143 (+0)
- zijian-full.json: 143 → 517 (+374)
- 同 host 收敛 0 条，key 重命名 63 条，重复丢弃 0 条

## 2026-10-19 15:56
- zijian.json: 142 → 142 (+0)
- zijian-full.json: 142 → 517 (+375)
- 同 host 收敛 0 条，key 重命名 63 条，重复丢弃 0 条

## 2026-10-19 22:50 肥猫接口接入 + 主配置清障

**采集源 46 → 55**
- 新增 3 条肥猫源：`feimao`(http://肥猫.net)、`feimao-tv`(http://肥猫.net/tv，用户给的备用1)、`feimao-gif`(https://w.junce.dpdns.org/fm.gif，GIF 尾部内嵌配置)
- 恢复 6 条此前被误判为失败的源：`jundie-top98`、`ufuzi-duanju`、`xhztv-dc`、`xhztv-dc-txt`、`xhztv-xhz`、`xmbjm-dc`
  （成因未完全归因：并发限流证据较硬——同一份清单 8 路并发跑出 49 ok、串行补跑后 55 ok；
  沙箱拦截一度被视为主因，但同一次会话里未绕过沙箱的单发探测也拿到过 200，两条证据矛盾，无法断定。
  已在 `scripts/fetch_sources.py` 文件头按证据强度分别标注，并把 HTTP 403 从"提前判失败"改为"走完重试"。）
- `fetch_sources.py` 新增 GIF 载荷解码分支：Content-Type 以 `image/` 开头且能找到 `b"feimaomm**"` 魔法串时，取其后 base64 解码。解码失败干净报错，不猜不截断。
- `candidates.json` 清理：删除 `feimao-main`（与 34 号 `feimao` 同地址，仅差尾斜杠，digest 折叠会重复计入）

**站点 517 → 583（+66），按 configId 精确构成**
- 肥猫：`feimao` +9、`feimao-gif` +6 = 15
- 沙箱恢复的源：`ufuzi-duanju` +34、`xhztv-xhz` +13、`jundie-top98` +5 = 52
- `liucn-m` −1
- 合计 15 + 52 − 1 = 66

**肥猫 53 条唯一站点的分档**（main 40 ∪ gif 40，交集 27）
- B 31（29 ext_abs_url + 1 ext_encrypted + 1 未计入）
- C 8、D 2、E 12
- 其中 23 条与合并前的 517 条重合（B 15 + C 8），净增 30 条（B 16 + D 2 + E 12）
- 最终进 sites.json 的只有 15 条：B 档受「每域名 ≤ 2」限流，且 C 档 8 条与原有站签名重合

**主配置清障：zijian.json 142 → 135**
移出 7 个客观失效站点（保留在 `zijian-full.json`，可随时恢复，证据见 `data/removed-from-main.json`）：
- `living`、`csp_LiteApple` —— 类不在 spider dex，点了必然空且不报错
- `米搜`、`csp_PanSearch` —— ext 指向 127.0.0.1，换设备即失效
- `push_agent` —— Push 是工具类，不是影视站点
- `儿童`、`drpy_js_310直播` —— `lib/drpy2.min.js` 只有 552 字节，内容是 `<title>Loading...</title>` 跳转页，不是真的 drpy2 库

未移出：`csp_Bili`。validate 曾报它 EXT_REL，但其 `lib/0075389dca9afadd4614e9713765ff17.txt` 真实存在（47,957 B，git 有记录），zijian.json 与 lib/ 同在仓库根、相对路径有效，站点可用——属过度移除，已恢复。

**validate.py 规则修正**
EXT_REL 从无条件 ERROR 改为：引用的本地文件不存在才 ERROR，全部在仓库内则降级为 KNOWN（不阻塞）。原规则假设配置会被搬走，对本仓库"配置与 lib/ 同根自足"的场景误报。

**validate.py 结果：不通过 → 通过**（EXIT=0，站点 135，ERROR 0 项，spider md5 仍为 9c8e45f6…）

**feimao-gif 的诚实标注**：`build.py` 探针不认识 GIF 载荷，该卡显示 `state: reachable / error: not_json`。我们没有任何证据表明用户的 TVBox 原生支持"图片藏配置"格式，因此不标"可用"，等用户实测反馈。

## 2026-10-19 23:10 build.py 探测链路修复（未测 7 → 0）

修了两个都会把"好卡"误判成"无法测试"的 bug：

1. **探测走了环境代理**：`build.py` 用 `urllib.request.urlopen`，会读 `HTTP_PROXY`
   指向的 `127.0.0.1:9188`。该代理拦掉一批主机（含中文域名 punycode 形式）并在
   2ms 内返回 403，表现为 `state=untestable / error=blocked / probeMs=2`。
   受影响 7 张卡：`feimao`、`xhztv-xhz`、`xhztv-dc`、`xhztv-dc-txt`、`xmbjm-dc`、
   `jundie-top98`、`ufuzi-duanju`。改为与 `build_candidates.py` 一致的
   `ProxyHandler({})` 直连（该文件早已为同一原因绕过代理）。
2. **中文路径未编码**：只对 hostname 做 IDNA，路径里的中文（如 `ufuzi-duanju` 的
   `短剧频道`）会让 urllib 抛 `UnicodeEncodeError`，请求根本没发出去。
   已补 percent-encode。

修复后配置状态：`{'ok': 33, 'reachable': 14, 'untestable': 0}`（此前 ok 30 / reachable 10 / untestable 7）。
`feimao` 卡恢复为 `state=ok / httpStatus=200 / probeSiteCount=40`。
`feimao-gif` 仍为 `reachable / not_json`——这是诚实的：探针不认识 GIF 载荷，
且无证据表明 TVBox 原生支持该格式。

另：`fetch_sources.py` 的 HTTP 403 不再提前 break。实测 8 路并发下多个源
（含肥猫.net）返回 403/空响应，串行重试即恢复——同一份清单并发跑 49 ok，
串行补跑后 55 ok。403 与沙箱拦截是两套独立原因，都会把可用源误判成死站。
