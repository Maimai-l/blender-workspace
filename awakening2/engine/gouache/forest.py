"""forest.py - reusable forest-interior painting kit (screen space, per shot).

broadleaf()      a mid-distance broadleaf tree: varied trunk (lean, curve, flare,
                 fork into 2-4 limbs), irregular layered crown built from several
                 asymmetric masses of rounded clusters at the limb ends (no flat pads).
far_trunks()     a row of far trunks with varied width, lean, forks, side branches,
                 some dissolving into mist at the bottom, some ending in hazy crowns.
giant()          a huge near trunk with buttress roots, moss, ivy, light flecks.
floor()          forest floor between a horizon and the bottom edge: colour by depth,
                 moss and litter patches, surface roots, dappled sun patches, low
                 vegetation hugging trunk feet, flowers; keeps a robot zone open.
undergrowth()    an irregular band of shrubs/ferns on the horizon, fading into mist.
leafy_mass()     generic clump of foliage clusters (for shrubs, canopy edges).
All take a light vector L3 (toward the sun, z<0 = backlit) and a haze colour.
"""
import numpy as np

from .color import C, mix, ramp, jitter, aerial, smoothstep
from .canvas import dabs, stroke, catmull, taper
from .foliage import Blobs, render_gbuffer, paint_mass, spray, vine
from .trees import species, paint_tube, trunk_path, buttress_roots, Frame, limb_fan, MOSS
from .ground import ground, fern, grass, stone, flowers
from .atmos import dapple

LEAF = [C(20, 30, 48), C(28, 48, 62), C(44, 78, 72), C(98, 130, 72), C(170, 176, 86)]
TRANS = C(200, 204, 92)
RIM = C(255, 214, 140)


def pal(d, haze, stops=None):
    return [aerial(c, d, haze) for c in (stops or LEAF)]


def leafy_mass(cv, rng, blobs, d, haze, L3, sun2, leaf, density=0.9, trans_amt=0.6, rim_amt=0.7, stops=None,
               under=0.35, droop=0.45, edge_leaves=1.0, vnoise=0.15, tip_amt=0.1, lz=None):
    lz = L3[2] if lz is None else lz
    G = render_gbuffer(cv, blobs, light3=(L3[0], L3[1], lz), wrap=0.5, under=under)
    paint_mass(cv, G, rng, pal(d, haze, stops), leaf=leaf, density=density, trans=aerial(TRANS, d * 0.6, haze),
               trans_amt=trans_amt, rim=aerial(RIM, d * 0.4, haze), rim_amt=rim_amt,
               tip=aerial(C(255, 226, 150), d * 0.5, haze), tip_amt=tip_amt, sun2=sun2, droop=droop,
               vnoise=vnoise, edge_leaves=edge_leaves)
    return G


