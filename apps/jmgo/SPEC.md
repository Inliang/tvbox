# Spec - 坚果 N1S 4K 兼容版 TVBox 客户端 v0.1

> 生成日期：2026-11-07
> 基于：PRD v1.1（产品经理）+ 架构文档 v2（架构师，Phase 1 + 决策变更）+ 兼容性验收清单 v1（测试工程师，AC-01~AC-31）
> 状态：已确认（用户 2026-11-07 完成三文档确认与三项决策）
> 作用：团队内部规格契约。Phase 2 / 3 / 4 全部以此为准，范围外的功能一律不做。

---

## 1. 产品定义

- **一句话**：为坚果 N1S 4K 高亮版自动构建一个可覆盖安装、连续播放不闪退的 FongMi（蜂蜜版）电视客户端 APK。
- **目标用户**：本机主，当前装官方 FongMi 5.8.7 leanback 32 位包（40MB 以上，包名 `com.fongmi.android.tv`），现象是「用一会儿随机闪退」。
- **核心问题**：3GB RAM 定制 Android 11 环境下，上游爬虫资源释放/生命周期缺陷、独立 runtime 模块依赖 GitHub 可达性、32 位主包与 64 位 runtime 模块潜在不匹配，三者叠加。
- **不是**：再造一个 TVBox 分支。用户要的是「一口气看完整部片不闪退」。

## 2. MVP 范围（锁定，不在此列表的一律不做）

| 优先级 | 功能 | 验收摘要 |
| --- | --- | --- |
| P0 | F1 按设备出正确架构产物 | 同时产出 `arm64_v8a` 与 `armeabi_v7a` 两个 leanback 包，各自独立 Artifact |
| P0 | F3 push 即自动构建可安装 APK | Actions 成功 → Artifact + Release，附 sha256 / run id / commit / ABI |
| P0 | 固定签名 | 每次构建同一 keystore，可覆盖安装 |
| P0 | runtime 模块可达 | 首次启动到可播放不依赖访问 GitHub；拉取失败给明确错误态而非闪退 |
| P1 | F2 低内存稳定性收敛 | 裁剪重模块、缓存/生命周期收敛、保守默认解码与清晰度；不做「加 largeHeap」 |
| P1 | 播放状态持久化 | 被 LMK 回收后恢复播放位置，不依赖系统白名单或 Root |
| P1 | 产物可核验 | `build-info.json` + `SHA256SUMS.txt` |
| P1 | 双基线兜底 | A 基线 CI 连续两次跑不通 → 自动切 B 基线 |

## 3. 明确不做（锁定）

| 不做的功能 | 原因 |
| --- | --- |
| 新 UI / 换肤 / 重建前端 | 复用上游界面，ROI 不足且引入新崩溃面 |
| 内置影视源 / 内置配置地址 | 沿用仓库现有 `zijian.json`，本仓库只出客户端 |
| 直播弹幕、DLNA、网盘登录、投屏接收 | 与闪退无关，属范围蔓延 |
| 多机型兼容矩阵 | 只针对坚果 N1S 4K 高亮版一台 |
| 应用内热更新 / 自动升级 | 由 GitHub Release + 手动覆盖安装承担 |
| Root / 刷机 / 改系统 WebView | 破坏保修且不可分发 |
| 账号体系 / 云同步 | 上游无此能力 |
| 增加 `android:largeHeap` | 上游已开启；3GB 设备再放大堆可能加速 lmkd 回收 |
| OpenAPI / REST API 契约 | 本项目无服务端，改用 `build-contract.md` |
| 清数据 / 后台白名单 / 换内核绕过 / 降级系统 | 临时解法，不算修好 |
| 引入 `ApplicationExitInfo` | API 31+，本机 Android 11 / API 30 不可用 |
| emoji 作功能图标、紫粉渐变、硬编码色、空洞占位文案 | 团队 P0 绝对规则 |

## 4. 技术架构（锁定，含版本锚定）

| 层 | 技术 / 值 | 依据 |
| --- | --- | --- |
| 上游源码 | `FongMi/TV` @ `4512b4c9f82534ff66acfde06ccdd68f35b074f0`（fongmi 分支 HEAD，2026-11-06，versionName 5.8.7） | GitHub API 复核 |
| Gradle | 9.7.1 | `gradle/wrapper/gradle-wrapper.properties` |
| AGP / buildTools | 9.4.0 / 37.0.0 | `gradle/libs.versions.toml` |
| JDK | 21 (temurin) | 架构师 Phase 1 |
| SDK | compileSdk 37 / targetSdk 37 / minSdk 24 | `gradle/libs.versions.toml` |
| NDK / CMake | 28.2.13676358 / CMake 3.22.1（runner 需显式安装，或改用 3.31.5） | 架构师 Phase 1 |
| CI | GitHub Actions `ubuntu-latest` | 用户决策 |
| 签名 | 固定 keystore；优先 GitHub Secrets，退化用仓库内 jks | 覆盖安装要求 |
| 设备 | 坚果 N1S 4K 高亮版 J31-8K2 / Android 11 / MT9667 / 3GB RAM / 64GB ROM | 规格页，**待 getprop 实测** |
| 产物形态 | 只执行 `assembleLeanbackRelease`；上游 `splits.abi` 默认双 ABI 且 `universalApk=false`，一次出两个包，不做 universal，不构建 mobile | 架构师核实 `app/build.gradle` |

