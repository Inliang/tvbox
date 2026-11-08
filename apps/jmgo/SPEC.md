# Spec - 坚果 N1S 4K 兼容版 TVBox 客户端 v0.2

> 生成日期：2026-11-07；方向变更升版：2026-11-08（v0.2）
> 基于：PRD v1.2（产品经理）+ 架构文档 v2（架构师，Phase 1 + 决策变更）+ 兼容性验收清单 v1.1（测试工程师，AC-01~AC-31 顺延 AC-32）+ 技术裁定 v1.0（架构师，`docs/TECH-VERDICT.md`）
> 状态：已确认（用户 2026-11-07 完成三文档确认与三项决策；2026-11-08 用户拍板路线变更）
> 作用：团队内部规格契约。范围外的功能一律不做。

> **方向变更声明（v0.2，效力高于下文一切历史条款）**：2026-11-08 核实 —— `FongMi/TV` 5.8.7 的 `app` 引用 52 个未开源的私有 `androidx.media3.*` 类，`FongMi/media` 全历史 26625 个 commit、另一分支、Google Maven、jitpack、`FongMi/Release` 的 `module` 目录均无对应 AAR，上游 `.gitignore` 的 `lib-*.aar` 证明私有定制 AAR 从未入库，**clean clone 源码重建不可行**。用户拍板改走「官方包兼容化」路线：**主通道 = 官方 `FongMi/Release` 5.8.7 四包基线 + 校验聚合 + 零改造原样发布；实验通道 = 可选二进制兼容层（默认关闭）**。因此下文中所有 `assembleLeanbackRelease` / Gradle / NDK / CMake / clone + 打补丁 / P001~P008 / 双基线兜底 等源码编译表述，**均为 v0.1 历史记录、已废止、不再作为现行约束**；第 13 节总监裁决同理，涉及源码编译的条款以本节与第 13 节第 17 条为准。完整技术裁定见 `docs/TECH-VERDICT.md`。明确不做：不承诺修好闪退。

---

## 1. 产品定义

- **一句话**：为坚果 N1S 4K 高亮版聚合分发官方 FongMi（蜂蜜版）5.8.7 的四包基线，校验后原样交付可覆盖安装的 APK；可选二进制兼容层默认关闭。
- **目标用户**：本机主，当前装官方 FongMi 5.8.7 leanback 32 位包（40MB 以上，包名 `com.fongmi.android.tv`），现象是「用一会儿随机闪退」。
- **核心问题**：3GB RAM 定制 Android 11 环境下，上游爬虫资源释放/生命周期缺陷、独立 runtime 模块依赖 GitHub 可达性、32/64 位包与 runtime 模块潜在不匹配，三者叠加。**根因尚未实机取证**（ACCEPTANCE 第 5 节标 no-go / 未评级）。
- **不是**：再造一个 TVBox 分支，也不是宣称已修好闪退。用户要的是「一口气看完整部片不闪退」，本路线只保证「官方包必定可用、可覆盖安装、可核验、可如实实验」，稳定性结论交给 Phase 4 实机取证。

## 2. MVP 范围（锁定，不在此列表的一律不做）

| 优先级 | 功能 | 验收摘要 |
| --- | --- | --- |
| P0 | F1 按设备出正确架构产物 | 主通道聚合官方 `FongMi/Release` 5.8.7 的 4 个原包（leanback/mobile × arm64_v8a/armeabi_v7a），每个独立校验、独立标注 ABI 与 flavor，字节一致、零改造 |
| P0 | F3 push 即校验聚合 + 发布 | Actions 成功 -> 4 个官方原包 + `SHA256SUMS.txt` + `build-info.json` + 发布说明；附 sha256 / run id / 来源 tag / ABI / 官方证书指纹 |
| P0 | 保持官方原签名 | 主通道不重签、零改造，用户可直接覆盖安装当前官方包、零迁移、零配置丢失；runtime 模块同签名链路完整 |
| P0 | runtime 模块可用性如实告知 | 官方 4 包行为与官方一致，按官方机制按需拉取 runtime 模块；不承诺离线可用、不改 catalog，缺失行为以官方包实际表现与 Phase 4 取证为准 |
| P1 | F2 可选二进制兼容层（实验通道） | 默认关闭；任何 apktool 反编译/改 Manifest/回编译/重签只在实验通道，失败不阻断主通道，产出为空如实标注。零改造主通道不做「裁剪重模块/保守解码/largeHeap」等源码级改动 |
| P1 | 播放状态持久化 | `[工程推断]` 属上游 Java 层能力，二进制零改造路线无法新增；列为 Phase 4 实机取证项，不作为本期承诺 |
| P1 | 产物可核验 | `build-info.json` + `SHA256SUMS.txt` + `apksigner verify --print-certs` + `aapt dump badging` |
| P1 | 双通道兜底 | 取消 v0.1「A/B 源码基线切换」（私有 AAR 不可重建）；改为「主通道恒定可用 + 实验通道可弃用」，实验通道整体失败不影响主通道发布 |