def broadleaf(cv, rng, base, height, wb, d, haze, L3, sun2, leaf=8.0, sp=None, lean=None, spread=None,
              mist_fade=None, mist_col=None, crown_only=False, ivy=0.0, moss=0.6, detail=0.6, lz=-0.1,
              fork_at=None, n_limbs=None, density=0.9, mass_scale=1.0, stops=None):
    """Mid-distance broadleaf tree standing at base (x, y_ground) with total height."""
    x, y = base
    H = float(height)
    sp = sp or ['camphor', 'beech', 'camphor', 'cedar'][int(rng.integers(0, 4))]
    lean = rng.normal(0, 0.05) if lean is None else lean
    spread = spread or H * rng.uniform(0.28, 0.45)
    fa = fork_at or rng.uniform(0.42, 0.62)
    fork = np.array([x + lean * H * fa + rng.normal(0, 0.02) * H, y - H * fa], np.float32)
    bark = species(sp, depth=d, haze=haze)
    pts, ww = trunk_path(rng, (x, y), fork, wb, wb * rng.uniform(0.6, 0.8), sway=rng.uniform(0.01, 0.05),
                         bulge=0.07, flare=rng.uniform(0.2, 0.6), flare_h=0.06, lean_curve=rng.normal(0, 0.04))
    nl = n_limbs or int(rng.integers(2, 5))
    base_ang = -np.pi / 2 + lean * 1.5
    angs = base_ang + np.linspace(-0.85, 0.85, nl) * rng.uniform(0.7, 1.1) + rng.normal(0, 0.12, nl)
    lens = H * (1 - fa) * rng.uniform(0.55, 0.95, nl) * (1 - 0.25 * np.abs(np.sin(angs + np.pi / 2)))
    wl = wb * 0.62 * rng.uniform(0.6, 0.85, nl)
    limbs, tips, tw = limb_fan(rng, fork, angs, lens, wl, levels=2, split=(1, 2), curl=0.35)
    if not crown_only:
        paint_tube(cv, pts, ww, rng, bark, L3, depth=d, haze=haze, moss=moss, ivy=ivy, detail=detail,
                   twist=0.15 if sp == 'camphor' else 0.0, mist_fade=mist_fade, mist_col=mist_col)
        for lp, lw, lvl in sorted(limbs, key=lambda l: -l[1][0]):
            paint_tube(cv, lp, lw, rng, bark, L3, depth=d, haze=haze, moss=moss * 0.5 if lvl == 0 else 0.0,
                       detail=detail * 0.7, end_fade=0.15)
    # crown: masses around the outer limbs (asymmetric, some gaps), rounded clusters
    b = Blobs()
    items = []
    centres = [lp[-1] for lp, lw, lvl in limbs if lvl >= 1] or [t for t in tips]
    for c in sorted(centres, key=lambda c: c[1]):
        R = H * rng.uniform(0.08, 0.13) * mass_scale
        layered_mass(b, rng, c[0], c[1] - R * 0.2, R, flat=0.55, droop=0.35)
    # a few small clusters along the main limbs (twiggy leafage)
    for lp, lw, lvl in limbs:
        if lvl == 0:
            for t in (0.6, 0.85):
                q = lp[int(t * (len(lp) - 1))]
                r = H * rng.uniform(0.035, 0.06) * mass_scale
                items.append((rng.normal(0, 5), q[0] + rng.normal(0, r), q[1] - r * 0.5, r, r * 0.8))
    items.sort(key=lambda it: it[0])
    for z, cx, cy, rx, ry in items:
        b.add(cx, cy, rx, ry, rot=rng.normal(0, 0.25), light=rng.uniform(0.8, 1.1), hue=rng.normal(0, 0.05),
              val=rng.normal(0, 0.05), rng=rng, lumpy=0.2)
    leafy_mass(cv, rng, b, d, haze, L3, sun2, leaf, density=density, lz=lz, stops=stops)
    return fork


def far_trunks(cv, rng, xs, base_y, top_range, d, haze, L3, mist_col, mist_band, width=(10, 60), fade_p=0.4,
               fork_p=0.4, branch_p=0.5, leaf=5.0, crown_p=0.3, sun2=(0.55, -0.83), lean_sd=0.05):
    """Varied far trunks at xs (flat x), feet at base_y (+-), tops in top_range."""
    for x in xs:
        w = float(np.exp(rng.uniform(np.log(width[0]), np.log(width[1]))))
        top = rng.uniform(*top_range)
        Ht = base_y - top
        lean = rng.normal(0, lean_sd)
        dd = float(np.clip(d + rng.uniform(-0.08, 0.14), 0, 0.95))
        sp = ['camphor', 'beech', 'cedar', 'beech'][int(rng.integers(0, 4))]
        bark = species(sp, depth=dd, haze=haze)
        by = base_y + rng.uniform(-25, 20)
        sw = rng.uniform(0.004, 0.016) * min(1.0, 700.0 / max(Ht, 1.0))
        pts, ww = trunk_path(rng, (x, by), (x + lean * Ht, top), w, w * rng.uniform(0.45, 0.8),
                             sway=sw, bulge=0.06, flare=rng.uniform(0.1, 0.5), flare_h=0.04,
                             lean_curve=rng.normal(0, 0.012))
        sf = rng.uniform(0.15, 0.55) if rng.random() < fade_p else 0.0
        paint_tube(cv, pts, ww, rng, bark, L3, detail=0.3, depth=dd, haze=haze, moss=0.3, start_fade=sf,
                   end_fade=0.12, mist_fade=mist_band, mist_col=mist_col)
        fr = Frame(pts, ww)
        if rng.random() < fork_p:
            s0 = rng.uniform(0.6, 0.85)
            p0, w0, _ = fr.at(s0, 0)
            for sgn in (-1, 1):
                a = -np.pi / 2 + lean + sgn * rng.uniform(0.2, 0.55)
                L = Ht * rng.uniform(0.15, 0.3)
                q = np.array([p0, p0 + L * 0.5 * np.array([np.cos(a), np.sin(a)]) + rng.normal(0, 4, 2),
                              p0 + L * np.array([np.cos(a + sgn * 0.15), np.sin(a + sgn * 0.15)])], np.float32)
                paint_tube(cv, catmull(q, n=16), np.linspace(float(w0) * 0.55, float(w0) * 0.25, 16), rng, bark, L3,
                           detail=0.3, depth=dd, haze=haze, end_fade=0.3)
        if rng.random() < branch_p:
            s0 = rng.uniform(0.35, 0.75)
            p0, w0, _ = fr.at(s0, 0)
            sgn = rng.choice([-1, 1])
            a = -np.pi / 2 + sgn * rng.uniform(0.7, 1.2)
            L = Ht * rng.uniform(0.08, 0.18)
            p1 = p0 + L * np.array([np.cos(a), np.sin(a)])
            stroke(cv, [p0, (p0 + p1) / 2 + [0, -L * 0.1], p1], taper(3, 1.0, 0.3, max(float(w0) * 0.2, 2)),
                   aerial(C(70, 66, 86), dd, haze), bristle=0.3, rag=0.2, rng=rng)
            if rng.random() < crown_p:
                b = Blobs()
                for k in range(int(rng.integers(4, 8))):
                    f = rng.uniform(0.35, 1.05)
                    q = p0 + (p1 - p0) * f
                    r = L * rng.uniform(0.08, 0.16)
                    b.add(q[0] + rng.normal(0, r * 0.8), q[1] + rng.normal(0, r * 0.5) - r * 0.2, r * 1.3, r * 0.7,
                          rot=float(np.arctan2(p1[1] - p0[1], p1[0] - p0[0])) * 0.5, light=rng.uniform(0.8, 1.05),
                          rng=rng, lumpy=0.25)
                leafy_mass(cv, rng, b, min(dd + 0.05, 0.95), haze, L3, sun2, leaf, density=0.7, trans_amt=0.4,
                           rim_amt=0.4)


