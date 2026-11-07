# 兼容性补丁清单

这些补丁由 `../scripts/apply-patches.py` 在 CI 内对克隆到固定 SHA 的上游 `FongMi/TV` 源码应用。
每个补丁都是**已核实的字面量替换**，不靠猜测；未命中目标的 required 补丁会让构建直接失败（硬门禁）。

| ID | 文件 | 是否必需 | 作用 |
| --- | --- | --- | --- |
| P-00 | `buildSrc/.../AbiApkPackaging.groovy` | 必需 | 移除 `VerifyMpvNativeTask` 校验。clean clone 不含 `libs/lib-mpvplayer-release.aar` / `lib-decoder-ffmpeg-release.aar`，原校验必然失败（F1）。移除后不影响出包，MPV 解码走系统/备用路径。 |
| P-01 | `app/build.gradle` | 必需 | `runtimeCatalog` 默认置空。首启不再向 GitHub 拉取模块目录，离线即可用；拉取失败给错误态而非闪退。 |
| P-03 | `app/src/leanback/AndroidManifest.xml` | 可选 | 用 `tools:node="remove"` 移除 `BootReceiver`，减少后台驻留进程被 LMK 回收引发的连锁不稳定。未命中则跳过，不阻断构建。 |

## 暂未纳入（下一迭代，待 CI 转绿 + 真机取证）

- **P-04 / P-05（Java 层稳定性）**：播放状态持久化（被 LMK 回收后恢复进度）、爬虫资源释放/生命周期收敛。需要先读取上游对应 Java 源再做字面量补丁，避免盲改导致编译失败；列入 Phase 4 实机验收后的加固项。
- **ABI 选择**：不做单变体。CI 恒定产出 `arm64_v8a` + `armeabi_v7a` 两个 leanback 包（上游 `splits.abi` 默认双 ABI 且 `universalApk=false`），由真机分别试装决定哪个稳定。
