"""ground.py - forest floor painted in screen space.

ground(cv, ...)     floor between a horizon line and the bottom: colour by depth
                    (misty far, cool shadowed near), horizontal moss/litter dabs whose
                    size grows toward the viewer (perspective by hand, no 3D plane).
fern(cv, ...)       a fern plant: arching fronds with alternate pinnae, lit tips.
grass(cv, ...)      a grass tuft of tapered blades.
stone(cv, ...)      a mossy stone (dome-lit, moss cap).
log(cv, ...)        a fallen mossy log (uses trees.paint_tube).
flowers(cv, ...)    wildflower dots with tiny stems.
root(cv, ...)       a surface root snaking over the ground (mossy top).
"""
import numpy as np

from .canvas import dabs, stroke, catmull, taper, normals
from .color import C, mix, ramp, jitter, smoothstep, aerial, shade
from .noise import fbm, noise1d

FERN = dict(dark=C(24, 52, 60), mid=C(52, 100, 70), lit=C(132, 172, 80), tip=C(214, 214, 110))


def ground(cv, rng, y_h, y_b, x0, x1, col_far, col_mid, col_near, light=None, lit_col=None,
           n_mult=1.0, size_far=4, size_near=40, opacity=1.0, base=True):
    """Floor band from horizon y_h to y_b. light(x, y) -> 0..1 sun on the floor."""
    if base:
        X, Y = cv.coords()
        t = np.clip((Y - y_h) / max(y_b - y_h, 1), 0, 1)
        rgb = ramp([col_far, col_mid, col_near], t ** 0.8)
        a = smoothstep(y_h - 6, y_h + 10, Y) * ((X >= x0) & (X <= x1))
        cv.over(rgb, a * opacity)
    # dabs in rows; size grows with depth toward the viewer
    rows = 70
    for r in range(rows):
        t = (r + rng.random()) / rows
        y = y_h + (y_b - y_h) * t ** 1.5
        sz = size_far + (size_near - size_far) * t ** 1.5
        n = int((x1 - x0) / max(sz * 0.55, 1) * 1.6 * n_mult)
        xs = rng.uniform(x0, x1, n)
        ys = y + rng.normal(0, sz * 0.25, n)
        tt = np.clip((ys - y_h) / max(y_b - y_h, 1), 0, 1)
        base_c = ramp([col_far, col_mid, col_near], tt ** 0.8)
        if light is not None and lit_col is not None:
            lt = np.clip(light(xs, ys), 0, 1)
            base_c = mix(base_c, lit_col, (lt * 0.85)[:, None])
        cols = jitter(base_c, rng, dl=0.045, dc=0.15, dh=0.08)
        dabs(cv, xs, ys, sz * rng.uniform(0.6, 1.4, n), cols, aspect=rng.uniform(0.18, 0.4, n),
             angle=rng.normal(0, 0.12, n), opacity=opacity * rng.uniform(0.6, 1.0, n), edge=0.3, rag=0.5,
             bristle=0.4, shape='flat', rng=rng)


FERN_KINDS = ('sword', 'lady', 'bracken', 'hart', 'maidenhair')


def frond_body(cv, rng, P, width, pal, a0, sun2, opacity=1.0):
    """Opaque frond body painted in two planes (the half facing the light lighter) under the
    leaflets, so a fern never reads as a lacy, see-through card."""
    sx, sy = sun2
    nx, ny = -np.sin(a0), np.cos(a0)                 # +side normal of the frond direction
    facing = nx * sx + ny * sy
    dark = mix(pal['dark'], pal['mid'], 0.45)
    lit = mix(pal['mid'], pal['lit'], 0.45)
    c1, c2 = (dark, lit) if facing > 0 else (lit, dark)
    stroke(cv, P, width, c1, opacity=opacity, color2=c2, load2=0.75, edge=0.3, bristle=0.35, rag=0.45, rng=rng)



