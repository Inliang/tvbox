# 实机取证与四包对照试装手册

> 文件：`apps/jmgo/docs/FIELD-TEST.md`
> 适用设备：坚果 N1S 4K 高亮版（国行 J31-8K2），Android 11，无 Root，无网口，走 Wi-Fi ADB
> 适用产物：本仓库发布的 4 个官方 5.8.7 包（leanback / mobile，各有 64 位与 32 位）
> 面向读者：本机使用者，不需要开发经验

## 这份文档能做什么，不能做什么

能做的：把「用一会儿随机闪退」变成**可诊断、可对照、可归因**的证据。按本手册操作后，你能拿到一份包含原始日志、内存曲线和崩溃归档的回传包，别人可以据此判断是低内存回收、播放器内核崩溃，还是程序自身异常。

不能做的：**不承诺修好闪退**。本轮发布的是官方原包的聚合与兼容性对照，不是已验证的修复版。四包试装的目的，是找出这台机器上哪一个包更稳定、闪退属于哪一类，而不是保证某一个包一定不出问题。

**只认机械证据，不认主观描述。**「我觉得不卡了」「好像没再闪」「没弹停止运行框」都不能作为结论。能作数的是：原始日志文件、系统崩溃归档、进程编号变化、内存采样曲线，以及你记录下来的操作时间点。

---

## 0. 开始之前

### 0.1 三不要（务必先读，否则会毁掉最值钱的证据）

设备会把历次崩溃自动存进一份叫 DropBox 的系统归档，它不会因为日志缓冲区被覆盖而消失，是「随机闪退」最难复现、却最容易直接命中根因的一手证据。所以在完成第 2 节取证之前：

1. **不要清除应用数据**（设置里的「清除数据」「清除缓存」都不要点）。
2. **不要恢复出厂设置**。
3. **不要卸载重装被测应用**。

这三步都会让历史崩溃归档失效。即使某个包装不上、想重来，也先按第 2 节把证据抓下来再说。

### 0.2 如果只想做最少的事

时间有限的话，完成下面五步就够产生有效证据：

1. 按第 1 节连上 ADB。
2. 按第 2 节 G1 打开全量日志落盘（这个窗口一直开着别关）。
3. 打开影视应用，**连续播放至少 30 分钟**（能到 60 分钟更好），期间换几次线路或片源、把应用切到桌面再切回来几次。
4. 一旦闪退，记下**当时的时间**和**当时正在做什么**（例如「换到第 3 个源后约 2 秒退回桌面」）。
5. 按第 2 节 G3、G5 补抓崩溃归档与 bugreport，然后按第 5 节模板回传。

30 分钟是「最小可行动作」，不是验收标准。正式验收窗口仍以 `ACCEPTANCE.md` 第 3 节已锁定的阈值为准（60 分钟 P0 门槛、120 分钟加固线、换线路 ≥20 次跨 ≥3 站点、前后台切换 ≥10 次、重复 ≥3 轮），**本手册没有降低任何一条**。

### 0.3 准备清单

- 一台电脑，和投影仪连在**同一个 Wi-Fi**（投影仪没有网口，只能走无线）。
- 电脑上装好 Android SDK Platform-Tools（Google 官方 `developer.android.com/tools/releases/platform-tools`，解压即可，不需要装 Android Studio）。下文所有 `adb` 命令都在解压出来的文件夹里打开命令行执行。
- Windows 用户请用 **CMD**（命令提示符）。不要用 PowerShell 的 `>` 重定向保存日志，它会把文件写成 UTF-16 导致日志乱码。
- 把 4 个 APK 下载到同一个文件夹，记住它们的文件名。
- 一支遥控器，和一点耐心。

---

## 1. 开启开发者选项与 ADB 连接

坚果定制系统的菜单名称随固件版本略有差异，下面给的是常见路径；若某一级找不到，就在同级菜单里找名字相近的项（「关于设备」「系统信息」「高级设置」「更多设置」）。

### 1.1 开启开发者选项

