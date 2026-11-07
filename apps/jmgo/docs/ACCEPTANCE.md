# 验收契约 - 坚果 N1S 4K 高亮版兼容版 TVBox 客户端

> 文件：`apps/jmgo/docs/ACCEPTANCE.md`
> 版本：v1.0（精简版，AC 编号体系锁定为 AC-01~AC-31，由 QA 维护）
> 上位契约：`apps/jmgo/SPEC.md`（团队内部规格契约）
> 状态：AC 契约冻结；阈值已签字锁定
> 适用范围：仅坚果 N1S 4K 高亮版（国行 J31-8K2）一台真机

---

## 0. 文档控制

### 0.1 基线锚定

| 项 | 值 |
| --- | --- |
| 构建源码基线 | `FongMi/TV` fongmi 分支 @ `4512b4c9f82534ff66acfde06ccdd68f35b074f0`（5.8.7） |
| 官方产物参考基线 | `FongMi/Release` 5.8.7（arm64_v8a / armeabi_v7a） |
| 包名 | `com.fongmi.android.tv` |
| 产物 | `tvbox-jmgo-leanback-arm64_v8a-5.8.7-<短哈希>.apk` 与 `tvbox-jmgo-leanback-armeabi_v7a-5.8.7-<短哈希>.apk` |
| 溯源文件 | `build-info.json`（run id / commit sha / 两个 APK 的 sha256 / 构建时间戳 / ABI）、`SHA256SUMS.txt` |
| 目标系统 | Android 11 / API 30，MT9667，3GB RAM / 64GB ROM，无 Root，无网口 |

### 0.2 目标设备

国行型号 **J31-8K2** = 坚果 N1S 4K 高亮版，蓝牙 + 红外 + 语音遥控，USB 3.0 ×1，**无网口**，长测走 Wi-Fi ADB。

## 1. 只认的证据（机械证据，不认主观描述）

| 证据 | 采集方式 |
| --- | --- |
| 原始日志 | `adb logcat -b all -v threadtime` 全量落盘，本地受限保存，仅 QA 可访问，不自动上传 |
| 零崩溃标记 | DropBox `data_app_crash` / `data_app_anr` / `data_app_native_crash` / `SYSTEM_TOMBSTONE` 为空 |
| PID 不变量 | 主进程 PID 在观测窗口内稳定或按预期重启，无静默退出 |
| 内存曲线 | `dumpsys meminfo <pkg>` 周期性采样，绘制 PSS / Java Heap 曲线 |

**不认**：「我觉得修好了」「不卡了」「没弹停止运行框」。

## 2. 死因三类（区分后再归因）

1. **低内存回收（lmkd）**：`am_low_memory` / `Low on memory` / kill 日志；非崩溃但表现为「退回桌面 / 重开」。
2. **native 崩溃**：`tombstone` / `SIGSEGV` / `abort`；`data_app_native_crash`。
3. **Java 未捕获异常**：`customactivityoncrash` 的 `:error_activity` 新进程 + 原进程被杀；`data_app_crash`。

## 3. 锁定阈值（不得为换绿调低）

| 参数 | 锁定值 |
| --- | --- |
| 连续播放 | 60 分钟 = P0 阻断门槛；120 分钟 = P1 加固线（Phase 4 至少 1 次） |
| 线路切换 | ≥20 次，跨 ≥3 个不同站点/线路类型，禁止同一线路刷次数 |
| 前后台切换 | ≥10 次，含 ≥1 次切出停留 >5 分钟再返回 |
| TOTAL PSS | ≤512MB；基线本身超标则判基线不合格、换轻量基线，不得调高阈值 |
| Java Heap | ≤ `heapgrowthlimit` 的 80% |
| 内存净增长 | 60 分钟内 ≤50MB 且 GC 后回落（最关键稳定性指标） |
| 重复轮次 | k≥3，跨不同冷启动与时段，pass^k 全绿 |
| 首次导入配置 | 30 秒内出现站点列表或明确错误态 |

## 4. AC 编号体系（概述，明细由 QA 维护 AC-01~AC-31）

按能力域分组，编号唯一、不得与 PM 旧 AC1~AC8 混用：

- **AC-01~AC-08 构建与产物**：CI 成功产出两个 APK；sha256 可追溯；`aapt`/`apksigner` 静态校验通过；包名 / ABI / versionName / targetSdk / LEANBACK_LAUNCHER 正确；固定签名可覆盖安装。
- **AC-09~AC-12 安装与首启**：双 ABI 分别可安装；首启不崩 / 不白屏 / 不静默退出；runtime 模块离线可达或给明确提示；30 秒内出站点列表或错误态（D-01 兜底口径）。
- **AC-13~AC-20 播放稳定性**：连续 60 分钟不闪退（P0）；120 分钟加固（P1）；≥20 次切源跨 ≥3 站点；≥10 次前后台切换；播放位置被回收后可恢复。
- **AC-21~AC-25 内存**：TOTAL PSS ≤512MB；Java Heap ≤ heapgrowthlimit×80%；60 分钟净增长 ≤50MB 且回落；k≥3 轮一致。
- **AC-26~AC-28 兼容与合规**：沿用现有 `zijian.json` 可加载；港澳台/国外/地方频道分组不被破坏；不引入 `ApplicationExitInfo`；不加大堆。
- **AC-29~AC-31 取证与对照**：原始日志 + 零崩溃标记 + PID 不变量 + 内存曲线齐备；**中性三组对照**（官方 arm64 / 官方 armeabi-v7a / 用户当前包，同机各 60 分钟统一取证），不预设「装错 32 位包」为根因方向；日志脱敏前后 sha256 与行数差留痕。

## 5. 当前评级

- 构建侧（Phase 3）：A 基线已实现并通过本地补丁干跑验证（13/13 hunk 应用）。**未评级**——需等首次 GitHub Actions 实跑产出 APK。
- 实机稳定性（Phase 4）：**no-go / 未评级**——尚无实机机械证据。本版本是「降低闪退概率」的兼容性构建，不是已验证修复。
- 若首次 CI 连续两次失败，按 SPEC 决策切 B 基线（`q215613905/TVBoxOS`，手动 `workflow_dispatch` 验证，自动切换待落地）。