def giant(cv, rng, base, top, wb, wt, L3, sp='camphor', roots=6, ivy=0.6, moss=1.3, twist=0.2, flare=0.55,
          keep_out=None, flecks=0.3, d=0.0, haze=None, lichen=None, blotch=None, root_spread=1.5, detail=1.0,
          traits=None):
    """Huge near trunk with buttress roots. keep_out=(x0, x1): roots avoid this x range."""
    pts, ww = trunk_path(rng, base, top, wb, wt, sway=0.025, bulge=0.08, flare=flare, flare_h=0.045)
    bark = species(sp, depth=d, haze=haze)
    if lichen is not None:
        bark.lichen = lichen
    if blotch is not None:
        bark.blotch = blotch
    sp_ = catmull(pts, spacing=3.0)
    fr = Frame(sp_, np.interp(np.linspace(0, 1, len(sp_)), np.linspace(0, 1, len(ww)), ww))
    rts = buttress_roots(rng, fr, roots, base[1] - 25, wb, spread=root_spread)
    for rp, rw, sd in rts:
        if keep_out is not None and np.any((rp[:, 0] > keep_out[0]) & (rp[:, 0] < keep_out[1])):
            continue
        paint_tube(cv, rp, rw, rng, bark, L3, moss=1.6, detail=0.8 * detail, start_fade=0.25, depth=d, haze=haze)
    paint_tube(cv, pts, ww, rng, bark, L3, moss=moss, ivy=ivy, twist=twist, flecks=flecks, detail=detail,
               moss_base=0.5, sky_side=0.3, depth=d, haze=haze)
    if traits:
        character(cv, rng, pts, ww, bark, L3, **traits)
    return pts, ww


def surface_roots(cv, rng, specs, L3, d=0.0, haze=None):
    """specs: list of ((x0, y0), (x1, y1), width)."""
    bark = species('camphor', depth=d, haze=haze)
    for (p0, p1, w0) in specs:
        p0 = np.asarray(p0, np.float32)
        p1 = np.asarray(p1, np.float32)
        L = float(np.hypot(*(p1 - p0)))
        m1 = p0 + (p1 - p0) * 0.35 + rng.normal(0, 0.06, 2) * L
        m2 = p0 + (p1 - p0) * 0.7 + rng.normal(0, 0.06, 2) * L
        pts = catmull(np.array([p0, m1, m2, p1], np.float32), n=26)
        paint_tube(cv, pts, np.linspace(w0, w0 * 0.25, 26), rng, bark, L3, moss=2.2, detail=0.7, start_fade=0.15,
                   end_fade=0.2, depth=d, haze=haze)


def undergrowth(cv, rng, y, x0, x1, d, haze, L3, sun2, leaf=6.0, height=(30, 150), centre=None, gap=None,
                n=46, density=0.9):
    """Irregular shrub band standing on y (taller toward the sides if centre given)."""
    b = Blobs()
    xs = np.sort(rng.uniform(x0, x1, n))
    for x in xs:
        side = 1.0 if centre is None else float(np.clip(abs(x - centre[0]) / centre[1], 0, 1))
        if gap is not None and gap[0] < x < gap[1] and rng.random() < 0.6:
            continue
        hgt = height[0] + (height[1] - height[0]) * side ** 1.5 * rng.uniform(0.5, 1.2)
        for k in range(int(1 + 3 * side)):
            r = hgt * rng.uniform(0.4, 0.75)
            b.add(x + rng.normal(0, 25), y - k * r * 0.55 - rng.uniform(0, 0.3) * hgt, r, r * rng.uniform(0.6, 0.85),
                  light=rng.uniform(0.8, 1.1), hue=rng.normal(0, 0.05), val=rng.normal(0, 0.05), rng=rng, lumpy=0.24)
    leafy_mass(cv, rng, b, d, haze, L3, sun2, leaf, density=density, lz=0.15, trans_amt=0.7, under=0.4)