## 5. 构建产物契约（替代 API 端点清单）

| 产物 | 命名 | 校验 |
| --- | --- | --- |
| APK (64) | `tvbox-jmgo-leanback-arm64_v8a-5.8.7-<commit短哈希>.apk` | `aapt dump badging` + `apksigner verify` + sha256 |
| APK (32) | `tvbox-jmgo-leanback-armeabi_v7a-5.8.7-<commit短哈希>.apk` | 同上 |
| 构建信息 | `build-info.json` | run id / commit sha / 两个 APK 的 sha256 / 构建时间戳 / ABI 标识 |
| 校验和 | `SHA256SUMS.txt` | 与 Artifact 一一对应，含官方 module 资产 digest |
| 运行时模块 | runtime 模块目录或可达 catalog 地址 | 首次启动不依赖 GitHub 直连 |

静态校验项：`native-code` / `versionName` / `targetSdkVersion` / `applicationId` / `LEANBACK_LAUNCHER`。

## 6. 目录结构（锁定）

```
.github/workflows/build-jmgo.yml      # 触发文件，必须在仓库根
apps/jmgo/SPEC.md                     # 本文件
apps/jmgo/build-contract.md           # 构建契约 + ADR
apps/jmgo/docs/PRD.md                 # 产品需求
apps/jmgo/docs/ACCEPTANCE.md          # 验收清单 AC-01~AC-31
apps/jmgo/patches/*                   # 上游补丁
apps/jmgo/scripts/*                   # 补丁应用 / APK 收集脚本
apps/jmgo/keystore/*                  # 签名（或 Secrets 说明）
apps/jmgo/README.md                   # 用户向说明
```

**硬约束**：GitHub Actions 只识别仓库根 `.github/workflows/*.yml`，故触发文件不能放进子目录。

## 7. 页面清单 / 设计 Token

不适用：无新增 UI，沿用上游 FongMi leanback 界面。P0 视觉规则仍适用于任何新增文案与图标。

## 8. 验收标准（锁定，引用测试工程师独立清单）

以 `apps/jmgo/docs/ACCEPTANCE.md` 的 **AC-01~AC-31** 为唯一验收契约，产品经理不自造编号；PM 旧版 AC1~AC8 作废，只做映射。

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
- **不要求用户提前开启 ADB**：双 ABI 出包后分别试装，能装上且稳定者即为目标包；`getprop` 六项取证留到 Phase 4 由 QA 执行。
- **不施加临时解法**：清数据、加后台白名单、换内核绕过、降级系统 WebView 均不算修好，依赖这些才稳定则验收不通过。
- **runtime 模块必须离线可用**；拉取失败给错误态，不闪退；空状态须覆盖「模块未就绪」。
- **每次构建同一签名**，否则无法覆盖安装。
- **禁止引入 `ApplicationExitInfo`**（API 31+，本机 API 30 不可用）；崩溃取证走 logcat / DropBoxManager / bugreport，并区分 LMK 回收、native crash、customactivityoncrash 重启三类。
- **Java 层须实现播放状态持久化**：被 LMK 回收后恢复播放位置。
- 日志与本地事件不记录配置源地址明文、不记录片名；崩溃栈仅本地落盘、用户显式导出、不自动上传。

## 10. 已知坑（Phase 1 + 架构决策变更沉淀）