> **范围口径**：本期不承诺「修好闪退」，不承诺「连续播放不闪退」。用户当前装的官方 32 位包正是闪退对象，主通道原样交付不引入稳定性变化，稳定性结论必须由 Phase 4 实机机械证据给出（ACCEPTANCE AC-01~AC-31 / AC-31 中性三组对照）。

## 3. 明确不做（锁定）

| 不做的功能 | 原因 |
| --- | --- |
| **clean clone 源码编译 / `assembleLeanbackRelease` / 打补丁 / Gradle / NDK / CMake** | 52 个私有 media3 类未开源、私有 AAR 未入库，源码重建不可行（v0.2 方向变更，详见 `docs/TECH-VERDICT.md` 第 0.1 节） |
| 主通道对官方 APK 做任何字节改造（反编译/改 Manifest/回编译/重签） | 改动必然改变 v2/v3 签名，破坏覆盖安装与 runtime 模块同签名链路；仅实验通道可选、默认关闭 |
| 主通道用 jmgo 密钥重签 | 会导致首次必须卸载官方版、丢配置，且 `RuntimeModule.verifyPackage` 判 runtime 模块签名不一致而全线失效 |
| 新 UI / 换肤 / 重建前端 | 复用上游界面，ROI 不足且引入新崩溃面 |
| 内置影视源 / 内置配置地址 | 沿用仓库现有 `zijian.json`，本仓库只出客户端 |
| 直播弹幕、DLNA、网盘登录、投屏接收 | 与闪退无关，属范围蔓延 |
| 多机型兼容矩阵 | 只针对坚果 N1S 4K 高亮版一台 |
| 应用内热更新 / 自动升级 | 由官方 `FongMi/Release` 新 tag + 手动覆盖安装承担 |
| Root / 刷机 / 改系统 WebView | 破坏保修且不可分发 |
| 账号体系 / 云同步 | 上游无此能力 |
| 增加 `android:largeHeap` / 关闭硬件加速 | 上游已开启 `largeHeap=true` 与 `hardwareAccelerated=true`；前者是 no-op 且被 QA 列为防假修复项，后者会导致 TextureView 播放器黑屏（负收益）。详见裁定三 |
| OpenAPI / REST API 契约 | 本项目无服务端，改用 `build-contract.md` |
| 清数据 / 后台白名单 / 换内核绕过 / 降级系统 | 临时解法，不算修好 |
| 引入 `ApplicationExitInfo` | API 31+，本机 Android 11 / API 30 不可用 |
| 承诺「修好闪退」/ 把工程推断写成已验证结论 | 根因未实机取证；纪律见 `docs/TECH-VERDICT.md` 第 0 节 |
| emoji 作功能图标、紫粉渐变、硬编码色、空洞占位文案 | 团队 P0 绝对规则 |

## 4. 技术架构（锁定，含版本锚定，v0.2 方向变更后）