def floor(cv, rng, y_h, y_b, x0, x1, haze, L3, sun2, warm, keep=None, near=C(34, 48, 70), mid=C(74, 98, 78),
          far=None, lit=C(200, 190, 118), litter=True, patches=34, roots=(), veg=(), flowers_n=60,
          dapple_col=C(214, 206, 116), size_near=26):
    """Forest floor. warm(x, y)->0..1 sun on the floor; keep=(x0, y0, x1, y1) robot zone
    where only low texture is painted; roots: surface_roots specs; veg: list of
    (cx, cy, sx, sy, n) low vegetation clumps hugging trunk feet."""
    far = far if far is not None else aerial(C(150, 158, 124), 0.55, haze)
    ground(cv, rng, y_h, y_b, x0, x1, far, mid, near,
           light=lambda x, y: warm(x, y) * (1 - smoothstep(y_h + (y_b - y_h) * 0.35, y_b, y)) * 0.8,
           lit_col=lit, size_far=5, size_near=size_near)
    if litter:
        for (c0, n0, a0) in [(C(126, 150, 84), 22, 0.7), (C(150, 118, 92), 30, 0.65), (C(34, 48, 66), 24, 0.75),
                             (C(98, 84, 96), 14, 0.5)]:
            px = rng.uniform(x0, x1, n0)
            py = y_h + (y_b - y_h) * rng.uniform(0.05, 1.0, n0)
            sc = 0.4 + (py - y_h) / max(y_b - y_h, 1)
            for i in range(n0):
                m = int(60 * sc[i])
                xx = px[i] + rng.normal(0, 70 * sc[i], m)
                yy = py[i] + rng.normal(0, 14 * sc[i], m)
                cc = jitter(mix(c0, mid, 0.3), rng, m, dl=0.04, dc=0.15, dh=0.08)
                dabs(cv, xx, yy, rng.uniform(8, 22, m) * sc[i], cc, aspect=rng.uniform(0.2, 0.45, m),
                     angle=rng.normal(0, 0.15, m), opacity=a0 * rng.uniform(0.5, 1, m), shape='flat', rag=0.5,
                     edge=0.3, bristle=0.4, rng=rng)
    if roots:
        surface_roots(cv, rng, roots, L3)
    if veg:
        gc = Blobs()
        for (cx, cy, sx, sy, n_) in veg:
            for i in range(n_):
                xx = cx + rng.normal(0, sx * 0.5)
                yy = cy + rng.normal(0, sy * 0.4)
                sc = 0.3 + (yy - y_h) / max(y_b - y_h, 1)
                r = rng.uniform(26, 60) * sc
                gc.add(xx, yy, r * rng.uniform(0.9, 1.4), r * rng.uniform(0.6, 0.9), rot=rng.normal(0, 0.3),
                       light=rng.uniform(0.75, 1.1), hue=rng.normal(0, 0.06), val=rng.normal(0, 0.05), rng=rng,
                       lumpy=0.26)
        G = render_gbuffer(cv, gc, light3=(L3[0], L3[1], 0.15), wrap=0.5, under=0.5)
        paint_mass(cv, G, rng, [C(30, 46, 66), C(42, 72, 72), C(76, 110, 74), C(150, 166, 84), C(214, 204, 116)],
                   leaf=9, density=0.9, trans=TRANS, trans_amt=0.6, rim=RIM, rim_amt=0.6, sun2=sun2, droop=0.5,
                   vnoise=0.18, edge_leaves=1.4, fringe=1.2)
    if patches:
        xs = rng.uniform(x0 + 100, x1 - 100, patches)
        ys = y_h + (y_b - y_h) * rng.uniform(0.04, 0.6, patches)
        sz = rng.uniform(18, 50, patches) * (0.5 + (ys - y_h) / max(y_b - y_h, 1))
        dapple(cv, rng, xs, ys, sz, dapple_col, flatten=0.22, opacity=(0.45, 0.85), cluster=7, mode='lock')
    if flowers_n:
        fx = rng.uniform(x0, x1, flowers_n)
        fy = y_h + (y_b - y_h) * rng.uniform(0.05, 0.5, flowers_n)
        flowers(cv, rng, fx, fy, 2.5 + (fy - y_h) / 60)


