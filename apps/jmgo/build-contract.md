# 构建契约 - 坚果 N1S 4K 兼容版 TVBox 客户端

> 文档版本：v2.0（方向变更后，2026-11-08 升版）
> 上位文档：`apps/jmgo/SPEC.md` v0.2（团队内部规格契约）
> 技术裁定：`apps/jmgo/docs/TECH-VERDICT.md` v1.0（5 点裁定，本契约的上游依据）
> 验收契约：`apps/jmgo/docs/ACCEPTANCE.md`（AC-01~AC-32，v1.1 顺延 AC-32）
> 状态：生效。本文件定义「官方 `FongMi/Release` 5.8.7 四包 -> 校验聚合 -> 原样发布」+「可选二进制兼容层」的全部技术约束。

> **方向变更声明（v2.0，效力高于下文一切历史条款）**：2026-11-08 核实 —— `FongMi/TV` 5.8.7 的 `app` 引用 52 个未开源的私有 `androidx.media3.*` 类，`FongMi/media` 全历史 26625 commit、另一分支、Google Maven、jitpack、`FongMi/Release` 的 `module` 目录均无对应 AAR，上游 `.gitignore` 的 `lib-*.aar` 证明私有定制 AAR 从未入库，**clean clone 源码重建不可行**。用户拍板改走「官方包兼容化」路线：主通道 = 官方 `FongMi/Release` 5.8.7 四包基线 + 校验聚合 + 零改造原样发布；实验通道 = 可选二进制兼容层（默认关闭）。完整论证见 `docs/TECH-VERDICT.md` 第 0.1 节。
>
> **下文 0~4 节为 v2.0 现行约束**。v0.1/v1.0 的下列条款**均为历史记录、已废止、不再是现行约束**：第 2 节「补丁目录（P001~P008，位置 `patches/jmgo-v1/`）」整张表（含 P006「本地缺 mpv/ffmpeg AAR 时跳过一致性校验 / REQUIRED / 已应用」）、上游检出 `git clone --filter=blob:none --no-checkout` → `git fetch --depth 1 <SHA>` → `git checkout FETCH_HEAD`、构建 `./gradlew :app:assembleLeanbackRelease`（只 leanback / 双 ABI 一次出两个包 / 不构建 mobile / 不做 universal）、`local.properties` 固定 jmgo keystore 重签、Gradle 9.7.1 / AGP 9.4.0 / JDK 21 / NDK / CMake、双源码基线兜底、`apply_patches.py` 与 `patches-applied.json` 的 13/13 hunk 干跑。其原文完整保存在 git HEAD（`git show HEAD:apps/jmgo/build-contract.md`）供溯源；本文件**保留 0~4 节编号骨架与契约定位**，逐节改写为现行口径，不整篇重写、不丢失编号。补丁与源码编译措辞的核对另见 `docs/TECH-VERDICT.md` 第 3.1 节。
>
> **结论分级**沿用 `docs/TECH-VERDICT.md` 第 0 节三级：`[已验证事实]` / `[工程推断]` / `[需 CI 验证]`，不得跨级引用。ABI 推荐为 `[工程推断]`，须实机 `getprop ro.product.cpu.abilist` / `ro.zygote` 与 AC-31 中性三组对照，不得写成已验证结论；**不承诺修好闪退**。

---

## 0. 契约地位

`build-contract.md` 定义构建侧技术约束；`.github/workflows/build-jmgo.yml` 必须逐条实现主通道；
`apps/jmgo/scripts/*` 是校验聚合的落盘实现。与 `SPEC.md` 冲突时以 `SPEC.md` 为准，与 `docs/TECH-VERDICT.md` 的技术裁定冲突时以裁定为准。本项目无服务端、无 REST API，故不写 `openapi.yaml`。

主通道 / 实验通道分层（裁定五）：

