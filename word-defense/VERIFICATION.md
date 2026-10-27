# 验证记录

## 用时

北京时间。

| 工作 | 开始 | 完成 | 用时 |
| --- | --- | --- | --- |
| 制作游戏 | 2026-10-26 23:23 | 2026-10-27 02:22 | 2 小时 59 分钟 |
| 重写 HUD 和界面 | 2026-10-27 18:21 | 2026-10-27 20:03 | 1 小时 42 分钟 |

所有检查都在用户电脑上实际运行：Windows，i7-14700KF，RTX 5070 Ti，Unity 6000.4.2f1，项目 `D:/Unity/Projects/Word Defence`。下面是界面重写后、在最终代码上的结果，原始记录在 [`smoketest/`](smoketest/)。

## 总表

| # | 检查 | 结果 |
| --- | --- | --- |
| 1 | 编译 | 通过：0 错误，0 警告 |
| 2 | 保存 → 关闭 → 重新打开 | 通过：22 秒后新编辑器打开同一项目，场景、组件、字体和设置都在，0 个丢失脚本，控制台 0 错误 0 警告 |
| 3 | Play Mode：完整通关 | 通过 36/36，在重新打开后的编辑器里 |
| 4 | Play Mode：失败和重开 | 通过 19/19，同上 |
| 5 | 生成 Windows 构建 | 通过：Succeeded，0 错误，0 警告，175 MB |
| 6 | 构建冒烟测试：完整通关 | 通过 36/36 |
| 7 | 构建冒烟测试：失败和重开 | 通过 19/19 |
| 8 | 启动构建，不带参数，和双击一样 | 通过：窗口 “Word Defense” 正常运行和响应，正常关闭，日志无错误 |

## 测试方法

游戏里内置了 `AutoPilot`（`Scripts/Test/AutoPilot.cs`），只有带 `-autopilot` / `-autopilot-defeat` 参数启动构建，或在编辑器里调用 `WDTicker.RunAutopilot(1/2)` 时才会出现。它和玩家走同一条输入路径：通过 EventSystem 点击按钮、释义和单词标签，用射线点击场景里的敌人，模拟按键（1–4、空格、Esc）。每一项检查读取游戏的真实状态（城堡耐久、连击、敌人速度、托盘内容、Boss 进度等），并截图。测试使用单独的学习记录 `memory_autotest.json`，开始时清空，不影响玩家自己的进度；测试期间静音。

**通关脚本**依次验证：标题界面和词库加载 → 打开再关闭“玩法” → 开始游戏 → 故意答错一次 → 故意放一个敌人撞城 → 暂停和继续 → 连对 3 次后放寒霜齐射 → 四波正常作战，同时每一帧检查“至少一个释义对应场上的敌人”和“托盘里有 3–4 个释义” → Boss 战先故意打乱顺序，再按顺序打完所有关键词 → 胜利界面 → 再来一局 → 新一局里记忆深刻的释义自动发射并追踪命中。每个 Boss 关键词算一项，所以 Boss 句子有 4 个关键词时比 3 个时多一项。

**失败脚本**：打开再关闭“玩法” → 开始游戏 → 故意答错 3 次，然后不再防守，直到城堡被摧毁 → 失败界面 → 再来一局 → Esc 暂停 → 暂停菜单返回标题。

两个脚本都有两项贯穿全程的检查：

- 运行期间不能出现任何错误或异常日志。唯一放行的是锁屏时播放器启动打印的 “Failed to get first mouse position!”，这时没有前台窗口，取不到鼠标位置。
- 文字里的格式标记必须全部生效：每 0.2 秒扫描一次界面上所有带标记的文字，只要有 `<font=…>` 这类标记被原样显示出来就算失败。

编辑器里 Play Mode 由 `WDTicker` 推进，因为编辑器在后台时 Unity 不走帧（见 CLAUDE.md）；构建版按真实时间运行。

## 1. 编译

每次修改后都检查了编译：0 错误，游戏代码 0 警告。生成构建时为播放器重新编译脚本，同样 0 错误 0 警告。

## 2. 保存 → 关闭 → 重新打开

记录：[`reopen_check.txt`](smoketest/reopen_check.txt)。

1. 19:47:40 保存场景和资源（`SaveOpenScenes`、`SaveAssets`），记下当时状态：编辑器已运行 554 秒，场景没有未保存的修改。
2. `EditorApplication.OpenProject` 关闭编辑器并重新打开同一个项目，22 秒后新编辑器响应。
3. 19:48:09 检查：编辑器运行 28 秒，确实是新进程；自动打开 `WordDefense.unity`，0 个丢失脚本，12 个游戏组件都在；GameManager 的引用都在，包括 6 种字体和 6 个光晕材质；玩家设置（产品名、1600×900 窗口、后台运行、无启动画面、线性色彩空间）、构建场景列表、9 个模型和随包词库副本都在；控制台 0 错误 0 警告。
4. 第 3、4 项的两个 Play Mode 测试就在这个重新打开的编辑器里运行。