def layered_mass(blobs, rng, cx, cy, R, flat=0.55, n=None, light=1.0, hue=0.0, droop=0.3):
    """An irregular foliage mass: many clusters of mixed size in a wide, lumpy envelope
    with a ragged, drooping lower edge and satellite clumps (no round pad, no disc)."""
    n = n or int(rng.integers(10, 20))
    items = []
    for k in range(n):
        u = rng.uniform(-1, 1)
        top = -np.sqrt(max(1 - u * u, 0.0)) * R * rng.uniform(0.5, 1.0)
        bot = R * flat * rng.uniform(0.2, 0.8) + droop * R * (0.4 + 0.6 * rng.random()) * (abs(u) > 0.5)
        y = cy + rng.uniform(top, bot)
        x = cx + u * R * 1.5
        r = R * rng.uniform(0.18, 0.5) * (1.0 - 0.35 * abs(u))
        items.append((y, x, y, r))
    for k in range(int(rng.integers(2, 6))):          # satellites / hanging tongues
        a = rng.uniform(0, 2 * np.pi)
        x = cx + np.cos(a) * R * rng.uniform(1.2, 1.7)
        y = cy + abs(np.sin(a)) * R * rng.uniform(0.4, 1.0) * (1 if rng.random() < 0.6 else -0.6)
        items.append((y, x, y, R * rng.uniform(0.12, 0.25)))
    items.sort(key=lambda it: it[0] + rng.normal(0, R * 0.2))
    for _, x, y, r in items:
        blobs.add(x, y, r * rng.uniform(1.0, 1.3), r * rng.uniform(0.75, 0.95), rot=rng.normal(0, 0.4),
                  light=light * rng.uniform(0.8, 1.1), hue=hue + rng.normal(0, 0.04), val=rng.normal(0, 0.05),
                  rng=rng, lumpy=0.26)


def leaf_spray_mass(blobs, rng, p0, p1, size, droop=0.25, n=None, light=1.0, hue=0.0):
    """Clusters along a branch p0->p1 forming an irregular horizontal spray with a
    drooping, ragged end (bigger in the middle, satellites, gaps)."""
    p0 = np.asarray(p0, np.float32)
    p1 = np.asarray(p1, np.float32)
    d = p1 - p0
    L = float(np.hypot(*d)) + 1e-6
    ang = float(np.arctan2(d[1], d[0]))
    for t in sorted(rng.uniform(0.35, 1.0, int(rng.integers(2, 4)))):
        q = p0 + d * t
        layered_mass(blobs, rng, q[0], q[1] + droop * size * 1.5 * t, size * rng.uniform(1.0, 1.6), flat=0.5,
                     light=light, hue=hue, droop=0.4)
    return
    n = n or int(np.clip(L / size * 2.2, 5, 18))
    for k in range(n):
        t = rng.uniform(0.15, 1.08)
        q = p0 + d * t
        r = size * (0.5 + 0.65 * np.sin(np.pi * min(t, 1.0))) * rng.uniform(0.55, 1.25)
        off = rng.normal(0, size * 0.6)
        sag = droop * size * 2.0 * t * t
        cx = q[0] - np.sin(ang) * off * 0.6
        cy = q[1] + np.cos(ang) * off + sag - r * 0.15
        blobs.add(cx, cy, r * rng.uniform(0.9, 1.35), r * rng.uniform(0.7, 0.95), rot=ang * 0.4 + rng.normal(0, 0.35),
                  light=light * rng.uniform(0.8, 1.1), hue=hue + rng.normal(0, 0.04), val=rng.normal(0, 0.05), rng=rng,
                  lumpy=0.24)


