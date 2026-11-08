# 技术裁定 - 官方包兼容化路线（替代源码编译）

> 文件：`apps/jmgo/docs/TECH-VERDICT.md`
> 版本：v1.0（2026-11-08，方向变更后首次裁定）
> 上位契约：`apps/jmgo/SPEC.md` v0.2、`apps/jmgo/build-contract.md` v2.0
> 裁定人：首席架构师（高见远）
> 适用设备：坚果 N1S 4K 高亮版（国行 J31-8K2 / Android 11 API 30 / MT9667 / 3GB RAM / 无网口 / 无 Root）

---

## 0. 阅读约定与结论分级

全文结论分三级标注，**不得跨级引用**：

| 标记 | 含义 | 可否作为决策依据 |
| --- | --- | --- |
| `[已验证事实]` | 有官方一手来源或本次逐字核实的源码 / 文件 / 命令输出 | 可直接作为约束 |
| `[工程推断]` | 基于通用工程机理的推理，**未在本项目 / 本机实测** | 只能作为实验方向，不得写成结论 |
| `[需 CI 验证]` | 结论依赖尚未执行的构建或真机动作 | 必须验证后才能定论 |

**贯穿全文的纪律**：本裁定的目标是「保证官方 4 个包必定可用并如实交付」，**不承诺修好闪退**。用户报障的「用一会儿随机闪退」根因尚未实机取证（SPEC.md 第 1 节、ACCEPTANCE.md 第 5 节均标 no-go / 未评级）。「可用」仅指「可安装、与官方二进制行为一致、可覆盖安装、可核验」，不等于「不闪退」。

### 0.1 方向变更依据（team-lead 已核实，本裁定不重复论证）

FongMi/TV 5.8.7 的 `app` 模块引用 151 个 `androidx.media3.*` 类，其中 52 个在公开仓库无源码（SubtitleTranscript 全家、SecondaryTextTrackSelector、DecoderManager、FfmpegMotionRenderersFactory、DanmakuPlayerViewController、ISO 蓝光三件套、libass 全套）；把 `FongMi/media` 的 `release` 分支历史拉全到 26625 个 commit 后 0 命中，另一分支 `release-1.11.0-fongmi` 同样没有；`FongMi/media` 无 Release、jitpack 404、`FongMi/Release` 的 `module` 目录只有 `runtime-*.apk` 无 AAR；官方 Google Maven media3 1.11.0 不含这些类且作者改过 media3 核心类（fork 版 `DefaultRenderersFactory` 有 `setDolbyVisionOutputPolicy`，stock 没有）。上游 `.gitignore` 里 `lib-*.aar` + `test.gradle` 证明整套私有定制 AAR 从未入库。

**结论 `[已验证事实]`**：clean clone 源码重建在当前公开材料下不可行。用户已拍板改走「官方包兼容化」路线，故 `assembleLeanbackRelease` / Gradle / NDK / CMake / 源码补丁（P001~P008）整条链路不再是本期构建手段。

### 0.2 基线产物（`[已验证事实]`，team-lead 核实）

官方 `FongMi/Release` 5.8.7 发布 4 个完整包，下载前缀 `https://github.com/FongMi/Release/releases/download/5.8.7/`：

| 文件 | 字节数 | 通道 |
| --- | --- | --- |
| `leanback-arm64_v8a.apk` | 51412139 | 主通道（电视 / 64 位） |
| `leanback-armeabi_v7a.apk` | 44768123 | 主通道（电视 / 32 位） |
| `mobile-arm64_v8a.apk` | 51326563 | 主通道（手机 / 64 位） |
| `mobile-armeabi_v7a.apk` | 44682547 | 主通道（手机 / 32 位） |

仓库 `apps/jmgo/keystore/jmgo.p12.b64` 已存在（本次 `ls` 确认 3580 字节，base64 编码的 PKCS12）。apktool 当前发布版为 **3.0.3**（2026-07-20 发布）。

---

## 1. 裁定一：apktool 3.0.3 对 5.8.7 做「反编译 -> 改 Manifest -> 回编译 -> 重签名」的可行性

### 1.1 结论摘要

`[工程推断]` **不推荐把这条路放进主通道，只可作为实验通道，且默认关闭**。不是因为「一定做不到」，而是因为收益与风险严重不对称：为改一个 Manifest 布尔值，要承担整个 resources.arsc 重建、资源 ID 重排、native 库对齐、签名方案、API 37 资源表五类失败模式，且**任何一次回编译都会改变 APK 字节、进而改变签名**（见裁定二），把「零迁移覆盖安装」这个用户最在意的性质一起牺牲掉。