| 层 | 技术 / 值 | 依据 |
| --- | --- | --- |
| 主通道基线 | 官方 `FongMi/Release` tag `5.8.7` 的 4 个完整 APK（leanback/mobile × arm64_v8a/armeabi_v7a） | team-lead 核实；下载前缀 `https://github.com/FongMi/Release/releases/download/5.8.7/` |
| 基线字节数 | leanback-arm64_v8a 51412139 / leanback-armeabi_v7a 44768123 / mobile-arm64_v8a 51326563 / mobile-armeabi_v7a 44682547（字节） | team-lead 核实；聚合时逐包校验 |
| 主通道签名 | **保持官方原签名**，不重签、零改造；`keystore/jmgo.p12.b64` 仅实验通道重签用 | `docs/TECH-VERDICT.md` 裁定二 |
| 聚合 / 校验工具 | `apksigner verify --print-certs`、`aapt dump badging`、`sha256sum`、GitHub Actions artifact/release | 沿用原 `collect-apk.sh` 的校验结构（该脚本已删除），实现为 `scripts/verify-upstream.py`，输入为官方 4 包 |
| 实验通道工具 | apktool 3.0.3（2026-07-20，JDK 17+ / aapt2 only / 稳定版仅到 API 36.1，API 37 支持尚未发版） | `docs/TECH-VERDICT.md` 裁定一；`https://apktool.org/docs/unreleased/` |
| CI | GitHub Actions `ubuntu-latest`；主通道无需 JDK/Android SDK/NDK/CMake 编译链 | 用户决策；方向变更后 |
| 设备 | 坚果 N1S 4K 高亮版 J31-8K2 / Android 11 / MT9667（64 位 SoC）/ 3GB RAM / 64GB ROM | 规格页，**待 getprop 实测**；系统 ABI 位数未知 |
| 产物形态 | 主通道：4 个官方原包原样聚合 + 校验清单；不做 universal、不构建、不裁剪、不重签。实验通道：可选二进制兼容层，默认关闭、失败不阻断 | `docs/TECH-VERDICT.md` 裁定五 |

> **已废止的 v0.1 架构层**（历史记录，不再作为约束）：`FongMi/TV` @ `4512b4c` 源码锚定 / Gradle 9.7.1 / AGP 9.4.0 / JDK 21 / compileSdk 37 / NDK 28.2.13676358 / CMake 3.22.1 / `assembleLeanbackRelease` / `splits.abi` 双 ABI / `local.properties` 签名读取。这些参数曾用于源码编译路线，因私有 media3 AAR 未开源、源码重建不可行而整条作废。

## 5. 构建产物契约（替代 API 端点清单，v0.2）

主通道产物 = 「官方 4 包 + 校验聚合清单」，全部来自 `FongMi/Release` tag `5.8.7`。**APK 二进制字节、内容与官方原包完全一致，不重签、零改造**；仅在分发层用 `shutil.copyfile` 复制并重命名为带 `tvbox-jmgo-` 前缀、版本与 commit 短哈希的可溯源文件名。Android 覆盖安装判定依据是「包名 + 签名」，与文件名无关，故 `adb install -r` 覆盖安装能力不受影响。逐包 `assetName`（官方原名）与 `sourceUrl` 写入 `upstream-verify.json` / `build-info.json`，配合 `signingMode=upstream-original` 与官方证书指纹机械校验完成溯源：

| 产物 | 命名 | 校验 |
| --- | --- | --- |
| APK (leanback 64) | `tvbox-jmgo-leanback-arm64_v8a-5.8.7-<短哈希>.apk`（源 asset `leanback-arm64_v8a.apk`，51412139 B） | 字节数 + sha256 + `apksigner verify --print-certs` + `aapt dump badging` |
| APK (leanback 32) | `tvbox-jmgo-leanback-armeabi_v7a-5.8.7-<短哈希>.apk`（源 asset `leanback-armeabi_v7a.apk`，44768123 B） | 同上 |
| APK (mobile 64) | `tvbox-jmgo-mobile-arm64_v8a-5.8.7-<短哈希>.apk`（源 asset `mobile-arm64_v8a.apk`，51326563 B） | 同上 |
| APK (mobile 32) | `tvbox-jmgo-mobile-armeabi_v7a-5.8.7-<短哈希>.apk`（源 asset `mobile-armeabi_v7a.apk`，44682547 B） | 同上 |
| 构建信息 | `build-info.json` | 来源 tag `5.8.7` / run id / 本仓库 commit sha / 4 包各自 sha256 + 字节数 + ABI + flavor + 下载 URL + 官方证书指纹 / 聚合时间戳 |
| 校验和 | `SHA256SUMS.txt` | 与 4 个 Artifact 一一对应；**不**纳入官方 `module` 资产 digest（主通道不改 runtime 链路） |
| 发布说明 | `README`/Release notes | 4 包清单 + 保持官方签名可覆盖安装 + 不承诺修好闪退 + ABI 选择须实机 `getprop` / AC-32 四包对照试装与 AC-31 中性三组对照（工程推断，非结论） |
| 实验通道状态 | `experimental-status.json` | 仅实验通道**真正接入后**才产出，四值 `succeeded`/`failed`/`skipped`/`no-artifact`；空产物如实标注，不得静默假装成功。**本轮实验通道为占位、默认关闭，不产出该文件**；主通道由 `build-info.json` 的 `compatPatchStatus: not-applied` 如实标注 |