def fern(cv, rng, x, y, size, pal=None, sun2=(0.6, -0.8), n_fronds=None, spread=1.0, lean=0.0,
         light=1.0, depth=0.0, haze=None, opacity=1.0, droop=1.0, up=1.0, kind='sword', body=0.0):
    """Fern plant rooted at (x, y), frond length ~size. kind: sword (narrow alternate
    pinnae), lady (lacy, pinnae of tiny leaflets), bracken (triangular, divided pinnae),
    hart (undivided strap fronds), maidenhair (fans of round leaflets on dark stems)."""
    pal = pal or FERN
    if kind != 'sword':
        return fern_kind(cv, rng, x, y, size, kind, pal=pal, sun2=sun2, n_fronds=n_fronds, spread=spread,
                         lean=lean, light=light, depth=depth, haze=haze, opacity=opacity, droop=droop, body=body)
    if depth > 0 and haze is not None:
        pal = {k: aerial(v, depth, haze) for k, v in pal.items()}
    nf = n_fronds or int(rng.integers(6, 11))
    angs = -np.pi / 2 + lean + np.linspace(-1.25, 1.25, nf) * spread + rng.normal(0, 0.12 + 0.2 * body, nf)
    order = np.argsort(np.abs(angs + np.pi / 2))[::-1]          # outer (low) fronds first
    sx, sy = sun2
    for j in order:
        a0 = angs[j]
        L = size * rng.uniform(0.7, 1.1) * (1 - 0.25 * abs(np.cos(a0)) * 0)
        k = 14
        pts = [np.array([x, y], np.float32)]
        a = a0
        side = np.sign(np.cos(a0)) or 1.0
        for i in range(k):
            # arch: fronds bend outward and down along their length
            a += side * droop * 0.11 * (i / k) * (1 + abs(np.cos(a0))) + rng.normal(0, 0.03)
            pts.append(pts[-1] + L / k * np.array([np.cos(a), np.sin(a)], np.float32))
        P = catmull(np.array(pts), n=60)
        nrm = normals(P)
        tang = np.gradient(P, axis=0)
        ta = np.arctan2(tang[:, 1], tang[:, 0])
        lit_frond = np.clip(0.5 + 0.5 * (np.cos(a0) * sx + np.sin(a0) * sy) * 0.6, 0, 1) * light
        if body > 0:
            tb = np.linspace(0, 1, len(P))
            prof_b = np.sin(np.pi * np.clip(tb * 1.1, 0, 1)) ** 0.7 * (1 - 0.6 * tb)
            frond_body(cv, rng, P, (size * 0.16 * prof_b * 1.5 + 2) * body, pal, a0, sun2, opacity)
            stem_c = mix(pal['mid'], pal['lit'], 0.35)
        else:
            stem_c = mix(pal['dark'], pal['mid'], 0.35 + 0.3 * lit_frond)
        stroke(cv, P, taper(len(P), 1.0, 0.2, max(size * 0.012, 1.2)), stem_c, bristle=0.2, rag=0.1,
               opacity=opacity, rng=rng)
        # pinnae: alternate leaflets, longest a third of the way, shrinking to the tip
        npn = int(np.clip(L / max(size * 0.035, 2.0), 10, 44))
        t = np.linspace(0.06, 0.98, npn)
        idx = np.clip((t * (len(P) - 1)).astype(int), 0, len(P) - 1)
        prof = np.sin(np.pi * np.clip(t * 1.1, 0, 1)) ** 0.7 * (1 - 0.6 * t)
        pl = size * 0.16 * prof * rng.uniform(0.85, 1.15, npn) + 1.5
        for sgn in (-1.0, 1.0):
            la = ta[idx] + sgn * rng.uniform(1.0, 1.35, npn) * (0.9 + 0.2 * t)
            la = la + 0.25 * np.angle(np.exp(1j * (np.pi / 2 - la)))     # leaflets droop a little
            cx = P[idx, 0] + np.cos(la) * pl * 0.5
            cy = P[idx, 1] + np.sin(la) * pl * 0.5
            facing = np.cos(la) * sx + np.sin(la) * sy
            v = np.clip(0.28 + 0.45 * lit_frond + 0.2 * facing + 0.25 * t + rng.normal(0, 0.1, npn), 0, 1) * light
            cols = ramp([pal['dark'], pal['mid'], pal['lit'], pal['tip']], np.clip(v, 0, 1), [0, 0.4, 0.8, 1.0])
            cols = jitter(cols, rng, dl=0.025, dc=0.08, dh=0.05)
            dabs(cv, cx, cy, pl, cols, aspect=0.3, angle=la, shape='leaf', edge=0.25, rag=0.15,
                 bristle=0.15, split=0.1, opacity=opacity, rng=rng)


