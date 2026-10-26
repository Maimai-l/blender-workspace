# 验证记录

**用时**：2026-10-26 23:23 开始，2026-10-27 02:22 完成（北京时间），共 2 小时 59 分钟。

所有检查都在用户电脑上实际运行：Windows，i7-14700KF，RTX 5070 Ti，Unity 6000.4.2f1，项目 `D:/Unity/Projects/Word Defence`。原始记录在 [`smoketest/`](smoketest/)。

## 总表

| # | 检查 | 结果 |
| --- | --- | --- |
| 1 | 编译 | 通过：0 错误。游戏代码 0 警告；全量重编译时另有 8 条警告，全部来自 MCP 插件包（见下文） |
| 2 | Play Mode：完整通关 | 通过 30/30（编辑器，重新打开项目后） |
| 3 | Play Mode：失败和重开 | 通过 13/13（编辑器，重新打开项目后） |
| 4 | 保存 → 关闭 → 重新打开 | 通过：编辑器真正重启，场景、组件、设置都在，0 个丢失脚本 |
| 5 | 生成 Windows 构建 | 通过：Succeeded，0 错误，0 警告，156 MB |
| 6 | 启动构建（不带参数，和双击一样） | 通过：窗口 “Word Defense” 正常运行和响应，正常关闭，日志无错误 |
| 7 | 构建冒烟测试：完整通关 | 通过 31/31 |
| 8 | 构建冒烟测试：失败和重开 | 通过 13/13 |
| 9 | 最终状态再次保存 → 关闭 → 重新打开 | 通过：重启后场景、组件和设置（包括最后改的 VSync）都在；Play Mode 通关 30/30、失败 13/13 |

## 测试方法

游戏里内置了 `AutoPilot`（`Scripts/Test/AutoPilot.cs`），只有带 `-autopilot` / `-autopilot-defeat` 参数启动构建，或在编辑器里调用 `WDTicker.RunAutopilot(1/2)` 时才会出现。它和玩家走同一条输入路径：通过 EventSystem 点击按钮、炮弹卡片和单词标签，用射线点击场景里的敌人，模拟按键（1–4、空格、Esc）。每一项检查读取游戏的真实状态（城堡耐久、连击、敌人速度、托盘内容、Boss 进度等），并截图。测试使用单独的学习记录 `memory_autotest.json`，开始时清空，不影响玩家自己的进度；测试期间静音。

**通关脚本**（30 或 31 项，Boss 句子有 4 个关键词时多一项）依次验证：标题界面和词库加载 → 开始游戏 → 故意答错一次 → 故意放一个敌人撞城 → 暂停和继续 → 连对 3 次后放寒霜齐射 → 四波正常作战，同时每一帧检查“托盘里至少一颗炮弹对应场上敌人”和“托盘有 3–4 颗炮弹” → Boss 战先故意打乱顺序、再按顺序打完所有关键词 → 胜利界面 → 再来一局 → 新一局里的记忆深刻炮弹自动发射并追踪命中。

**失败脚本**（13 项）：故意答错 3 次，然后不再防守，直到城堡被摧毁 → 失败界面 → 再来一局 → Esc 暂停 → 暂停菜单返回标题。

编辑器里 Play Mode 由 `WDTicker` 每秒推进 50 帧（编辑器在后台时 Unity 不走帧，见 CLAUDE.md）；构建版按真实时间运行。

## 1. 编译

