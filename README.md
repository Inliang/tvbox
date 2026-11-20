# 📺 TVBox 配置合集

[![stars](https://img.shields.io/github/stars/Inliang/tvbox?style=flat-square&label=stars&labelColor=555&color=blue)](https://github.com/Inliang/tvbox/stargazers) [![forks](https://img.shields.io/github/forks/Inliang/tvbox?style=flat-square&label=forks&labelColor=555&color=blue)](https://github.com/Inliang/tvbox/network/members) [![issues](https://img.shields.io/badge/issues-0%20open-green?style=flat-square&labelColor=555)](https://github.com/Inliang/tvbox/issues) [![watchers](https://img.shields.io/github/watchers/Inliang/tvbox?style=flat-square&label=watchers&labelColor=555&color=blue)](https://github.com/Inliang/tvbox/watchers) [![contributors](https://img.shields.io/github/contributors/Inliang/tvbox?style=flat-square&label=contributors&labelColor=555&color=blue)](https://github.com/Inliang/tvbox/graphs/contributors) [![license](https://img.shields.io/github/license/Inliang/tvbox?style=flat-square&label=license&labelColor=555&color=blue)](https://github.com/Inliang/tvbox/blob/main/LICENSE) [![views](https://img.shields.io/badge/views-1908253-blue?style=flat-square&labelColor=555)](https://github.com/Inliang/tvbox)

给 TVBox / 影视仓 / OK 影视用的配置文件。只提供配置地址，不提供影片或播放功能。

## 配置地址

| 版本 | 站点数 | 直播分组 | 地址 |
| --- | ---: | ---: | --- |
| **主配置（推荐）** | 126 | 10 | https://raw.githubusercontent.com/Inliang/tvbox/main/zijian.json |
| 扩展配置 | 509 | 10 | https://raw.githubusercontent.com/Inliang/tvbox/main/zijian-full.json |

导入：App → 设置 → 配置地址 → 粘贴网址 → 重启。扩展版站点多、首次加载慢，日常用主配置即可。

网页版接口库：[inliang.github.io/tvbox](https://inliang.github.io/tvbox/)（48 个配置 / 585 个站点，支持搜索与一键复制）。本地也可直接打开 `docs/index.html`。

## 直播频道

主配置内置 10 个直播分组，默认第一组「流畅优选·测速」：

| 直播源 | 内容 |
| --- | --- |
| **流畅优选·测速** | 1492 个频道 / 1633 条线路，快线路排在前面 |
| 全部频道·聚合 | 1492 个频道 / 2258 条线路，最多 6 条线路/频道 |
| 其他分组 | Kimentanm、develop202、vbskycn、iptv-org·中国/港澳台、bestfan、全网聚合·高清、港澳台·精选、4K超清精选 |

- 直播源每 6 小时自动从 `vbskycn/iptv` 与 `iptv-org/iptv` 同步，并重新测速排序。
- 「（备用）」不单独成节目，同一频道的线路收在「线路 1/N」里。
- AKTV 已停服，不再接入；港台频道由「港澳台·精选」替代。中国香港、中国澳门、中国台湾地区频道归在「港澳台频道」。
- 公网真 4K 很少，标 4K 的频道码率可能偏低；测速是本机网络快照，换宽带/地区结果会变。

## 下载客户端

电视盒子/智能电视装「电视版」，手机/平板装「手机版」；近几年的设备基本都是 64 位，老盒子或安装报错再换 32 位。OK 影视直链始终指向官方最新版。

| 客户端 | 设备 | 64 位 | 32 位 |
| --- | --- | --- | --- |
| **OK 影视 / 影视仓**（推荐） | 电视版 | [下载 · 55 MB](https://github.com/FongMi/Release/releases/latest/download/leanback-arm64_v8a.apk) | [下载 · 47 MB](https://github.com/FongMi/Release/releases/latest/download/leanback-armeabi_v7a.apk) |
| **OK 影视 / 影视仓**（推荐） | 手机/平板 | [下载 · 55 MB](https://github.com/FongMi/Release/releases/latest/download/mobile-arm64_v8a.apk) | [下载 · 47 MB](https://github.com/FongMi/Release/releases/latest/download/mobile-armeabi_v7a.apk) |
| q215613905（Java） | 通用 | [下载 · 19 MB](https://github.com/j4Uq/TVBoxOSC/releases/download/20260914-1520/TVBox_q215613905_20260914-1520-java64.apk) | [下载 · 18 MB](https://github.com/j4Uq/TVBoxOSC/releases/download/20260914-1520/TVBox_q215613905_20260914-1520-java32.apk) |
| q215613905（Python） | 通用 | [下载 · 31 MB](https://github.com/j4Uq/TVBoxOSC/releases/download/20260914-1520/TVBox_q215613905_20260914-1520-python64.apk) | [下载 · 30 MB](https://github.com/j4Uq/TVBoxOSC/releases/download/20260914-1520/TVBox_q215613905_20260914-1520-python32.apk) |
| MBox（竖屏） | 手机/平板 | [下载 · 40 MB](https://github.com/XiaoRanLiu3119/TVBoxOS-Mobile/releases/download/v1.1.1/MBox_v1.1.1_release_20240828.apk)（通用） | 同左 |
| takagen99 | 通用 | [下载 · 7 MB](https://github.com/takagen99/Box/releases/download/v1.0.0-alpha/app-release.apk)（旧版通用） | 同左 |

其他客户端：[TVBox](https://tvbox.clbug.com/) · [q215613905/TVBoxOS](https://github.com/q215613905/TVBoxOS) · [takagen99/Box](https://github.com/takagen99/Box) · [猫影视复刻](https://github.com/mingjieyemen/CatVodOpen) · [皮皮虾](https://t.me/pipixiawerun)。

其他公开配置：[饭太硬](http://www.饭太硬.top/tv/) · [okjack](https://jihulab.com/okcaptain/kko/raw/main/ok.txt) · [王二小](http://tvbox.王二小放牛娃.xyz) · [摸鱼儿](http://我不是.摸鱼儿.top) · [南风](https://agit.ai/Yoursmile7/TVBox/raw/branch/master/XC.json) · [电视](https://raw.githubusercontent.com/qist/tvbox/master/jsm.json) · [俊于](http://home.jundie.top:81/top98.json) · [橘子柚](https://raw.githubusercontent.com/hackyjso/box/main/jzy.txt)。

GitHub 代理（择一）：`https://github.moeyy.xyz`、`https://mirror.ghproxy.com/`、`https://gh-proxy.com`、`https://ghproxy.net`。备用接口：[潇洒](https://raw.githubusercontent.com/qist/tvbox/master/xiaosa/api.json) · [饭太硬](https://raw.githubusercontent.com/qist/tvbox/master/fty.json)。

## 常见问题

- **获取配置失败**：确认网址从 `https://` 完整复制、能访问 `raw.githubusercontent.com`；国内网络可用上面的代理。
- **更新后还是旧内容**：GitHub / CDN 有缓存，等 5～10 分钟。
- **直播卡顿**：优先用「流畅优选·测速」；仍卡就切下一条线路。本机测速不代表你家宽带。
- **明文 http 流点不开**：Android 9+ 默认禁明文，换 OK 影视 / FongMi 系客户端。
- **看不到节目预告**：部分频道上游没有节目单，属正常。
- **想去掉风景慢直播**：在客户端跳过该分组即可。

## 维护

常用命令：

```bash
python scripts/catvod_check.py zijian.json zijian-full.json  # 校验配置
python scripts/update_lives.py --with-speed                  # 用测速结果重建直播列表
python scripts/build.py                                      # 重建官网数据与内联兜底
```

直播上游自动更新由 `.github/workflows/live-upstream.yml` 负责；`docs/` 由 `build.py` 单向生成，不要手改。站点筛选规则见 `scripts/`。

## 免责声明

本站仅收集、整理并测试公开 TVBox 配置地址，不提供、不存储、不分发任何音视频内容，也不提供播放功能。内容由第三方提供，仅供学习与技术交流。配置模板借鉴 [饭肥猫](http://肥猫.com) 等公开接口，在此致谢。如权利人认为索引地址侵犯权益，请通过 Issue 联系删除。

---

<p align="center">
  <a href="https://star-history.com/#Inliang/tvbox&Timeline"><img src="https://api.star-history.com/svg?repos=Inliang/tvbox&type=Timeline" alt="Star History" width="320"></a>
</p>