def fern_kind(cv, rng, x, y, size, kind, pal=None, sun2=(0.6, -0.8), n_fronds=None, spread=1.0, lean=0.0,
              light=1.0, depth=0.0, haze=None, opacity=1.0, droop=1.0, body=0.0):
    pal = dict(pal or FERN)
    shift = {'lady': (0.04, 1.1, -0.12), 'bracken': (-0.01, 0.95, 0.1), 'hart': (-0.02, 1.15, 0.05),
             'maidenhair': (0.03, 1.05, -0.05)}[kind]
    pal = {k: shade(v, dl=shift[0], dc=shift[1], dh=shift[2]) for k, v in pal.items()}
    if depth > 0 and haze is not None:
        pal = {k: aerial(v, depth, haze) for k, v in pal.items()}
    ramp4 = [pal['dark'], pal['mid'], pal['lit'], pal['tip']]
    nf = n_fronds or {'lady': int(rng.integers(7, 12)), 'bracken': int(rng.integers(5, 9)),
                      'hart': int(rng.integers(6, 12)), 'maidenhair': int(rng.integers(5, 9))}[kind]
    angs = -np.pi / 2 + lean + np.linspace(-1.25, 1.25, nf) * spread + rng.normal(0, 0.15 + 0.25 * body, nf)
    order = np.argsort(np.abs(angs + np.pi / 2))[::-1]
    sx, sy = sun2
    for j in order:
        a0 = angs[j]
        L = size * rng.uniform(0.6, 1.15)
        k = 12
        pts = [np.array([x, y], np.float32)]
        a = a0
        side = np.sign(np.cos(a0)) or 1.0
        arch = {'lady': 0.07, 'bracken': 0.05, 'hart': 0.12, 'maidenhair': 0.1}[kind] * droop
        if body > 0:
            arch = arch + rng.uniform(0.04, 0.1)          # curved, never ruler-straight stems
            L = L * rng.uniform(0.8, 1.15)
        for i in range(k):
            a += side * arch * (i / k) * (1 + abs(np.cos(a0))) + rng.normal(0, 0.035)
            pts.append(pts[-1] + L / k * np.array([np.cos(a), np.sin(a)], np.float32))
        P = catmull(np.array(pts), n=60)
        tang = np.gradient(P, axis=0)
        ta = np.arctan2(tang[:, 1], tang[:, 0])
        lit_frond = np.clip(0.5 + 0.5 * (np.cos(a0) * sx + np.sin(a0) * sy) * 0.6, 0, 1) * light
        if kind == 'hart':
            # one long undivided tongue per frond, wavy edge, a midrib
            n = 9
            t = np.linspace(0.08, 1.0, n)
            idx = np.clip((t * 59).astype(int), 0, 59)
            w = size * 0.11 * np.sin(np.pi * np.clip(t * 0.95 + 0.05, 0, 1)) ** 0.6 + 2
            v = np.clip(0.3 + 0.45 * lit_frond + 0.2 * t + rng.normal(0, 0.06, n), 0, 1)
            cols = jitter(ramp(ramp4, v, [0, 0.4, 0.8, 1.0]), rng, dl=0.02, dc=0.06)
            stroke(cv, P[idx], w, cols, opacity=opacity, edge=0.25, rag=0.25, bristle=0.25, rng=rng,
                   color2=pal['lit'], load2=0.35)
            stroke(cv, P[idx], np.maximum(w * 0.08, 1.0), pal['dark'], opacity=0.6 * opacity, bristle=0.2, rng=rng)
            continue
        if body > 0 and kind in ('lady', 'bracken'):
            tb = np.linspace(0, 1, len(P))
            if kind == 'bracken':
                prof_b = np.clip(1.05 - tb, 0, 1) * np.clip(tb * 6, 0, 1)
                wb_ = size * 0.42 * prof_b * 1.6 + 2
            else:
                prof_b = np.sin(np.pi * np.clip(tb * 0.95 + 0.05, 0, 1)) ** 0.9
                wb_ = size * 0.2 * prof_b * 1.6 + 2
            frond_body(cv, rng, P, wb_ * body, pal, a0, sun2, opacity)
            stem_c = mix(pal['mid'], pal['lit'], 0.35)
        else:
            stem_c = pal['dark'] if kind == 'maidenhair' else mix(pal['dark'], pal['mid'], 0.35 + 0.3 * lit_frond)
        stroke(cv, P, taper(len(P), 1.0, 0.2, max(size * (0.008 if kind == 'maidenhair' else 0.012), 1.0)), stem_c,
               bristle=0.2, rag=0.1, opacity=opacity, rng=rng)
        if kind == 'maidenhair':
            npn = int(np.clip(L / max(size * 0.06, 3), 6, 22))
            t = np.linspace(0.12, 1.0, npn)
            idx = np.clip((t * 59).astype(int), 0, 59)
            for sgn in (-1.0, 1.0):
                la = ta[idx] + sgn * rng.uniform(0.9, 1.4, npn)
                r = size * 0.05 * (1.1 - 0.5 * t) * rng.uniform(0.8, 1.2, npn) + 2
                cx = P[idx, 0] + np.cos(la) * r * 0.8
                cy = P[idx, 1] + np.sin(la) * r * 0.8
                v = np.clip(0.35 + 0.4 * lit_frond + 0.2 * (np.cos(la) * sx + np.sin(la) * sy) + rng.normal(0, 0.1, npn), 0, 1)
                cols = jitter(ramp(ramp4, v, [0, 0.4, 0.8, 1.0]), rng, dl=0.03, dc=0.08)
                dabs(cv, cx, cy, r * 2, cols, aspect=0.85, angle=la, shape='petal', edge=0.25, rag=0.25,
                     bristle=0.1, split=0.12, opacity=opacity, rng=rng)
            continue
        if kind == 'bracken':
            npn = int(np.clip(L / max(size * 0.09, 3), 5, 14))
            t = np.linspace(0.15, 0.95, npn)
            plen = size * 0.42 * (1.05 - t) * rng.uniform(0.85, 1.1, npn)   # triangular frond
            leaflet = size * 0.065
        else:   # lady: lanceolate, widest in the middle, lacy
            npn = int(np.clip(L / max(size * 0.05, 3), 8, 26))
            t = np.linspace(0.08, 0.97, npn)
            plen = size * 0.2 * np.sin(np.pi * np.clip(t * 0.95 + 0.05, 0, 1)) ** 0.9 * rng.uniform(0.85, 1.15, npn)
            leaflet = size * 0.036
        idx = np.clip((t * 59).astype(int), 0, 59)
        for sgn in (-1.0, 1.0):
            la = ta[idx] + sgn * rng.uniform(0.95, 1.3, npn)
            la = la + 0.2 * np.angle(np.exp(1j * (np.pi / 2 - la)))
            for i in range(npn):
                # each pinna is itself divided: a short rib with tiny leaflets
                n2 = max(3, int(plen[i] / max(leaflet * 0.9, 1.5)))
                u = np.linspace(0.15, 1.0, n2)
                bx = P[idx[i], 0] + np.cos(la[i]) * plen[i] * u
                by = P[idx[i], 1] + np.sin(la[i]) * plen[i] * u
                v0 = 0.3 + 0.45 * lit_frond + 0.2 * (np.cos(la[i]) * sx + np.sin(la[i]) * sy) + 0.2 * t[i]
                for s2 in (-1.0, 1.0):
                    a2 = la[i] + s2 * rng.uniform(0.7, 1.1, n2)
                    sz = leaflet * (1.15 - 0.6 * u) * rng.uniform(0.8, 1.2, n2) + 1.0
                    v = np.clip(v0 + rng.normal(0, 0.08, n2) + 0.1 * u, 0, 1) * light
                    cols = jitter(ramp(ramp4, v, [0, 0.4, 0.8, 1.0]), rng, dl=0.025, dc=0.08, dh=0.04)
                    dabs(cv, bx + np.cos(a2) * sz * 0.45, by + np.sin(a2) * sz * 0.45, sz, cols,
                         aspect=0.5 if kind == 'lady' else 0.55, angle=a2, shape='leaf', edge=0.25, rag=0.2,
                         bristle=0.1, split=0.1, opacity=opacity, rng=rng)