- 每次修改后都检查了编译：0 错误，游戏代码（`Assets/WordDefense`）0 警告。
- 重新打开项目后做了一次清空缓存的全量重编译（`CompilationPipeline.RequestScriptCompilation(CleanBuildCache)`）：0 错误；8 条警告全部在 `D:\Unity\Packages\unity-mcp\MCPForUnity\Runtime\Helpers\`（MCP 插件调用了 Unity 6 已标记过时的 API，CS0618），与游戏无关。同样的 7 条也会出现在重编译后的第一次构建里。

## 2–3. Play Mode（重新打开项目后的编辑器）

记录：[`editor_victory_after_reopen.txt`](smoketest/editor_victory_after_reopen.txt)、[`editor_defeat_after_reopen.txt`](smoketest/editor_defeat_after_reopen.txt)。

- 通关 30/30：Boss 句子 “Refraining from food at night gives our bodies time to assimilate nutrients and rest.”（关键词 food、night、rest）；敌速第 1 波 ×1.00 → 第 4 波 ×1.50 → Boss ×1.82；2688 帧里每一帧都有对应场上敌人的炮弹；5903 帧里托盘从未少于 3 颗；19 个敌人单词和 19 个炮弹释义全部能在 `vocabulary.db` 的词条里找到；寒霜齐射把敌速从 1.71 降到 0.60 m/s；第二局记忆深刻炮弹 “baby” 自动追踪命中。
- 失败 13/13：3 次答错都有反馈，11 次撞城扣耐久，城堡归零进入失败界面，再来一局后城堡满耐久，暂停菜单能返回标题。
- 重新打开之前，每次修改界面后也在编辑器里跑过通关脚本（两次，都是 30/30）。

## 4. 保存 → 关闭 → 重新打开

记录：[`reopen_check.txt`](smoketest/reopen_check.txt)。

1. 保存场景和资源（`SaveOpenScenes`、`SaveAssets`），记下当时状态：编辑器已运行 10325 秒，场景没有未保存的修改。
2. `EditorApplication.OpenProject` 关闭编辑器并重新打开同一个项目；新的 Unity 进程 01:54:39 启动，18 秒后 MCP 重新连上。
3. 检查结果：编辑器运行 25 秒（确实是新进程），自动打开 `WordDefense.unity`，0 个丢失脚本，12 个游戏组件都在（相机、城堡、炮台、GameManager、环境动画），GameManager 的引用（城堡、炮台、相机、字体）都在；玩家设置（产品名、1600×900 窗口、后台运行、无启动画面、线性色彩空间）、构建场景列表、9 个模型和随包词库副本都在；控制台 0 错误 0 警告。
4. 然后做全量重编译（见上），并跑了第 2、3 项的两个 Play Mode 测试。

最后一次修改（VSync）和最终构建之后，又做了一遍同样的保存 → 关闭 → 重新打开（[`final_reopen_check.txt`](smoketest/final_reopen_check.txt)）：新进程运行 23 秒时检查，结果同上，VSync 设置也保留了；控制台 0 错误 0 警告；在这个编辑器里再跑两个 Play Mode 测试：通关 30/30（[`editor_victory_final.txt`](smoketest/editor_victory_final.txt)），失败 13/13（[`editor_defeat_final.txt`](smoketest/editor_defeat_final.txt)）。

## 5. 构建

- `Word Defense → Build Windows Player`（`WDBuild.BuildWindows`）：Succeeded，0 错误，0 警告，156 MB，输出 `Builds/Windows/WordDefense.exe`。构建前自动把 `文档\vocabulary.db` 同步到随包副本。
- 构建前把 VSync 设为开（见“最后的修改”），之前一次全量重编译后的构建同样成功，只有上面那 7 条 MCP 插件警告。

## 6. 启动构建

记录：[`build_plain_launch.txt`](smoketest/build_plain_launch.txt)。

不带任何参数启动 `WordDefense.exe`，15 秒后：进程在运行并响应，窗口标题 “Word Defense”；通过关闭窗口正常退出，退出码 0。`Player.log` 没有异常或错误，记录了词库加载：`C:\Users\blender\Documents\vocabulary.db`，95,297 行，中等难度 1,113 个词、42 个 Boss 长句，约 0.76 秒。

## 7–8. 构建冒烟测试

记录：[`build_victory.txt`](smoketest/build_victory.txt)、[`build_defeat.txt`](smoketest/build_defeat.txt)，以及播放器日志 [`player_victory.log`](smoketest/player_victory.log)、[`player_defeat.log`](smoketest/player_defeat.log)。截图在 [`screenshots/`](screenshots/)。

- **完整通关 31/31**（Boss 句子 “Census data show that the number of unwed couples living together rose sharply last year.”，4 个关键词 census、data、show、year）：
  - 词库：`C:\Users\blender\Documents\vocabulary.db`，95,297 行；中等难度（difficulty 0.4–0.6）3,613 行 → 清洗后 2,803 个可用 → 1,113 个出题词，42 个 Boss 长句；后台读取 0.78 秒；
  - 故意答错：炮弹被弹开、连击 2 → 0、炮台装填、炮弹留在托盘、敌人亮出真正释义“统计”；
  - 故意漏掉一个敌人：城堡 100 → 90；
  - Esc 暂停时间停止，继续后恢复；
  - 连对 3 次后空格放寒霜齐射：场上敌人 2.31 → 0.81 m/s；
  - 敌速：第 1 波 ×1.00 → 第 4 波 ×1.53 → Boss ×1.86；
  - 350,292 帧里每一帧都有炮弹对应场上的敌人，674,396 帧里托盘从未少于 3 颗（锁屏时帧率上千，所以帧数很大）；
  - 20 个敌人单词和 20 个炮弹释义全部来自词库；
  - Boss：先用后面关键词的释义打，被挡开（顺序不对）且进度不变；再按顺序打完 4 个关键词 → 胜利界面；
  - 本局得分 10,210，正确率 95%，最佳连击 ×30；
  - 再来一局：新一局满耐久、得分清零，3 个记忆深刻的词进入新词组，金色炮弹 “egoism” 点一下自动发射并追踪命中。
- **失败和重开 13/13**：3 次答错都有反馈，11 次撞城，城堡归零进入失败界面；再来一局后城堡满耐久；Esc 暂停，暂停菜单返回标题。
- 两次运行的播放器日志都没有异常或错误，测完自动退出。

## 必需玩法对照

| 要求 | 怎么验证的（记录里的检查项） |
| --- | --- |
| 1 敌人沿道路走向城堡，单词清楚可见 | 敌人沿 Blender 导出的道路曲线行走；单词标签每帧跟随，截图 `02_wave` |
| 2 始终 3–4 个释义炮弹，至少一个对应场上敌人 | “3-4 shells in the tray”、“a shell always matched an enemy on the field”（逐帧检查，0 次违反） |
| 3 先点炮弹再点敌人；答对击倒、答错有反馈 | 全部射击都通过点击卡片和点击敌人完成；“wrong match: shell bounces off …”，截图 `03_wrong` |
| 4 撞城扣血，归零失败 | “an enemy reaching the castle damages it”、“castle destroyed -> defeat screen” |
| 5 速度随进度上升 | “enemy speed rises with progress (x1.00 … x1.5 … x1.8)” |
| 6 连对 3 次放减速技能 | “3 correct in a row charge 寒霜齐射; Space slows every enemy” |
| 7 记忆深刻的炮弹自动追踪 | “a word became 记忆深刻 …”、“记忆深刻 shell … fired itself and homed in (second game)” |
| 8 Boss 长句，按顺序打关键词 | “boss: a later keyword's meaning out of order is rejected”、“boss keyword N broken in order” |
| 9 单词和释义来自本地词库 | “word pool and boss sentences built from the local database”、“every pool word has medium difficulty”、“all … come from vocabulary.db” |
| 10 HUD 显示城堡耐久、连击进度、技能状态 | 截图：左上耐久条，右上得分和连击，左下寒霜齐射三段充能环和状态文字 |
| 11 击败 Boss 胜利；胜负都能重开 | “boss sentence broken -> victory screen”、“clicked 再来一局 on the victory/defeat screen”、“restart …” |
| 12 保存、关闭、重新打开后仍正常 | 第 4 项和重新打开后的第 2、3 项 |
| 13 独立构建可启动并通过冒烟测试 | 第 5–8 项 |

## 最后的修改

验证过程中发现并修好的问题：

- **截图合成**：原来的离屏截图把半透明界面的透明度算错了（面板看起来比屏幕上更深、红色受伤效果像一层粉雾）。改成把界面分别画在黑底和白底上，精确还原颜色和覆盖率；和编辑器 Game 视图的真实截图逐像素对比一致。
- **界面在屏幕上偏浅**：项目用线性色彩空间，Unity 在线性空间混合界面，深色半透明面板压在明亮的浮岛上显得像灰色。把面板不透明度从 0.80/0.88 提到 0.94/0.95，加深暂停和结算的遮罩、标题页左侧渐变和波次横幅的底衬。
- **受伤效果**：改成只沿屏幕四边泛红的光晕；寒霜和受伤的色调放到 HUD 下面，只染场景，不染面板。
- **答错提示**挪到敌人脚下，不再盖住它的单词；同时弹出的多个飘字靠近屏幕顶部时保持间距。
- **标题页**一开始不再闪过 HUD。
- **VSync**：原来关闭，构建在普通显示器上会以 1000 帧以上空跑；现在所有画质档都开启。
- 自动测试改为按真实时间等待界面动画再截图（构建在锁屏时上千帧每秒，按帧数等待会截到半透明的过渡画面），并在测试时静音。

## 说明

- **锁屏**：测试时电脑处于锁屏状态，构建的窗口不往屏幕输出画面，所以截图是把相机离屏渲染后合成的（`AutoPilot.CaptureOffscreen`），帧耗时也是渲染到 RenderTexture 后测的。锁屏时 VSync 不起作用，帧率会到上千，这是正常的。
- **性能**：每帧约 0.72 毫秒（1600×900，测量时临时关闭 VSync；最终构建在胜利界面测得，前一次构建在第 3 波场上 3 个敌人时也是 0.72 毫秒）。
- **日志里的无害信息**：`d3d12: failed to query info queue interface`（没有安装 D3D 调试层）、`Failed to get first mouse position!`（锁屏时没有鼠标位置），编辑器里偶尔出现的 “JobTempAlloc” 内部提示。
- **随机性**：每局的 Boss 句子从 42 句里排名靠前的 12 句中随机选（不与上一局重复），所以各次记录里的句子不同。
