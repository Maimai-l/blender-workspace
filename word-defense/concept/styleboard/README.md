# 美术方向风格板

三个东方方向的立体书场景：孤城、青绿山水、月下水乡。三张图用同一本书、同一个机位、同一条路线，只换意象、配色、光线和造型，可以直接对比。

画板：https://claude.ai/artifact/FM5csFa55frvYwgFceSvkm

| 图 | 内容 |
| --- | --- |
| `scene_a.jpg` | 孤城：黄昏逆光，皮影骑兵从长城缺口的沙尘里出来，夯土孤城用火箭守城 |
| `scene_b.jpg` | 青绿山水：绢本青绿，墨兽从烧穿的绢面爬出，柳堤是路，命中时盖朱印 |
| `scene_c.jpg` | 月下水乡：月夜水巷，乌篷船从夜雾里驶出，河道是路，水城门放烟火 |
| `tiles/` | 每个方向六张特写：城（`cheng`）、源（`yuan`）、敌（`di`）、路（`lu`）、木（`mu`）、技（`ji`） |

## 重新生成

脚本在 [`tools/styleboard/`](../../tools/styleboard/)，需要 Python 3（numpy）和 Node（Playwright 自带的 Chromium）。在该目录下运行：

1. `python3 scene_a.py`：生成 `out/scene_a.svg`（`scene_b.py`、`scene_c.py` 同理）。
2. `node render.js 1600 900 2 out/scene_a.svg out/scene_a.png`：按两倍分辨率渲染成图。
3. `python3 tiles.py a`：渲染孤城的六张特写（`b`、`c` 同理）。

`eng.py` 是透视相机和纸片渲染，`arch.py` 是城墙、城楼、屋顶、民居、拱桥，`nature.py` 是书本、山、树、台地，`figures.py` 是皮影、墨兽和墨灵。