静态校验项：`native-code` / `versionName` / `targetSdkVersion` / `applicationId` / `LEANBACK_LAUNCHER`，以及**签名方案 v2/v3 与官方证书指纹一致**。

> 裁决（team-lead，2026-11-08）：v0.1 废止的是「源码编译 + 重签名产物」这一**产物来源**，不是 `tvbox-jmgo-` 文件名前缀。方向变更后分发文件名带前缀与短哈希仅用于追溯与多版本共存，APK 本身仍是官方原包字节。避免把重签产物误标为官方包，靠的是 `signingMode` / 官方证书指纹 / `assetName` / `sourceUrl` 的机械校验，不靠文件名。落盘实现（workflow、`verify-upstream.py`、README、build-contract v2.0、ACCEPTANCE v1.1、PRD v1.2）六处已统一为重命名分发，本节据此对齐。

## 6. 目录结构（锁定）

```
.github/workflows/build-jmgo.yml      # 触发文件，必须在仓库根（主通道下载/校验/聚合/发布 + 实验通道占位）
apps/jmgo/SPEC.md                     # 本文件
apps/jmgo/build-contract.md           # 构建契约 v2.0（官方包基线 + 校验聚合 + ADR 历史）
apps/jmgo/docs/TECH-VERDICT.md        # 方向变更技术裁定 v1.0（5 点裁定，主/实验通道）
apps/jmgo/docs/PRD.md                 # 产品需求 v1.2
apps/jmgo/docs/ACCEPTANCE.md          # 验收清单 AC-01~AC-32（v1.1 顺延 AC-32）
apps/jmgo/docs/FIELD-TEST.md          # 实机取证与四包对照试装手册（QA 维护）
apps/jmgo/scripts/verify-upstream.py  # 机械校验（verify / package / list-assets / self-test）
apps/jmgo/scripts/gen-keystore.sh     # 上一路线固定密钥脚本，保留备用，主通道不调用
apps/jmgo/keystore/*                  # jmgo.p12.b64（仅实验通道重签用；主通道保持官方原签名）
apps/jmgo/README.md                   # 用户向说明（已对齐官方包聚合口径）
```

> 已删除：`apps/jmgo/patches/*`（P001~P008）、`scripts/apply-patches.py`、`scripts/collect-apk.sh`。方向变更后无施加补丁对象、无源码编译产物收集动作。

**硬约束**：GitHub Actions 只识别仓库根 `.github/workflows/*.yml`，故触发文件不能放进子目录。

> 目录内 `patches/` / `apply-patches.py` / `gen-keystore.sh` 为 v0.1 源码编译路线遗留，v0.2 不删除（避免越界改他人文件），但**明确标注为已废止、CI 不再调用**。清理由 team-lead / devops 决定时点。

## 7. 页面清单 / 设计 Token

不适用：无新增 UI，沿用上游 FongMi leanback 界面。P0 视觉规则仍适用于任何新增文案与图标。

## 8. 验收标准（锁定，引用测试工程师独立清单）

以 `apps/jmgo/docs/ACCEPTANCE.md` 的 **AC-01~AC-32** 为唯一验收契约（v1.1 顺延 AC-32，AC-01~AC-31 编号体系与条款不动），产品经理不自造编号；PM 旧版 AC1~AC8 作废，只做映射。

产品侧已签字阈值（锁定后不得为换绿调低；变更须 team-lead + PM + QA 三方书面同意并记入变更记录）：

| 参数 | 锁定值 |
| --- | --- |
| 连续播放 | 60 分钟 = P0 阻断门槛；120 分钟 = P1 加固线，Phase 4 至少执行 1 次 |
| 线路切换 | ≥20 次，且跨 ≥3 个不同站点/线路类型，禁止同一线路刷次数 |
| 前后台切换 | ≥10 次，含 ≥1 次切出停留 >5 分钟再返回 |
| TOTAL PSS | ≤512MB；若基线本身超标则判基线不合格、换轻量基线，不得调高阈值 |
| Java Heap | ≤ `heapgrowthlimit` 的 80% |
| 内存净增长 | 60 分钟内 ≤50MB 且 GC 后回落（最关键稳定性指标） |
| 重复轮次 | k≥3，跨不同冷启动与时段，pass^k 全绿 |
| 首次导入配置 | 30 秒内出现站点列表或明确错误态 |