## 3–4. Play Mode

记录：[`editor_victory_after_reopen.txt`](smoketest/editor_victory_after_reopen.txt)、[`editor_defeat_after_reopen.txt`](smoketest/editor_defeat_after_reopen.txt)。

- **完整通关 36/36**：Boss 句子 “I still have a cherished photo of him in his apron, standing over the grill, spatula in hand, smiling.”，关键词 photo、apron、hand。
  - 故意答错：炮弹被弹开，连击 2 → 0，炮台装填，释义留在托盘，敌人亮出真正的释义“照片”；
  - 故意漏掉一个敌人：城堡 100 → 90；
  - 连对 3 次后按空格放寒霜齐射：场上敌人 2.31 → 0.81 m/s；
  - 敌速：第 1 波 ×1.00 → 第 4 波 ×1.52 → Boss ×1.84；
  - 2,989 帧里每一帧都有释义对应场上的敌人，6,217 帧里托盘从未少于 3 个；19 个敌人单词和 19 个释义全部来自词库；
  - 本局得分 9,900，正确率 95%，最高连击 30；
  - 再来一局：3 个记忆深刻的词进入新词组，金色释义 “policy” 点一下就自动发射并追踪命中；
  - 74 段带格式标记的文字全部正确显示。
- **失败和重开 19/19**：打开和关闭玩法页；3 次答错都有反馈，11 次撞城扣耐久，城堡归零进入失败界面；再来一局后城堡满耐久；Esc 暂停，暂停菜单返回标题；20 段带格式标记的文字全部正确显示。

## 5. 构建

- `Word Defense → Build Windows Player`（`WDBuild.BuildWindows`）：Succeeded，0 错误，0 警告，175 MB，用时 11 秒，输出 `Builds/Windows/WordDefense.exe`。构建前自动把 `文档\vocabulary.db` 同步到随包副本。
- 体积比第一轮的 156 MB 大：新换的思源宋体三种字重的字库共约 36 MB，替换了第一轮约 18 MB 的字体。

## 6–7. 构建冒烟测试

记录：[`build_victory.txt`](smoketest/build_victory.txt)、[`build_defeat.txt`](smoketest/build_defeat.txt)，以及播放器日志 [`player_victory.log`](smoketest/player_victory.log)、[`player_defeat.log`](smoketest/player_defeat.log)。截图在 [`screenshots/`](screenshots/)。

- **完整通关 36/36**：Boss 句子 “Some people are very picky about who they choose to share their lives with.”，关键词 picky、choose、share。
  - 词库：`C:\Users\blender\Documents\vocabulary.db`，95,297 行；中等难度 3,613 行，清洗后 2,803 个可用，其中 1,113 个用来出题，另有 42 个 Boss 长句；后台读取 0.76 秒；
  - 故意答错：炮弹被弹开，连击 2 → 0，炮台装填，释义留在托盘，敌人亮出真正的释义“挑剔的”；
  - 故意漏掉一个敌人：城堡 100 → 92；
  - 连对 3 次后按空格放寒霜齐射：场上敌人 1.71 → 0.60 m/s；
  - 敌速：第 1 波 ×1.00 → 第 4 波 ×1.49 → Boss ×1.81；
  - 330,607 帧里每一帧都有释义对应场上的敌人，797,308 帧里托盘从未少于 3 个，锁屏时帧率上千，所以帧数很大；19 个敌人单词和 19 个释义全部来自词库；
  - Boss：先用后面关键词的释义打，被挡开且进度不变；再按顺序打完 3 个关键词，进入胜利界面；
  - 本局得分 9,900，正确率 95%，最高连击 30，用时 1:57；
  - 再来一局：新一局满耐久、得分清零，3 个记忆深刻的词进入新词组，金色释义 “brush” 点一下就自动发射并追踪命中；
  - 69 段带格式标记的文字全部正确显示。
- **失败和重开 19/19**：打开和关闭玩法页；3 次答错都有反馈，12 次撞城扣耐久，城堡归零进入失败界面；再来一局后城堡满耐久；Esc 暂停，暂停菜单返回标题；21 段带格式标记的文字全部正确显示。
- 两次运行的播放器日志都没有异常或错误，测完自动退出。

## 8. 启动构建

记录：[`build_plain_launch.txt`](smoketest/build_plain_launch.txt)。

