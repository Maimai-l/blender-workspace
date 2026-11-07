#!/usr/bin/env python3
"""Fill C:\\Users\\blender\\Documents\\qiting\\交付 and refresh the repo copies in ../deliverables.

    deliver.py

- 对照渲染: the comparison renders (renders\\cmp_<view>.jpg on the PC), as 对照_<name>.jpg
- 并排对比: reference | render side by side and the 50 % overlays (made in the session by cmpview.py), and an
  overview sheet of all of them
- 效果图: the beauty shots (renders\\hero_*.jpg / .png on the PC)
- 说明.md and 尺寸表.md: ../README.md and ../docs/dimensions.md
The repo keeps downscaled copies of the side-by-sides, the overview and the beauty shots."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xyp, pcx
from PIL import Image

VIEWS = [('W02', '侧面'), ('P340d', '西侧'), ('W01', '近景仰视'), ('Paf3b', '台阶正面'), ('P419', '傍晚有人物'),
         ('A1', '航拍A1'), ('A2', '航拍A2')]
HEROES = [('hero_stair', '台阶'), ('hero_sw', '西南'), ('hero_eave', '檐下'), ('hero_relief', '浮雕'), ('hero_aerial', '鸟瞰'),
          ('hero_dusk', '傍晚'), ('hero_lake', '湖景'), ('hero_shore', '湖岸'), ('hero_garden', '东侧草坪'),
          ('hero_vista', '远眺紫云楼')]
R = xyp.PC_ROOT
S = os.path.join(xyp.S, 'renders')
REPO = os.path.join(xyp.PROJ, 'deliverables')

# 1. copies made on the PC
cmds = ['cd "%s"' % pcx._unix(R), 'mkdir -p 交付/对照渲染 交付/并排对比 交付/效果图']
for cal, cn in VIEWS:
    cmds.append('cp -f renders/cmp_%s.jpg "交付/对照渲染/对照_%s.jpg"' % (cal, cn))
for h, cn in HEROES:
    cmds.append('cp -f renders/%s.jpg "交付/效果图/效果图_%s.jpg"' % (h, cn))
    cmds.append('cp -f renders/%s.png "交付/效果图/效果图_%s.png"' % (h, cn))
print(pcx.bash(' && '.join(cmds) + ' && echo copied on the PC'))

# 2. side-by-sides, overlays and the overview sheet
rows = []
for cal, cn in VIEWS:
    sbs = os.path.join(S, 'sbs_%s.jpg' % cal)
    pcx.put(sbs, R + '\\交付\\并排对比\\并排对比_%s.jpg' % cn)
    pcx.put(os.path.join(S, 'ovl_%s.jpg' % cal), R + '\\交付\\并排对比\\叠加_%s.jpg' % cn)
    rows.append(Image.open(sbs).convert('RGB'))
W = 2400
rows = [im.resize((W, int(im.size[1] * W / im.size[0])), Image.LANCZOS) for im in rows]
sheet = Image.new('RGB', (W, sum(im.size[1] for im in rows) + 12 * (len(rows) - 1)), (255, 255, 255))
y = 0
for im in rows:
    sheet.paste(im, (0, y))
    y += im.size[1] + 12
ov = os.path.join(S, '并排对比_总览.jpg')
sheet.save(ov, quality=85)
pcx.put(ov, R + '\\交付\\并排对比\\并排对比_总览.jpg')
print('side-by-sides, overlays and overview uploaded')

# 3. notes
pcx.put(os.path.join(xyp.PROJ, 'README.md'), R + '\\交付\\说明.md')
pcx.put(os.path.join(xyp.PROJ, 'docs', 'dimensions.md'), R + '\\交付\\尺寸表.md')
print('notes uploaded')

# 4. repo copies, downscaled
os.makedirs(REPO, exist_ok=True)
for cal, cn in VIEWS:
    im = Image.open(os.path.join(S, 'sbs_%s.jpg' % cal)).convert('RGB')
    im.thumbnail((2000, 2000), Image.LANCZOS)
    im.save(os.path.join(REPO, '并排对比_%s.jpg' % cn), quality=82)
im = sheet.copy()
im.thumbnail((1600, 4000), Image.LANCZOS)
im.save(os.path.join(REPO, '并排对比_总览.jpg'), quality=80)
for h, cn in HEROES:
    im = Image.open(os.path.join(S, h + '.jpg')).convert('RGB')
    im.thumbnail((1600, 1600), Image.LANCZOS)
    im.save(os.path.join(REPO, '效果图_%s.jpg' % cn), quality=85)
print('repo copies written to', REPO)