1. 用遥控器进入「设置」→「系统设置」→「关于本机」（或「关于设备」）。
2. 光标选中「软件版本号」或「系统版本」，**连续按确认键 7 次**。
3. 屏幕出现「您已进入开发者模式」或「ADB 调试已打开，请重启」之类的提示。
4. **按提示重启一次投影仪**。不重启的话后面的开关可能不生效。
5. 重启后回到「设置」，在「更多设置」/「高级设置」/「开发者选项」里，开启：
   - 「USB 调试」或「USB 调试（ADB）」；
   - 「网络 ADB 调试」（有这一项就开，这是无线连接的关键）；
   - 「允许安装未知来源的应用」（用 ADB 装包时需要）。

如果系统提供的是 Android 11 原生的「无线调试」而不是「网络 ADB 调试」，见 1.4 的路径 B。

### 1.2 查投影仪的 IP 地址

进入「设置」→「网络」/「网络信息」→ 当前连接的 Wi-Fi，记下 IPv4 地址，形如 `192.168.1.105`。**下文所有 `192.168.1.105` 都要换成你这个地址。**

### 1.3 确认电脑和投影仪互通

在电脑上打开 CMD，进入 platform-tools 文件夹（把 `C:\platform-tools` 换成你实际解压出来的路径）：

```
cd /d C:\platform-tools
adb version
adb devices
```

`adb version` 能打印版本号即工具可用；此时 `adb devices` 列表为空是正常的，还没连接。后文所有命令都在这个文件夹的 CMD 窗口里执行。

### 1.4 连接（两条路径，优先路径 A）

**路径 A：网络 ADB（坚果固件常见，推荐）**

```
adb connect 192.168.1.105:5555
adb devices
```

看到 `connected to 192.168.1.105:5555`、且 `adb devices` 里出现该设备并显示为 `device`，即连接成功。

**路径 B：Android 11「无线调试」（仅当系统只有这一项时）**

在投影仪「开发者选项」→「无线调试」里选择「使用配对码配对」，屏幕上会显示配对 IP、端口和 6 位配对码；再回到「无线调试」主页面记下另一个「设备 IP 与端口」（端口通常与配对端口不同）：

```
adb pair 192.168.1.105:37xxx
adb connect 192.168.1.105:38xxx
adb devices
```

第一条命令执行后会提示输入配对码，输入屏幕上的 6 位数字回车。

**连不上时按顺序检查**：电脑与投影仪是否同一个 Wi-Fi；IP 是否填错；开发者选项里的「USB 调试 / 网络 ADB 调试」是否都开着；是否漏了 1.1 第 4 步的重启；路由器是否开启了「AP 隔离 / 访客网络隔离」（会阻断设备互访）。仍不行就换一台电脑或换个 Wi-Fi 再试，不要为此恢复出厂设置。

### 1.5 记录设备指纹（一次即可）

```
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell getprop ro.product.cpu.abilist
adb shell getprop ro.zygote
adb shell getprop dalvik.vm.heapgrowthlimit
adb shell getprop dalvik.vm.heapsize
adb shell dumpsys meminfo com.fongmi.android.tv
adb shell pm list packages com.fongmi.android.tv
```

把输出整段复制进回传模板的「设备信息」栏。特别注意 `ro.product.cpu.abilist`：它决定这台机器实际支持哪种架构，**不要凭「芯片是 64 位」去猜**。

---

## 2. 取证命令（可直接复制粘贴）

**所有命令都在 platform-tools 文件夹里打开的 CMD 窗口执行**（就是 1.3 里 `cd /d C:\platform-tools` 的那个文件夹），产物也直接生成在该文件夹。不要 `cd` 到别处再执行 `adb`，否则命令行会找不到 adb；若确实要换目录，请先把 platform-tools 的完整路径加进 Windows 的 PATH 环境变量。

建议开 3 个 CMD 窗口，都在同一个文件夹：窗口一跑 G1 全程日志，窗口二跑 G2 周期采样，窗口三执行 G3~G6 的单次命令。

> 说明：命令块里以 `::` 开头的行是注释，在 .bat 文件里会被忽略；交互式 CMD 里可以不复制。

