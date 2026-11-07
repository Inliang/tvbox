# 坚果 N1S 4K 兼容版 TVBox 客户端（jmgo）

为 **坚果 N1S 4K 高亮版（型号 J31-8K2 / Android 11 / MT9667 / 3GB RAM）** 自动构建的
FongMi（蜂蜜影视）电视客户端。基于上游开源源码 `FongMi/TV` 固定版本，**推送即由 GitHub Actions
自动编译出可直接安装的 APK**，无需在本机配置 Android 开发环境。

> 这是「兼容性构建」，目标是**降低随机闪退的概率**，不是宣称已彻底修好。
> 若装上后仍会闪退，请按文末「仍闪退怎么办」采集证据反馈。

---

## 怎么拿到 APK

1. 打开本仓库 **Actions → `build-jmgo`**；
2. 最新一次运行（绿色对勾）底部 **Artifacts** 里下载 `tvbox-jmgo-apks.zip`，
   内含两个文件：
   - `tvbox-jmgo-leanback-arm64_v8a-5.8.7-<commit>.apk`（64 位）
   - `tvbox-jmgo-leanback-armeabi_v7a-5.8.7-<commit>.apk`（32 位）
3. 推送到 `main` 分支时，也会自动发布一份到仓库 **Releases**（标签 `jmgo-<编号>`）。

## 怎么安装

- **两个包分别试装**，哪个能装上且连续播放更稳，就用哪个。芯片是 64 位不代表系统就是
  64 位——这台投影仪上 32 位包往往更稳，所以**两个都构建、都提供**。
- 覆盖安装时请用**同一个签名**：本项目的签名密钥是固定的（见 `keystore/`），能直接覆盖旧版。
- 沿用仓库已有的 `zijian.json` 配置，无需重新导入源。

---

## 这个版本改了什么（相对上游 5.8.7）

所有改动都在 `patches/jmgo-v1/`，以最小、可逆、不破坏控制流的方式落地：

| 补丁 | 改动 | 目的 |
| --- | --- | --- |
| P001 | 运行时模块清单地址支持 Gradle 属性 / 环境变量注入 | 可注入可达镜像，不硬编码第三方代理 |
| P002 | 关闭 `BootReceiver` 与 `DLNARendererService` | 不开机常驻爬虫/投屏接收，省后台占用 |
| P003 | 关闭 `UpdateService` 前台服务 | 更新由 GitHub Release 手动覆盖安装承担 |
| P004 | 首次启动默认更保守（关闭音频透传/字幕渲染/后台播放/预加载/自动更新） | 降低 3GB 内存下的并发驻留 |
| P005 | `Spider.destroy()` 补做对话框挂起请求释放 | 收敛爬虫资源释放/生命周期滞留 |
| P006 | 本地缺少 mpv/ffmpeg 的 AAR 时跳过一致性校验 | 干净 CI 才能通过构建（否则必然失败） |
| P007 | 从构建图剪掉 nodejs/chaquo/quickjs/thunder | 无需安装 NDK/CMake，CI 更快更稳 |
| P008 | 显式声明签名 storeType=PKCS12 | 避免不同 AGP 版本下签名失败 |

构建结果里 `patches-applied.json` 会记录每个补丁的实际状态（applied / skipped），
**不会静默假装成功**。

## 没改什么（明确不做）

- 不换界面、不复古皮肤；沿用上游 leanback 界面。
- 不内置影视源、不内置配置地址（仍用仓库 `zijian.json`）。
- 不增加 `android:largeHeap`（上游已开启，3GB 设备再加堆反而可能加速系统回收）。
- 不引入 `ApplicationExitInfo`（需要 API 31+，本机是 API 30）。
- 不依赖清数据 / 后台白名单 / Root / 换系统 WebView 等临时解法。

## 关于运行时模块 / 离线

- 默认 **catalog 为空**，首次启动**不联网拉取模块清单**，不会因国内访问不到 GitHub 而白屏/退出。
- 部分需要 Python / Node 解析的站点依赖独立的 runtime 模块 APK；缺失时应用会给出**明确提示**，
  而不是闪退。需要这些解析能力时，可自行安装 `FongMi/Release` 的对应 runtime 模块。

---

## 仍闪退怎么办（取证反馈）

请提供机械证据，而不是「又崩了」：

```bash
# 设备开启开发者选项 → 网络 ADB（或 USB ADB）后，在电脑上：
adb logcat -b all -v threadtime > logcat.txt &
adb shell                       # 在投影仪上复现：连续播放/切源/前后台切换
# 复现后回到电脑 Ctrl-C 停止 logcat
# 取崩溃/回收证据：
adb shell ls /data/system/dropbox/ | grep -iE 'crash|anr|native_crash|tombstone'
adb bugreport bugreport.zip
```

把 `logcat.txt` 与上述目录里对应时间戳的文件一并反馈。请区分三类死因：
**低内存被系统回收（lmkd）** / **native 崩溃（tombstone）** / **Java 未捕获异常（customactivityoncrash 重启）**。
日志里的片名、源地址属于隐私，反馈前可自行脱敏。

---

## 自行修改 / 切换基线

- 工作流：`.github/workflows/build-jmgo.yml`（仓库根，GitHub 只识别这里）。
- 补丁与脚本：`apps/jmgo/patches/`、`apps/jmgo/scripts/`。
- 改上游版本：手动触发 `workflow_dispatch`，填 `upstream_sha`（需对齐 `patches/` 是否仍适用）。
- 签名密钥以 base64 形式入库（`keystore/jmgo.p12.b64`，自签名）。如不想公开，可改为
  GitHub Secrets（`KEYSTORE_BASE64` 等）并在工作流中解码，详见 `scripts/gen_keystore.sh`。

## 目录结构

```
apps/jmgo/
  SPEC.md                 规格契约（团队内部）
  build-contract.md       构建契约（Phase 2 技术契约）
  docs/ACCEPTANCE.md      验收标准 AC-01~AC-31
  patches/jmgo-v1/        P001~P008 补丁
  scripts/                apply_patches.py / collect_apk.py / gen_keystore.sh
  keystore/               jmgo.p12.b64（固定签名）
.github/workflows/build-jmgo.yml   自动构建触发文件（仓库根）
```