不带任何参数启动 `WordDefense.exe`，15 秒后：进程在运行并响应，窗口标题 “Word Defense”，占用内存 829 MB；关闭窗口后正常退出，退出码 0。`Player.log` 共 44 行，没有异常或错误，记录了词库加载：`C:\Users\blender\Documents\vocabulary.db`，95,297 行，中等难度 1,113 个词、42 个 Boss 长句，0.76 秒。

## 必需玩法对照

| 要求 | 怎么验证的（记录里的检查项） |
| --- | --- |
| 1 敌人沿道路走向城堡，单词清楚可见 | 敌人沿 Blender 导出的道路曲线行走；单词标签每帧跟随，截图 `02_wave` |
| 2 始终 3–4 个释义炮弹，至少一个对应场上敌人 | “3-4 shells in the tray”、“a shell always matched an enemy on the field”，逐帧检查，0 次违反 |
| 3 先点炮弹再点敌人；答对击倒、答错有反馈 | 全部射击都通过点击释义和点击敌人完成；“wrong match: shell bounces off …”，截图 `03_wrong` |
| 4 撞城扣血，归零失败 | “an enemy reaching the castle damages it”、“castle destroyed -> defeat screen” |
| 5 速度随进度上升 | “enemy speed rises with progress” |
| 6 连对 3 次放减速技能 | “3 correct in a row charge 寒霜齐射; Space slows every enemy” |
| 7 记忆深刻的炮弹自动追踪 | “a word became 记忆深刻 …”、“记忆深刻 shell … fired itself and homed in (second game)” |
| 8 Boss 长句，按顺序打关键词 | “boss: a later keyword's meaning out of order is rejected”、“boss keyword N broken in order” |
| 9 单词和释义来自本地词库 | “word pool and boss sentences built from the local database”、“every pool word has medium difficulty”、“all … come from vocabulary.db” |
| 10 HUD 显示城堡耐久、连击进度、技能状态 | 截图：左上城堡耐久条，掉血时留一段红色残影；右上得分和连击；左下寒霜圆盘的三段充能，充满后旁边出现“空格”，释放时蓝环随剩余时间收缩 |
| 11 击败 Boss 胜利；胜负都能重开 | “boss sentence broken -> victory screen”、“clicked 再来一局 on the victory/defeat screen”、“restart …” |
| 12 保存、关闭、重新打开后仍正常 | 第 2 项，以及在重新打开的编辑器里跑的第 3、4 项 |
| 13 独立构建可启动并通过冒烟测试 | 第 5–8 项 |

## 界面重写中发现并修好的问题

- **格式标记被原样显示**：连击数和“单词 释义”飘字用 `<font=… material=…>` 给英文换字体并保留光晕。注册光晕材质时用了区分大小写的哈希，而 TMP 解析标记时按不区分大小写的哈希查找，找不到材质就把整段标记当文字显示出来。在最终构建的截图里发现，改用相同的哈希后正常；同时给两个测试脚本加了上面那项“格式标记必须全部生效”的检查。之前没发现，是因为改动之后看过的截图里恰好都没有连击和飘字。
- **第二局界面失灵**：再来一局时重复注册同一个光晕材质会抛异常，第二局的界面停止更新。加了判断；同时给测试加上“运行期间不能有错误日志”的检查。
- **结算页文字重叠**：TMP 不能在隐藏的界面里测量文字高度，Boss 句子和译文叠在一起。改成先显示结算页，再按实际高度排版。
- **玩法页排版**：规则文字互相重叠，按键说明压住“关闭”按钮。改成按每段文字的实际高度依次排下来。
- **飘字像按钮**：飘字原来带纸色底板，看起来像能点的单词标签。改成只有文字和光晕，纸色只留给能点的东西。

## 说明

- **锁屏**：测试时电脑处于锁屏状态，构建的窗口不往屏幕输出画面，所以截图是把相机离屏渲染后合成的（`AutoPilot.CaptureOffscreen`），帧耗时也是渲染到 RenderTexture 后测的。锁屏时 VSync 不起作用，帧率会到上千，这是正常的。
- **性能**：构建版每帧约 0.96 毫秒（第 3 波，场上 3 个敌人）和 0.76 毫秒（胜利界面），1600×900，测量时临时关闭 VSync。
- **旧字体**：第一轮的 Inter 和思源黑体字库及其字体资源还留在 `Assets/WordDefense/Fonts`，已经没有任何引用，不会打进构建。Unity MCP 不允许删除资源，所以没有删。
- **日志里的无害信息**：`d3d12: failed to query info queue interface`（没有安装 D3D 调试层）、`Failed to get first mouse position!`（锁屏时没有鼠标位置），以及编辑器里偶尔出现的 “JobTempAlloc” 内部提示。
- **随机性**：每局的 Boss 句子从 42 句里排名靠前的 12 句中随机选，不与上一局重复，所以各次记录里的句子不同。