def forest_row(cv, rng, x0, x1, y_ground, y_top, n, d, haze, L3, sun2, mist_col=None, mist_band=None,
               width=(16, 60), leaf=6.0, branches=(1, 3), saplings=0.5, vines=0.3, keep=None, fade_p=0.3,
               leaf_size=None, top_jitter=120, hue=0.0, lz=-0.15, canopy=True, soft=0.0):
    """One row of a forest seen from inside: varied trunks; leafy side-branch sprays at
    many heights; saplings between trunks; hanging vines. Foliage of the whole row is
    painted in one pass after the trunks. keep=(x0, x1): no saplings there."""
    xs = np.sort(rng.uniform(x0, x1, n))
    Hrow = float(y_ground - y_top)
    leaf_size = leaf_size or Hrow * 0.035
    blobs = Blobs()
    vine_specs = []
    for x in xs:
        w = float(np.exp(rng.uniform(np.log(width[0]), np.log(width[1]))))
        top = y_top + rng.uniform(-top_jitter, top_jitter * 0.3)
        Ht = y_ground - top
        lean = rng.normal(0, 0.03)
        dd = float(np.clip(d + rng.uniform(-0.05, 0.08), 0, 0.95))
        sp = ['camphor', 'beech', 'cedar', 'beech', 'camphor'][int(rng.integers(0, 5))]
        bark = species(sp, depth=dd, haze=haze)
        sw = rng.uniform(0.004, 0.014) * min(1.0, 700.0 / max(Ht, 1.0))
        pts, ww = trunk_path(rng, (x, y_ground + rng.uniform(-10, 15)), (x + lean * Ht, top), w,
                             w * rng.uniform(0.5, 0.8), sway=sw, bulge=0.07, flare=rng.uniform(0.15, 0.6),
                             flare_h=0.05, lean_curve=rng.normal(0, 0.012))
        sf = rng.uniform(0.1, 0.4) if rng.random() < fade_p else 0.0
        if soft > 0:
            paint_tube(cv, pts, ww, rng, bark, L3, detail=0.1, depth=dd, haze=haze, moss=0.0, start_fade=sf,
                       end_fade=0.08, flecks=0.0, soft_edge=soft)
        else:
            paint_tube(cv, pts, ww, rng, bark, L3, detail=0.35, depth=dd, haze=haze, moss=0.5, start_fade=sf,
                       end_fade=0.08, mist_fade=mist_band, mist_col=mist_col, flecks=0.2)
        fr = Frame(pts, ww)
        for j in range(int(rng.integers(branches[0], branches[1] + 1))):
            if rng.random() < 0.45:
                continue
            s0 = rng.uniform(0.55, 0.95)
            p0, w0, _ = fr.at(s0, 0)
            sgn = rng.choice([-1, 1])
            a = -rng.uniform(0.1, 0.55) if sgn > 0 else np.pi + rng.uniform(0.1, 0.55)
            L = Hrow * rng.uniform(0.12, 0.3)
            p1 = p0 + L * np.array([np.cos(a), np.sin(a) * 0.6 - 0.15])
            pm = p0 + (p1 - p0) * 0.35 + np.array([0, -L * rng.uniform(0.03, 0.1)])
            pe = p0 + (p1 - p0) * 0.62
            stroke(cv, [p0, pm, pe], taper(3, 1.0, 0.25, max(float(w0) * 0.32, 3.0)), aerial(C(64, 58, 78), dd, haze),
                   bristle=0.3, rag=0.25, rng=rng)
            leaf_spray_mass(blobs, rng, p0 + (p1 - p0) * 0.25, p1, leaf_size * rng.uniform(0.8, 1.3),
                            droop=rng.uniform(0.1, 0.4), hue=hue)
            if rng.random() < vines:
                vine_specs.append((p1[0] - rng.uniform(0, 0.4) * (p1[0] - p0[0]), p1[1], dd))
    # saplings between trunks (low, irregular)
    ns = int(n * saplings)
    for i in range(ns):
        x = rng.uniform(x0, x1)
        if keep is not None and keep[0] < x < keep[1]:
            continue
        h = Hrow * rng.uniform(0.08, 0.2)
        # a bushy young tree: foliage from near the ground up (no bare stem)
        for k in range(int(rng.integers(2, 4))):
            yy = y_ground - h * (0.25 + 0.3 * k) - rng.uniform(0, 0.1) * h
            layered_mass(blobs, rng, x + rng.normal(0, h * 0.15), yy, h * rng.uniform(0.35, 0.55) * (1 - 0.15 * k),
                         flat=0.6, hue=hue, droop=0.3)
    # canopy undersides hanging from the top of the row: an irregular band with tongues
    if canopy:
        xs_c = np.arange(x0 - leaf_size * 2, x1 + leaf_size * 2, leaf_size * 2.2)
        for xc in xs_c:
            depth_c = Hrow * (0.06 + 0.2 * rng.random() ** 1.5)
            layered_mass(blobs, rng, xc + rng.normal(0, leaf_size), y_top + depth_c,
                         leaf_size * rng.uniform(1.6, 2.8), flat=0.6, hue=hue, droop=0.6)
    if len(blobs):
        if soft > 0:
            from .sky import paint_planes
            cols = tuple(aerial(c, d, haze) for c in (LEAF[1], LEAF[2], LEAF[3], LEAF[4]))
            paint_planes(cv, rng, blobs, cols, light3=(L3[0], L3[1], 0.2), th=(0.4, 0.68, 0.95), noise_amt=0.07,
                         strokes=0.7, brush_edge=1.0, leafy_edge=0.15, leaf_px=max(leaf * 2.5, 8), glob=0.45,
                         rim=aerial(RIM, d * 0.5, haze), rim_amt=0.35)
        else:
            leafy_mass(cv, rng, blobs, d, haze, L3, sun2, leaf, density=0.85, trans_amt=0.55, rim_amt=0.6, lz=lz,
                       droop=0.5)
    if soft > 0:
        vine_specs = vine_specs[::3]
    for (vx, vy, dd) in vine_specs:
        vine(cv, vx, vy, Hrow * rng.uniform(0.15, 0.4), rng, aerial(C(50, 50, 58), dd, haze),
             aerial(C(36, 60, 60), dd, haze), aerial(C(130, 156, 84), dd * 0.8, haze), leaf=max(leaf * 1.2, 5),
             width=max(leaf * 0.25, 1.2), sun2=sun2)