### 1.2 已验证事实（工具链与产物特征）

| 项 | 已核实值 | 来源 |
| --- | --- | --- |
| 5.8.7 编译 SDK | `compileSdk 37` / `targetSdk 37` / `minSdk 24` | 上游 `gradle/libs.versions.toml`（团队 Phase 1 核实） |
| apktool 稳定版 | 3.0.3，2026-07-20 发布；jar 15478013 B；要求 64 位 JDK 17+ | apktool.org 首页 CLI 样例；darknet.org.uk 评测 |
| 3.0.3 稳定版支持上限 | API 36.1（Baklava）；3.x 砍掉 aapt1，只认 aapt2 | CSDN 版本综述；redoapk 工具链拆解 |
| **API 37 支持状态** | `[#4214] Add support for API 37 (Cinnamon Bun) internal frameworks`、`[#4223] Add aapt/2 built against API 37` **位于 "Upcoming Release" changelog，尚未发版** | `https://apktool.org/docs/unreleased/` 逐字 |
| 5.8.7 主 Manifest | `android:largeHeap="true"`、`android:hardwareAccelerated="true"`、`android:pageSizeCompat="enabled"`、`android:usesCleartextTraffic="true"`、`android:allowBackup="false"` | 上游 `app/src/main/AndroidManifest.xml` @ `4512b4c` 逐字 |
| 5.8.7 leanback Manifest | `BootReceiver`（`BOOT_COMPLETED` + `QUICKBOOT_POWERON`，`priority=999`，`exported=true`）、`DLNARendererService`、`LEANBACK_LAUNCHER` 已声明 | 上游 `app/src/leanback/AndroidManifest.xml` @ `4512b4c` 逐字 |
| native 资源 | 含 `libmpv.so` 等 native 库（runtime 模块另带 `libplayer.so` / `libnode.so` 等） | 上游 `RuntimeModule.libraries()` 逐字 |
| `resources.arsc` 对齐要求 | targetSdk 30+ 要求 `resources.arsc` 未压缩且 4 字节对齐；`apktool b` 默认会压缩它，需 `zip -0` 修正 | tutorialpedia / Android 官方 zipalign 语义 |
| 签名顺序 | 必须 `apktool b` -> `zip -0` 修 arsc -> `zipalign -p -f 4` -> `apksigner sign`（v2/v3）。顺序颠倒或签名后再改字节，签名即失效 | 多来源一致（sheratonhq、bugnet、tutorialpedia、renrendaima） |
| Android 11 签名门槛 | targetSdk 30+ 在 Android 11 上必须含 v2 或更高方案；仅 v1（jarsigner）拒装 | Android 11 行为变更（多来源转述一致） |

### 1.3 五类已知失败模式（`[已验证事实]` 为通用机制，`[需 CI 验证]` 为对本包是否触发）

| # | 失败模式 | 机制 | 对本包的判定 |
| --- | --- | --- | --- |
| F1 | `Could not decode arsc` 反编译中断 | 资源表由较新 aapt2 产出，apktool 内置解析器不认新表结构；厂商/定制资源表更易触发 | `[工程推断]` 高风险：本包 compileSdk 37，而 3.0.3 稳定版 aapt2 为 API 36.1 构建，且带 `pageSizeCompat` / `feature flags` 等新结构。`[需 CI 验证]` |
| F2 | `INSTALL_FAILED_INVALID_APK` 回编译成功但装不上 | `apktool b` 产物是裸包，无 zipalign、无签名；或 `resources.arsc` 被压缩、未 4 字节对齐；或 `extractNativeLibs=false` 时 `.so` 被压缩 / 未页对齐 | `[已验证事实]` 必然触发，除非严格按 1.2 的 `zip -0` + `zipalign -p -f 4` 流程。`[需 CI 验证]` 本包 `pageSizeCompat="enabled"` 下的对齐结果 |
| F3 | 资源 ID 重排 / 引用丢失 | 回编译重建整个 resources.arsc，凡改动牵涉 `@string` / `@mipmap` / dataBinding 生成资源，ID 可能变；`AndroidManifest.xml` 里 `XXX not found` 是典型症状 | `[工程推断]` 中高风险：5.8.7 有 dataBinding / viewBinding 生成资源与大量 `<intent-filter>` 引用。`[需 CI 验证]` |
| F4 | 稀疏资源 / protobuf 资源表丢失 | AAPT2 的 sparse resource table、`.pb` compact 资源表、overlay 是 AGP 新链路特性；apktool 的 arsc/axml 读写对 r/w feature flags 的支持 `[#4220]` 同样还在 upcoming | `[工程推断]` 中风险，未能确认 5.8.7 是否启用。`[需 CI 验证]` 用 `aapt2 dump resources` 比对改造前后资源表条目数与 ID |
| F5 | 签名块失效导致覆盖安装失败 | v2/v3 覆盖整个 APK 字节；回编译后必须用新密钥重签，不同证书覆盖安装报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | `[已验证事实]` 必然触发，见裁定二 |

