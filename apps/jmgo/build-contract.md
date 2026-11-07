# 构建契约 - 坚果 N1S 4K 兼容版 TVBox 客户端

> 文档版本：v1.0（精简版，对应 Phase 2 / 3 落盘）
> 上位文档：`apps/jmgo/SPEC.md` v0.1（团队内部规格契约，用户已确认）
> 验收契约：`apps/jmgo/docs/ACCEPTANCE.md`（AC-01~AC-31）
> 状态：生效。本文件定义「上游源码 → CI → 两个可安装 APK」的全部技术约束。

---

## 0. 契约地位

`build-contract.md` 定义构建侧技术约束；`.github/workflows/build-jmgo.yml` 必须逐条实现；
`apps/jmgo/scripts/*` 是落盘实现；`apps/jmgo/patches/jmgo-v1/*` 是具体补丁。
与 `SPEC.md` 冲突时以 `SPEC.md` 为准。本项目无服务端、无 REST API，故不写 `openapi.yaml`。

## 1. 上游锚定（已逐字核实于 SHA `4512b4c9f82534ff66acfde06ccdd68f35b074f0`）

| 项 | 值 | 核实来源 |
| --- | --- | --- |
| 仓库 / 分支 | `FongMi/TV` @ `fongmi` 分支 HEAD | GitHub API |
| versionName | 5.8.7 | `app/build.gradle` |
| Gradle / AGP / buildTools | 9.7.1 / 9.4.0 / 37.0.0 | `gradle-wrapper.properties` / `gradle/libs.versions.toml` |
| compileSdk / targetSdk / minSdk | 37 / 37 / 24 | `gradle/libs.versions.toml` |
| 产物命名 | `leanback-<abi>.apk`（buildSrc 重命名） | `AbiApkPackaging.groovy` |
| splits | `arm64-v8a`,`armeabi-v7a`；`universalApk=false` | `app/build.gradle` |
| 签名读取 | `local.properties` 的 storeFile/keyAlias/keyPassword/storePassword | `app/build.gradle` |
| runtime catalog 占位 | `manifestPlaceholders.runtimeCatalog = gradleProperty('tvRuntimeCatalog').getOrElse(...)` | `app/build.gradle` |

## 2. 补丁目录（P001~P008，位置 `patches/jmgo-v1/`）

| 补丁 | 目标文件 | 作用 | 必需性 | 实测结果 |
| --- | --- | --- | --- | --- |
| P001 | `app/build.gradle` | catalog 地址支持 gradle 属性 / 环境变量三级解析 | best-effort | 已应用 |
| P002 | `app/src/leanback/AndroidManifest.xml` | 关闭 `BootReceiver` 与 `DLNARendererService` | best-effort | 已应用（2 hunk） |
| P003 | `app/src/main/AndroidManifest.xml` | 关闭 `UpdateService` 前台服务 | best-effort | 已应用 |
| P004 | `DecodeSetting/PlayerSetting/PreloadSetting/Setting.java` | 首次启动默认更保守 | best-effort | 已应用（5 hunk） |
| P005 | `catvod/.../Spider.java` | `destroy()` 补做对话框挂起请求释放 | best-effort | 已应用 |
| P006 | `buildSrc/.../AbiApkPackaging.groovy` | 本地缺 mpv/ffmpeg AAR 时跳过一致性校验 | **REQUIRED** | 已应用 |
| P007 | `settings.gradle` | 剪掉 nodejs/chaquo/quickjs/thunder，省去 NDK/CMake | best-effort | 已应用 |
| P008 | `app/build.gradle` | 显式 `storeType "pkcs12"` | best-effort | 已应用 |

> 实测：在干净检出（仅含上述 10 个上游文件）上运行 `apply_patches.py`，13/13 hunk 全部 `applied`，0 skipped，0 failed。
> `patches-applied.json` 记录每个补丁状态，**不会静默假装成功**。

## 3. CI 技术契约（workflow 必须实现）

1. 触发：push 到 `apps/jmgo/**` 或本文件；另含 `workflow_dispatch`（可覆盖 `upstream_sha` / `tv_runtime_catalog`）。
2. 环境：`ubuntu-latest`；`setup-java` JDK 21 (temurin)；Python 3.12；`android-actions/setup-android` 后
   `sdkmanager "platforms;android-37" "build-tools;37.0.0"`。
3. 上游检出：`git clone --filter=blob:none --no-checkout` → `git fetch --depth 1 <SHA>` → `git checkout FETCH_HEAD`。
4. 补丁：`python apps/jmgo/scripts/apply_patches.py --upstream <dir> --patches-dir apps/jmgo/patches/jmgo-v1`。
5. 签名：解码 `apps/jmgo/keystore/jmgo.p12.b64` → p12；写入上游根 `local.properties`（storeFile/storePassword/keyAlias/keyPassword）。
   固定密钥，每次构建同一把，保证覆盖安装。
6. catalog：构建传 `-PtvRuntimeCatalog=`（空）→ 首启不联网拉清单，不依赖 GitHub。
7. 构建：`./gradlew :app:assembleLeanbackRelease`（只 leanback，双 ABI 一次出两个包；不构建 mobile、不做 universal）。
8. 收集：`collect_apk.py` 从 `app/build/outputs/apk/leanback/release/` 取两个 APK，重命名为
   `tvbox-jmgo-leanback-{abi}-5.8.7-<commit8>.apk`，计算 sha256，跑 `aapt2` / `apksigner` 静态校验，
   产出 `SHA256SUMS.txt` 与 `build-info.json`。
9. 产物：upload-artifact `tvbox-jmgo-apks`；push 到 `main` 时 `softprops/action-gh-release`（continue-on-error）发布到 Releases。

## 4. 关键约束与诚实声明

- **双 ABI 恒定产出**：芯片 64 位 ≠ 系统 64 位；CI 固定出 `arm64_v8a` 与 `armeabi_v7a` 两个包，由用户实机试装决定用哪个。
- **不加大堆**：绝不改 `android:largeHeap`（上游已 `true`），验收按 `heapgrowthlimit × 80%` 从严。
- **不引入 `ApplicationExitInfo`**（API 31+，本机 API 30）。
- **不索取用户信息**：Phase 2/3 落盘不要求 getprop / APK 文件名 / MD5 / 留出集授权；这些留给 Phase 4 实机验收。
- **双基线兜底（状态：半实现）**：A 基线 = `FongMi/TV` 5.8.7（已实现）；B 基线 = `q215613905/TVBoxOS`（未实现）。
  `workflow_dispatch` 的 `upstream_sha` 输入可指向 B 基线做手动验证，但**自动切换（连续两次失败→切 B）未在本版 workflow 中落地**，
  理由：B 基线构建结构与签名配置未经核实，盲目自动切换可能二次失败。当前优先保证 A 基线一次跑通；B 基线作为手动应急路径保留。
- **本版本是「降低闪退概率」的兼容性构建，不是彻底修复**：真正的根因定位依赖 Phase 4 实机日志证据（logcat / DropBox / bugreport）。
