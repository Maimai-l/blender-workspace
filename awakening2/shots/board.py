"""Storyboard thumbnails and the animatic, rendered from shotdefs.

Boards: rough screen-space layouts — sky, horizon, the giant trunks
(projected from the world layout so every board agrees), canopy band with
the gap, a light-direction arrow, and the robot drawn by the cel engine.
"""
import os, sys, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import shotdefs as SD
import anim
import r3d, cel
import warden as WD

OUT = os.path.join(HERE, '..', 'board')
# giant trunks around the robot: (x, y, radius)
TREES = [(-15, 13, 2.8), (12, 12, 3.2), (-9, -13, 2.4), (17, -7, 3.0), (-27, 3, 3.4), (5, 27, 2.2),
         (-34, 26, 2.6), (24, 22, 2.9), (-20, -24, 3.1), (30, -20, 2.5), (-44, -6, 3.6), (38, 6, 3.3)]


def draw_bg(img, cam, shot):
    H, W = img.shape[:2]
    # sky gradient + horizon from the camera
    far = cam.pos + np.array([cam.f[0], cam.f[1], 0], np.float32) * 5000
    hy = cam.project(far[None])[0, 1]
    ys = np.arange(H, dtype=np.float32)[:, None]
    t = np.clip(ys / max(hy, 1), 0, 1)
    sky = np.array([0.55, 0.62, 0.78]) * (1 - t[..., None]) + np.array([0.98, 0.84, 0.62]) * t[..., None]
    img[:] = sky
    ground = (ys > hy)[..., 0]
    img[ground] = (0.36, 0.42, 0.30)
    # trunks
    items = []
    for x, y, r in TREES:
        P = np.array([[x, y, 0], [x, y, 70]], np.float32)
        q = cam.project(P)
        if q[0, 2] < 1 or q[1, 2] < 1:
            continue
        items.append((q[0, 2], q, r))
    for z, q, r in sorted(items, key=lambda a: -a[0]):
        w0 = cam.fpx * r / q[0, 2]; w1 = cam.fpx * r * 0.8 / q[1, 2]
        poly = np.array([[q[0, 0] - w0, q[0, 1]], [q[0, 0] + w0, q[0, 1]], [q[1, 0] + w1, q[1, 1]], [q[1, 0] - w1, q[1, 1]]], np.int32)
        k = np.clip(30.0 / z, 0.25, 1.0)
        col = np.array([0.20, 0.22, 0.20]) * k + np.array([0.85, 0.78, 0.66]) * (1 - k)
        cv2.fillPoly(img, [poly], col.tolist())
    # canopy at 42 m with a gap above the robot
    gx, gy = np.meshgrid(np.linspace(-120, 120, 61), np.linspace(-120, 120, 61))
    pts = np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, 44.0)], -1).astype(np.float32)
    gap = np.hypot(pts[:, 0] - 2, pts[:, 1] - 6) < 13
    q = cam.project(pts)
    for (sx, sy, sz), g in zip(q, gap):
        if g or sz < 1:
            continue
        rr = int(np.clip(cam.fpx * 5.0 / sz, 2, 400))
        cv2.circle(img, (int(sx), int(sy)), rr, (0.18, 0.26, 0.20), -1)
    return hy


def light_arrow(img, cam, L):
    H, W = img.shape[:2]
    c = cam.pos + cam.f * 30
    q = cam.project(np.array([c, c + np.asarray(L, np.float32) * 6], np.float32))
    d = q[0, :2] - q[1, :2]
    if np.linalg.norm(d) < 1e-3:
        return
    d = d / np.linalg.norm(d) * 60
    p0 = np.array([W - 90, 90]); p1 = p0 + d
    cv2.arrowedLine(img, tuple(int(a) for a in p0 - d * 0.5), tuple(int(a) for a in p1 - d * 0.5), (1.0, 0.85, 0.3), 4, tipLength=0.35)


