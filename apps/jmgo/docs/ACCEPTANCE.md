# 验收契约 - 坚果 N1S 4K 高亮版兼容版 TVBox 客户端

> 文件：`apps/jmgo/docs/ACCEPTANCE.md`
> 版本：v1.1（基线变更；AC 编号体系锁定为 AC-01~AC-31，顺延 AC-32，由 QA 维护）
> 上位契约：`apps/jmgo/SPEC.md`（团队内部规格契约）
> 状态：AC 契约冻结；阈值已签字锁定
> 适用范围：仅坚果 N1S 4K 高亮版（国行 J31-8K2）一台真机

---

## 0. 文档控制

> **基线变更 v1.1（2026-11-08，team-lead 派发，QA 执行）**
> 原因：`FongMi/TV` 源码重建路线已证伪——上游依赖 52 个从未开源的私有 media3 类，`FongMi/media` 全历史无这些类，作者私有 AAR 未入库，本仓库无法从源码编译出可运行产物。经用户拍板改走「官方包兼容化」：CI 直接聚合官方 `FongMi/Release` 5.8.7 的 4 个已编译完整包，做机械校验后发布。
> 影响范围：仅 0.1 基线锚定表、第 4 节产物数量与签名表述、第 5 节构建侧评级、顺延 AC-32、第 6 节变更记录。**第 3 节锁定阈值一字未降；AC-01~AC-31 编号体系与条款不动。**
> 本轮核心用户价值：让「用一会儿随机闪退」变成可诊断、可对照、可归因（见 `docs/FIELD-TEST.md`），而不是编译补丁。

### 0.1 基线锚定

| 项 | 值 |
| --- | --- |
| 上游产物基线 | 官方 `FongMi/Release` 5.8.7 的 **4 个已编译完整包**（`leanback` / `mobile` × `arm64_v8a` / `armeabi_v7a`），官方原签名 |
| 交付形态 | 官方产物聚合 + 机械校验 + 发布；**不是源码编译产物，不含源码补丁** |
| 包名 | `com.fongmi.android.tv` |
| 产物 | `tvbox-jmgo-{flavor}-{abi}-5.8.7-<短哈希>.apk`，共 4 个：`tvbox-jmgo-leanback-arm64_v8a-5.8.7-<短哈希>.apk`、`tvbox-jmgo-leanback-armeabi_v7a-5.8.7-<短哈希>.apk`、`tvbox-jmgo-mobile-arm64_v8a-5.8.7-<短哈希>.apk`、`tvbox-jmgo-mobile-armeabi_v7a-5.8.7-<短哈希>.apk` |
| 签名 | 沿用官方原签名，与用户现装官方 5.8.7 32 位包同签名，可直接 `adb install -r` 覆盖安装且不丢收藏 / 历史 / 播放进度 |
| 溯源文件 | `build-info.json`（run id / commit sha / 4 个 APK 的 sha256 / 构建时间戳 / flavor / ABI）、`SHA256SUMS.txt`、**`upstream-verify.json`（上游产物签名指纹 / ABI / 包名 / versionName 机械校验结果）**、**`docs/FIELD-TEST.md`（实机取证与四包对照试装手册）** |
| 目标系统 | Android 11 / API 30，MT9667，3GB RAM / 64GB ROM，无 Root，无网口 |
| 参考（不作构建基线） | `FongMi/TV` fongmi 分支 @ `4512b4c9f82534ff66acfde06ccdd68f35b074f0`（5.8.7）；仅用于核对版本号与来源，源码重建不可行 |

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

## 4. AC 编号体系（概述，明细由 QA 维护 AC-01~AC-31，v1.1 顺延 AC-32）

按能力域分组，编号唯一、不得与 PM 旧 AC1~AC8 混用：

- **AC-01~AC-08 产物与静态校验**：CI 成功聚合发布 4 个官方包（leanback / mobile × arm64_v8a / armeabi_v7a）；sha256 可追溯；`aapt`/`apksigner` 静态校验通过；包名 / ABI / versionName / targetSdk / 各 flavor 启动器声明正确；官方原签名一致、可覆盖安装；`upstream-verify.json` 校验通过。
- **AC-09~AC-12 安装与首启**：4 个包分别可安装（含 mobile flavor 遥控器可用性记录）；首启不崩 / 不白屏 / 不静默退出；runtime 模块离线可达或给明确提示；30 秒内出站点列表或错误态（D-01 兜底口径）。
- **AC-13~AC-20 播放稳定性**：连续 60 分钟不闪退（P0）；120 分钟加固（P1）；≥20 次切源跨 ≥3 站点；≥10 次前后台切换；播放位置被回收后可恢复。
- **AC-21~AC-25 内存**：TOTAL PSS ≤512MB；Java Heap ≤ heapgrowthlimit×80%；60 分钟净增长 ≤50MB 且回落；k≥3 轮一致。
- **AC-26~AC-28 兼容与合规**：沿用现有 `zijian.json` 可加载；港澳台/国外/地方频道分组不被破坏；不引入 `ApplicationExitInfo`；不加大堆。
- **AC-29~AC-31 取证与对照**：原始日志 + 零崩溃标记 + PID 不变量 + 内存曲线齐备；**中性三组对照**（官方 arm64 / 官方 armeabi-v7a / 用户当前包，同机各 60 分钟统一取证），不预设「装错 32 位包」为根因方向；日志脱敏前后 sha256 与行数差留痕。

**AC-32 四包对照试装与证据回传**（基线变更 v1.1 顺延，沿用 EARS 格式；不改动 AC-01~AC-31，不另设阈值）