| 维度 | 主通道（默认开） | 实验通道（默认关） |
| --- | --- | --- |
| 输入 | 官方 `FongMi/Release` tag `5.8.7` 的 4 个原包 | 主通道产物副本 + apktool 3.0.3 改造 |
| 动作 | 下载 -> 校验 -> 原样聚合 -> 发布 | 反编译 -> 改 Manifest -> 回编译 -> zipalign -> apksigner 重签 -> 装机自检 |
| 签名 | 官方原签名，零改动 | jmgo 密钥重签（触发裁定二全部代价） |
| 失败语义 | 下载/校验不通过即构建失败（不允许静默降级） | `continue-on-error`，不阻断主通道 |
| 空产物 | 不允许（4 包缺一即失败） | 允许，但必须如实标注 `no-artifact` / `failed` / `skipped` |

> 该表为裁定五的**契约目标**；当前落盘实现中实验通道仍为占位、`experimental-status.json` 未产出，实况见第 3 节第 10 条 `[已验证事实]`。两者不可混读。

**已废止的 v1.0 契约对象**（历史，不再引用）：`apps/jmgo/patches/jmgo-v1/*`（P001~P008）、`apply-patches.py` 补丁应用、`patches-applied.json`、`collect-apk.sh`。v2.0 主通道不克隆上游、不施加任何源码补丁；校验聚合实现为 `apps/jmgo/scripts/verify-upstream.py`。

> **文档与落盘实现的一致性口径**：本契约区分「契约要求」与「当前已实现」，避免文档声称已实现而实际没有。`.github/workflows/build-jmgo.yml` 与 `apps/jmgo/scripts/verify-upstream.py` 已落盘的产物与断言，本文按 `[已验证事实]` 如实记录；尚未接入的部分（如实验通道 `experimental-status.json`）标 `[需 CI 验证 / 待接入]`。凡本文与落盘实现或上位 `SPEC.md` 不一致处，均在对应条文就地标注并上报 team-lead，不静默抹平。

## 1. 基线锚定（官方 Release 产物，非源码 SHA）

| 项 | 值 | 核实来源 |
| --- | --- | --- |
| 基线来源 | 官方 `FongMi/Release` tag `5.8.7` | team-lead 核实；下载前缀 `https://github.com/FongMi/Release/releases/download/5.8.7/` |
| 产物数量 | 4 个完整 APK：leanback/mobile × arm64_v8a/armeabi_v7a | 官方 Release |
| 基线字节数 | leanback-arm64_v8a 51412139 / leanback-armeabi_v7a 44768123 / mobile-arm64_v8a 51326563 / mobile-armeabi_v7a 44682547 B | team-lead 核实，聚合时逐包校验 |
| 签名 | **官方原签名**（主通道零改造、不重签）；`keystore/jmgo.p12.b64` 仅实验通道重签用 | 裁定二 |
| 应用属性（只读事实，非改造目标） | versionName 5.8.7 / targetSdk 37 / minSdk 24 / `com.fongmi.android.tv` / `largeHeap=true` / `hardwareAccelerated=true` / `pageSizeCompat=enabled` / `LEANBACK_LAUNCHER` 已声明 | 上游源码 @ `4512b4c` 逐字；产物以 `aapt2 dump badging`（回退 `aapt`）为准 |
| 校验工具 | `unzip -t`、`aapt2 dump badging`（回退 `aapt`）、`apksigner verify --verbose --print-certs`、`sha256sum`；驱动脚本 `apps/jmgo/scripts/verify-upstream.py`（`verify` / `package` / `list-assets` / `self-test`） | Android SDK build-tools `34.0.0`；`collect-apk.sh` 已删除、不再引用，输入为官方 4 包 |

> 说明：`4512b4c9f82534ff66acfde06ccdd68f35b074f0`（`FongMi/TV` fongmi 分支 HEAD）在 v2.0 中**仅作只读事实溯源**，不再是构建输入。官方 Release 二进制与该 commit 是否严格对应未逐字核实，标 `[需 CI 验证]`——不影响主通道「原样分发官方包」的正确性。

## 2. 校验聚合清单（替代 v1.0 的 P001~P008 补丁目录）