### G1 全量日志落盘（最重要，全程开着）

**推荐做法：写到设备内部，不依赖电脑持续接收。**

日志写在设备内部，Wi-Fi ADB 短暂断连时已写入的内容仍保存在设备上，重新连接后可以取回；电脑侧窗口关掉也不会把设备上的文件一起清空。

另开一个 CMD 窗口，同样在 platform-tools 文件夹里执行：

```
adb logcat -b all -v threadtime -f /data/local/tmp/jmgo-logcat.txt
```

这个窗口会一直停在采集状态，且**不会滚动输出文字，这是正常的**——日志正在写进设备内部文件，这样做是为了 Wi-Fi ADB 中途断连时已采集的日志不丢。**不要关掉它**，也不要在这台设备上执行 `adb logcat -c`（清空日志缓冲区等于销毁证据）。去做第 3 节的试装与播放即可。

播放/闪退结束后，回到这个窗口按 `Ctrl+C` 停止，然后在窗口三把日志取回电脑（保存成当前文件夹下的 `jmgo-logcat.txt`）：

```
adb pull /data/local/tmp/jmgo-logcat.txt
```

**备用做法（若上一条报路径错误）：写到电脑本地。**

```
adb logcat -b all -v threadtime > logcat-full.txt
```

同样保持窗口开着，结束时按 `Ctrl+C`。务必用 CMD，不要用 PowerShell 的 `>`。

为什么必须 `-b all`：崩溃堆栈可能在 crash 缓冲区，低内存回收在 system / kernel 缓冲区，上下文在 main 缓冲区，只抓一部分会漏判。**不要**把命令改成只 grep 某几个关键字后保存，过滤只能用于事后检索，判定必须基于全量原始文件。

### G2 内存曲线周期采样

在窗口二所在的文件夹里，用记事本新建一个 `sample-meminfo.bat`（另存时「保存类型」选「所有文件」，文件名一定要带 `.bat` 后缀），内容如下，然后双击运行，按 `Ctrl+C` 停止：

```
@echo off
:loop
echo ==== >> meminfo-series.txt
adb shell date >> meminfo-series.txt
adb shell dumpsys meminfo com.fongmi.android.tv >> meminfo-series.txt
timeout /t 60 /nobreak > nul
goto loop
```

每 60 秒采一次，结果写进同目录的 `meminfo-series.txt`。**这段必须存成 .bat 文件运行**：`:loop` 与 `goto` 是批处理语法，逐行粘贴到交互式 CMD 窗口会报错。

若用 macOS / Linux，等价写法：

```
while true; do echo "====" >> meminfo-series.txt; adb shell date >> meminfo-series.txt; adb shell dumpsys meminfo com.fongmi.android.tv >> meminfo-series.txt; sleep 60; done
```

同时建议在每个整点或每次换源前后，顺手记一次进程编号，用来判断应用是否被静默重启：

```
adb shell pidof com.fongmi.android.tv
adb shell "ps -A | grep com.fongmi"
```

进程编号（PID）变了，就说明进程被重启过，即使你没看见闪退画面，也要记一次。

### G3 系统崩溃归档（DropBox）

闪退发生后执行，四类都要抓（没有内容也是有效信息，说明该类未记录到）：

```
adb shell dumpsys dropbox > dropbox-index.txt
adb shell dumpsys dropbox --print data_app_crash > dropbox-data_app_crash.txt
adb shell dumpsys dropbox --print data_app_native_crash > dropbox-data_app_native_crash.txt
adb shell dumpsys dropbox --print SYSTEM_TOMBSTONE > dropbox-SYSTEM_TOMBSTONE.txt
adb shell dumpsys dropbox --print data_app_anr > dropbox-data_app_anr.txt
```

`dropbox-index.txt` 是全部条目的索引，能看出历史崩溃发生的时间点，请一并回传。

### G4 tombstone（原生崩溃现场）

```
adb shell ls -l /data/tombstones/
```