def board_frame(shot, t, W=640, H=347):
    cam = SD.camera(shot, t, W, H)
    img = np.zeros((H, W, 3), np.float32)
    draw_bg(img, cam, shot)
    pose = anim.pose_at(shot, t)
    if pose is not None:
        mf, pf = WD.style_fns(SD.rig())
        st = dict(light=shot['light'], pal=WD.PALETTE, ss=1, emissive={WD.GLOW: WD.hexc('ffdc8c')}, matfn=mf, panelfn=pf,
                  seed=1, widths={1: 1.4, 2: 1.2, 3: 1.0, 4: 0.8, 5: 0.6}, shadow_clean=(1, 1, 8, 0.6))
        rgba = cel.render(SD.rig(), pose, cam, st)
        img = rgba[..., :3] + img * (1 - rgba[..., 3:4])
    light_arrow(img, cam, shot['light'])
    return img


def make_boards():
    os.makedirs(OUT, exist_ok=True)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
    font2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
    rows = []
    for shot in SD.SHOTS:
        dur = shot['t1'] - shot['t0']
        ts = [0.0, dur * 0.5, dur - 0.05]
        tiles = [board_frame(shot, t) for t in ts]
        row = Image.new('RGB', (3 * 650 + 520, 380), (245, 240, 228))
        d = ImageDraw.Draw(row)
        for i, (im, t) in enumerate(zip(tiles, ts)):
            row.paste(Image.fromarray(cel.to_u8(im)), (5 + i * 650, 25))
            d.text((10 + i * 650, 3), f"{shot['id']}  +{t:.1f}s", fill=(70, 40, 30), font=font)
        x = 3 * 650 + 10
        d.text((x, 25), f"{shot['id']}  {shot['t0']:.1f}-{shot['t1']:.1f}s  ({dur:.1f}s, on {shot['step']}s)", fill=(70, 40, 30), font=font)
        import textwrap
        y = 55
        for line in textwrap.wrap(shot['desc'], 52) + [''] + textwrap.wrap(shot.get('notes', ''), 52):
            d.text((x, y), line, fill=(60, 50, 45), font=font2); y += 19
        row.save(os.path.join(OUT, f"board_{shot['id']}.jpg"), quality=88)
        rows.append(row)
        print('board', shot['id'], flush=True)
    # sheets of 6 rows
    for k in range(0, len(rows), 6):
        chunk = rows[k:k + 6]
        sh = Image.new('RGB', (chunk[0].width, sum(r.height for r in chunk)), (245, 240, 228))
        y = 0
        for r in chunk:
            sh.paste(r, (0, y)); y += r.height
        sh.save(os.path.join(OUT, f'storyboard_{k // 6 + 1}.jpg'), quality=85)


def make_animatic(fps=8, W=640, H=347):
    tmp = os.path.join(OUT, 'animatic_frames')
    os.makedirs(tmp, exist_ok=True)
    n = 0
    total = SD.SHOTS[-1]['t1']
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
    for shot in SD.SHOTS:
        dur = shot['t1'] - shot['t0']
        nf = int(round(dur * fps))
        for i in range(nf):
            t = i / fps
            im = board_frame(shot, t, W, H)
            pil = Image.fromarray(cel.to_u8(im))
            d = ImageDraw.Draw(pil)
            d.text((6, H - 20), f"{shot['id']} {shot['t0'] + t:5.1f}s  {shot['desc'][:70]}", fill=(255, 255, 255), font=font)
            pil.save(os.path.join(tmp, f'a_{n:05d}.jpg'), quality=80)
            n += 1
        print('animatic', shot['id'], flush=True)
    out = os.path.join(OUT, 'animatic.mp4')
    audio = os.path.join(HERE, '..', 'audio', 'mix.wav')
    cmd = f"ffmpeg -y -v error -framerate {fps} -i {tmp}/a_%05d.jpg "
    if os.path.exists(audio):
        cmd += f"-i {audio} -c:a aac -b:a 128k -shortest "
    cmd += f"-c:v libx264 -pix_fmt yuv420p -r 24 {out}"
    os.system(cmd)
    print('wrote', out)


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'boards'
    if what == 'boards':
        make_boards()
    else:
        make_animatic()
