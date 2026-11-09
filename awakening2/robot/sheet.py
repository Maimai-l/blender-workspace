"""Model-sheet renderer: front, 3/4, side and back views of a rig in a neutral pose."""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'engine'))
sys.path.insert(0, HERE)
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import r3d, cel
from rig import PAINT, METAL, LENS, GLOW, DARK, LIDS, MOSS, WOOD, CABLE


def view_cam(az_deg, height, dist, target_z, lens=120, W=900, H=1300, elev_target=None):
    a = np.radians(az_deg)
    # az 0 = front (camera on +Y looking toward -Y)
    pos = (dist * np.sin(a), dist * np.cos(a), height)
    tgt = (0, 0, target_z if elev_target is None else elev_target)
    return r3d.Camera(pos, tgt, lens=lens, W=W, H=H)


def sheet(rig, pose, pal, out_path, title, light=(0.5, 0.6, 0.8), emissive=None, extra_style=None,
          views=((0, 'FRONT'), (35, '3/4'), (90, 'SIDE'), (180, 'BACK')), dist=95, lens=120,
          target_z=10.5, W=900, H=1300, ss=2):
    rig.build_meshes()
    tiles = []
    for az, label in views:
        cam = view_cam(az, target_z + 1.5, dist, target_z, lens=lens, W=W, H=H)
        # light rotates with the view so every view is lit from upper left-front
        a = np.radians(az)
        Lx, Ly, Lz = light
        Lw = (Lx * np.cos(a) + Ly * np.sin(a), -Lx * np.sin(a) + Ly * np.cos(a), Lz)
        st = dict(light=Lw, pal=pal, ss=ss, emissive=emissive or {}, seed=az)
        if extra_style:
            st.update(extra_style)
        t = time.time()
        rgba = cel.render(rig, pose, cam, st)
        print(f'  view {label}: {time.time()-t:.1f}s')
        tiles.append((cel.to_u8(cel.on_paper(rgba)), label))
    # silhouette thumbnails (readability test at thumbnail size)
    thumbs = []
    for img, label in tiles:
        g = img.astype(np.float32).mean(-1)
        sil = (g < 225).astype(np.uint8) * 255
        th = cv2.resize(255 - sil, (W // 6, H // 6), interpolation=cv2.INTER_AREA)
        thumbs.append(th)
    pad = 30
    sheet = Image.new('RGB', (len(tiles) * W + pad * 2, H + 140 + H // 6 + 20), (245, 240, 228))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 40)
        font2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
    except Exception:
        font = font2 = None
    d.text((pad, 20), title, fill=(60, 40, 35), font=font)
    for i, (img, label) in enumerate(tiles):
        sheet.paste(Image.fromarray(img), (pad + i * W, 100))
        d.text((pad + i * W + 20, 110), label, fill=(120, 90, 80), font=font2)
    for i, th in enumerate(thumbs):
        sheet.paste(Image.fromarray(th).convert('RGB'), (pad + i * (W // 6 + 20), H + 120))
    d.text((pad + len(thumbs) * (W // 6 + 20) + 20, H + 160), 'silhouettes at thumbnail size', fill=(120, 90, 80), font=font2)
    sheet.save(out_path, quality=90)
    print('wrote', out_path)