def grass(cv, rng, x, y, h, pal=None, n=None, spread=0.5, sun2=(0.6, -0.8), light=1.0, opacity=1.0,
          width=None):
    pal = pal or FERN
    n = n or int(rng.integers(7, 16))
    for i in range(n):
        a = -np.pi / 2 + rng.normal(0, spread)
        L = h * rng.uniform(0.5, 1.1)
        bend = rng.normal(0, 0.35) + np.sign(np.cos(a)) * 0.3
        k = 6
        pts = [np.array([x + rng.normal(0, h * 0.04), y], np.float32)]
        aa = a
        for j in range(k):
            aa += bend / k
            pts.append(pts[-1] + L / k * np.array([np.cos(aa), np.sin(aa)], np.float32))
        P = np.array(pts)
        v = np.clip((0.35 + 0.35 * (np.cos(aa) * sun2[0] + np.sin(aa) * sun2[1]) + rng.normal(0, 0.15)) * light, 0, 1)
        col = ramp([pal['dark'], pal['mid'], pal['lit'], pal['tip']], np.array([v * 0.5, v]), [0, 0.4, 0.8, 1.0])
        stroke(cv, P, taper(len(P), 1.0, 0.0, width or max(h * 0.045, 1.5)), col, bristle=0.25, rag=0.1,
               edge=0.25, opacity=opacity, rng=rng)