| 坑 | 证据 | 处置 |
| --- | --- | --- |
| 上游已开 `largeHeap=true` | `q215613905/TVBoxOS` Manifest；架构师核实 | 不要再加大堆；开/关做 A/B 对照 |
| FongMi 5.8.6+ 拆分 Python / Node.js / QuickJS / MPV / Thunder 独立模块，`catalog.json` 默认指向 GitHub Release | 架构师核实 Release Note | 注入可达镜像或模块随包发布，升为 P0 |
| 上游 5.8.5 / 5.8.6 / 5.8.7 连续修「代理网址闪退 / 爬虫资源释放 / 爬虫生命周期」 | `FongMi/Release/releases` | 用户已装 5.8.7 仍闪退，说明问题未完全覆盖；F2 须含爬虫生命周期收敛 |
| runner 预装缺 NDK 28.2.13676358 / CMake 3.22.1 | 架构师核实 | workflow 显式 `sdkmanager` 安装 + 失败诊断日志 |
| `yebook/TV` 依赖 jcenter 与明文 http maven 仓库，已失效 | 架构师核实 | 不采用该基线 |
| `FongMi/TV` 无 APK 构建 workflow（只有 `pages.yml`） | GitHub API 复核 | 自建 workflow，参考 `j4Uq/TVBoxOSC` 生产级流程 |
| 芯片 64 位 ≠ 系统 64 位 ABI | QA / PM / 架构师共识 | 双 ABI 出包，实机试装决定推荐 |
| 上游 `app/build.gradle` 默认 `splits.abi.include "arm64-v8a","armeabi-v7a"` 且 `universalApk=false`，buildSrc 已重命名为 `leanback-<abi>.apk` | 架构师核实 | 双 ABI 补丁归零，CI 直接 `assembleLeanbackRelease` 出两个包 |
| `FongMi/Release` 的 `module` Release 六类运行时模块（python 1.1.3 / nodejs 1.0.7 / quickjs 1.0.4 / mpv 1.1.0 / bdj 1.0.1）均同时提供两个 ABI，catalog.json 带 sha256 `84f89736...` | 架构师核实 | 32 位系统下运行时链路完整；digest 直接进产物完整性校验 |
| `yebook/TV` 的 `applicationId` 是 `com.fongmi.android.tv`（FongMi 系旧 fork）；`com.github.tvbox.osc` 属于 `q215613905/TVBoxOSC` | 架构师核实 | PRD 竞品表须修正，两条产品线不可混写 |
| QA 引用的「上游 README 建议优先 32 位变体」并非 FongMi 官方内容（官方 README 全文无 ABI 建议，出自第三方聚合站） | 架构师核实 | 验收文档不得写成上游官方建议 |
| 「蜂蜜版」混指两条代码基线（FongMi/TV 与 TVBoxOSC 系） | PM 竞品调研 | 已由用户「40MB 官方 FongMi 5.8.7」锁定为 FongMi/TV |
| 上游 `mobile` 与 `leanback` 包名相同，同设备只能装一个 | 社区资料 | 只出 leanback，README 提示覆盖安装 |

## 11. 端到端验证步骤

1. push 到 `main` → Actions 触发 `.github/workflows/build-jmgo.yml`
2. 查询 run 状态；失败按日志修，最多 2 轮；2 轮仍不通 → 按用户决策切 B 基线
3. 下载两个 APK，比对 `SHA256SUMS.txt` 与 `build-info.json` 的 run id / commit
4. `aapt dump badging` 确认包名 `com.fongmi.android.tv`、ABI 标识、versionName、targetSdkVersion；`apksigner verify` 确认签名
5. 实机分别 `adb install` 两个包，记录能装上的是哪个（此步不要求用户提前做，随包分发时执行）
6. 按 AC-01~AC-31 执行：冷启动 10 次 / 连续 60 分钟 / 切源 20 次 / 前后台 10 次 / 首次导入配置 / k≥3 轮
7. 证据包齐全且全绿 → 交付

## 12. 用户决策（已锁定）

| 决策 | 结果 |
| --- | --- |
| 上游基线 | 先 A（`FongMi/TV` 5.8.7）后 B（`q215613905/TVBoxOS`）；A 连续两次 CI 跑不通自动切 B |
| 直装对照 | 不需要；用户确认当前装的就是 5.8.7 |
| 当前包来源 | 40MB 以上官方蜂蜜影视，`FongMi/TV` 系 |
| 落地位置 | 当前 `tvbox` 仓库下 `apps/jmgo/` 子目录 |
| 构建产物 | push 即产出可安装 APK |

## 13. 总监裁决（Phase 1 一致性检查 + Phase 2 放行）

1. **双 ABI 不砍 32 位**：只执行 `assembleLeanbackRelease`，同时产出两个 ABI 包。否决「芯片 64 位故锁 arm64 单变体」；架构师已主动撤回并修订 ADR-003 / 006 / 007 / 008。
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
16. **D-01 对外口径定为兜底版**：「沿用现有配置可加载；若旧爬虫或模块不兼容，须给明确提示与可执行迁移路径」，不承诺「一定能沿用旧配置」。三条底线：首启不崩/不白屏/不静默退出；提示须说明不兼容类型与下一步具体操作；迁移不得要求用户自找新配置源、不得把清数据列为步骤、收藏/历史/进度不得丢失。

## 14. 变更记录

| 日期 | 变更 | 原因 | 影响范围 |
| --- | --- | --- | --- |
| 2026-11-07 | v0.1 建立 | 三文档确认 + 用户三项决策 + PM Addendum v1.1 裁决 | 全流程起点 |
| 2026-11-07 | v0.1 修订 | 架构师决策变更（撤回单变体、双 ABI 零补丁、包名与归因纠错、API 30 约束） + 驳回 ABI 探测门禁 | 第 2/3/4/5/9/10/13 节 |
| 2026-11-07 | v0.1 定稿 | QA 收口汇总（AC-31 中性三组对照、largeHeap 从严、日志脱敏、五处引用纠错） + 全队终裁不索取用户信息 + D-01 兜底口径 | 全文 AC 编号 / 第 9、13 节 |