补充 `[已验证事实]`：3.0.3 调 aapt2 会传 `--no-compile-sdk-metadata`，部分非官方 aapt2 不认该参数直接 usage 退出（redoapk 工具链拆解）；3.0.2 修复了路径穿越 CVE-2026-39973，故**至少用 3.0.3，不要用更旧的 jar**。

### 1.4 安全改动 vs 破坏包的改动清单

**相对安全（仍需逐项 `[需 CI 验证]`）**：
- 修改 `AndroidManifest.xml` 中已存在的**纯布尔属性**且不新增/删除资源引用，例如把现有 `android:largeHeap="true"` 改为 `"false"`（不推荐，见裁定三）、`android:debuggable` 开关。
- 修改 `res/values/` 下已存在字符串的值（长度变化不影响 ID）。
- 仅做 `apktool d -m` / `aapt2 dump` 的**只读分析**，不回编译、不分发产物。

**会破坏包或引入崩溃（禁止）**：
- 新增 / 删除组件（`<receiver>` / `<service>` / `<activity>`）却指向不存在的类，或删除仍被 intent / 代码引用的组件 -> 安装后 `ClassNotFoundException` 或功能静默缺失。
- 新增任何资源引用（新 `@string` / `@mipmap` / new style），或删除被 dataBinding / viewBinding 生成类引用的资源 -> 资源 ID 重排后崩溃。
- 改动 `applicationId`（破坏 runtime 模块 `com.fongmi.runtime.*` 的 `<queries>` 命名空间与覆盖安装）、改动 `versionCode`（破坏覆盖安装升级路径）。
- 改动 `android:pageSizeCompat` / `android:extractNativeLibs`、动 `.so` 的压缩与对齐 -> 安装失败或 native 加载失败。
- 用 `jarsigner` 或只出 v1 签名；在签名之后再做任何 zipalign / 资源替换。
- 把回编译产物当作「官方包」标注分发（签名已变，见裁定二）。

**架构结论 `[已验证事实]`**：即便是「相对安全」的布尔属性改动，也要付出「整包重编译 + 重签名」的代价，而收益仅为改一个属性。因此**主通道零改造**，任何 Manifest 改动只进实验通道。

---

## 2. 裁定二：签名策略二选一 + 代价 + 推荐

### 2.1 必须先点破的约束（`[已验证事实]`）

team-lead 给的两个选项里隐含一个密码学矛盾，裁定前必须澄清：

**「改 AndroidManifest 后保持官方原签名」在技术上不可能**。v2/v3 APK 签名方案对**整个 APK 文件字节**做完整性保护；apktool 回编译会重建 APK，原签名块随即失效。我方不持有 FongMi 的发布私钥，无法用原证书重新生成官方签名。因此：

- 「保持官方原签名」**严格等价于「不对 APK 做任何字节改动，原样分发官方 4 包」**，它不是一种改造方案，而是「零改造」方案。
- 只要任务 1 的 apktool 改造发生，产物就**自动**落入方案 B（重签名），并连带承担方案 B 的全部代价。
- 换言之，裁定一与裁定二不是两个独立选择：**启用二进制改造 == 启用重签名**。

### 2.2 方案 A：保持官方原签名（原样分发，零改造）

| 维度 | 说明 |
| --- | --- |
| 做法 | 直接下载 4 个官方包，校验字节数 / sha256 / `apksigner verify`，原样作为 Artifact / Release 产出 |
| 收益 `[已验证事实]` | 用户当前装的就是官方包（PRD 第 1 节），证书一致 -> 可直接覆盖安装、零迁移、零配置丢失、收藏/历史/进度保留 |
| 收益 `[已验证事实]` | 官方 6 类 runtime 模块（Python / Node.js / QuickJS / MPV / Thunder / BD-J）仍是同签名，模块链路完整可用 |
| 代价 `[已验证事实]` | 无法做任何二进制改造（一旦改造签名必变） |
| 代价 `[已验证事实]` | 我方无法用该签名持续发版：后续版本只能取官方 `FongMi/Release` 的新 tag |
| 代价 `[已验证事实]` | **不改善闪退**：用户当前 32 位官方包正是闪退的那个包，原样分发不引入任何变化 |