**只认**：原始日志文件 + 零崩溃标记 + PID 不变量 + 内存曲线。
**不认**：「我觉得修好了」「不卡了」「没弹停止运行框」等主观描述。

## 9. 边界与约束

- **留出集**：用户真实配置 URL 由 QA 独立持有；开发阶段不得接触、不得硬编码、不得对特定源做特判或白名单。本项目留出集可用仓库 README 已公开的配置地址，无需用户提供私密 URL，也不存在凭据进入日志的风险。
- **不要求用户提前开启 ADB**：主通道交付官方 4 包，用户按需分别试装；`getprop` 六项取证留到 Phase 4 由 QA 执行。芯片 64 位不等于系统 64 位，任何 ABI 推荐均为工程推断、须实测。
- **不施加临时解法**：清数据、加后台白名单、换内核绕过、降级系统 WebView 均不算修好，依赖这些才稳定则验收不通过。
- **runtime 模块可用性如实告知**：主通道零改造，不改 catalog、不注入镜像，官方包按官方机制按需拉取 runtime 模块；不承诺离线可用、不承诺「拉取失败给错误态」这类需改 Java 层才能达成的性质，实际表现以官方包行为与 Phase 4 取证为准。此项是 v0.1 的 P0 需求，因路线变更降级为「如实告知 + 观察项」。
- **主通道保持官方原签名、不重签**：零改造保证可直接覆盖安装当前官方包、零迁移、零配置丢失。jmgo 密钥仅实验通道重签用，且重签会破坏 runtime 模块同签名校验（裁定二）。
- **禁止引入 `ApplicationExitInfo`**（API 31+，本机 API 30 不可用）；崩溃取证走 logcat / DropBoxManager / bugreport，并区分 LMK 回收、native crash、customactivityoncrash 重启三类。
- **播放状态持久化**：v0.1 要求「Java 层须实现」属源码改造，零改造路线无法新增；降级为 Phase 4 实机观察项，不作为本期承诺（见第 2 节）。
- 日志与本地事件不记录配置源地址明文、不记录片名；崩溃栈仅本地落盘、用户显式导出、不自动上传。（注：主通道不改应用行为，此条为取证侧与实验通道的约束，非对官方包的改造承诺。）
- **不承诺修好闪退**：主通道产物与官方二进制字节一致，不引入稳定性变化；「必定可用」仅指可安装 / 可覆盖 / 可核验，不等于不闪退。

## 10. 已知坑（Phase 1 + 架构决策变更沉淀）

> **口径（v0.2）**：下表「证据」列仍为有效的一手事实，保留供溯源；但「处置」列中凡涉及 clone 源码 / `assembleLeanbackRelease` / Gradle 补丁 / NDK / 自建编译 workflow 的条目，随方向变更**已废止、不再执行**，仅作历史记录。竞品/ABI/包名/取证类事实与处置不受影响。

