# Galgame 自动解包工具 — 项目上下文

个人自用/学习项目：自动解包 galgame，产出**视频、音频、图片**三类资源。
**不做**：打包回写、文本提取、翻译、对外分发。

> **⭐ 终局目标（2026-10-27 用户明确）**：把这套工作流最终做成**一套可复用的 Windows 软件**
> （打包分发的那种，不是散装脚本）。当前所有解包攻坚都在为它攒三样东西：
> ① 决策树/规则表（分派逻辑）② 已验证的自研工具（引擎分支实现）③ verified-findings（实测证据）。
> 写新工具时向这个方向靠：依赖要轻（C# csc 优先）、规则要数据驱动、各分支接口要统一。
> 完整方案（Windows 打包、许可证/法律）见 `galgame-ai-unpack-workflow-plan.md`。

> **⭐ 项目主目录：`D:\K\deepseek`**（2026-10-29 用户确认）。所有新产出（解包产物、清单、
> 报告、新脚本、文档更新）一律放这里；外部工具在 `D:\K\galgame\`（见「环境」），勿搬。
>
> **📦 版本控制**：`D:\K\deepseek` 是本地 git 仓库；远程
> **`git@github.com:KTEC1200/GalgameUnpacker.git`**（2026-11-08 由 game-get 改名）。
> **2026-11-09 起用户 GitHub 账号封禁中——不推送，本地提交即唯一记录**（别反复试 push）。
> `.gitignore` 已排除 `_extracted/`、`packaging/Output/`、`_spike_pkg/dist|build/`、
> `_spike_pkg/agent_contract.json` 等大产物。
>
> **📦 交付形态（2026-11-04 用户定：只做便携版，安装器已删）**：
> `python build_exe.py --tag <名>` = 冻结 + 出 `packaging/Output/GalgameUnpacker-<版本>-<名>-portable.zip`；
> **当前交付 `bugfix13`**（2026-11-11，142.0 MiB，SHA256 `e0719391…cd43ec`），
> **标准路径 `D:\GalgameUnpacker\orchestrator` 已部署**。同名 zip 拒绝覆盖。

## 📌 当前状态（2026-11-11）

- **基线**：`tests=909 / 0 failures / 0 errors`（skip 16~20 随环境波动）+ golden 8 fixture +
  12 真实样本零漂移。**源码 22 个本地提交**（HEAD 附近：`f128216` 数据现场、`36260ec` 交付、
  `ac463e8` Agent P2），工作树只余用户自己的 `新功能.md`（Agent 能力的需求出处，勿动勿加）。
- **能力面**：10 条引擎链路（Ren'Py / KiriKiri / RPG Maker / Yu-Ris / AdvHD / ExHIBIT /
  CatSystem2 / Unity / Artemis / Tyrano 判得出无链路 rc=2）；加密 KiriKiri 走 `--allow-gui`
  或人工拖 + `--reuse-raw`；Agent 攻坚六命令（`--agent-diagnose/plan/run/validate/taskbook/candidate`）。
- **Unity 队列 9/9 闭环**（2026-11-09~10）：SexCP_069、The Neighbor's Wife、The Detective
  Servant、Summer Clover（494 条音频抢救全收）、Kaiju Princess 2（data.unity3d 离线管线）、
  Rebirth Pub（Unity 6000 混合形态）、MiraisMidnight（IL2CPP 媒体无需 Il2CppDumper）、
  SUMMER-田舎の性活（3344 音频 12 轮全收敛）、Bunny（壳层；真身 LINK6 .arc = KAGUYA 家族
  **用户维持划走**，候选规则 rejected 留档）。
- **数据现场**：`D:\GalgameOutput\` 13 部**只留记录**（manifest + 类目清单 + _work 日志，
  4.8M；媒体经用户批准已删，42G→4.8M）+ **aniyome 第 14 部闭环（11-11，媒体暂留待定夺）**；
  HY 游戏本体在；重解=对源全新跑（判定/经验库齐）。
- **Agent 攻坚能力（新功能.md 全量落地）**：P0 诊断包/错误码表、P1 经验库 12 条+沙箱 11 动作+
  硬验证器、P2 任务书/候选规则/文档（`agent-workflow.md`）。**用户数据现场样例**：
  `D:\GalgameOutput\aniyome\_work\diagnostic\{diagnostic.json,taskbook.md}`。
- **本机 .NET 6/8/9/10 齐全**；AssetStudioNext = Razviar/assetstudio v2.4.1
  （`D:\K\galgame\unity\AssetStudioNext\`，Unity 6000 用它，env `TOOLBRIDGE_ASSETSTUDIO` 切换）；
  Il2CppDumper v6.7.46 与 vgmstream r2168 已备（`D:\K\galgame\unity\`）——**媒体产出线不需要
  Il2CppDumper（IL2CPP 三部实证）**。

## ⚠️ 动手前先看（五个坑，每个都花过代价）

1. **`GARbro.Console.exe` ≠ `GARbro.GUI.exe`** — Console 会**假阴性**：GUI 能提取的游戏它报
   `unknown format`。→ Console 报「读不出」不可信，只能把「可识别」当正面证据；拿不准用 GUI 复核。
2. **别试图静态预测「能否解包」** — 两种判据（搜 UTF-16LE 扩展名、解析 XP3 索引长度）全失败过。
   → **直接调用工具，不要预测。**
3. **纯魔数扫描判「有没有视频」会大量假阳性** — 判据：**命中偏移 == 条目/资源起始偏移** 才算真；
   Unity 直接看 AssetStudio 枚举的 `VideoClip` 数量。**镜像面**：StreamingAssets 的裸视频
   AssetStudio 不枚举，要按扩展名收（链路已内置 `_unity_loose_videos`）。
4. **⭐ `AssetStudio.CLI` 的 `--types`：逗号静默归零、退出码 0 毫无意义** — 只用单类型或不写；
   必须数产物文件。**镜像面**：AudioClip Convert 有 **≈8 个/次导出上限**（§41），超出静默 skip。
5. **⭐ 分类必须「扩展名优先」** — 目录名不可信（images/ 下混过 avi/webm/jpg）；
   分类逻辑错了就「修逻辑 + 从源重跑」，不写迁移脚本原地修。

## 工作约定（纪律）

- **⭐ 跑多 GB 级样本前看内存**（本机 13.8 GiB）：大文件 mmap/流式分块；别在重负载旁开大任务；
  AssetStudio 类任务**串行**（两条 11G 加载并行 = thrash 互拖死）。
- **事实先核实再断言**；未核实标「未核实」。仓库事实查 `api.github.com`。
- **用户的教程与实操结论优先于检索与推断**；未经校验的工具输出不是地面真相。
- **两次栽在只看日志尾部**——关键信息常在开头。先开头、再结尾、并数产物文件。
- **PowerShell 调外部程序用 `&`**，不要 `Start-Process -ArgumentList` 拆含空格路径。
- **⭐ 本环境 Bash 会吃反斜杠转义**（`\\`、`\xNN`、`` ` ``）：含正则/转义的代码**一律先
  Write 成 .py 文件再执行**；CJK 字面量进 bash 参数会乱码，用文件系统 glob 解析路径。