> When 在国行 J31-8K2 真机执行实机验收，验收系统必须按 `docs/FIELD-TEST.md` 第 3 节规定的固定顺序依次试装 CI 产出的 4 个包（`leanback-arm64_v8a` → `leanback-armeabi_v7a` → `mobile-arm64_v8a` → `mobile-armeabi_v7a`），且每轮必须记录能否安装、连续播放时长、换源或换线路次数、前后台切换次数、是否闪退、闪退发生时的操作与时间点。
> If 任一轮发生闪退或安装失败，验收系统必须留存该轮全量 `logcat -b all -v threadtime` 原始日志、DropBox 四类条目、tombstone / bugreport 摘要、meminfo 周期采样与 PID 变化记录，并按 `FIELD-TEST.md` 第 5 节回传模板提交。
> Where 同签名可直接覆盖安装，验收系统必须不清除应用数据、不恢复出厂设置、不卸载重装被测应用。

- 判据：4 轮判定表全部填满且无空格，每轮证据包可追溯到具体文件与 sha256；观察窗口按第 3 节锁定阈值执行（60 分钟 P0 / 120 分钟 P1、≥20 次换源跨 ≥3 站点、≥10 次前后台、k≥3），**本条不新设更低门槛**。
- 证据：`docs/FIELD-TEST.md` 判定表、4 轮原始日志与回传记录、脱敏前后 sha256 与行数差。
- 失效判定：只试装 1 个包、判定表留空、只记录「能播 / 不能播」而无原始日志、或以短窗口「没闪退」替代正式验收窗口。
- 不预设结论方向：既不支持也不排除任一 ABI 或 flavor，四包结果只用于对照与归因。

## 5. 当前评级

- 构建侧（Phase 3）：**未评级**——基线已变更为官方产物聚合，需等首次 GitHub Actions 实跑产出 4 个包并核对 `upstream-verify.json`。原「A 基线本地补丁干跑 13/13 hunk」属源码编译路线，随基线变更作废。
- 实机稳定性（Phase 4）：**no-go / 未评级**——尚无实机机械证据。本版本是官方原包的聚合与兼容性对照交付，**不是已验证修复，不承诺消除闪退**。
- 实机取证口径：以 `docs/FIELD-TEST.md` 为准（四包对照试装顺序、全量 logcat、DropBox、bugreport、meminfo 曲线、三类死因判别、回传模板、三不要前置）。
- 已知待修（不在本版范围）：AC-28 崩溃计数口径存在假阴性风险（崩溃恢复框架接管 Java 未捕获异常后，系统崩溃归档 `data_app_crash` / `am_crash` 可能缺席），须按 AC 冻结规则走三方书面增补派发，本版未改第 2 节与 AC 条款；`FIELD-TEST.md` 第 4 节已先行补入 `CustomActivityOnCrash` 标记行作为现场取证依据，避免现场漏判。

## 6. 变更记录

| 版本 | 日期 | 变更 | 执行 | 范围与约束 |
| --- | --- | --- | --- | --- |
| v1.0 | 2026-11-07 | 初版验收契约：AC-01~AC-31 编号体系、锁定阈值、死因三类、当前评级 | QA | 源码编译基线 `FongMi/TV` @ `4512b4c9` |
| v1.1 | 2026-11-08 | **基线变更**：源码重建证伪（52 个私有 media3 类未开源、作者私有 AAR 未入库），改走官方 `FongMi/Release` 5.8.7 四包聚合 + 机械校验 + 发布；0.1 锚定表改为四包基线、产物名改为 4 个、溯源文件增 `upstream-verify.json` 与 `docs/FIELD-TEST.md`；第 4 节产物数量与签名表述对齐、顺延 AC-32 四包对照试装；第 5 节构建侧评级去掉源码补丁口径 | QA（team-lead 派发） | **第 3 节锁定阈值一字未降；AC-01~AC-31 编号与条款不动；只改冲突段落并追加本记录，未整篇重写**。核心用户价值改为「可诊断、可对照、可归因」 |
| v1.2 | 2026-11-08 | **CI 实跑状态同步**：run `42468716759` 13 步全绿、Release `jmgo-42468716759` 8 文件齐备；文末同步状态段由「CI 尚未实跑、四包产物尚未出」改为已闭环，上线阻断由 4 条收敛为 3 条实机侧 | QA advisory 书面动议 + team-lead 终裁代笔 | **仅改第 6 节文末同步状态段 + 追加本行**；第 3 节 8 条锁定阈值、AC-01~AC-31 与 AC-32 条款一字未动 |

> 同步状态（team-lead 收口，2026-11-08 更新）：`build-jmgo.yml`（官方包下载/校验/聚合/发布）、`SPEC.md` v0.2、`build-contract.md` v2.0、`README.md` 已全部对齐官方包聚合口径，上述待办已关闭。
> **CI 已实跑通过**：Actions run `42468716759`（commit `6fada51`）13 步全绿；Release `jmgo-42468716759` 已发布 8 个交付文件；`upstream-verify.json` 实测 `allPassed=true`、4 包各 10 项 checks 全为 True、签名指纹一致。
> **剩余阻断（仅实机侧，3 条）**：① 实机机械证据（logcat / DropBox / bugreport / meminfo / PID 序列）仍为空白；② AC-28 CAOC 吞异常导致的 DropBox 假阴性 P0 未归零，AC-17 + AC-28 条款增补未正式派发（#13 pending）；③ AC-32 四包对照试装与 AC-31 中性三组对照未执行。产品上线维持 **no-go**（见第 5 节）；第 3 节锁定阈值与 AC-01~AC-31、AC-32 条款一字未动。
