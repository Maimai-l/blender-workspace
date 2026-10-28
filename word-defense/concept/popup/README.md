# 立体书场景原型

一本打开成 90° 的立体书：地面页是战场，后页是夜空。敌人从后页被撕开的洞里出来，沿着小路走到右前方的城堡。全部用 Blender 搭建，所有景物都是带厚度的纸片，城堡里的灯从窗户和纸墙透出来。

| 图 | 内容 |
| --- | --- |
| `game.jpg` | 游戏镜头 |
| `book.jpg` | 整本书 |
| `stage.jpg` | 低机位，看纸片前后分层 |
| `castle.jpg` | 城堡近景 |
| `tear.jpg` | 撕开的出生点 |
| `pond.jpg`、`rows.jpg` | 池塘和中排景物近景 |

Blender 文件在用户电脑上：`C:\Users\blender\Documents\WordDefense\popup\WD_Popup.blend`，图里的每个视角都存成了相机（`Cam_Game`、`Cam_Book` 等）。

## 重新生成

脚本在 [`blender/`](../../blender/)，放到 `C:\Users\blender\Documents\WordDefense\scripts\` 后，在打开的 `WD_Popup.blend` 里运行：

1. `pp_scene.py`：清空并重建整个场景（书、天空页、撕口、各排纸片、路、河、池塘、城堡、灯光、相机）。
2. `pp_final.py`：渲染上面的七张图。

`pp_lib.py` 是纸张材质和裁纸工具，`pp_shapes.py` 是树、灌木、山等剪影，`pp_castle.py` 是城堡。