def stone(cv, rng, x, y, r, col_dark=C(58, 60, 84), col_mid=C(112, 110, 122), col_lit=C(200, 186, 160),
          sun2=(0.6, -0.8), moss=0.7, moss_pal=None, flatten=0.62, opacity=1.0):
    """Mossy stone sitting on the ground at (x, y) (bottom-centre)."""
    from .foliage import Blobs, render_gbuffer, paint_mass
    from .trees import MOSS
    b = Blobs()
    cy = y - r * flatten * 0.8
    b.add(x, cy, r, r * flatten, rot=rng.normal(0, 0.1), light=1.0, rng=rng, lumpy=0.06)
    G = render_gbuffer(cv, b, light3=(sun2[0], sun2[1], 0.5), wrap=0.3, under=0.6)
    small = r < 34
    paint_mass(cv, G, rng, [col_dark, col_mid, col_lit], leaf=max(r * 0.18, 3), density=0.5 if small else 0.8,
               shape='flat', aspect=0.6, edge_leaves=0.0 if small else 0.2, droop=0.0, vnoise=0.08,
               bristle=0.3, rag=0.1 if small else 0.3, edge=0.3, split=0.0, opacity=opacity, orient='tangent',
               fringe=0.1)
    if moss > 0:
        mp = moss_pal or MOSS
        m = int(r * r * 0.12 * moss) + 10
        u = rng.uniform(-1, 1, m)
        px = x + u * r * 0.95
        top = cy - np.sqrt(np.clip(1 - u * u, 0, 1)) * r * flatten
        py = top + np.abs(rng.normal(0, 0.28, m)) * r * flatten
        v = np.clip(0.35 + 0.4 * u * sun2[0] + 0.3 * (1 - (py - top) / (r * flatten)) + rng.normal(0, 0.1, m), 0, 1)
        cols = jitter(ramp([mp['dark'], mp['mid'], mp['lit'], mp['tip']], v, [0, 0.4, 0.8, 1]), rng, dl=0.03, dc=0.1)
        order = np.argsort(v)
        dabs(cv, px[order], py[order], np.clip(r * rng.uniform(0.06, 0.14, m), 2, 30)[order], cols[order],
             aspect=rng.uniform(0.5, 0.9, m), rag=0.5, edge=0.3, opacity=opacity, rng=rng)


def flowers(cv, rng, xs, ys, size, cols=None, opacity=1.0, stem=None):
    xs = np.asarray(xs, np.float32)
    ys = np.asarray(ys, np.float32)
    n = len(xs)
    if n == 0:
        return
    cols = cols if cols is not None else [C(250, 248, 236), C(250, 238, 170), C(212, 196, 236), C(246, 214, 222)]
    k = rng.integers(0, len(cols), n)
    sz = np.broadcast_to(np.asarray(size, np.float32), (n,)) * rng.uniform(0.7, 1.3, n)
    if stem is not None:
        for i in range(n):
            if sz[i] > 4:
                stroke(cv, [[xs[i], ys[i] + sz[i] * 2.5], [xs[i] + rng.normal(0, 1), ys[i]]],
                       max(sz[i] * 0.12, 1.0), stem, bristle=0.1, rag=0.1, opacity=opacity, rng=rng)
    base = np.array([cols[i] for i in k], np.float32)
    c = jitter(base, rng, dl=0.03, dc=0.1, dh=0.04)
    # petals: 4-5 small dabs around the centre
    m = 5
    rep = np.repeat(np.arange(n), m)
    ang = np.tile(np.linspace(0, 2 * np.pi, m, endpoint=False), n) + np.repeat(rng.uniform(0, 6.28, n), m)
    dabs(cv, xs[rep] + np.cos(ang) * sz[rep] * 0.3, ys[rep] + np.sin(ang) * sz[rep] * 0.3 * 0.8,
         sz[rep] * 0.6, c[rep], aspect=0.6, angle=ang, shape='petal', edge=0.3, rag=0.2,
         opacity=opacity, rng=rng)
    dabs(cv, xs, ys, sz * 0.32, C(240, 196, 90), aspect=0.9, edge=0.3, opacity=opacity, rng=rng)