主通道**零改造**，不存在补丁与补丁应用状态。本节保留原「清单」定位与 C-01~C-08 编号，内容改为聚合期必须逐项执行并留痕的校验动作，逐项对齐 `apps/jmgo/scripts/verify-upstream.py` 的实际断言 `[已验证事实]`：

| 编号 | 校验动作 | 失败语义 | 状态 |
| --- | --- | --- | --- |
| C-01 | 逐包机械校验，结果写入 **`upstream-verify.json`**：文件存在 / 体积下限 `>30MB` / 字节数与第 1 节四个数字精确一致（零偏差，防下错版本或 asset 被替换）/ `unzip -t` 完整性（无 unzip 时回退 `zipfile.testzip`）/ `aapt2 dump badging` 校验 `package=com.fongmi.android.tv` 与 `versionName=5.8.7` / 文件名声明的 `nativeAbi` 与 `badging native-code` + APK 内 `lib/<abi>/` 目录并集一致 | 任一断言失败 -> 写出含失败明细的 JSON、stderr 打印 `FAIL <assetName>: <reason>`、脚本非零退出 -> 构建失败 | 必需 |
| C-02 | 逐包 `sha256sum`，写 `SHA256SUMS.txt`，与产物一一对应并跑 `sha256sum -c`；复制/重命名后二次 sha256 复核，确认 APK 字节与官方 asset 完全相同 | 缺失/不符即失败 | 必需 |
| C-03 | `apksigner verify --verbose --print-certs`：解析签名证书 SHA-256 指纹与 v2/v3 方案；**四包指纹一致性** `signingCertificateSha256Consistent`，任一缺失或不一致即把 4 包全部标 `fail` | 指纹不一致/仅 v1/解析失败即失败 | 必需 |
| C-04 | `aapt2 dump badging`（缺 aapt2 时回退 `aapt`）：确认 `package` / `native-code` / `versionName` / `targetSdkVersion` / `launchable-activity`(LEANBACK_LAUNCHER) | 与基线不符即失败 | 必需 |
| C-05 | 生成 `build-info.json`：来源 tag `5.8.7` / run id / 本仓库 commit sha / short sha / 4 包各自 sha256 + 字节数 + ABI + flavor + 下载 URL + 官方证书指纹 / `deliveryMode=upstream-aggregate` / `signingMode=upstream-original` / `compatPatchStatus` / 聚合时间戳 | 生成失败即失败 | 必需 |
| C-06 | 交付清单门禁 + 发布说明：4 个 APK + `SHA256SUMS.txt` + `build-info.json` + `upstream-verify.json` + `docs/FIELD-TEST.md` 缺一即失败；发布说明含 4 包清单 + 保持官方签名可覆盖安装 + 不承诺修好闪退 + ABI 选择须实机 `getprop` / AC-31 对照（工程推断，非结论） | 缺项即失败 | 必需 |
| C-07 | 官方 `module` 资产 digest | **不纳入主通道校验**（主通道不改 runtime 链路） | 排除 |
| C-08 | 实验通道 `experimental-status.json`（四值 `succeeded`/`failed`/`skipped`/`no-artifact`） | 允许为空，但不得静默假装成功 | 仅实验通道；**当前落盘为占位、尚未产出，见第 3 节第 10 条** |

> `upstream-verify.json` 字段（`schemaVersion: 1`，`[已验证事实]`）：批次级 `generatedAt` / `upstreamRepo` / `upstreamTag` / `sourceUrlPrefix` / `expectedPackage` / `expectedVersionName` / `minSizeBytes` / `buildToolsVersion` / `tools` / `signingCertificateSha256Consistent` / `signingCertificateSha256` / `packageCount` / `allPassed` / `packages[]`；逐包 `assetName` / `sourceUrl` / `flavor` / `abi` / `nativeAbi` / `expectedSizeBytes` / `sizeBytes` / `sha256` / `zipIntegrityMethod` / `badgingTool` / `package` / `versionName` / `targetSdkVersion` / `nativeCode` / `libAbis` / `nativeCodeObserved` / `checks{}` / `failures[]` / `status(pass|fail)` / `signingCertificateSha256` / `signatureSchemes{}`。`allPassed=false` 时 `package` 子命令拒绝打包。

