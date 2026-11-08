# 坚果 N1S 4K 兼容版 TVBox 客户端（jmgo）

面向 **坚果 N1S 4K 高亮版（国行 J31-8K2 / Android 11 / MT9667 / 3GB RAM）** 的
FongMi（蜂蜜影视）电视客户端分发包。

本仓库不产出源码编译产物：`.github/workflows/build-jmgo.yml` 自动聚合官方
`FongMi/Release` 5.8.7 的 4 个已编译完整包，逐包做机械校验，再作为 Artifact 与
GitHub Release 发布。上游 `FongMi/TV` 依赖从未开源的私有 media3 类，源码重建路线
已被证伪，因此这里提供的是**官方原包 + 可核验的交付链**。

> 目标是让「用一会儿随机闪退」变成可诊断、可对照、可归因，而不是宣称已彻底修好。
> 本版**不包含**任何二进制改造补丁。

---

## 拿到 APK

1. 打开本仓库 **Actions → `build-jmgo`**，取最新一次成功运行的 **Artifacts**，
   下载 `tvbox-jmgo-5.8.7.zip`。
2. 推送到 `main` 分支时，同一批文件会发布到 **Releases**，标签 `jmgo-<run id>`。
   每次运行一个标签，历史版本都保留，可直接取回上一版（见「回滚」）。

Artifact 内含 8 个文件：

| 文件 | 用途 |
| --- | --- |
| `tvbox-jmgo-leanback-arm64_v8a-5.8.7-<短哈希>.apk` | 电视端 64 位 |
| `tvbox-jmgo-leanback-armeabi_v7a-5.8.7-<短哈希>.apk` | 电视端 32 位 |
| `tvbox-jmgo-mobile-arm64_v8a-5.8.7-<短哈希>.apk` | 手机/触屏端 64 位（备选） |
| `tvbox-jmgo-mobile-armeabi_v7a-5.8.7-<短哈希>.apk` | 手机/触屏端 32 位（备选） |
| `SHA256SUMS.txt` | 4 个 APK 的 sha256 清单 |
| `build-info.json` | run id / commit sha / 上游 tag / 来源 URL / 每包 sha256、大小、ABI、原生签名指纹 |
| `upstream-verify.json` | 逐包机械校验结果（包名 / versionName / native-code / 签名指纹一致性） |
| `FIELD-TEST.md` | 实机取证与四包对照试装手册 |

## 包的来源与签名

4 个包全部来自固定地址 `https://github.com/FongMi/Release/releases/download/5.8.7/`，
文件名与官方 asset 逐字符一致，**沿用官方原签名**（未重新签名、未改动字节）。
包名 `com.fongmi.android.tv`，versionName `5.8.7`。

CI 实际下载走 GitHub API 的 release assets endpoint（同一 tag `5.8.7`、同一 4 个 asset、
同一份字节），因为官方下载页在连续下载多个大文件时会返回 `504`；溯源字段 `sourceUrl`
仍记录上面的官方 release 地址，产物字节与签名均不变。

因为签名与用户现装的官方 5.8.7 一致，可以直接 `adb install -r` 覆盖安装，
**不会丢失收藏、历史与播放进度**；不需要先卸载。

## 四包对照试装顺序（顺序仅为对照用，非优劣排序）

主通道把 4 个官方原签名包原样分发（不重新签名、不改动字节、零二进制改造），
**不预设任何一个「更稳」**。按以下顺序逐轮对照试装；顺序只是对照实验的记录编号，
不是优劣排序：

1. `tvbox-jmgo-leanback-arm64_v8a-5.8.7-<短哈希>.apk`（leanback / 64 位）
2. `tvbox-jmgo-leanback-armeabi_v7a-5.8.7-<短哈希>.apk`（leanback / 32 位）
3. `tvbox-jmgo-mobile-arm64_v8a-5.8.7-<短哈希>.apk`（mobile / 64 位）
4. `tvbox-jmgo-mobile-armeabi_v7a-5.8.7-<短哈希>.apk`（mobile / 32 位）

