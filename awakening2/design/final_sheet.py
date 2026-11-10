"""Final model sheet of the Warden (production robot: growth, decals, rivets, vines)
and the face in three states. Writes design/warden_model_sheet.jpg and design/warden_faces.jpg."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
for p in ('engine', 'robot', 'shots'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import build, r3d, cel, poses as PZ, warden as WD
import vines as VN, vineplan

F_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
F_R = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
PAPER = (0.95, 0.93, 0.87)


def draw_view(rig, style, pose, cam, light, vset=None, seed=1, glow=0.0):
    st = dict(style)
    st.update(light=light, ss=2, seed=seed, lens_fn=lambda o, l, g=glow: WD.eye_colour(o, g, l))
    skip = tuple(n for n in rig.order if getattr(rig.parts[n], 'world', False))   # no ground growth on the sheet
    rgba, ps = cel.render(rig, pose, cam, st, return_passes=True, skip=skip)
    img = cel.on_paper(rgba, PAPER)
    if vset is not None:
        cv_ = np.zeros((cam.H, cam.W, 4), np.float32)
        d = np.where(ps['mask'], ps['depth'], np.inf)[::2, ::2][:cam.H, :cam.W]
        vset.draw(cv_, 0, cam, depth=d, light=(-0.6, -0.8))
        img = img * (1 - cv_[..., 3:4]) + cv_[..., :3] * cv_[..., 3:4]
    return cel.to_u8(img)


def main():
    rig, style = build.make()
    pose = PZ.grounded(rig, dict(WD.STAND, lid_R=(-20, 0, 0), lid_L=(-20, 0, 0)))
    vs = vineplan.plan(rig, PZ.grounded(rig, PZ.KNEEL_DORMANT))
    vs = [v for v in vs if v.root is None]          # rooted vines tore loose when it stood up
    vset = VN.VineSet(rig, vs, lambda t: pose)
    W, H = 760, 1120
    tiles = []
    for az, label in ((0, 'FRONT'), (38, '3/4'), (90, 'SIDE'), (180, 'BACK'), (215, 'BACK 3/4')):
        a = np.radians(az)
        cam = r3d.Camera((62 * np.sin(a), 62 * np.cos(a), 12.5), (0, 0, 11.2), lens=105, W=W, H=H)
        Lx, Ly, Lz = (-0.55, 0.6, 0.75)
        L = (Lx * np.cos(a) + Ly * np.sin(a), -Lx * np.sin(a) + Ly * np.cos(a), Lz)
        tiles.append((draw_view(rig, style, pose, cam, L, vset, seed=az), label))
    pad = 24
    sheet = Image.new('RGB', (len(tiles) * W + 2 * pad, H + 230), tuple(int(c * 255) for c in PAPER))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 18), 'THE WARDEN  —  final model sheet', fill=(70, 40, 35), font=ImageFont.truetype(F_B, 46))
    d.text((pad, 74), 'height 21 m standing / 13 m kneeling.  Oxidised red-brown lacquer over dark iron, riveted plates, a faded sun crest on each shoulder, verdigris shrine-roof carapace, '
                      'brass fittings, amber lamp-eyes behind lid shutters, furnace grille in the chest, twin engine bells under the roof.',
           fill=(90, 70, 60), font=ImageFont.truetype(F_R, 22))
    for i, (img, label) in enumerate(tiles):
        sheet.paste(Image.fromarray(img), (pad + i * W, 120))
        d.text((pad + i * W + 16, 128), label, fill=(120, 90, 80), font=ImageFont.truetype(F_B, 28))
    # thumbnails of the silhouette
    for i, (img, label) in enumerate(tiles):
        g = img.astype(np.float32).mean(-1)
        sil = ((np.abs(img.astype(np.float32) - np.array(PAPER) * 255).sum(-1) > 30)).astype(np.uint8) * 255
        th = cv2.resize(255 - sil, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
        sheet.paste(Image.fromarray(th).convert('RGB'), (pad + i * (W // 8 + 16), H + 125))
    d.text((pad + 5 * (W // 8 + 16) + 20, H + 170), 'silhouettes at thumbnail size', fill=(120, 90, 80), font=ImageFont.truetype(F_R, 24))
    out = os.path.join(HERE, 'warden_model_sheet.jpg')
    sheet.save(out, quality=90)
    print('wrote', out)

    # faces: dormant / waking / resolute, kneeling head, seen from in front of the face
    import shotdefs as SD
    SD._RIG = rig
    states = [('DORMANT', 'KNEEL_DORMANT', 0.0, (-0.6, 0.55, 0.35)),
              ('WAKING', 'KNEEL_WAKE', 0.6, (-0.6, 0.55, 0.35)),
              ('RESOLUTE', 'STAND_LOOKUP', 1.4, (-0.4, 0.6, 0.65))]
    FW, FH = 900, 760
    faces = []
    for name, pname, glow, Ldir in states:
        p = PZ.grounded(rig, getattr(PZ, pname))
        M = rig.world_mats(p)['head']
        fwd = M[:3, :3] @ np.array([0, 1, 0], np.float32)
        right = M[:3, :3] @ np.array([1, 0, 0], np.float32)
        up = M[:3, :3] @ np.array([0, 0, 1], np.float32)
        eyes = r3d.xform_points(M, np.array([[0, 2.1, 1.0]], np.float32))[0]
        pos = eyes + fwd * 11.0 - right * 2.6 + up * 0.8
        cam = r3d.Camera(pos, eyes - up * 0.25, lens=55, W=FW, H=FH, up=tuple(up))
        L = np.asarray(Ldir, np.float32)
        L = L[0] * right + L[1] * fwd + L[2] * up
        faces.append((draw_view(rig, style, p, cam, L, None, seed=7, glow=glow), name))
    fs = Image.new('RGB', (3 * FW + 2 * pad, FH + 150), tuple(int(c * 255) for c in PAPER))
    d = ImageDraw.Draw(fs)
    d.text((pad, 16), 'THE WARDEN  —  face states (the eyes carry the emotion)', fill=(70, 40, 35), font=ImageFont.truetype(F_B, 40))
    notes = {'DORMANT': 'lids shut, glass dark, head bowed', 'WAKING': 'lids crack open, amber light flickers',
             'RESOLUTE': 'lids up, white-hot cores, head raised'}
    for i, (img, name) in enumerate(faces):
        fs.paste(Image.fromarray(img), (pad + i * FW, 80))
        d.text((pad + i * FW + 16, 90), name, fill=(255, 245, 230), font=ImageFont.truetype(F_B, 34))
        d.text((pad + i * FW + 16, FH + 95), notes[name], fill=(100, 75, 65), font=ImageFont.truetype(F_R, 24))
    out = os.path.join(HERE, 'warden_faces.jpg')
    fs.save(out, quality=90)
    print('wrote', out)


if __name__ == '__main__':
    main()