| 坑 | 证据 | 处置 |
| --- | --- | --- |
| **私有 media3 AAR 未开源，源码重建不可行** | 151 个 `androidx.media3.*` 引用中 52 个无源码；`FongMi/media` 全历史 26625 commit / 另一分支 / Google Maven / jitpack / `module` 目录均无 AAR；上游 `.gitignore` 有 `lib-*.aar` | **方向变更根因**：改走官方包兼容化；详见 `docs/TECH-VERDICT.md` 第 0.1 节 |
| **apktool 3.0.3 稳定版仅支持到 API 36.1，API 37 支持尚未发版** | `https://apktool.org/docs/unreleased/`(#4214/#4223) | 5.8.7 是 compileSdk 37，实验通道反编译/回编译可行性标 `[需 CI 验证]`（裁定一 V1） |
| **改包必然改变签名；重签破坏 runtime 模块同签名校验** | `RuntimeModule.verifyPackage` 逐字；v2/v3 覆盖整包字节 | 主通道保持官方原签名、零改造；jmgo 重签仅实验通道（裁定二） |
| 上游已开 `largeHeap=true` + `hardwareAccelerated=true` | `app/src/main/AndroidManifest.xml` @ `4512b4c` 逐字 | 加 largeHeap 是 no-op 且属防假修复；关硬件加速会致播放器黑屏，均不做（裁定三） |
| FongMi 5.8.6+ 拆分 Python / Node.js / QuickJS / MPV / Thunder 独立模块，`catalog.json` 默认指向 GitHub Release | 架构师核实 Release Note | v0.1「注入可达镜像，升 P0」已废止；主通道不改 catalog，行为随官方包，列为 Phase 4 观察项 |
| 上游 5.8.5 / 5.8.6 / 5.8.7 连续修「代理网址闪退 / 爬虫资源释放 / 爬虫生命周期」 | `FongMi/Release/releases` | 用户已装 5.8.7 仍闪退，说明问题未完全覆盖；F2 源码级「生命周期收敛」已废止，交给实机取证 |
| runner 预装缺 NDK 28.2.13676358 / CMake 3.22.1 | 架构师核实 | v0.1「workflow 显式 sdkmanager 安装」已废止（主通道不编译）；仅历史 |
| `yebook/TV` 依赖 jcenter 与明文 http maven 仓库，已失效 | 架构师核实 | 不采用该基线（结论不变） |
| `FongMi/TV` 无 APK 构建 workflow（只有 `pages.yml`） | GitHub API 复核 | v0.1「自建编译 workflow」已废止；现改为校验聚合 workflow |
| 芯片 64 位 ≠ 系统 64 位 ABI | QA / PM / 架构师共识 | 4 包齐发不预设单变体；ABI 推荐为工程推断、须实机 `getprop`（裁定四） |
| 上游 `app/build.gradle` 默认 `splits.abi.include "arm64-v8a","armeabi-v7a"` 且 `universalApk=false`，buildSrc 已重命名为 `leanback-<abi>.apk` | 架构师核实 | v0.1「双 ABI 补丁归零，CI 直接 assemble」已废止；现直接取官方现成 4 包 |
| `FongMi/Release` 的 `module` Release 六类运行时模块均同时提供两个 ABI，catalog.json 带 sha256 `84f89736...` | 架构师核实 | digest 不再进主通道校验清单（主通道不改 runtime 链路）；重签场景下模块会失效，见裁定二 |
| `yebook/TV` 的 `applicationId` 是 `com.fongmi.android.tv`（FongMi 系旧 fork）；`com.github.tvbox.osc` 属于 `q215613905/TVBoxOSC` | 架构师核实 | PRD 竞品表须修正，两条产品线不可混写（结论不变） |
| QA 引用的「上游 README 建议优先 32 位变体」并非 FongMi 官方内容（官方 README 全文无 ABI 建议，出自第三方聚合站） | 架构师核实 | 验收文档不得写成上游官方建议（结论不变） |
| 「蜂蜜版」混指两条代码基线（FongMi/TV 与 TVBoxOSC 系） | PM 竞品调研 | 已由用户「40MB 官方 FongMi 5.8.7」锁定为 FongMi/TV（结论不变） |
| 上游 `mobile` 与 `leanback` 包名相同，同设备只能装一个 | 社区资料 | v0.1「只出 leanback」改为「4 包齐发但发布说明提示同包名只能装一个」，由用户按设备选 leanback 包 |

## 11. 端到端验证步骤（v0.2）

1. push 到 `main` 或 `workflow_dispatch` -> Actions 触发 `.github/workflows/build-jmgo.yml`。
2. 主通道：下载 `FongMi/Release` tag `5.8.7` 的 4 个官方原包；逐包校验字节数（51412139 / 44768123 / 51326563 / 44682547）与 sha256；`apksigner verify --print-certs` 确认官方签名方案与证书指纹；`aapt dump badging` 确认 `com.fongmi.android.tv` / `native-code` / `versionName` / `targetSdkVersion` / `LEANBACK_LAUNCHER`。
3. 下载失败、字节数不符、sha256 不符、签名不符、4 包缺任一 -> **主通道构建失败**（唯一正确信号，不允许静默降级或补包冒充）。
4. 校验通过 -> 原样聚合 4 包 + `SHA256SUMS.txt` + `build-info.json` + 发布说明 -> Artifact / Release；发布说明含「保持官方原签名、可覆盖安装、4 包按设备选、不承诺修好闪退」。
5. 实验通道（默认关闭）：仅当显式开关开启时执行 apktool 改造 + jmgo 重签 + 装机自检；失败 `continue-on-error`，写 `experimental-status.json`（四值），不阻断主通道、不影响 Release、空产物如实标注。
6. 用户按需试装；`aapt dump badging` / 实机 `getprop ro.product.cpu.abilist` 等 ABI 判定留到 Phase 4 由 QA 执行，本阶段不索取。
7. 按 AC-01~AC-31 执行稳定性取证（冷启动 10 次 / 连续 60 分钟 / 切源 20 次 / 前后台 10 次 / AC-31 中性三组对照 / k>=3 轮）；证据包齐全且全绿 -> 交付稳定性**结论**。主通道产物可用性与稳定性结论是两件事，前者此时已成立，后者尚待 Phase 4。

> 已废止的 v0.1 步骤：clone 上游 SHA / 应用 P001~P008 补丁 / 注入 `local.properties` / `assembleLeanbackRelease` / 连续两次失败切 B 基线。

## 12. 用户决策（已锁定）

| 决策 | 结果 |
| --- | --- |
| 上游基线 | **v0.2 改**：官方 `FongMi/Release` tag `5.8.7` 四包基线 + 校验聚合（用户 2026-11-08 拍板）。v0.1 的「先 A（`FongMi/TV` 5.8.7）后 B（`q215613905/TVBoxOS`）、A 连续两次 CI 跑不通切 B」已废止——A 因私有 AAR 不可重建，B 亦不采用 |
| 直装对照 | 不需要；用户确认当前装的就是 5.8.7 |
| 当前包来源 | 40MB 以上官方蜂蜜影视，`FongMi/TV` 系 |
| 落地位置 | 当前 `tvbox` 仓库下 `apps/jmgo/` 子目录 |
| 构建产物 | **v0.2 改**：push 即校验聚合并发布官方 4 原包（零改造、保持官方原签名），非「编译产出」 |
| 路线变更 | 2026-11-08：私有 media3 AAR 未开源导致源码重建不可行，用户拍板改走官方包兼容化；主通道零改造、实验通道默认关闭 |

## 13. 总监裁决（Phase 1 一致性检查 + Phase 2 放行；第 17 条为 v0.2 方向变更）

> **口径（v0.2）**：下列第 1~16 条为 v0.1 历史裁决，保留编号供溯源。其中涉及 `assembleLeanbackRelease` / clone 源码 / 补丁 / 双 ABI 编译 / P0「runtime 模块离线可用」/ Java 层改造 的条款（第 1、2、3、4、8、10、11 条相关部分），因 2026-11-08 方向变更**已被第 17 条取代、不再作为现行约束**；与路线无关的裁决（第 5、6、7、9、12、13、14、15、16 条：不索取用户信息、AC 编号冻结、阈值锁定、largeHeap 从严、日志脱敏、D-01 兜底）继续有效。

1. **双 ABI 不砍 32 位**（历史，源码编译口径，已废止）：v0.1 曾要求「只执行 `assembleLeanbackRelease`，同时产出两个 ABI 包」，并否决「芯片 64 位故锁 arm64 单变体」；架构师当时已主动撤回并修订 ADR-003 / 006 / 007 / 008。v0.2 对应口径见第 2 节 F1 与裁定四：4 个官方原包齐发、不预设单变体。
2. **不做加 largeHeap**：改走裁剪重模块 + 缓存/生命周期收敛 + 保守解码，largeHeap 开/关列 A/B。
3. **runtime 模块可达性升为 P0 需求**，不是警告。
4. **不做 OpenAPI**：本项目无 REST API，用 `build-contract.md` + workflow 契约 + patches 清单代替。
5. **PM 四件待确认事项不打断用户**：留出集用仓库公开配置地址；不索取 APK MD5；不要求提前开 ADB；不索取私密配置 URL。
6. **验收以 QA 的 AC-01~AC-31 为唯一编号体系**，PM 自造的 AC1~AC8 作废。
7. **阈值锁定表采纳 PM 签字版**，一字不改。
8. **F2 目标按 PM Addendum 修正**：不只降内存，还须覆盖上游爬虫资源释放/生命周期缺陷。
9. **驳回「实机 ABI 探测作为 Phase 2 放行门禁」**：架构师 ADR-006 已自认「探测结果决定推荐哪个包，不决定 CI 产物矩阵」，探测与 workflow 落盘无因果关系，不构成阻塞。CI 恒定出双 ABI 两包；README 用「两包分别试装，能装上且稳定者即为目标包」替代推荐；`getprop` 六项取证移到 Phase 4 由 QA 执行。**不向用户索取 APK 文件名 / MD5 / getprop**，用户已明确装的是官方 5.8.7，且本阶段承诺不再打断用户。
10. **批准路线 B 落盘**：以 `build-contract.md` 作为 Phase 2 技术契约文档，不生成 `openapi.yaml`。
11. **采纳架构决策变更的新增约束**：禁止 `ApplicationExitInfo`；Java 层播放状态持久化；产物静态校验含 LEANBACK_LAUNCHER；官方 module 资产 digest 纳入校验清单；PRD 包名纠错；QA 归因纠错。
12. **终裁：不向用户索取任何信息**（第 4 次驳回，全队广播）。「实机 getprop / aapt dump badging / APK 文件名 / 版本号 / 闪退时机 / 留出集授权 / 当前包」等一律不作为 Phase 2 / 3 落盘门禁。理由：CI 恒定出双 ABI 两包、探测只决定推荐不决定产物矩阵；用户已给等价信息；本阶段已承诺不打断用户。所有此类 blocking 一律降级为 Phase 4 实机验收动作，由 QA 执行。
13. **AC 契约冻结为 AC-01~AC-31**：采纳 QA 的中性三组对照（官方 arm64 / 官方 armeabi-v7a / 用户当前包，同机各 60 分钟统一取证），不预设「装错 32 位包」为根因方向；PM 自造编号作废。
14. **largeHeap 从严**：上游已开大堆时生效堆上限为 `dalvik.vm.heapsize`，但验收仍按 `heapgrowthlimit × 80%` 判，不因 largeHeap 放宽阈值；「加 largeHeap」不得作为修复项上报。
15. **日志脱敏方案采纳**：全量 `logcat -b all -v threadtime` 原始文件本地受限保存、仅 QA 可访问、不上传；对外副本脱敏 URL / token / 片名，但保留时间戳、级别、TAG、堆栈结构和五类死因关键字；脱敏前后 sha256 与行数差须留痕；「借脱敏之名删日志」列为第 21 条自欺行为。构建侧日志脱敏可行性作为 Phase 3 运维评估项，不是 Phase 2 门禁。
16. **D-01 对外口径定为兜底版**（继续有效）：「沿用现有配置可加载；若旧爬虫或模块不兼容，须给明确提示与可执行迁移路径」，不承诺「一定能沿用旧配置」。三条底线：首启不崩/不白屏/不静默退出；提示须说明不兼容类型与下一步具体操作；迁移不得要求用户自找新配置源、不得把清数据列为步骤、收藏/历史/进度不得丢失。注：v0.2 主通道零改造，「给明确提示」这类需改 Java 层的性质降级为观察项，三条底线仍作为实验通道与产品对外口径约束。
17. **方向变更终裁（v0.2，2026-11-08，效力最高）**：私有 media3 AAR 未开源，`clean clone` 源码重建不可行，用户拍板改走「官方包兼容化」。主通道 = 官方 `FongMi/Release` 5.8.7 四包基线 + 校验聚合 + 零改造原样发布 + 保持官方原签名；实验通道 = 可选二进制兼容层（apktool 改造/重签），默认关闭、失败不阻断、产出为空如实标注。裁定一~五见 `docs/TECH-VERDICT.md`。**不承诺修好闪退**，工程推断不得写成已验证结论，ABI 推荐须实机 `getprop` / AC-31 对照。v0.1 的 assemble/Gradle/NDK/CMake/clone+补丁/P001~P008/双源码基线兜底 全部废止。此前凡与本条冲突的裁决，以本条为准。

## 14. 变更记录

| 日期 | 变更 | 原因 | 影响范围 |
| --- | --- | --- | --- |
| 2026-11-07 | v0.1 建立 | 三文档确认 + 用户三项决策 + PM Addendum v1.1 裁决 | 全流程起点 |
| 2026-11-07 | v0.1 修订 | 架构师决策变更（撤回单变体、双 ABI 零补丁、包名与归因纠错、API 30 约束） + 驳回 ABI 探测门禁 | 第 2/3/4/5/9/10/13 节 |
| 2026-11-07 | v0.1 定稿 | QA 收口汇总（AC-31 中性三组对照、largeHeap 从严、日志脱敏、五处引用纠错） + 全队终裁不索取用户信息 + D-01 兜底口径 | 全文 AC 编号 / 第 9、13 节 |
| 2026-11-08 | **v0.2 方向变更** | **私有 media3 AAR 未开源（52 个类无源码，全历史/分支/仓库/jitpack/module 目录均无对应 AAR），`clean clone` 源码编译不可行；用户拍板改走官方包兼容化路线** | 头部方向变更声明；第 1/2/3/4/5/6/9/10/11/12/13/14 节；新增 `docs/TECH-VERDICT.md`；`build-contract.md` 同步升 v2.0 |