> **诚实声明**：v1.0 的「13/13 hunk applied、`patches-applied.json` 不静默假装成功」是源码补丁时代的产物，已废止。v2.0 把同一条纪律落到聚合校验（C-01~C-06 任一失败即构建失败）、`verify-upstream.py self-test` 的三个伪造包场景（all-missing / tiny-fake-apk / exact-size-non-zip 均证明失败必非零退出且写出诊断 `[已验证事实]`）与实验通道状态（C-08 四值如实标注）：**不生成空文件当产物、不把主通道产物复制进实验通道冒充成功、不把「未执行」写成成功**。

## 3. CI 技术契约（workflow 必须实现）

1. 触发：`push` 到 `apps/jmgo/**` 或 `.github/workflows/build-jmgo.yml`；另含 `workflow_dispatch`，输入 `enable_compat_patch`（boolean，**默认 `false`**）。v1.0 的 `upstream_sha` / `tv_runtime_catalog` 输入（clone 上游 SHA / 注入空 catalog）**已废止**，不再需要。
2. 环境：`ubuntu-latest`，`timeout-minutes: 30`，`permissions: contents: write`，`concurrency` 组 `build-jmgo`。主通道**不需要** Gradle / NDK / CMake / `platforms;android-37` / `sdkmanager` 装 SDK 37（无编译步骤）；仅需 JDK 17（`apksigner` 运行时）、Python 3.12、Android SDK build-tools `34.0.0` 的 `apksigner` 与 `aapt2`（缺失时 `aapt` 回退）、`curl` / `sha256sum` / `unzip`。实验通道若启用，另需 apktool 3.0.3 + 64 位 JDK 17+。
3. 获取：从 `SOURCE_URL_PREFIX=https://github.com/FongMi/Release/releases/download/5.8.7/` 下载 4 个固定文件名官方原包（`curl -fL --retry 3`，`test -s` 非空门禁）；记录每个文件的 HTTP 状态、字节数、下载 URL。**禁止回退其它 tag 或版本**。
4. 校验：`python3 apps/jmgo/scripts/verify-upstream.py verify --apk-dir ... --out jmgo-out/upstream-verify.json --android-home ... --build-tools ...`，执行第 2 节 C-01~C-04；任一断言失败 -> 脚本非零退出 -> `set -euo pipefail` 终止构建并打印失败包名与不符项，不静默补包、不降级到「取任一可用包」。脚本自带 `self-test`（三场景）证明失败必终止且写出诊断 `[已验证事实]`。
5. 签名：主通道**不签名、不重签**（保持官方原签名）。v1.0 的「解码 `keystore/jmgo.p12.b64` -> 写上游根 `local.properties` -> 固定密钥每次构建同一把」**已废止**；`keystore/jmgo.p12.b64` 与 `apksigner sign` 仅在实验通道改造后使用，顺序严格为 `apktool b` -> `zip -0` 修 `resources.arsc` -> `zipalign -p -f 4` -> `apksigner sign`（v2/v3），签名后不得再改字节。
6. catalog：主通道**不注入** `runtimeCatalog`，官方包按官方机制行为；离线可用性不作为本期承诺（SPEC 第 9 节）。
7. 构建步骤：**无** `./gradlew :app:assembleLeanbackRelease`。主通道产物即下载校验后的 4 个官方原包，不重打包、不裁剪、不做 universal、**不改任何 APK 字节**。聚合期由 `verify-upstream.py package` 统一重命名为 `tvbox-jmgo-{flavor}-{abi}-{tag}-{shortSha}.apk`（`shutil.copyfile` + 复制后 sha256 复核保证字节一致 `[已验证事实]`）。**口径冲突已闭环（team-lead 2026-11-08 裁决）**：`SPEC.md` 第 5 节原写「官方原名、文件名保持原样」，与本落盘实现不一致。裁决保留重命名分发 —— APK 二进制字节与官方原包完全一致、官方原签名不变，覆盖安装看「包名 + 签名」而非文件名；溯源靠 `signingMode` / 官方证书指纹 / `assetName` / `sourceUrl`，不靠文件名。`SPEC.md` 第 5 节已据此改写，workflow、`verify-upstream.py`、README、ACCEPTANCE、PRD 六处与本节现已统一，冲突关闭。
8. 打包：`python3 apps/jmgo/scripts/verify-upstream.py package`，读取 `upstream-verify.json`，`allPassed` 为真才允许打包；产出 `SHA256SUMS.txt` 与 `build-info.json`，并对 `SHA256SUMS.txt` 跑 `sha256sum -c`。**`collect-apk.sh` 已删除，不再是本契约引用的实现**。
9. 产物：交付清单门禁断言 4 个 APK + `SHA256SUMS.txt` + `build-info.json` + `upstream-verify.json` + `docs/FIELD-TEST.md` 齐全（缺一即失败）；`actions/upload-artifact@v4`（`if-no-files-found: error`，保留 30 天）；push 到 `main` 时 `softprops/action-gh-release@v2` 发布到 Releases，发布说明含来源 URL、包名 / versionName / 官方原签名可覆盖安装、校验文件清单、试装手册与 `compatPatchStatus: not-applied`。
10. 实验通道落盘现状 `[已验证事实]`：当前 workflow 的 `Experimental compat patch channel` 步骤为**占位**，只打印 `enable_compat_patch` 请求值与「compat patch disabled (pending TECH-VERDICT)」，无论 dispatch 是否开启都**不执行**反编译 / 重打包 / 重签；`build-info.json` 恒写 `compatPatchStatus: "not-applied"`，**不产出** `experimental-status.json`。因此 C-08 的四值状态文件与 `continue-on-error` 属裁定五的**契约目标** `[需 CI 验证 / 待接入]`，接入前不得写成已实现。接入时必须满足裁定五三条硬纪律：默认关闭（显式开关，不得在主通道 push 时顺带执行）、失败不阻断主通道与 Release、产出为空如实标注（四值 + 原因 + 日志路径）；禁止把主通道产物复制进实验通道目录冒充成功、禁止把「未执行」写成 `succeeded`、禁止生成空文件当产物。