### 2.3 方案 B：用仓库固定 jmgo 密钥重签

| 维度 | 说明 |
| --- | --- |
| 做法 | apktool 改造后用 `keystore/jmgo.p12.b64` 解出的 PKCS12 重签，`zipalign -p -f 4` -> `apksigner sign`（v2/v3） |
| 收益 | 形成独立发布线，可做二进制改造，可持续发版 |
| 代价 1 `[已验证事实]` | 首次必须**卸载**官方版（`INSTALL_FAILED_UPDATE_INCOMPATIBLE`），配置 / 收藏 / 历史 / 播放进度全部丢失。与 SPEC.md 第 13 节第 16 条「不得把清数据列为迁移步骤、收藏/历史/进度不得丢失」直接冲突 |
| 代价 2 `[已验证事实]` | **runtime 模块全线失效**：`catvod/.../RuntimeModule.java` 的 `verifyPackage(PackageInfo)` 逐字比较宿主与 runtime APK 的签名，`expected != actual` 即抛 `IOException("Invalid runtime signer")`；`require()` -> `getMetadata()` 会把该异常包成 `IllegalStateException("Invalid <Module> module")`。官方 `module` 目录的 `runtime-*.apk` 全是官方签名，重签后需要 Python / Node / QuickJS / MPV 解析的站点打不开。要恢复必须把 6 类 runtime 模块**逐个用 jmgo 密钥重签并改造 catalog 指向**，而 `RuntimeInstaller` 还会校验每个资产的 `sha256` digest 与 ELF ABI，等于再开一条完整构建链 |
| 代价 3 `[工程推断]` | 若 app 有签名自校验 / 防篡改会直接崩。本次对 `FongMi/TV` 做 `GET_SIGNATURES` / `antiTamper` / `signatureCheck` code search 为 **0 命中**，但这是「未在源码层发现」，不能排除 smali 层混淆后的自校验或第三方 SDK 内校验。`[需 CI 验证]` 装机后观察 |
| 代价 4 `[已验证事实]` | 覆盖安装链路断裂，用户从官方版迁移有一次性成本 |
| 代价 5 | 重签产物与官方包行为不再一致，出问题无法用「官方也这样」归因 |

### 2.4 推荐（`[已验证事实]` 决策依据 + `[工程推断]` 权衡）

**推荐方案 A 用于主通道：原样分发官方 4 包，保持官方原签名，零改造、零迁移。** 三条理由：

1. 用户对「可覆盖安装、不丢配置」的诉求是硬性的，方案 B 明确违反 SPEC 第 13 节第 16 条底线。
2. 代价 2 是决定性的：重签会让 runtime 模块签名校验全面失败，等于用「牺牲一大类播放能力」去换「改一个 Manifest 布尔值」，收益为负。
3. 方案 A 与裁定五的「主通道零改造保证 4 个原包必定可用」完全自洽，且天然避开了裁定一的全部 apktool 失败模式。

**方案 B 仅保留为实验通道的可选能力**，且必须同时满足：默认关闭；显式声明「首次需卸载官方版、会丢配置」；明确「runtime 模块需同签名重配套，否则不可用」；失败不阻断主通道；不得把重签产物标注为官方包。若后续确实要独立发布线，应先解决 runtime 模块重签与 catalog 重建，再单独立项评估，不在本期范围。

---

## 3. 裁定三：二进制层三项改动的真实收益与风险

前置事实 `[已验证事实]`：上游 `app/src/main/AndroidManifest.xml` 逐字为 `android:largeHeap="true"`、`android:hardwareAccelerated="true"`。因此「**加** largeHeap」这个动作在本基线上是 **no-op**（已经是 true），「**关**硬件加速」则是从 true 改成 false。