def character(cv, rng, pts, ww, bark, L3, knots=3, fungi=2, hollow=False, ivy_bands=0, moss_cushions=0,
              ivy_pal=None, side=None):
    """Give a near trunk individual features (alpha-locked onto the trunk, except fungi and
    cushions which may overhang): knot holes with a lit lip, bracket fungi, a dark hollow
    between the roots, ivy in a few distinct climbing bands (dense at the foot, thinning
    upward, bare gaps between) and thick moss cushions on the root flare."""
    from .trees import IVY
    sp_ = catmull(np.asarray(pts, np.float32), spacing=3.0)
    fr = Frame(sp_, np.interp(np.linspace(0, 1, len(sp_)), np.linspace(0, 1, len(ww)), np.asarray(ww, np.float32)))
    L = np.asarray(L3, np.float32)
    L2 = L[:2] / (np.hypot(L[0], L[1]) + 1e-6)
    nd = fr.N[len(sp_) // 2]
    lit_sgn = 1.0 if (nd[0] * L2[0] + nd[1] * L2[1]) > 0 else -1.0
    side = side if side is not None else lit_sgn
    dark = mix(bark.dark, C(16, 12, 24), 0.5)
    # --- knot holes: dark oval, lit lower lip, a ring of bark strokes around it
    for k in range(knots):
        s0 = rng.uniform(0.12, 0.75)
        t0 = rng.uniform(-0.55, 0.55)
        p, w, _ = fr.at(s0, t0)
        r = float(w) * rng.uniform(0.035, 0.07)
        ang = float(np.arctan2(fr.T[int(s0 * (len(sp_) - 1)), 1], fr.T[int(s0 * (len(sp_) - 1)), 0]))
        dabs(cv, [p[0]], [p[1]], [r * 3.2], mix(bark.mid, bark.dark, 0.6), aspect=0.62, angle=ang, edge=0.35,
             rag=0.5, bristle=0.4, mode='lock', rng=rng)
        dabs(cv, [p[0]], [p[1]], [r * 2.0], dark, aspect=0.5, angle=ang, edge=0.25, rag=0.4, bristle=0.1,
             mode='lock', rng=rng)
        lip = np.array([p[0] + np.cos(ang + np.pi / 2) * r * 0.9 * lit_sgn, p[1] + np.sin(ang + np.pi / 2) * r * 0.9 * lit_sgn])
        dabs(cv, [lip[0]], [lip[1]], [r * 1.8], mix(bark.lit, bark.rim, 0.3), aspect=0.25, angle=ang, edge=0.35,
             rag=0.3, bristle=0.3, opacity=0.8, mode='lock', rng=rng)
    # --- hollow at the base between two buttress roots
    if hollow:
        p, w, _ = fr.at(rng.uniform(0.0, 0.04), rng.uniform(-0.25, 0.25))
        hw_ = float(w) * rng.uniform(0.18, 0.26)
        n = 40
        xs = p[0] + rng.normal(0, hw_ * 0.3, n)
        ys = p[1] - np.abs(rng.normal(0, hw_ * 0.7, n))
        dabs(cv, xs, ys, rng.uniform(hw_ * 0.4, hw_ * 0.8, n), jitter(np.broadcast_to(dark, (n, 3)), rng, dl=0.02),
             aspect=0.7, edge=0.3, rag=0.6, bristle=0.2, mode='lock', rng=rng)
        # mossy lip around the hollow
        m = 60
        a = rng.uniform(np.pi * 1.0, np.pi * 2.0, m)
        lx = p[0] + np.cos(a) * hw_ * 0.75
        ly = p[1] - hw_ * 0.6 + np.sin(a) * hw_ * 0.9
        dabs(cv, lx, ly, rng.uniform(6, 16, m), jitter(mix(C(78, 122, 72), C(160, 188, 86), rng.random(m)[:, None]), rng,
             dl=0.03), aspect=0.7, edge=0.3, rag=0.5, mode='lock', rng=rng)
    # --- bracket fungi: stacked shelves on the side of the trunk (overhang the silhouette)
    for k in range(fungi):
        s0 = rng.uniform(0.08, 0.45)
        t0 = side * rng.uniform(0.65, 0.95) * rng.choice([1, -1], p=[0.7, 0.3])
        p, w, _ = fr.at(s0, t0)
        nshelf = int(rng.integers(2, 5))
        for j in range(nshelf):
            sw = float(w) * rng.uniform(0.07, 0.13) * (1 - 0.15 * j)
            cx = p[0] + np.sign(t0) * sw * 0.35 + rng.normal(0, sw * 0.15)
            cy = p[1] - j * sw * 0.42
            # shadow under the shelf
            dabs(cv, [cx], [cy + sw * 0.16], [sw * 1.9], C(40, 30, 40), aspect=0.2, angle=0.0, edge=0.4, rag=0.3,
                 opacity=0.7, rng=rng)
            col = mix(C(200, 168, 120), C(238, 216, 170), rng.uniform(0.2, 0.8))
            dabs(cv, [cx], [cy], [sw * 1.8], col, aspect=0.32, angle=0.0, shape='round', edge=0.3, rag=0.25,
                 bristle=0.3, rng=rng)
            dabs(cv, [cx + L2[0] * sw * 0.1], [cy - sw * 0.06], [sw * 1.2], C(255, 236, 196), aspect=0.18, angle=0.0,
                 edge=0.4, rag=0.2, opacity=0.7, rng=rng)
    # --- ivy in distinct climbing bands
    ip = ivy_pal or IVY
    for b_ in range(ivy_bands):
        t0 = rng.uniform(-0.75, 0.6)
        s_top = rng.uniform(0.3, 0.8)
        n = int(240 * s_top)
        ss = np.sort(rng.uniform(0, s_top, n) ** 1.6 * s_top / max(s_top ** 1.6, 1e-6))
        tt = t0 + np.sin(ss * 9 + rng.uniform(0, 6)) * 0.12 + rng.normal(0, 0.09 + 0.12 * (1 - ss / s_top), n)
        ok = np.abs(tt) < 0.97
        ss, tt = ss[ok], tt[ok]
        q, w, _ = fr.at(ss, tt)
        i_ = np.clip((ss * (len(sp_) - 1)).astype(int), 0, len(sp_) - 1)
        ndl = fr.N[i_, 0] * L2[0] + fr.N[i_, 1] * L2[1]
        val = np.clip(0.45 + 0.4 * tt * np.sign(ndl) + rng.normal(0, 0.15, len(ss)), 0, 1)
        cols = jitter(ramp([ip['dark'], ip['mid'], ip['lit'], ip['gloss']], val, [0, 0.4, 0.8, 1.0]), rng, dl=0.03,
                      dc=0.1, dh=0.05)
        sz = np.clip(w * rng.uniform(0.035, 0.065, len(ss)), 6, 30) * (1.15 - 0.4 * ss / s_top)
        order = np.argsort(val)
        dabs(cv, q[order, 0], q[order, 1], sz[order], cols[order], aspect=rng.uniform(0.6, 0.9, len(ss))[order],
             angle=rng.uniform(0, 2 * np.pi, len(ss))[order], shape='petal', edge=0.22, rag=0.2, split=0.12, rng=rng)
    # --- thick moss cushions on the root flare (overhang a little, lit tops)
    for k in range(moss_cushions):
        p, w, _ = fr.at(rng.uniform(0.0, 0.12), rng.uniform(-0.9, 0.9))
        R = float(w) * rng.uniform(0.08, 0.14)
        b = Blobs()
        for j in range(int(rng.integers(3, 6))):
            r = R * rng.uniform(0.5, 0.9)
            b.add(p[0] + rng.normal(0, R * 0.6), p[1] + rng.normal(0, R * 0.3), r * 1.2, r * 0.75,
                  light=rng.uniform(0.9, 1.1), hue=rng.normal(0, 0.05), rng=rng, lumpy=0.25)
        from .sky import paint_planes
        paint_planes(cv, rng, b, (C(32, 60, 62), C(62, 100, 68), C(118, 150, 78), C(176, 186, 100)),
                     light3=(L3[0], L3[1], 0.5), th=(0.3, 0.58, 0.85), strokes=0.0, leafy_edge=0.8, leaf_px=7,
                     leaf_cols=[C(36, 66, 62), C(78, 116, 70), C(140, 166, 84)], noise_amt=0.1, rim=None)
