"""check_edges.py FILM.mp4 [step]  - flag frames where a background ran out or a card edge shows.

For every `step`-th frame it measures:
  * flat borders: a strip along an edge whose colour barely varies along the edge and differs
    from the strip next to it (a missing-background band, like the old S10 orange strip);
  * vertical/horizontal seams: a column (row) whose step to its neighbour is much larger than
    the steps around it along most of its length (a card edge).
Prints suspicious timestamps; exit code 1 if any were found.
"""
import sys, subprocess
import numpy as np


def frames(path, step):
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=not(mod(n\\,{step})),scale=960:520',
           '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = p.stdout.read(960 * 520 * 3)
        if len(buf) < 960 * 520 * 3:
            break
        yield n * step, np.frombuffer(buf, np.uint8).reshape(520, 960, 3).astype(np.float32)
        n += 1


def flat_border(img, w=6):
    out = []
    for name, strip, inner in (('top', img[:w], img[w:3 * w]), ('bottom', img[-w:], img[-3 * w:-w]),
                               ('left', img[:, :w], img[:, w:3 * w]), ('right', img[:, -w:], img[:, -3 * w:-w])):
        along = strip.reshape(-1, 3) if name in ('top', 'bottom') else strip.transpose(1, 0, 2).reshape(-1, 3)
        var = float(along.std(0).mean())
        diff = float(np.abs(strip.mean((0, 1)) - inner.mean((0, 1))).mean())
        if var < 2.0 and diff > 12.0:
            out.append(f'flat {name} (var {var:.1f}, step {diff:.0f})')
    return out


def seams(img):
    g = img.mean(-1)
    out = []
    dx = np.abs(np.diff(g, axis=1))                     # (H, W-1)
    ref = np.median(dx, axis=1, keepdims=True) + 2.0
    strong = (dx > 6 * ref + 10).mean(0)                # fraction of rows where the column jumps
    for x in np.where(strong > 0.6)[0]:
        if 3 < x < g.shape[1] - 4:
            out.append(f'vertical seam at x={x * 2}')
    dy = np.abs(np.diff(g, axis=0))
    ref = np.median(dy, axis=0, keepdims=True) + 2.0
    strong = (dy > 6 * ref + 10).mean(1)
    for y in np.where(strong > 0.6)[0]:
        if 3 < y < g.shape[0] - 4:
            out.append(f'horizontal seam at y={y * 2}')
    return out


def main(path, step=6):
    bad = 0
    for f, img in frames(path, int(step)):
        issues = flat_border(img) + seams(img)
        if issues:
            bad += 1
            print(f'{f / 24:7.2f}s  f{f}: ' + '; '.join(issues[:4]))
    print(f'{bad} suspicious frames')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