| 改动 | 真实收益 | 风险 | 裁定 |
| --- | --- | --- | --- |
| **去 BootReceiver** | `[工程推断]` 减少开机后一次自启与常驻机会，理论上略降后台进程数。但用户报障是「**播放一会儿**随机闪退」，发生在交互过程中，开机广播与其无因果关系 -> 对本报障收益极低 | `[已验证事实]` 该 receiver 在 `app/src/leanback/AndroidManifest.xml`，带 `BOOT_COMPLETED` + `QUICKBOOT_POWERON`，`priority=999`；删除组件须整体反编译回编译，触发裁定一 F1~F5。`[工程推断]` 若代码里有对该 receiver 的显式引用，删除后可能 `ClassNotFoundException` | **不做**（收益与风险不对称）。若要做，只放实验通道且必须 `tools:node="remove"` 等价的纯声明删除并做装机自检 |
| **加 largeHeap** | `[已验证事实]` **零收益**：上游已是 `true`，无「加」的空间。`[已验证事实]` QA 已裁定「加 largeHeap 不得作为修复项上报」，且 3GB 设备上抬高大堆上限会推高 LMK 回收优先级，与「看完整部片不闪退」相悖 | `[已验证事实]` 若反而去动它（改成 false 或重复声明），要么改变已验证基线行为，要么触发资源表重建；SPEC 第 3 节、第 13 节第 2/14 条、ACCEPTANCE 第 4 节 AC-26~28 均把「加 largeHeap」列为防假修复 / 禁止项 | **不做，且明确标注为 no-op**。README 里「不增加 `android:largeHeap`（上游已开启）」这句**事实正确，予以保留** |
| **关硬件加速**（`hardwareAccelerated="false"`） | `[工程推断]` 理论上减少 GPU 侧显存占用，但对本报障无直接证据 | `[已验证事实]` Android 官方语义：`TextureView can only be used in a hardware accelerated window. When rendered in software, TextureView will draw nothing`。媒体播放界面普遍依赖 TextureView / SurfaceView 与 MediaCodec 硬解；关闭后典型症状正是「有声音没画面 / 黑屏」，社区有多起 `hardwareAccelerated=false` 导致播放器黑屏的实测报告。5.8.7 是媒体播放应用且 `hardwareAccelerated="true"` | **严禁**。这是负收益改动，会把「随机闪退」换成「必然黑屏」，命中 QA 反作弊门的「用功能退化换绿」 |

### 3.1 对 README.md 旧路线说法的核实与纠正

**核实结论**：README.md 第 30~46 行列的 **P001~P008 是「源码 clone + 打补丁 + Gradle 编译」路线的产物**，随方向变更整体失效——本期不再 clone 源码、不再 `assembleLeanbackRelease`，`patches/jmgo-v1/` 下的字面量补丁、13/13 hunk 干跑、`patches-applied.json` 全部不再有施加对象。README 第 52 行「不增加 `android:largeHeap`（上游已开启）」经本次逐字核实**是事实，不需要改**。

因此真正的过时项是：

| README 位置 | 旧说法 | 判定 |
| --- | --- | --- |
| 第 4~5 行 | 「基于上游开源源码 `FongMi/TV` 固定版本，推送即由 GitHub Actions 自动编译出 APK」 | 过时，改为「基于官方 `FongMi/Release` 5.8.7 四包，推送即校验聚合并发布」 |
| 第 16~18、24、45~46 行 | 「两个 ABI 包」「两个都构建」「`patches-applied.json` 记录补丁状态」 | 过时：主通道是 4 个官方原包，不构建、无补丁状态文件 |
| 第 30~43 行 | P001~P008 补丁表 | 过时，整体作废；不得表述为「本期已应用」 |
| 第 52 行 | 「不增加 `android:largeHeap`（上游已开启）」 | **事实正确，保留** |
| 第 25 行 | 「本项目签名密钥固定，能直接覆盖旧版」 | 过时且与裁定二冲突：主通道保持**官方原签名**，不是 jmgo 密钥；jmgo 密钥只用于实验通道重签 |

> 边界说明：本次任务只授权写 `TECH-VERDICT.md`、`SPEC.md`、`build-contract.md` 三个文件。README.md / workflow / scripts 的措辞纠正**不在本次落盘范围**，此处登记为给 team-lead / devops 的 advisory（见裁定五与回传 RoleVerdict），由其决定同步时点。

---

## 4. 裁定四：ABI 选型（64 位 SoC 与 32 位包）

### 4.1 已验证事实