## 4. 关键约束与诚实声明

- **结论分级**：全文沿用 `docs/TECH-VERDICT.md` 第 0 节三级 —— `[已验证事实]`（官方一手来源 / 逐字核实的文件与命令输出）、`[工程推断]`（通用工程机理，未在本机实测）、`[需 CI 验证]`（依赖尚未执行的构建或真机动作），不得跨级引用。构建侧整体当前为「未实跑」`[需 CI 验证]`（ACCEPTANCE 第 5 节标 no-go / 未评级）；ABI 推断不得写成结论，**不承诺修好闪退**。
- **4 包恒定齐发、零改造**：主通道恒定聚合官方 `FongMi/Release` 5.8.7 的 4 个原包，字节一致、保持官方原签名，不预设任何 ABI/flavor 为「更稳」。芯片 64 位不等于系统 64 位；ABI 推荐是 `[工程推断]`，须实机 `getprop ro.product.cpu.abilist` / `ro.zygote` 与 AC-31 中性三组对照，不得写成已验证结论（裁定四）。
- **主通道不重签（硬约束）**：v1.0 的「固定 jmgo keystore 重签」**不再适用于主通道**。`[已验证事实]` v2/v3 签名覆盖整个 APK 字节，改包必然改变签名，我方不持有 FongMi 发布私钥、无法用原证书重签；`catvod/.../RuntimeModule.java` 的 `RuntimeModule.verifyPackage()` 逐字比较宿主与 runtime APK 的签名，`expected != actual` 即抛 `IOException("Invalid runtime signer")`，`require()` 再包成 `IllegalStateException("Invalid <Module> module")` —— 重签会让官方 **6 类 runtime 模块（Python / Node.js / QuickJS / MPV / Thunder / BD-J）全线失效**；且首次必须卸载官方版（`INSTALL_FAILED_UPDATE_INCOMPATIBLE`）、丢收藏 / 历史 / 播放进度，与 SPEC 第 13 节第 16 条冲突。这是保持官方原签名的硬约束，见 `docs/TECH-VERDICT.md` 第 2.3 节；jmgo 重签仅实验通道可选、默认关闭（裁定二）。
- **不改 `android:largeHeap` / 不关硬件加速**：上游已 `largeHeap=true`（「加」是 no-op，且属 QA 防假修复项）、`hardwareAccelerated=true`（关闭会导致 TextureView 播放器黑屏，负收益）。验收仍按 `heapgrowthlimit × 80%` 从严（裁定三）。
- **不引入 `ApplicationExitInfo`**（API 31+，本机 API 30）。
- **不索取用户信息**：落盘不要求 getprop / APK 文件名 / MD5 / 留出集授权；这些留给 Phase 4 实机验收（SPEC 第 13 节第 9/12 条终裁继续有效）。
- **取消双源码基线兜底**：v1.0「A 基线 `FongMi/TV` / B 基线 `q215613905/TVBoxOS`、连续两次失败切 B」已废止（A 因私有 AAR 不可重建，B 亦不采用）。v2.0 兜底语义改为「主通道恒定可用 + 实验通道可弃用」。
- **apktool 实验通道的已知门槛** `[已验证事实/需 CI 验证]`：3.0.3 稳定版 aapt2 仅 API 36.1，5.8.7 为 compileSdk 37，`Could not decode arsc` / `INSTALL_FAILED_INVALID_APK` / 资源 ID 重排 / native 库页对齐 / 签名块失效 五类失败模式见 `docs/TECH-VERDICT.md` 第 1.3 节；每个实验项须按裁定五第 5.4 节 V1~V6 验证。
- **不承诺修好闪退**：主通道产物与官方二进制字节一致，用户当前官方 32 位包正是闪退对象，主通道不引入任何稳定性变化。「4 包必定可用」仅指可安装 / 可覆盖 / 可核验，不等于不闪退；真正的根因定位依赖 Phase 4 实机机械证据（logcat / DropBox / bugreport、AC-01~AC-31）。工程推断不得写成事实。