**无 Root 时这条通常返回 `Permission denied`，这是预期结果，不是你操作错了。** 原生崩溃的现场文件要靠 G5 的 bugreport 间接取得：解开 `bugreport.zip` 后，在 `FS/data/tombstones/` 目录里找 `tombstone_00` 等文件。

### G5 bugreport（可用时）

```
adb bugreport bugreport.zip
```

这条耗时几分钟，会生成一个 zip。请把整个 zip 回传，不要只挑几行日志贴出来。

### G6 收尾

```
adb shell dumpsys meminfo com.fongmi.android.tv > meminfo-final.txt
adb shell getprop ro.product.cpu.abilist > device-abi.txt
dir
```

`dir` 的输出能证明证据包里有哪些文件、各多大，一并截图或复制进回传模板。

---

## 3. 四包对照试装

### 3.1 四个包与试装顺序

本仓库每次发布 4 个包，文件名形如 `tvbox-jmgo-{flavor}-{abi}-5.8.7-{短哈希}.apk`。**顺序固定，不要跳着试**，因为这是一组对照实验，顺序本身就是记录的一部分：

| 轮次 | 包名（示例文件名，短哈希以你实际下载的为准） |
| --- | --- |
| 第 1 轮 | `tvbox-jmgo-leanback-arm64_v8a-5.8.7-abc1234.apk`（电视版 / 64 位） |
| 第 2 轮 | `tvbox-jmgo-leanback-armeabi_v7a-5.8.7-abc1234.apk`（电视版 / 32 位） |
| 第 3 轮 | `tvbox-jmgo-mobile-arm64_v8a-5.8.7-abc1234.apk`（手机版 / 64 位） |
| 第 4 轮 | `tvbox-jmgo-mobile-armeabi_v7a-5.8.7-abc1234.apk`（手机版 / 32 位） |

> 「leanback」是遥控器操作的电视版，「mobile」是触控版。两者都试，是为了判断闪退跟界面形态有没有关系。
> 「arm64_v8a」是 64 位包，「armeabi_v7a」是 32 位包。**目前不预设哪一个是对的**，第 1.5 节查到的 `ro.product.cpu.abilist` 只是参考，最终以实机对照结果为准。

### 3.2 关于覆盖安装（重要）

这 4 个包使用**官方原签名**，与你现在装的官方 5.8.7 32 位包同签名，因此可以直接覆盖安装：

```
adb install -r tvbox-jmgo-leanback-arm64_v8a-5.8.7-abc1234.apk
```

`-r` 表示替换已安装的应用但保留数据，**收藏、历史记录、播放进度不会丢**。看到 `Success` 即安装成功。