- **Git Bash 会把 `/FLAG` 改写成 `C:/Program Files/Git/FLAG`**（MSYS 路径转换）——给原生
  exe 传旗标加 `MSYS_NO_PATHCONV=1` 前缀；CJK 输出过管道先 `PYTHONIOENCODING=utf-8`。
- **pytest 本机坑**：`--basetemp` 别指仓库所在盘（删除守卫制造假失败）；退出码不可信
  （基线看 `run_all.py` 的 junit 行）；验收 JSON 别用 grep（反斜杠双写）；**别并发两个 pytest**。
- **⭐ 试跑产物落 `<仓库>/_extracted/<游戏名>/`**；正式交付落 `D:\GalgameOutput\<游戏名>\`；
  不写进游戏目录（stage 副本除外）。
- **长任务 `python -u`**，进度看 `<out>/_work/<阶段>.log`。
- **⭐ 前台 shell 5 分钟硬上限**：超 5 分钟的活一律 `run_in_background: true`（工具自带的后台
  job 才不被会话清理；自起 `&` 的进程也可能被收）。
- **⭐ 删除守卫**：Python 侧 `shutil.rmtree` >50 文件触发人工确认抛 BaseException——临时目录
  用「唯一名 + 尽力清理」（`toolbridge.drop_tree`）；批量清残留用 bash `rm -rf`。
- **⭐ 新链路四条硬规矩**：① 地面真相只写一份；② `EXTRACTORS` 存函数名不存函数对象；
  ③ `IMPLEMENTED` 与 `IMPLEMENTED_CHAINS` 同步（有护栏测试）；④ 有意排除的输入必须显式报出。
- **PyInstaller 打包清单**：新模块一律 orchestrator **顶部静态 import**（§19.2）；
  代码要读的数据文件同步 `build_exe.DATA_FILES`。
- **提交一律显式 add，禁用 `git add -A`**；改完先回写文档再清临时产物再提交。

## 环境

- **shell**：pwsh 在 workspace-write 下启动失败（0xC0000142，DSH 沙盒缺陷）；用户已切完全权限。
  不要设 `sandbox_permissions`（会被自动拒绝）。
- **本机 DPI 200%**（物理 2880×1800，无感知 1440×900）——UI 自动化必须 `SetProcessDPIAware()`
  全程物理坐标。
- **网络**：`api.github.com` 直连可用（查 release 列表）；release zip 直连慢（~9KB/s）要
  `curl -C -` 续传 + 1800s 超时；代理口 7897/18788 不通；github.com SSH 不稳（push 别试）。
- **本机对未签名 exe 有敏感面写过滤**（火绒/深信服按进程信誉）：安装类写盘会被拒——
  别误诊成产品 bug（证据链 `antivirus-false-positives.md` §5）。

### 外部工具位置（均在 `D:\K\deepseek` 之外，勿搬）

| 工具 | 路径 |
|---|---|
| GARbro-Mod | `D:\K\galgame\GARbro\GARbro.Console.exe`、`GARbro.GUI.exe` |
| AssetStudio.CLI（旧版） | `D:\K\galgame\unity\AssetStudio\AssetStudio.CLI.exe` |
| **AssetStudioNext（Razviar v2.4.1，Unity 6000 用）** | `D:\K\galgame\unity\AssetStudioNext\AssetStudio.CLI.exe` |
| tlg2png | `D:\K\galgame\tlg2png\tlg2png.exe` |
| KrkrExtract 三件套 | `D:\K\galgame\krkr\krkr\`（Lite 5.0.0.2 + Core + UI） |
| KrkrzExtract | `D:\K\galgame\krkr\krkrz\` |
| RPA-Explorer / AsarKit / FModel / umodel / quickbms / SpineViewer | `D:\K\galgame\rpa|asar|UE\` |
| ffmpeg / ffprobe | `D:\ffmpeg\bin\` |
| **Il2CppDumper v6.7.46** / **vgmstream r2168** | `D:\K\galgame\unity\Il2CppDumper\`、`...\vgmstream\` |
| Inno Setup | 已无用（安装器废弃）， winget 装的还在 LocalAppData |

## 文件索引（按需读）

| 文件 | 何时读 |
|---|---|
| `galgame-unpack-decision-tree.md` | **写任何分派/判定逻辑前必读**：决策树、报错串→动作、后处理、验收判据 |
| `verified-findings.md` | 需要实测证据、工具行为、坑的细节时（§10~§42，按节号 grep） |
| `agent-workflow.md` | Agent 攻坚怎么用/怎么审规则/怎么扩展白名单（唯一定义处） |
| `tutorials/` | 规则原始出处（用户提供的资料，勿删） |
| `galgame-ai-unpack-workflow-plan.md` | 完整方案、Windows 打包、许可证/法律 |
| `software-plan.md` | 软件化路线 |
| `_ui/` | 界面截图与 `shot_app.py`（改 UI 后核对） |
| `galgame_dispatch.py` / `planner.py` / `orchestrator.py` | 分派 / 提取计划 / 主编排（十条链路） |
| `toolbridge.py` | 外部工具桥（找工具+调用+数产物，rc 只进诊断） |
| `manifest.py` / `case_lib.py` / `manual.py` / `faillog.py` / `doctor.py` | 交付契约 / 案例查表 / 人工方案 / 失败日志 / 环境自检 |
| `diagnostics.py` / `experiences.py` / `errorcodes.py` / `agent_cli.py` / `sandbox/` | Agent 攻坚（诊断包 / 经验检索 / 错误码 / 六命令 / 动作+验证器） |
| `_unity_extract.py` / `_as_audio_collect2.py` | Unity 导出 / FSB5 按名补齐 |
| `krkr_auto_extract.py` / `_xp3_carve.py` | 加密 KiriKiri 动态提取 / index 兜底 |
| `build_exe.py` | 冻结 + 便携包（数据清单唯一出处，`--check` 单验） |
| `cases/` / `rules/` | 案例库（22 case） / 引擎指纹规则表 + 经验库 + 候选 |

## 维护纪律（本文档怎么长不大）★接手人必读★

1. **本文件 ≤400 行**：它只装「当前状态 + 待办 + 硬规矩 + 坑 + 索引」。
2. **新叙事/过程记录一律写 `verified-findings.md`**（带 § 号），本文件**只换状态块、
   不追加历史**；已完成事项在「历史节点索引」加一行。
3. 引擎细节写 verified-findings 或 decision-tree；本文件只留速查表。
4. 状态块超过 ~60 行就压缩：已稳定段落一句话进历史索引。
5. 交接协议见文末「接手顺序」——**新会话读完本文件即可开工，不需要再翻历史**。

## 历史节点索引（过程与证据都在 verified-findings.md，按 § 查）

| 日期 | 主题 | 证据 |
|---|---|---|
| 10-25~26 | SPITE(Electron/asar) + Ren'Py×2 + RPGMaker + AdvHD + Yu-Ris + ExHIBIT 首样本 | §10~15 |
| 10-27~28 | CatSystem2 逆向 / KiriKiri 动态提取全链 | §16 / §17 |
| 11-01 | 案例库 / PyInstaller 打包可行 | §18 / §19 |
| 11-02 | 打包三条必修 + 十样本 + Toshiue(Artemis) | §18.3 / §19.2 |
| 11-03 | 软件加固（假绿/假红根因） | §20 |
| 11-04 | v0.1.2 重跑口径 / 半自动协作 / faillog / v0.2.0~v0.4.2 输出目录系列 | §21~28 |
| 11-05 | 教师催眠2 复盘两个记录缺口 + v0.4.3 | §29 / §30 |
| 11-06 | v0.5.0 音频提速 / 输出不可写真因 / organize / v0.7.1 闭环 / v0.8.2 首发前 | §31 / §32 / git log |
| 11-07~08 | --allow-gui 实跑系列 / 死因闭环 / bugfix2~8 / 产物出库 | §33~38 |
| 11-08 | Unity bugfix11（同名去重） | §39 |
| 11-09~10 | Unity 队列 9/9 + 散装视频 + bugfix12/13 + 离线音频管线 + 抢救配方 | §40 / §41 |
| 11-09~10 | **Agent 攻坚 P0/P1/P2**（诊断包/经验库/沙箱/验证器/六命令） | §42 |
| 11-11 | bugfix13 交付 + GalgameOutput 只留记录 + AGENTS 瘦身（2386→220 行）+ **复盘审查**（taskbook 冻结崩溃修复、脚本丢失记录、11 条发现）| 状态块 / VF §43 |
| 11-11 | **aniyome 人工拖拽闭环**（手势定案：先拖 exe→提取 UI→Full Unpack→逐包拖；落点意外 + 三方对账一致）| VF §44 |

## 引擎分支速查（实测要点；细节见 verified-findings 对应 §）

| 引擎 | 判定 | 关键坑/出路 |
|---|---|---|
| KiriKiri | `.xp3`+已知包名 | 明文 GARbro 直解；加密走 `krkr_auto_extract --allow-gui`（真实桌面、ASCII stage）或人工拖 3 分钟；index 兜底仅明文索引（§17） |
| Ren'Py | `.rpa` | 正则抓索引头；offset/length 要 XOR key；patch 交集定语义；0 字节先查索引（§9/§11） |
| Unity | `*_Data`+ggm | JSON 枚举=唯一真相；FSB5 按名补齐；**批≤8**；data.unity3d 单文件输入（**aa 混合必须 folder**）；音频离线切片+vgmstream；散装视频按扩展名收（§8/§31/§39~41） |
| RPG Maker MV/MZ | NW.js 壳+www | 假头 16B + 前 16B XOR，key 在 System.json（§12） |
| AdvHD | AdvHD.exe+`.arc` | garbro_list 计数（无表头）；`.dat`=ASF→wmv；`.pna` carve（§13） |
| Yu-Ris | `pac/*.ypf` | GARbro 真不支持；自研 `_ypf_extract`（§14） |
| ExHIBIT | `.gyu/.grp` | 密钥在文件头；22 加密 BGM **显式排除并报出**（§15） |
| CatSystem2 | `.int`+cs2.exe | Blowfish-ECB 全包；扩展名二次轮换**按魔数归一**；护栏判据按平台语义（§16） |
| Artemis | `iarsys*.dll`+`.pfs` | SHA1(索引) 取 key；散装媒体单独对账（§18.3） |
| Tyrano/Electron | `app.asar` | 判得出无链路 rc=2；`asar_tool.py` 现成（§10） |

## 案例库与样本速览

- `cases/` **22 case / 14 签名**（2026-11-10）：13 个旧样本（manifest 4 + docs 8）+
  Unity 队列 9 部（manifest 绝对路径指 `D:\GalgameOutput`）。`--validate` 全过；
  dry-run 命中实测。**已知坑**：同签名靠 `discriminator` 区分；`engine` 必须用规范名；
  案例 `expected_total` 只进提示、**不进 reconcile**。
- 判定基线：`_fixtures/` 8 个（可重建，含 rpgmaker/advhd 补位）+ 12 真实样本（缺失即跳过），
  与 `tests/golden_detect.json` 逐字锁定——`python tests/make_golden.py --check` 应零漂移。
- **划走（用户明确不做，别再提）**：pf8/.pfs 家族 ×8、KAGUYA「LINK」.arc ×3（Bunny 的
  LINK6 同族，2026-11-10 复核维持）、夏への方舟 ×3、NekoSDK、夕凪荘 22 BGM 内存 dump、
  GUI 弹窗确认、安装器；出圈外：nier/nikke2/Miside/EnderLilies/EnderMagnolia。

## 归档与验收纪律（跨样本沉淀）

1. **先拿「地面真相」再动手**——索引/枚举是唯一权威；不预测工具行为。
2. **计数必须对账到 0**——「差不多」等于没验。
3. **验收看产物，不看退出码**——rc=0 而 0 文件是常态陷阱。
4. **数媒体按扩展名**，不按容器内流数（ffprobe 会把内嵌封面算成视频流）。
5. **patch 新增/覆盖用索引交集**判断，不猜。
6. **解包前看磁盘余量**（大样本解包后 ≈ 原包体积）。
7. **中途临时产物最终要清，但结论先转写文档**；「修逻辑+从源重跑」永远优于原地修数据。
8. 有意排除的输入必须**显式报出**（无声的漏验最危险）。

## 📋 待办（2026-11-11）

1. **Full Unpack 泛化**：昼下がり×2、Doinaka（9 包 krkrZ）——GUI 链独占真实桌面
   ~40 分钟/部，**等用户在场**。
2. ACE 来源排查（不阻塞；规矩：别在 D:\K\deepseek 树里跑 exe）。
3. **不要加暗色模式**（2026-11-06 用户明确）；**LINK6/KAGUYA 家族不做**（2026-11-10 复核）。
4. GitHub 恢复后再 push（账号封禁中，别反复试）。
5. aniyome 媒体去留等用户定夺（第 14 部闭环，其余 13 部已按「只留记录」清过）；
   `D:\GalgameOutput\KrkrExtract_Output\`（3.1G 冗余中间产物，已逐字对账进 raw\）去留同问；
   manual.log 模板两处欠准随下次发包一并修（VF §44.1：缺「先拖游戏 exe」步骤、
   重跑命令缺 `--organize`）。

## 🚀 接手顺序（新会话照此四步）

① **通读本文件**（≤400 行，一次读完）——当前状态/待办/坑/纪律全在；细节按文件索引跳。
② `git status`——工作树有未提交改动先问是不是修复产物；`git log --oneline -10` 看最近动作。
③ 跑基线：`C:\Python314\python.exe tests\run_all.py`（**不要裸 `python`**；判读看 junit 行，
   退出码本机不可信）+ `C:\Python314\python.exe tests\make_golden.py --check`（应零漂移；
   样本缺失先查盘再查代码）。
④ 用标准路径 `D:\GalgameUnpacker\orchestrator\orchestrator.exe`（或源码态
   `C:\Python314\python.exe orchestrator.py`）推进「待办」；改完先回写
   verified-findings（过程）+ 本文件（只换状态块），清临时产物，显式 add 提交。