- MT9667 为 4×A73 + 4×A53 的 64 位 SoC `[已验证事实，团队给定参数]`；用户当前装的是 32 位 leanback 包并用一会儿闪退 `[已验证事实，用户报障]`。
- 官方 5.8.7 同时提供 `arm64_v8a` 与 `armeabi_v7a` 两个 leanback 包，字节数 51412139 / 44768123 `[已验证事实，第 0.2 节]`。
- 32 位进程虚拟地址空间上限约 4GB（Linux `VMSPLIT_3G` 下用户态约 3GB）；64 位 Android 默认 39-bit VA，可达 512GB `[已验证事实，besthub / tsight 架构资料]`。
- Meta/Oculus 官方工程博客逐字：**「Most applications crash from memory pressure because the virtual address space gets fragmented, not because of lack of physical memory」**；64 位把地址空间扩到极大，基本消除虚拟地址空间碎片导致的 OOM `[已验证事实，https://developers.meta.com/horizon/blog/the-memory-benefits-of-64-bit-how-it-works/]`。
- 5.8.7 含 native 解码库（`libmpv.so` 等），`lib-*.aar` / runtime 模块按 ABI 分别提供 `[已验证事实，RuntimeModule.libraries() 与 module Release]`。

### 4.2 工程推断（**不是结论**）

`[工程推断]` 在**系统确实是 64 位**的前提下，64 位 leanback 包相对 32 位包有四条**机理上**可能降低长时间播放崩溃概率的路径：

1. 地址空间：32 位进程约 3~4GB VA，媒体应用长时间播放时 native heap、`.so` mmap、ashmem / MediaCodec buffer、GL/解码器映射叠加，容易因 VA 碎片在「物理内存还够」时分配失败；64 位几乎消除该约束。
2. native 库加载：64 位主包与 64 位 runtime 模块的 `libmpv.so` / `libplayer.so` 走同一 ABI，避免 32 位主进程加载 32 位 native 库时的地址布局挤压。
3. 解码器内存：4K 解码的输入/输出 buffer 与 surface 映射在 32 位 VA 中更拥挤，切源频繁时碎片更易累积（对应 AC-13~20 的切源 / 前后台场景）。
4. 寄存器与指令集：AArch64 有 31 个 GPR（AArch32 为 15 个），解码/图像处理路径更少寄存器溢出。

### 4.3 为什么**必须**实测、不得写成已验证结论

以下每一条都是 `[已验证事实]` 的「未知」，足以推翻上面的推断：

1. **系统 ABI 位数未知**。64 位 SoC 不等于 64 位 Android：需 `getprop ro.product.cpu.abilist` / `ro.product.cpu.abi` / `ro.zygote` 实机确认。若系统是 32 位，`arm64_v8a` 包直接 `INSTALL_FAILED_NO_MATCHING_ABIS`，装不上。QA / PM 在前序轮次已就此正式纠正过「由 CPU 位数推出系统位数」的错误，SPEC 第 10 节、第 13 节第 9/12 条保留该约束。
2. **闪退根因未取证**。可能是上游爬虫 Java 未捕获异常、runtime 模块缺失/签名不匹配、解码器硬解路径崩溃、LMK 回收，这些**与 ABI 位数无关**，换 64 位包不会改善。
3. **存在反例 `[已验证事实，PM 前序记录]`**：用户明确报过官方 arm64 包也闪退、换到 32 位包才勉强能用。这与「64 位更稳」的推断方向相反。
4. **32 位包体积更小**（44768123 B vs 51412139 B），在 3GB RAM 设备上安装/加载开销略有差异，方向不确定。
5. **无任何本机实测数据**。ACCEPTANCE.md 第 5 节明确实机稳定性为 `no-go / 未评级`；AC-31 的中性三组对照尚未执行。

### 4.4 裁定

`[已验证事实]` **主通道同时提供 4 个官方原包（含两个 leanback ABI），不预设任何一个为「更稳」**。`[工程推断]` 基于 4.2 的机理，可以在**发布说明**里给出「若系统确认 64 位，建议优先试 `leanback-arm64_v8a`」这样的**实验性建议**，但必须同时写明：这是工程推断、不是已验证结论，且以实机 `getprop` 与 AC-31 对照结果为准。

**禁止**的表述：「64 位包能解决闪退」「已验证 64 位更稳定」「推荐包 = arm64_v8a」。**不承诺修好闪退**。

---

## 5. 裁定五：主通道 / 实验通道分层建议

### 5.1 分层结构

