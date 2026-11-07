# tvbox

[![Stars](https://img.shields.io/github/stars/Inliang/tvbox?style=flat-square)](https://github.com/Inliang/tvbox/stargazers)
[![Forks](https://img.shields.io/github/forks/Inliang/tvbox?style=flat-square)](https://github.com/Inliang/tvbox/network/members)
[![Watchers](https://img.shields.io/github/watchers/Inliang/tvbox?style=flat-square)](https://github.com/Inliang/tvbox/watchers)
[![Last commit](https://img.shields.io/github/last-commit/Inliang/tvbox?style=flat-square)](https://github.com/Inliang/tvbox/commits/main)
[![Pages](https://img.shields.io/badge/Pages-%E6%8E%A5%E5%8F%A3%E5%9C%B0%E5%9D%80%E5%BA%93-blue?style=flat-square)](https://inliang.github.io/tvbox/)

给 TVBox / 影视仓 / OK 影视 用的**配置文件**：本仓库只提供配置地址，不提供任何影片，也不提供播放功能。如果喜欢，请 Fork 自用。

配置模板借鉴 [饭肥猫](http://肥猫.com) 等公开接口，在此致谢。

**目录**：[快速开始](#快速开始) · [配置地址](#配置地址) · [直播频道](#直播频道) · [节目预告](#节目预告) · [常见问题](#常见问题) · [接口地址库](#接口地址库网页版) · [相关资源](#相关资源) · [进阶](#进阶维护与原理) · [免责声明](#免责声明)

---

## 快速开始

1. **装客户端**：手机或电视盒子安装 TVBox 系 App，推荐 OK 影视（见 [APP 推荐](#app-推荐)）。
2. **填配置地址**：打开 App →「设置」→「配置地址 / 接口地址」→ 粘贴下面任一网址 → 确定。
3. **重启 App**：首页出现点播站点，切到「直播」页即可看电视。

> 网址要从 `https://` 开始完整复制。国内网络若打不开，可试文末的 [GitHub 代理](#代理与备用接口)。

## 配置地址

| 版本 | 点播站点 | 适合谁 |
| --- | ---: | --- |
| **主配置（推荐）** | 135 | 日常使用，只保留已验证可用的站点 |
| 扩展配置 | 517 | 想"全都要"，能接受首次加载慢 |

```
主配置：https://raw.githubusercontent.com/Inliang/tvbox/main/zijian.json
扩展版：https://raw.githubusercontent.com/Inliang/tvbox/main/zijian-full.json
```

> 扩展版里有不少加密站点，客户端要逐个解密才能加载，**首次会明显变慢**；日常用主配置即可。

---

## 直播频道

两个配置内置同一套直播源，共 7 个，第一个「**全部频道·聚合**」是整理好的总表：
**914 条线路 / 546 个频道 / 12 个分组 / 280 个频道带台标**。

| 分组 | 频道数 | 内容 |
| --- | ---: | --- |
| 央视频道 | 26 | `CCTV1`–`CCTV17`、`CCTV5+`、`CETV1`、CGTN 系列 |
| 卫视频道 | 41 | 各省级卫视 |
| 4K超清 | 4 | 明确的 4K / 8K 频道 |
| 地方频道 | 340 | 国内各省市地方台与专业频道 |
| 港澳台频道 | 6 | **中国香港、中国澳门、中国台湾地区**频道（凤凰、TVB、翡翠台、人间卫视等） |
| 国外频道 | 76 | 欧美、日韩、俄罗斯、泰国、半岛等境外电视台 |
| 专业频道（体育 / 少儿 / 影视 / 纪录 / 音乐） | 34 | — |
| 风景慢直播 | 19 | 风景 / 星空 / 城市实景慢直播，不是电视频道，可整组跳过 |

几点说明：

- 央视统一命名为 `CCTV1`…`CCTV17`（`CCTV16` 奥林匹克、`CCTV17` 农业农村都是真实在播频道），按数字顺序排列，不再出现「CCTV1综合」「CCTV-1 (720p)」这类重复项。
- 同一个频道下可能有多条**线路**（最多 6 条）。播放卡住或画面不对时，切换线路即可。
- **「风景慢直播」已换成实测能出画面的直播间**：原来那批「直播中国」景区摄像头整批停服了（看着能连上，实际拉不到画面），现在改成 19 个风景 / 星空 / 城市实景频道，每个配 1–4 条不同来源的线路。直播间偶尔会下播，换一条线路或过一会再看即可。
- **「港澳台频道」是中国地区频道**，单独成组，不与「国外频道」混在一起。
- 部分客户端只认第一个直播源，所以聚合总表固定排在第一位；其余 6 个分源保留上游原始命名，方便对照。

> 直播流由第三方提供、会随时失效，仓库会定期刷新。维护者可用 `python scripts/update_lives.py` 重新探测，用 `python scripts/update_lives.py --refresh-scenery` 单独刷新风景直播线路。

---

## 节目预告

7 个直播源现在都带**节目单（EPG）**：进入直播、选中频道后，客户端会显示当前正在播什么、接下来播什么。

| 分组 | 预告情况 |
| --- | --- |
| 央视频道 / 卫视频道 / 4K超清 | 基本都有完整预告（例如 CCTV1 今天 33 条节目） |
| 少儿 / 纪录 / 影视 / 体育 | 多数有 |
| 地方频道 / 港澳台频道 / 国外频道 / 风景慢直播 | 上游多数没有节目单数据，会显示「精彩节目」占位 |

台标（频道图标）走同一套服务，命中的频道会自动显示。节目单内容、更新时间由第三方 EPG 服务决定，本仓库只做接入。

> 看不到节目单时，先确认用的是「**全部频道·聚合**」这个直播源；部分精简客户端只加载第一个源。

---

## 常见问题

| 现象 | 怎么办 |
| --- | --- |
| 提示「获取配置失败」 | 检查网址是否完整复制、能否访问 `raw.githubusercontent.com`；国内网络可改用文末 GitHub 代理 |
| 刚更新，看到的还是旧内容 | GitHub / CDN 有缓存，等 5～10 分钟；也可在地址末尾加 `?v=2` 强制刷新 |
| 直播只显示几个分组 | 客户端只读第一个直播源。重新导入一次配置即可（总表已在第一位） |
| 看不到节目预告 / 只显示「精彩节目」 | 节目单由第三方提供，地方台、境外台、风景慢直播上游本就没数据；央视卫视应有。若连央视都是占位，见文末进阶区的 EPG 写法 |
| 频道能显示，点开一直转圈 | 约七成是 `http://` 明文流，Android 9+ 默认禁止明文；换 OK 影视 / FongMi 系客户端，或切换线路 |
| 某个频道点开是别的台 | 已对上游错标流做过清洗；若仍遇到，请提 Issue 说明**频道名 + 第几条线路** |
| 风景慢直播转圈 / 黑屏 | 直播间临时下播或第三方代理波动，先切「线路 2 / 3」；整组都不行时提 Issue，我会重跑 `--refresh-scenery` |
| 搜不到想看的片 | 配置只提供站点入口，内容由第三方决定；可试扩展配置，或在网页版接口库里找其他配置 |
| 想去掉风景慢直播 | 直接跳过「风景慢直播」分组即可；进阶改法见文末 |

---

## 接口地址库（网页版）

在线：**[inliang.github.io/tvbox](https://inliang.github.io/tvbox/)** —— 收录 39 个公开配置接口、517 个站点源，支持搜索、按状态筛选、一键复制。
本地：直接双击 `docs/index.html`，数据已内联，不用起服务器。

> 页面上的状态只是浏览器探测结果，**不能证明能搜到片**，请点「打开」自行验证。灰色的「无法预验证 / 无结论」也不等于失效。

---

## 相关资源

> 以下 APP 与配置清单整理自 [qist/tvbox](https://github.com/qist/tvbox)，版权归各自维护者所有；链接有效性由第三方决定，仅供学习与技术交流。

### APP 推荐

| 客户端 | 项目地址 | 特点 |
| --- | --- | --- |
| **OK 影视**（FongMi） | [FongMi/TV](https://github.com/FongMi/TV) | 直播多线路、自动换源、直播倍速、手机投屏 |
| q215613905 版 | [q215613905/TVBoxOS](https://github.com/q215613905/TVBoxOS) | 支持直播回放 |
| takagen99 版 | [takagen99/Box](https://github.com/takagen99/Box) | 支持直播回放，界面美观 |
| 皮皮虾版 | [发布频道](https://t.me/pipixiawerun) | 支持直播回放，支持弹幕 |
| 新版猫影视 | [社区复刻](https://github.com/mingjieyemen/CatVodOpen) | 界面简洁，支持多平台；原 `catvod/CatVodOpen` 已失效 |
| 手机版 | [XiaoRanLiu3119/TVBoxOS-Mobile](https://github.com/XiaoRanLiu3119/TVBoxOS-Mobile) | 竖屏 |
| 编译版 APK | [o0HalfLife0o/TVBoxOSC](https://github.com/o0HalfLife0o/TVBoxOSC) | q215613905 / takagen99 版编译产物 |

基础客户端：[TVBox](https://tvbox.clbug.com/)、影视仓。

### TVBox 各路大佬配置（排名不分先后）

| 维护者 | 配置地址 |
| --- | --- |
| 饭太硬 | `http://www.饭太硬.top/tv/` |
| okjack | `https://jihulab.com/okcaptain/kko/raw/main/ok.txt` |
| 王二小放牛娃 | `http://tvbox.王二小放牛娃.xyz` |
| 摸鱼儿 | `http://我不是.摸鱼儿.top` |
| 霜辉月明 py | `https://raw.githubusercontent.com/lm317379829/PyramidStore/pyramid/py.json` |
| 小米小爆脾气 | `http://xhww.fun/小米/DEMO.json` |
| 南风 | `https://agit.ai/Yoursmile7/TVBox/raw/branch/master/XC.json` |
| 神器 | `https://神器每日推送.tk/pz.json` |
| 巧技 | `http://pandown.pro/tvbox/tvbox.json` |
| Ray | `https://100km.top/0` |
| 俊于 | `http://home.jundie.top:81/top98.json` |
| 橘子柚 | `https://raw.githubusercontent.com/hackyjso/box/main/jzy.txt` |
| 电视 | `https://raw.githubusercontent.com/qist/tvbox/master/jsm.json` |

### 代理与备用接口

| 用途 | 地址 |
| --- | --- |
| GitHub 代理（择一使用） | `https://github.moeyy.xyz`、`https://mirror.ghproxy.com/`、`https://gh-proxy.com`、`https://ghproxy.net` |
| Cloudflare Pages 镜像 | `https://qist.wyfc.qzz.io/jsm.json` |
| 潇洒接口 | `https://raw.githubusercontent.com/qist/tvbox/master/xiaosa/api.json`（或 `https://qist.wyfc.qzz.io/xiaosa/api.json`） |
| 饭太硬接口 | `https://raw.githubusercontent.com/qist/tvbox/master/fty.json`（或 `https://qist.wyfc.qzz.io/fty.json`） |

### Star

[![Star History Chart](https://api.star-history.com/svg?repos=Inliang/tvbox&type=Timeline)](https://star-history.com/#Inliang/tvbox&Timeline)

> 图表由 [star-history.com](https://star-history.com) 生成，随仓库 Star 数自动更新。觉得有用，欢迎点个 Star。

---

## 进阶：维护与原理

<details>
<summary>面向想自己改配置的人（点开展开）</summary>

### 维护脚本

```bash
python scripts/extract.py --probe   # 拆解候选配置，五档分类 + 实测
python scripts/merge.py --dry-run   # 试算合并计划，不写文件
python scripts/merge.py             # 合并（自动备份到 data/backup/ + 校验门禁）
python scripts/build.py             # 重新生成页面数据并内联进 index.html
python scripts/validate.py          # 单独校验配置合法性
python scripts/catvod_check.py      # 模拟客户端反序列化，查整包加载失败的风险
python scripts/update_lives.py     # 拉上游 + 全量探测去死链，重写 lib 下各播放列表
python scripts/update_lives.py --all-only  # 只重建 live-all.m3u 总表，不跑网络探测
python scripts/update_lives.py --refresh-logo  # 重新探测台标覆盖并重建总表
python scripts/update_lives.py --refresh-scenery  # 重测风景直播线路并重建总表
```

`merge.py` 只重建 `sites` 数组、覆盖前备份、校验不过不写盘。`docs/data/*.json` 与 `docs/index.html` 的内联数据全部由 `build.py` 生成，**请勿手改**；构建方向是单向的：`data/exports/` → `build.py` → `docs/`。

### 数据是怎么筛的

从 2024 个公开接口里解析站点，按「能否在自己的配置里跑起来」分五档：A/B/C 合并，D（依赖本机文件或 `127.0.0.1`）与 E（类不存在、地址是相对路径等）拒绝。判定依据是仓库内 spider 的 42 个类，其中 37 个是可用的站点类。

一个容易忽略的事实：公开接口里有 **869 个站点引用了不存在的类**，它们从来就没能跑起来。把别人的 `csp_XXX` 抄进自己的配置，只要 spider 里没这个类，这个站就永远转圈，而且 TVBox 不会报错。

### 直播源是怎么生成的

`scripts/update_lives.py` 拉取 6 个上游 → 并发探测剔除死链（404/410/5xx/超时，403/405 保留）→ 频道名归一化（别名、画质后缀、编号自然排序）→ 按地域分流 → 线路串台清洗（点播占位流、IPTV 编号多数裁决、URL 台号校验；编号裁决只对央视系列生效，地方台共用编号但各运营商含义不同）→ 写出自包含 m3u，并为有台标的频道补 `tvg-logo`。

播放列表是内联完整频道的 m3u，不依赖 APTV 私有的远程订阅扩展，也不走代理。台标探测结果缓存在 `lib/logo-names.json`，`--refresh-logo` 可重新探测。

**风景慢直播单独存在 `data/scenery.json`**：老「直播中国」景区摄像头（`/gc/...contentid=...`）整批停服，主列表返回 200 但子列表断连，播放器拉不到画面，所以探测与合并两处都会拦掉这类地址；分组改由这个 JSON 注入。每个频道可配多条不同代理的线路，TVBox 会显示成「线路 1/N」。房间下播时线路会 404，`--refresh-scenery` 会低并发两轮复测并剔除失效线路。**不想看这一组**：把 `channels` 清空后跑 `--all-only` 即可（或直接跳过客户端里的分组）。

### 节目预告是怎么接的

`lives[].epg` 用 **DIYP 按频道名查询**接口 `https://epg.112114.xyz/?ch={name}`，客户端把 `{name}` 换成频道名即可拿到当天节目单；`logo` 同理用 `{name}` 取台标。7 条 `lives` 的 `epg` / `logo` 已全部统一，原本缺这两个字段的 `Kimentanm` 也补齐了，失效节点 `diyp5.112114.xyz` 一并换掉。

**为什么不用静态 `pp.xml`**：那是 XMLTV 格式，靠 `tvg-id` 精确匹配，而本仓库 546 个频道里只有 117 个（21%）能对上 EPG 的 channel id，EPG 里甚至没有 `CCTV1`。改用按名查询后，抽样 96 个频道有 43 个拿到真实节目（45%），央视 / 卫视 11/12；地方台、境外台、风景慢直播上游本来就没有节目数据，换任何源都一样。m3u 头的 `x-tvg-url` 仍保留 `pp.xml`，给支持 XMLTV 的播放器备用。

**为什么 URL 里不写 `&date={date}`**：社区常见写法是 `?ch={name}&date={date}`，但该接口只认 `2026-11-07` 这类带分隔符的日期；部分客户端会把 `{date}` 换成 `20261107`，接口就返回 12 条「精彩节目」占位。去掉日期参数后接口默认返回当天，兼容性最稳，代价是不能在客户端左右切换日期。想切日期可自行把 `epg` 改成：

```json
"epg": "https://epg.112114.xyz/?ch={name}&date={date}"
```

若改完反而全是占位，说明客户端传了紧凑日期，换回不带 `date` 的写法即可。备用域名 `https://epg.112114.eu.org/` 与主源同数据。

### 网页版为什么没有「确认失效」

只有明确连不上才判死，403、证书异常、响应截断、超时、加密源一律归入灰色。**误判一个站"死"的代价，远大于漏判它"活"**——用户看到红色就再也不会点它了。所以页面顶部数字会比 517 小一些，这不是缺陷。

### 已知问题

- `csp_Living`（游戏直播）、`csp_LiteApple`（苹果影视）的类不在 spider 里，这两个站必然转圈
- `lib/drpy2.min.js` 实际是一段跳转 HTML，依赖它的两个 js 源（体育直播、儿童启蒙）不可用
- 「米搜」「盘搜」指向 `127.0.0.1:9978`，只有本机能用
- 有 9 个第三方配置因带注释 / BOM / 多仓结构被严格解析器判为不可解析，但 TVBox 的宽容解析能加载；这只影响页面标签，不影响站点数据（这些配置的站点早已收录）
- 探测判据仍有偏差（如中文路径未编码会被误判失效），复核后不会增加可用站点，待 v2 改进
- 页面数据由 `build.py` 单向生成，`validate.py` 会把上述已知问题标记为 `[KNOWN]`，不阻塞站点合并

</details>

---

## 免责声明

本站仅收集、整理并测试网络上公开的 TVBox 接口配置文件地址，不提供、不存储、不分发任何音视频内容，不提供播放功能。
所有内容均由第三方站点提供，接口可用性由第三方决定，与本站无关。仅供学习与技术交流使用。
如权利人认为本站索引的地址侵犯其权益，可通过仓库 Issue 联系删除。