芯片是 64 位不代表系统就是 64 位。以上顺序基于 MT9667 为 64 位 SoC 的**工程推断，
未在这台设备上实测**，不构成「哪个包更稳」的结论，也不承诺修好闪退。请先执行
`adb shell getprop ro.product.cpu.abilist` 确认系统实际支持的 ABI，再按
`docs/FIELD-TEST.md` 第 3 节「四包对照试装」的判定表逐轮记录，以实机 `getprop`
与 `docs/ACCEPTANCE.md` AC-32 四包对照试装、AC-31 中性三组对照结果为准。

具体操作步骤、观测窗口与取证命令见 `docs/FIELD-TEST.md`。

## 机械校验做了什么

CI 对每个包依次断言，任一失败即终止构建，并在 `upstream-verify.json` 写明失败包名与原因：

- `unzip -t` ZIP 完整性；
- `aapt2` / `aapt dump badging` 提取 `package=com.fongmi.android.tv`、
  `versionName=5.8.7`、`native-code` 与文件名声明的 ABI 一致；
- `apksigner verify --print-certs` 记录签名证书 SHA-256 指纹，并断言 **4 包指纹完全一致**；
- 文件大小大于 30MB，且与已核实的官方 asset 精确字节数一致（防止下错版本或 asset 被替换）。

下载固定为 tag 5.8.7 的 4 个固定文件名，`set -e` 下任一 `curl` 失败即终止，
**不回退到其它版本、不静默跳过**。

## 自己核验产物

拿到 Artifact 后，在本机（需 Android SDK build-tools 34.0.0）复核：

```bash
cd tvbox-jmgo-5.8.7
sha256sum -c SHA256SUMS.txt

# 逐个核对签名证书指纹，应与 build-info.json 的 signingCertificateSha256 一致
for f in *.apk; do
  echo "== $f =="
  "$ANDROID_HOME/build-tools/34.0.0/apksigner" verify --print-certs "$f" \
    | grep 'SHA-256 digest'
done
```

`build-info.json` 里 `compatPatchStatus` 恒为 `not-applied`：本版**不含**二进制改造补丁。
`enable_compat_patch` 只是待 TECH-VERDICT 的实验通道占位，当前不启用，不执行重打包。

## 回滚

- 每次 push 到 `main` 生成一个独立 Release 标签 `jmgo-<run id>`，历史产物不会被覆盖；
  需要回退时直接下载上一版标签里的 4 个 APK 覆盖安装即可（同签名，无需卸载）。
- 上游 asset 固定在 tag `5.8.7`，文件内容不可变；即便本仓库 CI 出问题，也能从
  `FongMi/Release` 的该标签取回同一批官方包。
- 本仓库不产生需要迁移的数据库或服务端状态，回滚只涉及客户端 APK 覆盖安装。

## 仍闪退怎么办（取证反馈）

请提供机械证据，而不是「又崩了」：

```bash
adb logcat -b all -v threadtime > logcat.txt &
adb shell                       # 在投影仪上复现：连续播放/切源/前后台切换
# 复现后回到电脑 Ctrl-C 停止 logcat
adb shell ls /data/system/dropbox/ | grep -iE 'crash|anr|native_crash|tombstone'
adb bugreport bugreport.zip
```

把 `logcat.txt` 与上述目录里对应时间戳的文件一并反馈。请区分三类死因：
**低内存被系统回收（lmkd）** / **native 崩溃（tombstone）** / **Java 未捕获异常（CAOC 重启）**。
日志里的片名、源地址属于隐私，反馈前可自行脱敏。

## 目录

```
apps/jmgo/
  README.md                   本文
  SPEC.md                     规格契约（团队内部）
  build-contract.md           构建契约（Phase 2 技术契约）
  docs/ACCEPTANCE.md          验收标准 AC-01~AC-32（QA 维护，v1.1 顺延 AC-32）
  docs/PRD.md                 产品需求
  docs/FIELD-TEST.md          实机取证与四包对照试装手册（QA 维护）
  scripts/verify-upstream.py  机械校验 + 产物打包（纯 Python，可本地复现）
  keystore/                   上一路线遗留的固定密钥，保留备用，本轮不参与流水线
.github/workflows/build-jmgo.yml   聚合 / 校验 / 发布触发文件（仓库根，GitHub 只识别这里）
```

上一轮「从源码重建」所用的补丁与脚本已从流水线移除；`keystore/` 与
`scripts/gen-keystore.sh` 按团队裁决保留，但本轮不读取、不生成签名文件。