| 维度 | 主通道（Main，默认开） | 实验通道（Experimental，默认关） |
| --- | --- | --- |
| 输入 | `FongMi/Release` 5.8.7 的 4 个官方原包 | 主通道产物的副本 + apktool 3.0.3 改造 |
| 动作 | 下载 -> 校验 -> 原样聚合 -> 发布 | 反编译 -> 改 Manifest -> 回编译 -> zipalign -> apksigner 重签（jmgo 密钥） -> 装机自检 |
| 签名 | **官方原签名，零改动** | jmgo 密钥重签（触发裁定二全部代价） |
| 产物 | 4 个官方 APK + `SHA256SUMS.txt` + `build-info.json` + 发布说明 | 二进制改造包，或**空** |
| 触发 | push / `workflow_dispatch` 默认 | 独立 feature flag / 显式 `workflow_dispatch` 输入，默认 `false` |
| 失败语义 | 下载失败 / 校验不通过 -> **构建失败**（这是唯一正确的信号，主通道不允许静默降级） | `continue-on-error`：失败**不阻断**主通道、不影响 Release |
| 空产物 | 不允许（4 包必须齐全，缺一即失败） | 允许为空，但**必须如实标注** |

### 5.2 主通道「必定可用」的边界（`[已验证事实]`）

「零改造保证 4 个原包必定可用」的准确含义是：**产物与官方发布二进制字节一致，因此可安装性、签名、覆盖安装、runtime 模块链路与官方完全相同**，不因我方流程引入新的不可用。它**不**包含「装上后不闪退」——用户当前官方 32 位包就闪退，这一点必须原样如实告知，不得用「主通道可用」暗示问题已解决。

主通道校验聚合的最小字段（承接 `build-contract.md` v2.0；原 `collect-apk.sh` 的 `build-info.json` 结构已由 `scripts/verify-upstream.py` 实现，该 shell 脚本已删除）：

- 每个包的：原始文件名、字节数、sha256、ABI、flavor（leanback / mobile）、下载 URL、官方 `apksigner verify --print-certs` 证书指纹。
- 批次级：run id、commit sha（本仓库 tag 5.8.7 若需）、聚合时间戳、4 包清单、来源 tag `5.8.7`。
- `SHA256SUMS.txt` 与产物一一对应；**不**把官方 `module` 资产 digest 写进主通道校验（主通道不改 runtime 链路，官方包自身会按需拉取）。
- 静态校验：`aapt dump badging` 取 `package` / `native-code` / `versionName` / `targetSdkVersion` / `launchable-activity`；`apksigner verify` 确认签名方案与证书指纹一致。

### 5.3 实验通道的三条硬纪律

1. **默认关闭**：必须由显式开关启用，不得在主通道 push 时顺带执行。
2. **失败不阻断**：改造 / 重签 / 装机自检任一失败，主通道产物照常发布；实验通道状态单独写入 `experimental-status.json`。
3. **产出为空必须如实标注**：状态只允许 `succeeded` / `failed` / `skipped` / `no-artifact` 四值，`no-artifact` 与 `failed` 必须带原因与日志路径。**禁止**把主通道产物复制到实验通道目录冒充成功、禁止把「未执行」写成 `skipped(成功)`、禁止生成空文件当产物。这与旧 README 第 45~46 行「`patches-applied.json` 记录 applied/skipped，不会静默假装成功」是同一条纪律，只是载体从补丁状态换成实验通道状态。

### 5.4 需 CI 验证清单（汇总，$P_0$ 为放行门槛）

| # | 事项 | 判定方式 | 关联裁定 |
| --- | --- | --- | --- |
| V1 | apktool 3.0.3 能否反编译 compileSdk 37 的 `leanback-arm64_v8a.apk` | `apktool d` 退出码 + `res/` 完整性 + `aapt2 dump resources` 条目数比对 | 一 / F1 |
| V2 | 回编译产物是否满足 arsc 未压缩 4 字节对齐、`.so` 页对齐 | `zipalign -c -v 4`、必要时 `zipalign -c -P 16 -v 4` | 一 / F2 |
| V3 | 改造前后资源 ID 与 dataBinding 引用是否一致 | `aapt2 dump resources` diff | 一 / F3 / F4 |
| V4 | 重签产物 `apksigner verify --verbose --print-certs` 是否含 v2/v3 | 命令输出 | 一 / F5、二 |
| V5 | 重签产物装机是否触发签名自校验崩溃 | 真机首次安装 + 冷启动 + 播放 60 秒 logcat | 二 / 代价 3 |
| V6 | 重签后官方 runtime 模块是否仍可用 | 装官方 `runtime-quickjs-*.apk` 后访问需解析的站点 | 二 / 代价 2（预期失败，用于证实约束） |
| V7 | 真机 `getprop ro.product.cpu.abilist` / `ro.zygote` | QA Phase 4 执行，本阶段不索取 | 四 |
| V8 | 64 位包在实机是否优于 32 位包 | AC-31 中性三组对照，不预设方向 | 四 |