## 5. 变更记录

| 日期 | 变更 | 原因 | 影响范围 |
| --- | --- | --- | --- |
| 2026-11-07 | v1.0 建立（精简版，源码编译契约） | Phase 2/3 落盘 | 全流程起点（历史） |
| 2026-11-08 | **v2.0 方向变更**：0~4 节逐节改写为「官方四包基线 + 校验聚合 + 可选二进制兼容层」；新增第 5 节变更记录 | **私有 media3 AAR 未开源（52 个类无源码，全历史/分支/Google Maven/jitpack/module 目录均无对应 AAR），clean clone 源码编译不可行；用户拍板改走官方包兼容化** | 0/1/2/3/4 节全部；新增第 5 节；与 `SPEC.md` v0.2、`docs/TECH-VERDICT.md` v1.0 同步 |
| 2026-11-08 | **v2.0 修订（对齐落盘实现）**：头部补「方向变更声明（v2.0，效力高于下文一切历史条款）」并逐字点名 P001~P008 / clone / `assembleLeanbackRelease` / 固定 keystore 重签为已废止历史；C-01~C-08 细化到 `verify-upstream.py` 断言项；补 `upstream-verify.json` 字段清单、`unzip -t`、体积下限、四包签名指纹一致性、交付清单门禁；清除 `collect-apk.sh` 悬空引用；登记产物命名与 `SPEC.md` 第 5 节冲突；标注实验通道当前为占位、`experimental-status.json` 尚未产出；补结论分级三级口径 | 交叉一致性预检发现契约与 `.github/workflows/build-jmgo.yml` / `apps/jmgo/scripts/verify-upstream.py` 落盘实现存在产物字段、断言项与命名差距；补齐后消除悬空引用 | 头部声明、第 0/1/2/3/4 节；**不触碰** `SPEC.md` / `TECH-VERDICT.md` / README / workflow / scripts |