若报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`（签名不一致）或其他错误：**把报错原文整行复制下来**，写进回传模板，然后**不要卸载重装**（见 0.1 三不要），先跳过该轮并在判定表里注明。

每一轮开始前，先用 `dir *.apk` 核对实际文件名，把命令里的 `abc1234` 换成真实短哈希。

### 3.3 每轮做什么

1. 安装该轮的包，记录能否安装。
2. 确认 G1 日志窗口仍在采集、G2 采样窗口仍在跑。
3. 打开应用，正常点播、换线路/换片源、切到桌面再切回来，尽量贴近你平时「用一会儿就闪退」的用法。
4. 记录：连续播放时长、换源或换线路次数、前后台切换次数、是否闪退、闪退发生时的操作与时间点。
5. 闪退后立刻执行 G3、G5，再在窗口三执行下面几行把该轮证据单独归档（以第 1 轮为例，后续轮次把 `round1` 换成 `round2` 等），避免四轮日志混在一起：

```
mkdir round1
move jmgo-logcat.txt round1\
move meminfo-series.txt round1\
move dropbox-*.txt round1\
move bugreport.zip round1\
```

某个文件不存在时 `move` 会提示找不到，跳过即可，不要因此重跑整轮。归档后回到窗口一重新执行 G1 命令、回到窗口二重新双击 .bat，再开始下一轮。

### 3.4 每轮建议观察窗口

| 用途 | 观察窗口 | 说明 |
| --- | --- | --- |
| 快速筛查（选包用） | 每轮 ≥30 分钟，≥3 次换源或换线路，≥2 次前后台切换（其中 1 次切出停留 >5 分钟再返回） | 目的是在四包之间找出相对稳定的候选，用户自行操作即可 |
| 正式验收（判定用） | 按 `ACCEPTANCE.md` 第 3 节锁定阈值：连续 60 分钟（P0）/ 120 分钟（P1 加固）、换线路 ≥20 次跨 ≥3 站点、前后台切换 ≥10 次、重复 ≥3 轮且跨不同冷启动 | 由 QA 在 Phase 4 执行；**筛查窗口不能替代正式验收，锁定阈值一字未降** |

四轮全部跑完约需 2 小时以上。如果时间不够，宁可只做**第 1 轮 + 0.2 的最小动作**并把证据抓完整，也不要四轮都只播 5 分钟——短窗口的「没闪退」没有判定价值。

### 3.5 判定表（每轮填一行）

| 轮次 | 包名 | 能否安装 | 连续播放时长 | 换源/换线路次数 | 前后台切换次数 | 是否闪退 | 闪退发生时的操作与时间点 | 证据文件夹 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | leanback-arm64_v8a | | | | | | | |
| 2 | leanback-armeabi_v7a | | | | | | | |
| 3 | mobile-arm64_v8a | | | | | | | |
| 4 | mobile-armeabi_v7a | | | | | | | |

填写要求：所有格子都要填，「没做」就写「未执行」，「没闪退」就写「否」，**不要留空**。留空的格子无法区分「做了没记」和「没做」。

---

## 4. 三类死因判别（回传前先自己分个类）

闪退不一定是「崩溃」。下面三类表现很像，处理方式完全不同。请先按时间戳把 G1 日志中闪退前后约 2 分钟的片段找出来，再对照下表。

| 类别 | 典型表现 | 在日志/DropBox 里找什么 | 该回传哪些片段 |
| --- | --- | --- | --- |
| ① 低内存回收（lmkd） | 突然退回桌面、再打开时重新加载，**通常不弹「已停止运行」框** | `am_low_memory`、`Low on memory`、`lowmemorykiller`、`lmkd`、`Killing`、`onTrimMemory`；`meminfo-series.txt` 里 TOTAL PSS 持续上涨 | 闪退前后 2 分钟 logcat 片段、`meminfo-series.txt` 全文、`dropbox-index.txt`；注明当时是否还开着别的应用 |
| ② 原生崩溃（native） | 播放中直接退出，可能伴随黑屏、花屏后退出 | `SIGSEGV`、`signal 11`、`SIGABRT`、`abort`、`DEBUG`、`tombstone`、`backtrace`；DropBox 的 `data_app_native_crash` 与 `SYSTEM_TOMBSTONE` | `bugreport.zip` 整个文件（内含 `FS/data/tombstones/`）、`dropbox-data_app_native_crash.txt`、`dropbox-SYSTEM_TOMBSTONE.txt`、闪退前后 2 分钟 logcat 片段 |
| ③ 程序自身异常（Java 未捕获异常） | 闪一下又回到首页、或直接退出；可能弹出崩溃界面 | `data_app_crash`、`am_crash`、`FATAL EXCEPTION`、`:error_activity` 新进程、`cat.ereza` / `CustomActivityOnCrash` 标记；尤其 `App has crashed, executing CustomActivityOnCrash's UncaughtExceptionHandler` 这一行 | `dropbox-data_app_crash.txt`、含上述标记行的 logcat 片段、`adb shell "ps -A | grep com.fongmi"` 的进程列表、闪退前后 2 分钟 logcat 片段 |

**关于第 ③ 类有一个容易漏判的点**：这个应用内置了崩溃恢复框架（CAOC）。它会接管未捕获异常并自行结束进程，在「后台静默」模式下既不弹框也不启动崩溃界面。因此**只看到闪退、但 `data_app_crash` 是空的，不能当成「没崩溃」**。请务必在 logcat 里搜 `CustomActivityOnCrash`，把命中的行连同后面的堆栈一起回传；这一行带完整堆栈，是判断这类闪退最直接的证据。同时用 G2 里的 PID 记录比对进程编号是否变化。