> V5~V8 属 Phase 4 实机验收，按 SPEC 第 13 节第 9/12 条与全队终裁，**本阶段不向用户索取任何信息**、不把真机取证列为落盘门禁。

---

## 6. 证据索引

| 编号 | 结论 | 来源 |
| --- | --- | --- |
| E1 | 私有 media3 AAR 未开源 -> 源码重建不可行 | team-lead 方向变更调研（本文件第 0.1 节转述） |
| E2 | 官方 4 包文件名 / 字节数 / 下载前缀 | team-lead 核实；`https://github.com/FongMi/Release/releases/download/5.8.7/` |
| E3 | apktool 3.0.3 版本 / 发布日期 / 64 位 JDK / aapt2 / CVE | `https://www.apktool.org/`；`https://www.darknet.org.uk/2026/11/apktool-decompile-edit-rebuild-android-apk/` |
| E4 | API 37 支持在 Upcoming Release（#4214 / #4223 / #4220），稳定版仅到 36.1 | `https://apktool.org/docs/unreleased/` 逐字 |
| E5 | 3.x 砍 aapt1 只认 aapt2；`--no-compile-sdk-metadata` 兼容问题 | `http://www.redoapk.com/Detail.aspx?id=12898` |
| E6 | arsc 解码失败 / INVALID_APK / 签名顺序 / v1-only 拒装 | `https://www.sheratonhq.com/news/201303`；`https://www.tutorialpedia.org/blog/targeting-r-version-30-and-above-requires-the-resources-arsc-of-installed-apks-to-be-stored-uncompressed-and-aligned-on-a-4-byte-boundary` |
| E7 | `extractNativeLibs=false` 需 `zipalign -p` 否则 native 库解压失败 | `https://stackoverflow.com/questions/63204032/` |
| E8 | targetSdk 30+ 需 v2+；不同签名报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`；签名后不得改字节 | Android 11 行为变更；`https://sekin.in/how-to-fix-install_parse_failed_no_certificates-when-installing-a-modified-apk`；`https://appforshare.io/blog/android-app-signing-apk-aab-sideload` |
| E9 | 5.8.7 主 / leanback Manifest 属性（largeHeap / hardwareAccelerated / pageSizeCompat / BootReceiver / LEANBACK_LAUNCHER） | `https://raw.githubusercontent.com/FongMi/TV/4512b4c9f82534ff66acfde06ccdd68f35b074f0/app/src/main/AndroidManifest.xml` 与 `.../app/src/leanback/AndroidManifest.xml` 逐字 |
| E10 | runtime 模块与宿主同签名校验 `Invalid runtime signer` | `https://raw.githubusercontent.com/FongMi/TV/4512b4c9f82534ff66acfde06ccdd68f35b074f0/catvod/src/main/java/com/github/catvod/utils/RuntimeModule.java` 逐字 |
| E11 | 主 APK 源码层未发现签名自校验（0 命中，不等于不存在） | GitHub code search `GET_SIGNATURES` / `antiTamper` / `signatureCheck` / `checkSignature` repo:FongMi/TV |
| E12 | `hardwareAccelerated=false` 导致 TextureView 黑屏 / 播放器有声无画 | Android 官方 TextureView 文档语义；`https://blog.csdn.net/qq_36707431/article/details/120851722` |
| E13 | 32 位 4GB VA 上限 / 64 位 512GB / VA 碎片是 OOM 主因 | `https://developers.meta.com/horizon/blog/the-memory-benefits-of-64-bit-how-it-works/`；`https://www.besthub.dev/articles/analysis-of-android-virtual-memory-and-address-space-in-qq-music-karaoke-app-338a3eb7b66b` |
| E14 | 上游 `largeHeap=true` 且 QA 裁定不得作为修复项 | SPEC 第 3 / 13 节；ACCEPTANCE 第 4 节；本文件 E9 |

---

## 7. 变更记录

| 日期 | 变更 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-11-08 | v1.0 建立，5 点裁定齐备 | 私有 media3 AAR 未开源，源码重建不可行；用户拍板改走官方包兼容化路线 | 取代 `assembleLeanbackRelease` 源码编译路线；`SPEC.md` / `build-contract.md` 同步升版 |
