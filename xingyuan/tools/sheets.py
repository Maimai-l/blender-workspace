# Build labelled side-by-side comparison sheets: reference photo (left) vs Blender render from the matched camera (right).
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from xyp import S, font as _xyfont
F = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'   # falls back via xyp.font
VIEWS = [
    ('aerial', '航拍（9 点标定机位，误差约 4 px）'),
    ('B1court', 'B1 院 · 向南看院门'),
    ('B1pav', 'B1 亭'),
    ('A2', 'A2 檐廊与匾额（照片在排版中被裁切并纵向拉伸约 1.47 倍，渲染按同比例拉伸；为看清立面，渲染隐藏了 B1 院树木）'),
    ('A5', 'A5 与许愿池'),
    ('B3north', 'B3 · 向北看北亭'),
    ('B3south', 'B3 · 向南看南亭'),
    ('B2', 'B2 竹林甬道 · A4'),
    ('A3porch', 'A3 前檐廊'),
]
def font(sz):
    return _xyfont(F, sz)
sheets = []
for key, title in VIEWS:
    a = Image.open('%s/refc/%s.jpg' % (S, key)).convert('RGB')
    b = Image.open('%s/deliver/对照_%s.jpg' % (S, key)).convert('RGB')
    if b.size[0] / b.size[1] > a.size[0] / a.size[1] * 1.15:          # render stretched to the photo's distorted aspect
        b = b.resize((b.size[0], int(b.size[0] * a.size[1] / a.size[0])), Image.LANCZOS)
    h = 900 if a.size[0] / a.size[1] < 1.6 else 640
    a = a.resize((int(a.size[0] * h / a.size[1]), h), Image.LANCZOS)
    b = b.resize((int(b.size[0] * h / b.size[1]), h), Image.LANCZOS)
    pad, top = 24, 96
    W = a.size[0] + b.size[0] + pad * 3
    H = h + top + pad
    out = Image.new('RGB', (W, H), (246, 244, 240))
    d = ImageDraw.Draw(out)
    d.text((pad, 14), title, fill=(30, 30, 30), font=font(30))
    d.text((pad, top - 30), '参考照片', fill=(110, 110, 110), font=font(20))
    d.text((pad * 2 + a.size[0], top - 30), 'Blender 渲染（对照机位）', fill=(110, 110, 110), font=font(20))
    out.paste(a, (pad, top)); out.paste(b, (pad * 2 + a.size[0], top))
    p = '%s/deliver/并排对比_%s.jpg' % (S, key)
    out.save(p, quality=90)
    sheets.append(out)
    print(p, out.size)
# overview contact sheet (scaled)
thumbs = []
for s in sheets:
    w = 1400
    thumbs.append(s.resize((w, int(s.size[1] * w / s.size[0])), Image.LANCZOS))
Ht = sum(t.size[1] for t in thumbs) + 12 * (len(thumbs) - 1)
cs = Image.new('RGB', (1400, Ht), (255, 255, 255))
y = 0
for t in thumbs:
    cs.paste(t, (0, y)); y += t.size[1] + 12
cs.save('%s/deliver/并排对比_总览.jpg' % S, quality=86)
print('contact', cs.size)
