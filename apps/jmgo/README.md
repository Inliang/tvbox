# JMGO 兼容版

适配 **坚果 N1S 4K 高亮版（K310 / Android 11 / MT9667 / 32 位系统）** 的 TVBox 兼容客户端。

主推版本基于 [FongMi/TV](https://github.com/FongMi/TV) 5.8.7 官方发布包聚合而成，
**未修改任何字节、沿用官方原签名**，只做「官方包校验 + 适配分发」。
另有基于官方包反编译改造、重新签名的可选版本（见下方「版本一览」），均以独立 Release 发布，互不影响。

> 本版目标是把「用一会儿随机闪退」变成可诊断、可对照、可归因，而不是宣称已彻底修好。
> 实测结论：在坚果 N1S 上，5.8.7 的 `leanback` 版 `armeabi-v7a`（32 位）包可装、可覆盖升级、较稳定；
> 但**不承诺**修复「切换播放源偶发退回首页」的历史问题。

---

## 版本一览

所有版本都是**独立 Release / 独立 tag**，历史版本一律保留、不删除、不覆盖，随时可回退。

| 版本 | 文件 | 说明 |
| --- | --- | --- |
| **JMGO 兼容版**（主推·官方签名） | `JMGO-Compatible-5.8.7.apk` | 官方原包，字节与签名均未改，runtime 模块完整，可直接覆盖安装 |
| JMGO 兼容版（重签·桌面显示名） | `JMGO-Compatible-5.8.7-resigned.apk` | 仅改桌面显示名；包名 `com.jmgo.android.tv`；重签后 runtime 模块失效 |
| **JMGO 兼容版（首页横条按钮）** | `JMGO-Compatible-5.8.7-horizontal-ui.apk` + `JMGO-Compatible-5.8.7-horizontal-ui-arm64.apk` | 32 位 ARM（坚果 N1S 等 32 位盒子）与 64 位 ARM（电视盒子/投影仪及 MuMu 等不带 32 位 ARM 转译的模拟器）**合一发布**；首页 6 个功能按钮由正方形改横向长方形，详见下节；包名 `com.jmgo.android.tv`；重签，runtime 模块失效；**桌面显示名统一为「JMGO 兼容版」**（32/64 不区分） |
| JMGO 兼容版 5.8.7 官方包聚合 | 8 个资产 | 最早基线，含 4 个架构官方包与校验文件 |

## 首页横条按钮版 · 改动与安装注意

首页「历史 / 直播 / 搜索 / 推送 / 收藏 / 设置」这 6 个功能按钮，官方包用的是
`res/layout/adapter_func.xml`：**`100dp × 100dp` 正方形、`orientation="vertical"`（图标在上、文字在下）**。
本版改成 **`120dp × 56dp` 横向长方形、`orientation="horizontal"`（图标在左、文字在右）**，
垂直占用减少约 44%，给下方海报墙腾出空间。桌面显示名仍是 **JMGO 兼容版**，
包名已改为 **`com.jmgo.android.tv`**（与原官方 `com.fongmi.android.tv` 及任何其它 TVBox 包名不同，可直接共存）。

- ⚠️ **与官方签名版签名不同，不能覆盖安装**：请先卸载旧版再安装。
  卸载前记下你的「配置地址」，装好后重新导入一次；本地收藏 / 播放记录会被清空。
- ⚠️ 重签后官方 runtime 模块（Python / Node / QuickJS / MPV / BD-J / Thunder）
  签名校验不一致会失效；常规直链点播与直播播放不受影响。需要网盘 / Python 爬虫 / 蓝光 BD-J
  等完整功能，请使用主推的**官方签名版**。
- 包名 **`com.jmgo.android.tv`**，versionName `5.8.7`；布局改动已用 `aapt2 dump xmltree`
  从编译后的 APK 回读确认（`orientation=horizontal`、`120dp × 56dp`）。

### 在 MuMu 等 x86 模拟器里安装

32 位 ARM 包（`JMGO-Compatible-5.8.7-horizontal-ui.apk`）在只支持
`x86_64 / arm64-v8a / x86`、不带 `armeabi-v7a` 转译的模拟器上会报
`INSTALL_FAILED_NO_MATCHING_ABIS`（MuMu 界面显示「**错误码 -16**」），
**不是安装包损坏，重新下载没用**。这类环境请用 64 位版
`JMGO-Compatible-5.8.7-horizontal-ui-arm64.apk`。

新的重签改造版包名已改为 **`com.jmgo.android.tv`**，与原官方 `com.fongmi.android.tv`
及任何其它 TVBox 包名都**不同，可直接共存、互不覆盖**，不再需要为装它去卸载官方版。
但**如果你上一版装过旧的同名重签版（当时还是 `com.fongmi.android.tv`）**，需先卸载那个旧包，
否则会因签名不同而报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`。卸载会清空收藏与播放记录，
**先记下配置地址**：

```bash
adb connect 127.0.0.1:16384          # MuMu 12 默认 ADB 端口
adb uninstall com.fongmi.android.tv   # 仅当上一版是旧的重签版（包名仍为 com.fongmi.android.tv）时才需要
adb install JMGO-Compatible-5.8.7-horizontal-ui-arm64.apk
```

> 64 位版只用于模拟器 / 64 位设备；坚果 N1S 4K 是纯 32 位用户空间，
> 仍然必须用不带 `-arm64` 后缀的 32 位包。

## 下载与安装

1. 打开本仓库 **Releases**，下载名为 **`JMGO-Compatible-5.8.7.apk`** 的文件（即官方 `leanback-armeabi_v7a` 包，仅改名）。
2. 通过以下任一方式安装到投影仪：
   - **ADB（推荐）**：`adb install -r JMGO-Compatible-5.8.7.apk`
   - **U 盘 / 文件管理器**：把 apk 拷到 U 盘，在投影仪文件管理器里点击安装
3. 因为是官方原签名，可直接覆盖你现装的官方 TVBox，**不会丢失收藏、历史与播放进度**，无需先卸载。

> 若 Release 页面下载缓慢或超时，可能是单一网络出口对 GitHub 大文件间歇性 `504`；
> 可重试，或从官方源 `https://github.com/FongMi/Release/releases/download/5.8.7/` 取同名包对照。

## 这是哪个包 / 为什么是这一个

- 你的设备是**纯 32 位用户空间**（`ro.product.cpu.abilist=armeabi-v7a,armeabi`，无 64 位），
  因此主推 **`leanback` 版 `armeabi-v7a`**；`arm64_v8a` 包在你的设备上无法安装。
  版本一览里的「首页横条按钮」版同时含 32/64 位两个 APK（文件名以 `-arm64` 区分），64 位那份是给 MuMu 等模拟器做预览用的，**别装到 N1S 上**。
- `leanback` 是电视 / 遥控大屏版，适合投影仪；`mobile` 是手机触屏版，不发布。
- 包名：主推**官方签名版**为 `com.fongmi.android.tv`；改造/重签版（横条按钮版、重签版）已改为 `com.jmgo.android.tv`，详见上方版本一览。versionName 均为 `5.8.7`。

## 兼容性诚实说明

- 沿用官方原签名与官方 runtime 模块（Python / Node / QuickJS / MPV / BD-J / Thunder），
  功能与官方 5.8.7 一致，**不增不减**。
- 不承诺修复历史闪退；若仍出现，请按下方「仍闪退怎么办」提供机械证据。

## 自己核验（可选）

拿到 apk 后，若有 Android SDK，可复核签名证书指纹是否与官方 5.8.7 一致：

```bash
"$ANDROID_HOME/build-tools/34.0.0/apksigner" verify --print-certs JMGO-Compatible-5.8.7.apk
```

## 回滚

- 每次构建生成独立 Release 标签（`jmgo-<run id>` / `jmgo-resigned-<run id>` / `jmgo-ui-<run id>`），
  历史版本全部保留，可随时取回上一版。官方签名版（包名 `com.fongmi.android.tv`）与重签改造版
  （包名 `com.jmgo.android.tv`）包名不同、可直接共存；同一包名下的重签版之间可用 `adb install -r`
  升级（同把 jmgo 密钥），与官方版因签名不同仍需先卸载官方版。
- 上游固定在 FongMi/Release tag `5.8.7`，文件内容不可变；即便本仓库出问题，也能从官方源取回同一批包。

## 仍闪退怎么办（取证反馈）

请提供机械证据，而不是「又崩了」：

```bash
adb logcat -b all -v threadtime > logcat.txt &
adb shell   # 在投影仪上复现：连续播放 / 切源 / 前后台切换
# 复现后回到电脑 Ctrl-C 停止 logcat
adb bugreport bugreport.zip
```

把 `logcat.txt` 与 `bugreport.zip` 一并反馈。片名、源地址属于隐私，反馈前可自行脱敏。

---

*官方签名版由 GitHub Actions 自动聚合并发布；改造版用 apktool 反编译替换资源后重打包重签。
上游源码重建路线因私有依赖已证伪，故不做完整重编译。*