**归因纪律**：一次闪退可能同时命中多类，按时间顺序分别记录，不要合并成一句「崩了」。分类错了，后面修的方向就会错。

---

## 5. 结果回传模板

复制下面的模板，逐项填写。**敏感信息可先脱敏**（见末尾说明），但不要删改时间戳、日志级别、TAG 和堆栈结构。

```
【设备信息】
型号：
Android 版本 / API：
ro.product.cpu.abilist：
ro.zygote：
dalvik.vm.heapgrowthlimit：
总内存 / 当前可用内存：
包名：com.fongmi.android.tv
试装前已装的版本与包名：

【试装判定表】
（粘贴第 3.5 节表格，四行填满）

【每轮证据文件】
第 1 轮：logcat-full.txt / meminfo-series.txt / dropbox-*.txt / bugreport.zip / 文件大小与 sha256（如有）
第 2 轮：
第 3 轮：
第 4 轮：

【闪退事件记录】
发生时间（时:分:秒）：
当时正在做什么（换源 / 换集 / 切后台 / 暂停恢复 / 只是放着）：
观察到的现象（退回桌面 / 回到首页 / 黑屏 / 弹框 / 无声退出）：
闪退前后 2 分钟 logcat 关键片段（原样粘贴，保留时间戳）：
DropBox 四类条目摘要（有内容就贴，无内容写「空」）：
tombstone 摘要（来自 bugreport.zip 的 FS/data/tombstones/，无 Root 直读失败也要写明）：
PID 变化记录（闪退前 PID / 闪退后 PID）：
内存曲线观察（TOTAL PSS 起始值 / 峰值 / 是否持续上涨）：

【自行初判】
命中的死因类别：① 低内存回收 / ② 原生崩溃 / ③ 程序自身异常 / 未判定
依据（对应第 4 节哪一行的哪些关键字）：

【脱敏说明】
已替换的内容类型：源站地址 / 账号 / 鉴权参数 / 片名（按需列举）
保留未动：时间戳、日志级别、TAG、堆栈结构、死因关键字
原始文件是否本地保留：是 / 否
```

**脱敏规则**：可以把配置源 URL、账号、鉴权参数、片名替换成 `已脱敏` 这类占位文字；**不要整行删除，也不要删日志里的崩溃、低内存、ANR、崩溃恢复框架相关行**。整行删除会让证据失去可核对性，等于白抓。原始全量日志建议在你自己电脑本地保留到复核完成，不要只在聊天里贴片段。

---

## 6. 判定纪律：什么不算数

以下情况不能作为「没问题」的结论，回传时也不要这样写：

- 「用了一会儿没闪，应该好了」——没有原始日志和观察时长，不构成证据。
- 「没弹停止运行框，所以没崩溃」——低内存回收和后台静默崩溃都不弹框。
- 只贴几行日志截图、或只贴 grep 过滤后的结果文件，不提供全量原始日志。
- 四轮都只播了几分钟，或只在同一个线路反复点播凑次数。
- 靠清数据、恢复出厂设置、卸载重装之后「暂时不闪了」——现场已被销毁。
- 只在别的设备、模拟器、手机上运行正常，就推断这台投影仪也正常。
- 把「加白名单」「换解码内核」「精简配置源才稳定」当成修好了——这些只是绕开触发条件。

**有效结论的门槛**：有全量原始日志、有系统崩溃归档或明确的「空」记录、有 PID 变化记录、有内存采样曲线、有四轮判定表、有闪退发生时的操作与时间点。缺任一项，判定为「证据不足」，需要补抓，不判通过，也不判失败。

---

> 相关文档：`ACCEPTANCE.md`（验收契约与锁定阈值）、`PRD.md`（产品需求）、`build-contract.md`（构建契约）。
> 本手册只提供取证与对照方法，不对闪退修复结果作任何承诺。
