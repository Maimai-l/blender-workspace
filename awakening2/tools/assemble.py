"""assemble.py - frames of all shots -> the film (H.264 + AAC), plus QA sheets.

  python3 tools/assemble.py vN            # encode deliver/awakening2_vN.mp4 and awakening2.mp4
  python3 tools/assemble.py vN --qa       # also: random stills, contact sheets, benchmark side-by-side
"""
import os, sys, glob, json, random, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'shots'))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FRAMES = os.environ.get('AW2_FRAMES', '/home/user/aw2_frames')
BENCH = '/home/user/bench_work/moss_keeper.mp4'


def shot_list():
    import json
    cues = json.load(open(os.path.join(ROOT, 'audio', 'cues.json')))
    return [(s['id'], s['in'], s['out']) for s in cues['shots']]


def frame_paths():
    out = []
    for sid, a, b in shot_list():
        n = int(round((b - a) * 24))
        for f in range(n):
            p = os.path.join(FRAMES, sid, f'{sid}_{f:04d}.png')
            out.append((sid, f, p))
    return out


def encode(version):
    paths = frame_paths()
    missing = [p for _, _, p in paths if not os.path.exists(p)]
    if missing:
        print(f'{len(missing)} frames missing, e.g. {missing[:3]}')
    lst = os.path.join(FRAMES, f'list_{version}.txt')
    with open(lst, 'w') as fh:
        last = None
        for sid, f, p in paths:
            if os.path.exists(p):
                last = p
            if last is None:
                continue
            fh.write(f"file '{last}'\nduration {1/24:.6f}\n")
    os.makedirs(os.path.join(ROOT, 'deliver'), exist_ok=True)
    out = os.path.join(ROOT, 'deliver', f'awakening2_{version}.mp4')
    audio = os.path.join(ROOT, 'audio', 'mix.wav')
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst]
    if os.path.exists(audio):
        cmd += ['-i', audio, '-c:a', 'aac', '-b:a', '192k', '-shortest']
    cmd += ['-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', '24',
            '-vf', 'fps=24', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    latest = os.path.join(ROOT, 'deliver', 'awakening2.mp4')
    subprocess.run(['cp', out, latest], check=True)
    print('wrote', out, os.path.getsize(out) // 1024, 'kB')
    return out


def font(n, bold=False):
    f = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(f, n)


def qa(version, mp4):
    """Random stills, contact sheets per shot (incl. mid-motion frames) and the benchmark side-by-side,
    all pulled from the encoded film."""
    qd = os.path.join(ROOT, 'qa', version)
    os.makedirs(qd, exist_ok=True)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4],
                               capture_output=True, text=True).stdout.strip())
    rng = random.Random(sum(map(ord, version)))
    times = sorted(round(rng.uniform(0.2, dur - 0.2) * 24) / 24 for _ in range(24))
    tiles = []
    for t in times:
        im = grab(mp4, t)
        im.save(os.path.join(qd, f'random_{t:06.2f}s.jpg'), quality=90)
        tiles.append((im.resize((480, 260)), f'{t:.2f}s'))
    sheet = Image.new('RGB', (480 * 4, 280 * 6), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for k, (im, lab) in enumerate(tiles):
        x = (k % 4) * 480; y = (k // 4) * 280
        sheet.paste(im, (x, y + 20)); d.text((x + 4, y + 2), lab, fill=(255, 220, 120), font=font(14))
    sheet.save(os.path.join(qd, 'random_24.jpg'), quality=88)
    # per-shot contact sheets: 8 frames per shot including mid-motion
    shots = shot_list()
    rows = []
    for sid, a, b in shots:
        ts = [a + (b - a) * k / 8 + 1 / 48 for k in range(8)]
        ims = [grab(mp4, t).resize((240, 130)) for t in ts]
        row = Image.new('RGB', (240 * 8 + 90, 134), (16, 16, 16))
        dd = ImageDraw.Draw(row)
        dd.text((4, 50), sid, fill=(255, 220, 120), font=font(22, True))
        for k, im in enumerate(ims):
            row.paste(im, (90 + 240 * k, 2))
        rows.append(row)
    cs = Image.new('RGB', (rows[0].width, 134 * len(rows)))
    for k, r in enumerate(rows):
        cs.paste(r, (0, 134 * k))
    cs.save(os.path.join(qd, 'shots_contact.jpg'), quality=86)
    # side by side with the benchmark at matching beats (ours t, theirs t)
    # beats: (name, our shot, fraction of that shot, benchmark time)
    tm = {sid: (a_, b_) for sid, a_, b_ in shot_list()}
    beat_spec = [('dawn wide', 'S00', 0.7, 3.0), ('dawn wide 2', 'S01', 0.97, 9.0), ('bird on the shoulder', 'S02', 0.55, 15.0),
                 ('face close-up', 'S03', 0.85, 21.5), ('chest light', 'S04', 0.8, 28.0), ('rise', 'S09', 0.45, 45.0),
                 ('launch', 'S14', 0.45, 62.0), ('flight', 'S16A', 0.5, 66.0), ('sky + trail', 'S16B', 0.75, 68.0),
                 ('ending', 'S17', 0.55, 74.0)]
    beats = []
    for name, sid, fr, tb in beat_spec:
        if sid in tm:
            a_, b_ = tm[sid]
            beats.append((name, round(a_ + (b_ - a_) * fr, 2), tb))
    rows = []
    for name, t_ours, t_bench in beats:
        a_ = grab(mp4, t_ours); b_ = grab(BENCH, t_bench)
        row = Image.new('RGB', (1920, 560), (12, 12, 12))
        row.paste(b_.resize((960, 520)), (0, 36)); row.paste(a_.resize((960, 520)), (960, 36))
        dd = ImageDraw.Draw(row)
        dd.text((10, 6), f'{name}: The Moss Keeper @ {t_bench}s', fill=(220, 220, 220), font=font(20, True))
        dd.text((970, 6), f'Awakening II {version} @ {t_ours}s', fill=(255, 210, 120), font=font(20, True))
        rows.append(row)
    sb = Image.new('RGB', (1920, 560 * len(rows)))
    for k, r in enumerate(rows):
        sb.paste(r, (0, 560 * k))
    sb.save(os.path.join(qd, f'vs_benchmark_{version}.jpg'), quality=88)
    print('qa ->', qd)


def grab(video, t):
    out = f'/tmp/_grab_{os.getpid()}.png'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', video, '-frames:v', '1', out], check=True)
    return Image.open(out).convert('RGB')


if __name__ == '__main__':
    v = sys.argv[1]
    if '--qa-only' in sys.argv:
        qa(v, os.path.join(ROOT, 'deliver', f'awakening2_{v}.mp4'))
    else:
        mp4 = encode(v)
        if '--qa' in sys.argv:
            qa(v, mp4)
