# JMGO 兼容版

适配 **坚果 N1S 4K 高亮版（K310 / Android 11 / MT9667 / 32 位系统）** 的 TVBox 兼容客户端。

基于 [FongMi/TV](https://github.com/FongMi/TV) 5.8.7 官方发布包聚合而成，**未修改任何字节、沿用官方原签名**。
本仓库不重新编译，也不对安装包做任何二进制改造——只做「官方包校验 + 适配分发」。

> 本版目标是把「用一会儿随机闪退」变成可诊断、可对照、可归因，而不是宣称已彻底修好。
> 实测结论：在坚果 N1S 上，5.8.7 的 `leanback` 版 `armeabi-v7a`（32 位）包可装、可覆盖升级、较稳定；
> 但**不承诺**修复「切换播放源偶发退回首页」的历史问题。

---

## 下载与安装

1. 打开本仓库 **Releases**，下载名为 **`JMGO兼容版.apk`** 的文件（即官方 `leanback-armeabi_v7a` 包，仅改名）。
2. 通过以下任一方式安装到投影仪：
   - **ADB（推荐）**：`adb install -r JMGO兼容版.apk`
   - **U 盘 / 文件管理器**：把 apk 拷到 U 盘，在投影仪文件管理器里点击安装
3. 因为是官方原签名，可直接覆盖你现装的官方 TVBox，**不会丢失收藏、历史与播放进度**，无需先卸载。

> 若 Release 页面下载缓慢或超时，可能是单一网络出口对 GitHub 大文件间歇性 `504`；
> 可重试，或从官方源 `https://github.com/FongMi/Release/releases/download/5.8.7/` 取同名包对照。

## 这是哪个包 / 为什么是这一个

- 你的设备是**纯 32 位用户空间**（`ro.product.cpu.abilist=armeabi-v7a,armeabi`，无 64 位），
  因此只发 **`leanback` 版 `armeabi-v7a`**；`arm64_v8a` 两个包在你的设备上无法安装。
- `leanback` 是电视 / 遥控大屏版，适合投影仪；`mobile` 是手机触屏版，不发布。
- 包名 `com.fongmi.android.tv`，versionName `5.8.7`。

## 兼容性诚实说明

- 沿用官方原签名与官方 runtime 模块（Python / Node / QuickJS / MPV / BD-J / Thunder），
  功能与官方 5.8.7 一致，**不增不减**。
- 不承诺修复历史闪退；若仍出现，请按下方「仍闪退怎么办」提供机械证据。

## 自己核验（可选）

拿到 apk 后，若有 Android SDK，可复核签名证书指纹是否与官方 5.8.7 一致：

```bash
"$ANDROID_HOME/build-tools/34.0.0/apksigner" verify --print-certs JMGO兼容版.apk
```

## 回滚

- 每次构建生成一个独立 Release 标签 `jmgo-<run id>`，历史版本都保留，可随时取回上一版覆盖安装。
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

*本客户端由 GitHub Actions 自动聚合官方包并发布；源码重建路线因上游私有依赖已证伪，故不做重编译。*
