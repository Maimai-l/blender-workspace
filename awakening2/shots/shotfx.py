"""shotfx.py - per-shot composition: painted layers, robot cel, effects, light.

Each shot class says which painting to use, how its layers sit around the
robot, how the 2D camera follows the 3D one, what light hits the robot, and
which drawn effects play. `Base.compose()` does the rest.
"""
import os, sys, math, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'engine'))
import numpy as np
import cv2
import r3d, comp, look, cel
import fx
import birds
import shotdefs as SD

W, H = comp.W, comp.H
BG = os.path.join(ROOT, 'bg')


# the small bird: a blue-and-white flycatcher palette on the white-eye model, so it reads against moss
BIRD_PAL = {'olive': '#2f5fa8', 'forehead': '#3d74c4', 'coverts': '#2c5698', 'edge': '#5a8fd6',
            'flight': '#22304e', 'tail': '#26406e', 'tail_under': '#d9d6cf', 'yellow': '#f1ede2',
            'white': '#f4f2ea', 'buff': '#dcd8cc', 'undertail': '#efece4', 'ring': '#3d74c4',
            'lores': '#1c2236', 'thigh': '#dcd8cc'}


def have(p):
    return os.path.exists(os.path.join(BG, p, 'layers.json'))


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


class Base:
    redraw_on_camera = False
    ground_growth = True          # world-fixed moss mounds around the kneel contacts
    light_az, light_el = 118.0, 38.0
    painting = 'S01'
    fallback = None            # (painting, window(x0,y0), scale, blur) if the painting isn't ready
    behind = None              # layer names behind the robot (None = all with depth <= robot_depth)
    robot_depth = 0.5
    ref_t = 0.0
    win0 = (0.0, 0.0)
    win_scale = 1.0
    haze = 0.0                 # extra haze on top of the distance-based amount
    haze_auto = True
    wrap = 0.32
    ground = True
    sky_dir = (0.0, 0.25, 1.0)
    fade_in = None
    fade_out = None
    parallax = 0.3             # strength of multiplane parallax around the robot plane
    shadow_tint = (0.42, 0.47, 0.62)
    grade_kw = {}

    vines = True
    wind = 1.2           # breeze strength (m/s^2) for the vines

    def __init__(self, S):
        self.S = S
        self.shot = S.shot
        self.setup_painting()
        self.setup()
        self.vineset = None
        if self.vines and self.shot['pose']:
            self._make_vines()

    def _make_vines(self):
        import vines as VN, vineplan, anim, poses as PZ
        rig = SD.rig()
        vs = vineplan.plan(rig, PZ.grounded(rig, PZ.KNEEL_DORMANT))
        k = self.wind
        def wind(t):
            return (k * (0.6 + 0.4 * math.sin(t * 0.9)), k * 0.3 * math.sin(t * 0.5 + 1.0), 0.0)
        self.vineset = VN.VineSet(rig, vs, lambda t: anim.pose_at(self.shot, t), wind=wind)

    def setup(self):
        pass

    # ------------------------------------------------------------ painting
    def setup_painting(self):
        self.blur_bg = 0
        name = self.painting
        if name and not have(name) and self.fallback:
            name, self.win0, self.win_scale, self.blur_bg = self.fallback
        self.P = comp.Painting(os.path.join(BG, name)) if name and have(name) else None
        self.pname = name

    def layer_k(self, depth):
        return 1.0 + (depth - self.robot_depth) * self.parallax / max(self.robot_depth, 0.1) * 0.9

    # ------------------------------------------------------------ 2D camera
    def anchor(self):
        return SD.A['pelvis']

    def cam2d(self, t, t_ref=None):
        """(a_ref, d, s): the anchor's screen position at t_ref, its displacement and scale at t."""
        t_ref = self.ref_t if t_ref is None else t_ref
        c0 = self.S.cam(t_ref); c1 = self.S.cam(t)
        P = np.asarray(self.anchor(), np.float32)[None]
        q0 = c0.project(P)[0]; q1 = c1.project(P)[0]
        # scale from the true distance (a pure pan/tilt keeps the size), lens from fpx
        d0 = float(np.linalg.norm(P[0] - c0.pos)); d1 = float(np.linalg.norm(P[0] - c1.pos))
        s = (c1.fpx / max(d1, 1e-3)) / (c0.fpx / max(d0, 1e-3))
        return q0[:2], q1[:2] - q0[:2], s

    def M_for(self, k, t, t_ref=None, shake=(0.0, 0.0)):
        a, d, s = self.cam2d(t, t_ref)
        sk = 1 + (s - 1) * k
        dk = d * k
        tx = a[0] + dk[0] - sk * a[0] + shake[0] * k
        ty = a[1] + dk[1] - sk * a[1] + shake[1] * k
        return np.array([[sk, 0, tx], [0, sk, ty]], np.float32)

    def M_cel(self, t, tc, shake):
        return self.M_for(1.0, t, t_ref=tc, shake=shake)

    def bg_stack(self, names, t, shake):
        """Premultiplied RGBA of the named layers stacked 'over', cached while the 2D camera holds."""
        if self.P is None or not names:
            return None
        Ms = []
        for L in self.P.layers:
            if L['name'] in names:
                Ms.append(np.round(self.M_for(self.layer_k(L['depth']), t, shake=shake), 3).tobytes())
        key = (tuple(names), tuple(Ms), tuple(round(self.layer_opacity(n, t), 3) for n in names))
        cache = self.__dict__.setdefault('_stack_cache', {})
        if key in cache:
            return cache[key]
        acc = np.zeros((H, W, 4), np.float32)
        for L in self.P.layers:
            if L['name'] not in names:
                continue
            img = comp.load_rgba(os.path.join(self.P.folder, L['file']), u8=True)
            k = self.layer_k(L['depth'])
            M = self.M_for(k, t, shake=shake)
            ox, oy = L['offset']
            x0, y0 = self.win0
            sc = self.win_scale
            A = np.array([[sc, 0, (ox - x0) * sc], [0, sc, (oy - y0) * sc], [0, 0, 1]], np.float32)
            Mf = np.vstack([M, [0, 0, 1]]) @ A
            lay = cv2.warpAffine(img, Mf[:2], (W, H), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REPLICATE if L.get('coverage', 0) > 0.98 else cv2.BORDER_CONSTANT,
                                 borderValue=(0, 0, 0, 0)).astype(np.float32) / 255.0
            if self.blur_bg:
                lay = cv2.GaussianBlur(lay, (0, 0), self.blur_bg)
            op = self.layer_opacity(L['name'], t)
            pm = lay.copy(); pm[..., 3] *= op; pm[..., :3] *= pm[..., 3:4]
            acc = pm + acc * (1 - pm[..., 3:4])
        if len(cache) > 3:
            cache.clear()
        cache[key] = acc
        return acc

    def bg_layers(self, rgb, names, t, shake, opacity=None):
        st = self.bg_stack(names, t, shake)
        if st is None:
            return rgb
        return st[..., :3] + rgb * (1 - st[..., 3:4])

    def layer_opacity(self, name, t):
        return 1.0

    def split_layers(self):
        if self.P is None:
            return [], []
        if self.behind is not None:
            b = [l['name'] for l in self.P.layers if l['name'] in self.behind]
        else:
            b = [l['name'] for l in self.P.layers if l['depth'] <= self.robot_depth]
        f = [l['name'] for l in self.P.layers if l['name'] not in b]
        return b, f

    # ------------------------------------------------------------ robot
    def cel_cam_time(self, tq):
        return self.ref_t

    def light(self, cam):
        return comp.light_from_screen(cam, self.light_az, self.light_el)

    eye_glow = None            # after the robot wakes (S07) its eyes stay lit

    def style(self, tq, cam):
        st = dict(light=self.light(cam), seed=int(tq * 24) // 2 + 17, sky_dir=self.sky_dir,
                  ground_fade=(0.0, 0.3))
        if not self.ground_growth:
            rg = SD.rig()
            st['skip_parts'] = [n for n in rg.order if getattr(rg.parts[n], 'world', False)]
        if self.eye_glow is not None:
            import warden as WD
            g = float(self.eye_glow)
            st['lens_fn'] = lambda o, l, g=g: WD.eye_colour(o, g, l)
        return st

    def robot_state(self, tq):
        return ()

    # ------------------------------------------------------------ effects hooks
    def fx_behind(self, rgb, f, t, ctx):
        return rgb

    def fx_mid(self, rgb, f, t, ctx):
        return rgb

    def fx_front(self, rgb, f, t, ctx):
        return rgb

    def light_buf(self, lb, f, t, ctx):
        pass

    def shake_gain(self, t):
        return 1.0

    # ------------------------------------------------------------ compose
    def robot_haze(self):
        """Aerial perspective for the robot, from its distance (it must sit in the same air as the trees)."""
        if self.haze_auto is False:
            return self.haze
        c = self.S.cam(self.ref_t)
        d = float(np.linalg.norm(np.asarray(self.anchor(), np.float32) - c.pos))
        return float(np.clip((d - 14.0) / 110.0, 0.0, 0.26)) + self.haze

    def compose(self, f, t, cam):
        # camera shake moves the whole photographed frame (all cels together), on 1s
        shake_xy = self.S.shake(f)
        shake = (0.0, 0.0)
        ctx = dict(cam=cam, shake=shake)
        rgb = np.zeros((H, W, 3), np.float32) + np.array([0.85, 0.80, 0.70], np.float32)
        behind, front = self.split_layers()
        rgb = self.bg_layers(rgb, behind, t, shake)
        rgb = self.fx_behind(rgb, f, t, ctx)
        ent = self.S.robot_cel(t)
        if ent is not None:
            tc = self.cel_cam_time(self.S.drawing_time(t)) if not self.redraw_on_camera else self.S.drawing_time(t)
            M = self.M_cel(t, tc, shake)
            cel_rgba = comp_warp(ent['rgba'], M)
            ctx['cel'] = cel_rgba; ctx['M'] = M; ctx['ent'] = ent
            if self.ground and ent.get('gshadow') is not None:
                g = comp_warp(ent['gshadow'][..., None].repeat(4, -1), M)[..., 0]
                rgb = rgb * (1 - 0.55 * g[..., None]) + rgb * np.asarray(self.shadow_tint, np.float32) * 0.55 * g[..., None]
            a = cel_rgba[..., 3]
            robot_rgb = cel_rgba[..., :3]
            hz = self.robot_haze()
            if hz > 0:
                mist = comp.blur_small(rgb, 25)
                robot_rgb = robot_rgb * (1 - hz) + mist * a[..., None] * hz
            if self.wrap > 0:
                robot_rgb = comp.light_wrap(robot_rgb, a, rgb, radius=16, strength=self.wrap)
            rgb = self.robot_extra(robot_rgb, a, rgb, f, t, ctx)
            if self.vineset is not None:
                cv_ = fx.new_canvas(H, W)
                d = ent['ps_small']['depth']
                self.vineset.draw(cv_, f, ent['cam'], depth=d, light=screen_dir(ent['cam'], ent['light']))
                rgb = comp.over_straight(rgb, comp_warp(cv_, M))
        rgb = self.fx_mid(rgb, f, t, ctx)
        rgb = self.bg_layers(rgb, front, t, shake)
        rgb = self.fx_front(rgb, f, t, ctx)
        lb = np.zeros((H, W, 3), np.float32)
        self.light_buf(lb, f, t, ctx)
        rgb = 1 - (1 - np.clip(rgb, 0, 1)) * (1 - np.clip(lb, 0, 1))
        if shake_xy[0] or shake_xy[1]:
            Ms = np.float32([[1.03, 0, shake_xy[0] - W * 0.015], [0, 1.03, shake_xy[1] - H * 0.015]])
            rgb = cv2.warpAffine(rgb, Ms, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        rgb = comp.finish(rgb, int(round(self.S.shot['t0'] * 24)) + f, **self.grade_kw)
        fade = 1.0
        if self.fade_in:
            fade = min(fade, ease(t / self.fade_in))
        if self.fade_out:
            a_, b_ = self.fade_out
            if t > a_:
                fo = 1 - ease((t - a_) / (b_ - a_))
                # fade out through a cool dark, not a muddy olive: desaturate and cool as it darkens
                lum = rgb.mean(-1, keepdims=True)
                cool = lum * np.array([0.78, 0.88, 1.12], np.float32)
                k = 1 - fo
                rgb = rgb * (1 - k) + cool * k
                fade = min(fade, fo)
        return rgb * fade

    def robot_extra(self, robot_rgb, a, rgb, f, t, ctx):
        return robot_rgb + rgb * (1 - a[..., None])


def comp_warp(img, M):
    if np.allclose(M, [[1, 0, 0], [0, 1, 0]], atol=1e-4):
        return img
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def screen_dir(cam, L):
    """Screen-space (x right, y down) unit vector pointing toward the light."""
    c = cam.pos + cam.f * 30
    q = cam.project(np.array([c, c + np.asarray(L, np.float32) * 5], np.float32))
    d = q[1, :2] - q[0, :2]
    n = np.linalg.norm(d)
    return (float(d[0] / n), float(d[1] / n)) if n > 1e-6 else (0.6, -0.8)


def project(cam, P):
    return cam.project(np.asarray(P, np.float32)[None])[0]


# ============================================================================ shots

class S01(Base):
    """Tilt-down reveal; ends locked on the kneeling robot."""
    painting = 'S01'
    ref_t = 7.9
    win0 = (0.0, 2900 - 1040)
    robot_depth = 0.45
    parallax = 0.08                   # the tilt is a pan down one tall painting (little parallax)
    behind = ('sky', 'far', 'mist_far', 'mid', 'mist_mid')
    fade_in = None
    light_az, light_el = 118, 38

    def setup(self):
        self.leaves = fx.LeafFall('S01_leaves', region=(200, -200, 1800, 900), frame0=0, count=10,
                                  size=(14, 24), fall=(1.0, 1.8), wind=(0.3, 0), preroll=200)
        self.bird = birds.crossing((-60, 380), (900, 470), 150, 192, scale=20, facing=1)
        self.motes = fx.Motes('S01_motes', (300, 0, 1700, 1000), count=160)

    def cam2d(self, t, t_ref=None):
        # the tilt is a vertical pan of the tall painting, eased, synced to the robot's anchor
        a, d, s = Base.cam2d(self, t, t_ref)
        return a, d, s

    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.leaves.draw(cv_, f)
        st = self.bird.state(f) if hasattr(self.bird, 'state') else None
        if st is not None:
            birds.draw_state(cv_, st, birds.Light(dir=(0.8, 0.5), depth=-0.4), palette_overrides=BIRD_PAL)
        return comp.over_straight(rgb, cv_)

    def light_buf(self, lb, f, t, ctx):
        if t > 4.0:
            k = ease((t - 4.0) / 2.0)
            mask = fx.sunbeams(lb, src=(1500, -500), angles=[math.radians(a) for a in (112, 118, 123)],
                               widths=[60, 110, 45], spread=0.03, intensity=0.18 * k, frame=f, scale=0.5)
            self.motes.draw(lb, f, mask=np.clip(mask * 3, 0, 1))


class S02(Base):
    """Shoulder close shot: the small bird lands on the mossy pauldron."""
    painting = 'S02'
    fallback = ('S01', (0.0, 1500.0), 1.0, 6)
    robot_depth = 0.6
    haze = 0.04
    light_az, light_el = 125, 42

    def setup(self):
        cam = self.S.cam(0.0)
        # perch point: top of the left pauldron's moss
        top = SD.anchor(SD.K, 'pauldron_L', (-0.6, 0.2, 2.15))
        q = project(cam, top)
        self.perch = (float(q[0]), float(q[1]))
        sc = cam.fpx * 0.085 / q[2]      # the bird is ~8.5 cm... scaled up for readability
        self.bscale = 230.0
        tf = lambda s: int(round((s - 8.0) * 24))
        self.track = birds.landing(x=self.perch[0], y=self.perch[1], scale=self.bscale, facing=1,
                                   t_flare=tf(9.6), t_touch=tf(10.1), t_hop=tf(10.9), t_chirp=tf(12.2), t_end=132)
        self.motes = fx.Motes('S02_motes', (0, 0, 1920, 1040), count=120)

    def fx_front(self, rgb, f, t, ctx):
        st = self.track.state(f)
        if st is None:
            return rgb
        cv_ = fx.new_canvas(H, W)
        birds.draw_state(cv_, st, birds.Light(dir=(0.75, 0.55), depth=-0.25, shadow_mul=(0.85, 0.85, 1.0)), palette_overrides=BIRD_PAL)
        return comp.over_straight(rgb, cv_)

    def light_buf(self, lb, f, t, ctx):
        mask = fx.sunbeams(lb, src=(1700, -300), angles=[math.radians(a) for a in (115, 121)],
                           widths=[90, 50], spread=0.03, intensity=0.14, frame=f, scale=0.5)
        self.motes.draw(lb, f, mask=np.clip(mask * 3, 0, 1))


class S03(Base):
    """Face close-up: the first ray of sun slides across the weathered face."""
    painting = 'S03'
    fallback = ('S01', (0.0, 300.0), 1.0, 5)
    robot_depth = 0.6
    ref_t = 0.0
    haze = 0.0
    wrap = 0.25
    light_az, light_el = 140, 30        # base: the face in shadow (backlight)
    ray_az, ray_el = -35, 8             # the first ray: a low sunrise sun from the front-left

    def setup(self):
        self.motes = fx.Motes('S03_motes', (0, 0, 1920, 1040), count=220)

    def robot_state(self, tq):
        return ('dual',)

    def beam(self, t):
        """The first ray: a cylinder of sunlight from the canopy gap that sweeps across the face."""
        u = ease((t - 0.8) / 3.8)
        c0 = SD.A['brow'] + np.array([-2.5, 1.0, 2.6], np.float32)       # starts above-left of the brow
        c1 = SD.A['eyes'] + np.array([0.2, 0.4, -0.2], np.float32)       # settles over the eyes
        c = c0 + (c1 - c0) * u
        rad = 0.6 + 1.5 * ease((t - 0.8) / 4.5)
        L = comp.light_from_screen(self.S.cam(t), self.ray_az, self.ray_el)
        return c, L, rad

    def ray_band(self, t, ent=None):
        ent = ent or self.S.robot_cel(t)
        ps = ent['ps_small']
        c, L, rad = self.beam(t)
        P = ps['wpos']
        d = P - c
        along = np.sum(d * L, -1)[..., None]
        perp = np.linalg.norm(d - along * L, axis=-1)
        band = ((perp < rad) & (ps['mask'] > 0.5)).astype(np.float32)
        band = look.clean_mask(band > 0.5, 2, 2, 60, 1.5).astype(np.float32)
        return band, (c, L, rad)

    def haze_off(self):
        return True

    def robot_extra(self, robot_rgb, a, rgb, f, t, ctx):
        ent = ctx['ent']
        lit = ent.get('lit_rgba')
        if lit is not None and t > 0.8:
            band, _ = self.ray_band(self.S.drawing_time(t), ent)      # the light shape moves on 2s
            band = comp_warp(np.repeat(band[..., None], 4, -1), ctx['M'])[..., 0]
            band = cv2.GaussianBlur(band, (0, 0), 0.8)
            litw = comp_warp(lit, ctx['M'])
            robot_rgb = robot_rgb * (1 - band[..., None]) + litw[..., :3] * band[..., None]
        return robot_rgb + rgb * (1 - a[..., None])

    def light_buf(self, lb, f, t, ctx):
        if t > 0.8:
            c, L, rad = self.beam(t)
            cam = ctx['cam']
            qc = project(cam, c); qd = project(cam, c + L * 1.5)
            d2 = qd[:2] - qc[:2]
            n2 = float(np.linalg.norm(d2))
            d2 = d2 / n2 if n2 > 1e-6 else np.array([-0.7, -0.7])
            r_px = cam.fpx * rad / max(qc[2], 1.0)
            p0 = np.clip(qc[:2] + d2 * 4000, -9000, 9000); p1 = np.clip(qc[:2] - d2 * 300, -9000, 9000)
            m = np.zeros((H, W), np.float32)
            cv2.line(m, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), 1.0, int(np.clip(r_px * 1.6, 4, 2000)), cv2.LINE_AA)
            soft = cv2.GaussianBlur(m, (0, 0), max(8, r_px * 0.5)) * 0.13 * ease((t - 0.8) / 1.0)
            lb += soft[..., None] * np.array([1.0, 0.86, 0.6], np.float32)
            self.motes.draw(lb, f, mask=np.clip(soft * 6, 0, 1))


class S04(Base):
    """Chest furnace grille: the core flickers on, then a heartbeat glow."""
    painting = 'S04'
    fallback = ('S01', (0.0, 1860.0), 1.0, 8)
    robot_depth = 0.6
    haze = 0.04
    light_az, light_el = 120, 40
    EVENTS = [(1.0, 0.55, 0.12), (1.5, 0.35, 0.1), (2.4, 0.6, None)]

    def glow_level(self, tq):
        g = 0.0
        if 1.0 <= tq < 1.12: g = 0.6
        elif 1.5 <= tq < 1.58: g = 0.4
        elif 1.75 <= tq < 1.83: g = 0.25
        elif tq >= 2.4:
            g = 0.55 + 0.1 * ease((tq - 2.4) / 0.6)
            for hb in (3.4, 4.4):
                if hb <= tq < hb + 0.45:
                    g += 0.35 * (1 - (tq - hb) / 0.45)
        return round(g * 4) / 4      # four drawings: 0, .25, .5, .75, 1

    def robot_state(self, tq):
        return ('glow', self.glow_level(tq))

    def style(self, tq, cam):
        st = Base.style(self, tq, cam)
        g = self.glow_level(tq)
        import warden as WD
        st['emissive'] = {}
        def glow_fn(o, g=g):
            # the furnace core: designed concentric bands (white-gold heart, orange, ember edge), in part space
            r = np.sqrt(((o[:, 0]) / 1.2) ** 2 + ((o[:, 2] - 4.35) / 1.0) ** 2)
            dark = np.array([0.20, 0.13, 0.15], np.float32)
            heart = np.array([1.0, 0.95, 0.78], np.float32); mid = np.array([1.0, 0.70, 0.30], np.float32)
            edge = np.array([0.78, 0.30, 0.16], np.float32)
            rr = r / max(0.25 + 0.75 * g, 1e-3)
            col = np.where((rr < 0.35)[:, None], heart, np.where((rr < 0.7)[:, None], mid, np.where((rr < 1.05)[:, None], edge, dark)))
            return (dark * (1 - g) + col * g).astype(np.float32) if g < 1 else col.astype(np.float32)
        if g > 0:
            st['glow_fn'] = glow_fn
            st['glow_mat'] = WD.GLOW
            M = SD.rig().world_mats(SD.K)['torso']
            C = r3d.xform_points(M, np.array([[0, 3.3, 4.35]], np.float32))[0]
            Nw = M[:3, :3] @ np.array([0, 1.0, 0], np.float32)
            parts_ok = [SD.rig().parts[n].index for n in ('grille', 'torso')]
            st['core_light'] = (C, Nw, 3.4 + 3.0 * g, (1.0, 0.68, 0.32), min(1.0, 0.5 + 0.6 * g), parts_ok)
        else:
            st['emissive'] = {WD.GLOW: np.array([0.20, 0.13, 0.15], np.float32)}
        return st

    def light_buf(self, lb, f, t, ctx):
        g = self.glow_level(self.S.drawing_time(t))
        if g > 0:
            q = project(ctx['cam'], SD.A['chest'])
            c = (float(q[0]) + ctx['shake'][0], float(q[1]) + ctx['shake'][1])
            fx.glow(lb, c, 360 * (0.6 + g), colour=(1.0, 0.70, 0.34), intensity=0.8 * g)
            fx.glow(lb, c, 110 * (0.6 + g), colour=(1.0, 0.95, 0.80), intensity=0.55 * g)


class S05(Base):
    """Ground close-up: pebbles and dew jump, soil cracks (tremor)."""
    painting = 'S05'
    fallback = ('S01', (300.0, 2000.0), 1.35, 3)
    robot_depth = 0.45
    behind = ('far', 'mid', 'ground')
    light_az, light_el = 120, 40

    def setup(self):
        self.pebbles = fx.DebrisBurst('S05_hop', origin=(960, 900), frame0=8, count=26,
                                      kinds={'pebble': 0.5, 'crumb': 0.4, 'moss': 0.1}, size=(5, 14),
                                      direction=(0, -1), spread=1.6, speed=(3, 7), gravity=0.9,
                                      ground=930, bounce=0.35, origin_radius=520)
        self.pebbles2 = fx.DebrisBurst('S05_hop2', origin=(900, 950), frame0=30, count=20,
                                       kinds={'pebble': 0.6, 'crumb': 0.4}, size=(4, 12),
                                       direction=(0, -1), spread=1.4, speed=(3, 8), gravity=0.9,
                                       ground=990, bounce=0.3, origin_radius=600)
        self.dust = fx.GroundDust('S05_dust', start=(1200, 960), direction=(-1, 0), frame0=20,
                                  distance=700, duration=36, height=70)

    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.dust.draw(cv_, f)
        self.pebbles.draw(cv_, f)
        self.pebbles2.draw(cv_, f)
        return comp.over_straight(rgb, cv_)


SHOT_CLASSES = {}


def make(S):
    cls = SHOT_CLASSES.get(S.sid) or globals().get(S.sid)
    return cls(S)


# ---------------------------------------------------------------------------- helpers

def eye_style(glow):
    import warden as WD
    return dict(lens_fn=lambda o, l, g=glow: WD.eye_colour(o, g, l))


def root_pos(shot, t):
    """Smooth (1s) world translation of the robot root from the pose keys' x/y/lift."""
    import anim
    keys = shot['pose']
    def kv(k):
        kw = k[2] if len(k) > 2 else {}
        return np.array([kw.get('x', 0.0), kw.get('y', 0.0), kw.get('lift', 0.0)], np.float32)
    if t <= keys[0][0]:
        return kv(keys[0])
    for a, b in zip(keys[:-1], keys[1:]):
        if t <= b[0]:
            u = (t - a[0]) / max(b[0] - a[0], 1e-6)
            return kv(a) + (kv(b) - kv(a)) * anim.spacing(u, 'heavy')
    return kv(keys[-1])


class S06(Base):
    """Treetops against the dawn sky: birds burst from the canopy."""
    painting = 'S06'
    fallback = ('S11', (0.0, 0.0), 1.0, 0)
    ground = False
    behind = ('sky', 'canopy_far')
    def setup(self):
        self.sim = birds.burst(n=130, canopy=((150, 640), (1800, 560)), f_start=2, frames=72, seed=7, span=(10, 46))
        self.lb = fx.LeafBurst('S06_leaves', origin=(960, 600), frame0=3, count=40, direction=(0, -1), spread=2.4,
                               speed=(6, 20), size=(14, 26), origin_radius=700, wind=(0.4, 0))
    def fx_mid(self, rgb, f, t, ctx):
        # the flock bursts from between the far and the near canopy
        cv_ = fx.new_canvas(H, W)
        self.lb.draw(cv_, f)
        birds.draw_flock(cv_, self.sim.at(f), light=birds.Light(dir=(0.7, 0.6), depth=-0.6), style='silhouette')
        return comp.over_straight(rgb, cv_)


class S07(S03):
    """Face: the lids crack open, the eyes flicker alive; the small bird flees."""
    painting = 'S03'
    fallback = ('S01', (0.0, 300.0), 1.0, 5)
    light_az, light_el = 145, 28        # backlit: the face in shadow so the waking eyes carry the shot
    def glow(self, tq):
        if tq < 1.3: return 0.0
        seq = [(1.3, 0.35), (1.42, 0.0), (1.5, 0.6), (1.62, 0.2), (1.7, 0.85), (2.0, 1.0)]
        g = 0.0
        for a, v in seq:
            if tq >= a: g = v
        return g
    def robot_state(self, tq):
        return ('glow', self.glow(tq))
    def style(self, tq, cam):
        st = Base.style(self, tq, cam)
        st.update(eye_style(self.glow(tq)))
        return st
    def setup(self):
        cam = self.S.cam(0.0)
        q = project(cam, SD.anchor(SD.K, 'pauldron_L', (-0.6, 0.2, 2.15)))
        x = float(np.clip(q[0], 120, 1800)); y = float(np.clip(q[1], 200, 980))
        self.flee = birds.flee(x=x, y=y, scale=150, facing=-1, t_startle=31, t_flee=50)
        self.motes = fx.Motes('S07_motes', (0, 0, 1920, 1040), count=160)
    def robot_extra(self, robot_rgb, a, rgb, f, t, ctx):
        return robot_rgb + rgb * (1 - a[..., None])
    def fx_front(self, rgb, f, t, ctx):
        st = self.flee.state(f)
        if st is None:
            return rgb
        cv_ = fx.new_canvas(H, W)
        birds.draw_state(cv_, st, birds.Light(dir=(-0.7, 0.6), depth=0.2), palette_overrides=BIRD_PAL)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        tq = self.S.drawing_time(t)
        g = self.glow(tq)
        if g > 0:
            import warden as WD, anim
            pose = anim.pose_at(self.shot, tq)
            # the lids cover the lamps during the blink
            lid = float(np.asarray(pose.get('lid_R', (-22, 0, 0)))[0])
            g *= float(np.clip((lid + 64.0) / 42.0, 0.0, 1.0))
            if g <= 0:
                return
            for side in (1, -1):
                ex, ey, ez = WD.EYE_C
                q = project(ctx['cam'], SD.anchor(pose, 'head', (side * ex, ey + 0.3, ez)))
                fx.glow(lb, (float(q[0]), float(q[1])), 220, colour=(1.0, 0.75, 0.35), intensity=0.5 * g)
    def beam(self, t):
        return S03.beam(self, 6.0)


class Rise(Base):
    """Shared rise effects: soil pouring, dust at contacts, leaves from the roof tree, shake."""
    light_az, light_el = 118, 38
    pours = ()          # (name, part, local point, t0, t1)
    puffs = ()          # (name, part, local point, t, size)
    def setup(self):
        self.pour_fx = []
        for name, part, loc, a, b in self.pours:
            emit = self._emitter(part, loc)
            self.pour_fx.append(fx.SoilPour(f'{self.S.sid}_{name}', emit, start=int(a * 24), end=int(b * 24), rate=9,
                                            strands=3, size=(3, 8), ground=self._ground_y(), veil_opacity=0.22,
                                            veil_size=22.0, kinds={'crumb': .72, 'clod': .24, 'moss': .04}))
        self.puff_fx = []
        for name, part, loc, t0, size in self.puffs:
            # the puff starts ON the ground under the contact (never an airborne ball)
            q = self._proj_at(part, loc, t0, on_ground=True)
            self.puff_fx.append(fx.DustPuff(f'{self.S.sid}_{name}', origin=(float(q[0]), float(q[1])), frame0=int(t0 * 24),
                                            size=size * 0.6, ground=float(q[1]) + size * 0.08, spread=3.0, life=40, aspect=0.45,
                                            palette=fx.palettes.DUST_DARK,
                                            light=screen_dir(self.S.cam(t0), self.light(self.S.cam(t0)))))
        tree = self._proj_at('roof_L', (-3.2, -0.2, 3.6), 0.0)
        self.leaves = fx.LeafBurst(f'{self.S.sid}_treeleaves', origin=(float(tree[0]), float(tree[1])), frame0=int(0.8 * 24),
                                   count=34, direction=(0, -1), spread=2.6, speed=(4, 12), size=(12, 22),
                                   origin_radius=120, wind=(0.3, 0))
    def _ground_y(self):
        cam = self.S.cam(0.0)
        return float(np.clip(project(cam, (0, 0, 0))[1] + 40, 0, H + 200))
    def _proj_at(self, part, loc, t, on_ground=False):
        import anim
        pose = anim.pose_at(self.shot, t)
        mats = SD.rig().world_mats(pose)
        P = r3d.xform_points(mats[part], np.array([loc], np.float32))[0]
        if on_ground:
            P = np.array([P[0], P[1], 0.0], np.float32)
        return project(self.S.cam(t), P)
    def _emitter(self, part, loc):
        cache = {}
        def emit(frame):
            if frame not in cache:
                q = self._proj_at(part, loc, frame / 24.0)
                cache[frame] = ((float(q[0]) - 45.0, float(q[1])), (float(q[0]) + 45.0, float(q[1]) + 6.0))
            return cache[frame]
        return emit
    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        for p in self.puff_fx:
            p.draw(cv_, f)
        for p in self.pour_fx:
            p.draw(cv_, f)
        self.leaves.draw(cv_, f)
        sx, sy = ctx['shake']
        if sx or sy:
            cv_ = cv2.warpAffine(cv_, np.float32([[1, 0, sx], [0, 1, sy]]), (W, H))
        return comp.over_straight(rgb, cv_)


class S08(Rise):
    eye_glow = 0.85
    painting = 'S08'
    fallback = ('S01', (0.0, 1860.0), 1.0, 0)
    robot_depth = 0.55
    behind = ('sky', 'far', 'mist_far', 'mid', 'mist_mid')
    pours = (('arm', 'forearm_L', (0, 1.2, -2.0), 0.9, 4.4), ('roof', 'roof_R', (5.6, -1.0, -1.2), 1.2, 4.4),
             ('chest', 'torso', (1.5, 3.4, 2.0), 1.6, 4.0))
    puffs = (('hand', 'hand_R', (0, 0.4, -1.8), 1.5, 220), ('knee', 'shin_R', (0, 0.9, 0.0), 2.6, 260))


class S09(Rise):
    eye_glow = 0.9
    painting = 'S09'
    fallback = ('S01', (0.0, 1700.0), 1.0, 0)
    robot_depth = 0.55
    behind = ('sky', 'far', 'mist_far', 'mid', 'mist_mid')
    light_az, light_el = 128, 34
    pours = (('arm', 'forearm_L', (0, 1.2, -2.0), 0.0, 3.0), ('roof', 'roof_L', (-5.6, -1.0, -1.2), 0.0, 3.4),
             ('thigh', 'thigh_L', (0, 1.0, -1.5), 0.3, 2.6))
    puffs = (('foot', 'foot_R', (0, 1.0, -1.2), 0.6, 240), ('foot2', 'foot_L', (0, 1.0, -1.2), 2.6, 200))


class S10(Base):
    painting = 'S10'
    fallback = ('S11', (0.0, 0.0), 1.0, 2)
    redraw_on_camera = False          # the tilt is a 2D pan of the cel and the painted layers
    parallax = 0.1
    robot_depth = 0.6
    ground = False
    light_az, light_el = 150, 68      # from the canopy gap above: the upturned face catches it
    def glow(self, tq):
        return 0.7 + 0.3 * ease((tq - 1.6) / 0.8)
    def robot_state(self, tq):
        return ('glow', round(self.glow(tq), 2))
    def style(self, tq, cam):
        st = Base.style(self, tq, cam)
        st.update(eye_style(self.glow(tq)))
        return st
    win0 = (0.0, 560.0)
    def setup(self):
        self.leaves = fx.LeafFall('S10_leaves', region=(0, -300, 1920, 800), frame0=0, count=18, size=(14, 26), preroll=120)
        self.motes = fx.Motes('S10_motes', (0, 0, 1920, 1040), count=150)
    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.leaves.draw(cv_, f)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        mask = fx.sunbeams(lb, src=(700, -500), angles=[math.radians(a) for a in (72, 80, 86)],
                           widths=[70, 120, 50], spread=0.03, intensity=0.2, frame=f, scale=0.5)
        self.motes.draw(lb, f, mask=np.clip(mask * 3, 0, 1))


class S11(Base):
    painting = 'S11'
    ground = False
    def setup(self):
        self.leaves = fx.LeafFall('S11_leaves', region=(200, -200, 1700, 900), frame0=0, count=26, size=(16, 30),
                                  spiral=0.8, preroll=150)
    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.leaves.draw(cv_, f)
        return comp.over_straight(rgb, cv_)
    def layer_opacity(self, name, t):
        return 0.0 if name == 'flare' else 1.0
    def light_buf(self, lb, f, t, ctx):
        fx.glow(lb, (1250, 260), 520, colour=(1.0, 0.86, 0.55), intensity=0.3)


class Engines:
    """Engine bell nozzles in world space for a pose."""
    BELLS = [(1.4, -3.75, 3.5), (-1.4, -3.75, 3.5)]
    @staticmethod
    def nozzles(pose, cam):
        mats = SD.rig().world_mats(pose)
        out = []
        for b in Engines.BELLS:
            P = r3d.xform_points(mats['torso'], np.array([b], np.float32))[0]
            P2 = P + np.array([0.0, -0.25, -2.0], np.float32)      # thrust points down
            q0 = project(cam, P); q1 = project(cam, P2)
            d = q1[:2] - q0[:2]; n = np.linalg.norm(d) + 1e-6
            rad = cam.fpx * 1.0 / max(q0[2], 1)
            out.append(((float(q0[0]), float(q0[1])), (float(d[0] / n), float(d[1] / n)), rad, q0[2]))
        return out


class S12(Base):
    eye_glow = 1.0
    painting = 'S12'
    fallback = ('S01', (0.0, 1500.0), 1.0, 4)
    robot_depth = 0.55
    light_az, light_el = 158, 30
    def setup(self):
        # the two engines cough at different moments (two identical flashes side by side read as eyes)
        sp = [[(int(2.35 * 24), .32), (int(2.75 * 24), .45)], [(int(2.55 * 24), .5), (int(2.9 * 24), .3)]]
        self.flames = [fx.EngineFlame(f'S12_e{i}', ignite=int(3.0 * 24) + i * 2, sputters=sp[i],
                                      diamonds=True, smoke=True, sparks=True) for i in range(2)]
        self.dust = fx.GroundDust('S12_dust', start=(960, 1000), direction=(1, 0), frame0=int(3.0 * 24), distance=900, duration=24, height=120,
                                  palette=fx.palettes.DUST_DARK)
        self.dust2 = fx.GroundDust('S12_dust2', start=(960, 1000), direction=(-1, 0), frame0=int(3.0 * 24), distance=900, duration=24, height=120,
                                   palette=fx.palettes.DUST_DARK)
    def fx_mid(self, rgb, f, t, ctx):
        import anim
        cv_ = fx.new_canvas(H, W)
        self.dust.draw(cv_, f); self.dust2.draw(cv_, f)
        pose = anim.pose_at(self.shot, t)
        for fl, (noz, d, rad, z) in zip(self.flames, Engines.nozzles(pose, ctx['cam'])):
            fl.draw(cv_, f, nozzle=noz, direction=d, radius=rad * 0.9, length=rad * 9)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        import anim
        pose = anim.pose_at(self.shot, t)
        for fl, (noz, d, rad, z) in zip(self.flames, Engines.nozzles(pose, ctx['cam'])):
            n2 = (noz[0] + d[0] * rad * 1.6, noz[1] + d[1] * rad * 1.6)      # the light sits in the flame
            fl.glow(lb, f, nozzle=n2, direction=d, radius=rad * 0.7, length=rad * 8)
    def shake_gain(self, t):
        return 0.3 if t < 3.0 else 1.0


class S13(Base):
    eye_glow = 1.0
    painting = 'S13'
    haze_auto = False
    haze = 0.08
    fallback = ('S01', (0.0, 1860.0), 1.0, 0)
    robot_depth = 0.5
    light_az, light_el = 110, 50
    def setup(self):
        cam = self.S.cam(0.0)
        c = project(cam, (0, 0, 0))
        self.ring = fx.WindRing('S13_ring', centre=(float(c[0]), float(c[1])), frame0=2, radius=1250, duration=66, r0=120,
                                ratio=0.55, persp=0.3, height=120, slots=48, grass=1000, leaves=110, lines=64)
        self.flames = [fx.EngineFlame(f'S13_e{i}', ignite=-30, sputters=[]) for i in range(2)]
        self.leaves = fx.LeafBurst('S13_leaves', origin=(float(c[0]), float(c[1])), frame0=6, count=70, direction=(0, -1),
                                   spread=6.28, speed=(12, 30), size=(14, 26), origin_radius=200)
    def fx_behind(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.ring.draw(cv_, f, part='back')
        return comp.over_straight(rgb, cv_)
    def fx_mid(self, rgb, f, t, ctx):
        import anim
        cv_ = fx.new_canvas(H, W)
        pose = anim.pose_at(self.shot, t)
        lb = ctx.setdefault('lb', np.zeros((H, W, 3), np.float32))
        for fl, (noz, d, rad, z) in zip(self.flames, Engines.nozzles(pose, ctx['cam'])):
            fl.draw(cv_, f, nozzle=noz, direction=d, radius=rad * 0.9, length=rad * 5)
            fl.glow(lb, f, nozzle=noz, direction=d, radius=rad * 0.9, length=rad * 5)
        self.ring.draw(cv_, f, part='front')
        self.leaves.draw(cv_, f)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        if 'lb' in ctx:
            lb += ctx['lb']


class S14(Base):
    """Launch: anticipation hold, smears, impact frames, exit upward."""
    eye_glow = 1.0
    vines = False
    painting = 'S08'
    fallback = ('S01', (0.0, 1860.0), 1.0, 0)
    robot_depth = 0.55
    behind = ('sky', 'far', 'mist_far', 'mid', 'mist_mid')
    redraw_on_camera = True
    light_az, light_el = 128, 34
    def anchor(self):
        return np.array([0, 0, 4.0], np.float32)
    def setup(self):
        cam = self.S.cam(0.0)
        g = project(cam, (0, 0, 0))
        self.blast = fx.DustPuff('S14_blast', origin=(float(g[0]), float(g[1]) + 40), frame0=7, size=380, spread=3.8,
                                 life=30, ground=float(g[1]) + 70, aspect=0.45, arms=1.2, direction=(0, -1),
                                 palette=fx.palettes.DUST, main=True)      # the launch keeps one big mass
        self.veil = fx.DustVeil('S14_veil', origin=(float(g[0]), float(g[1]) + 50), frame0=8, width=1700, height=300,
                                life=56, palette=fx.palettes.DUST_DARK, opacity=0.55, ground=float(g[1]) + 70)
        self.ring = fx.GroundDust('S14_ringL', start=(float(g[0]), float(g[1]) + 60), direction=(-1, 0), frame0=8,
                                  distance=1100, duration=20, height=170)
        self.ring2 = fx.GroundDust('S14_ringR', start=(float(g[0]), float(g[1]) + 60), direction=(1, 0), frame0=8,
                                   distance=1100, duration=20, height=170)
        self.debris = fx.DebrisBurst('S14_debris', origin=(float(g[0]), float(g[1])), frame0=8, count=70,
                                     direction=(0, -1), spread=2.4, speed=(14, 40), gravity=1.0, ground=float(g[1]) + 80,
                                     size=(5, 18), origin_radius=180)
        self.leafburst = fx.LeafBurst('S14_leaves', origin=(float(g[0]), float(g[1]) - 200), frame0=8, count=60,
                                      direction=(0, -1), spread=3.0, speed=(14, 34), size=(16, 30), origin_radius=400)
        self.flames = [fx.EngineFlame(f'S14_e{i}', ignite=-40, sputters=[]) for i in range(2)]
    def fx_mid(self, rgb, f, t, ctx):
        # after the impact: the flame column under the robot as it rockets out of frame
        if f < 10:
            return rgb
        import anim
        cv_ = fx.new_canvas(H, W)
        pose = anim.pose_at(self.shot, t)
        lb = ctx.setdefault('lb', np.zeros((H, W, 3), np.float32))
        for fl, (noz, d, rad, z) in zip(self.flames, Engines.nozzles(pose, ctx['cam'])):
            fl.draw(cv_, f, nozzle=noz, direction=(d[0] * 0.2, 1.0), radius=rad * 1.4, length=rad * 16)
            fl.glow(lb, f, nozzle=noz, direction=(d[0] * 0.2, 1.0), radius=rad * 1.4, length=rad * 16)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        if 'lb' in ctx:
            lb += ctx['lb']
    def fx_behind(self, rgb, f, t, ctx):
        # the engines fire from the back, so from the front the flames are behind the robot:
        # only their glow and the licks past the silhouette show
        if f > 6:
            return rgb
        import anim
        cv_ = fx.new_canvas(H, W)
        pose = anim.pose_at(self.shot, t)
        for fl, (noz, d, rad, z) in zip(self.flames, Engines.nozzles(pose, ctx['cam'])):
            fl.draw(cv_, f, nozzle=noz, direction=(d[0] * 0.3, 1.0), radius=rad * 1.3, length=rad * 9)
        return comp.over_straight(rgb, cv_)
    def compose(self, f, t, cam):
        if 8 <= f <= 9:      # impact frames
            ent = self.S.robot_cel(6 / 24)
            celr = ent['rgba'].copy()
            a = np.clip(celr[..., 3:4], 1e-4, 1)
            straight = np.concatenate([celr[..., :3] / a, celr[..., 3:4]], -1)
            return np.clip(fx.impact_frame(H, W, straight, mode='black_gold' if f == 8 else 'gold_black', frame=f)[..., :3], 0, 1)
        return Base.compose(self, f, t, cam)
    def robot_extra(self, robot_rgb, a, rgb, f, t, ctx):
        if 6 <= f <= 7:
            ent = ctx['ent']
            pm = ctx['cel']
            aa = np.clip(pm[..., 3:4], 1e-4, 1)
            straight = np.concatenate([pm[..., :3] / aa, pm[..., 3:4]], -1)
            sm = fx.smear_stretch(straight, motion=(0, -520 if f == 6 else -900), stretch=0.45, tail=1.6, name='S14', frame=f)
            return comp.over_straight(rgb, sm)
        return robot_rgb + rgb * (1 - a[..., None])
    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.ring.draw(cv_, f); self.ring2.draw(cv_, f)
        self.blast.draw(cv_, f)
        self.debris.draw(cv_, f)
        self.leafburst.draw(cv_, f)
        if 10 <= f <= 17:          # a short burst of focus lines with the impact, not a long overlay
            fx.speed_lines(cv_, (960, 250), f, n=56, inner=(0.34, 0.6), width=(1.5, 10.0), alpha=0.8)
        return comp.over_straight(rgb, cv_)
    def shake_gain(self, t):
        return 0.5 if t < 0.25 else (1.6 if t < 0.8 else 0.8)


class S15(Base):
    """From below: it tears up through the canopy gap; the canopy bursts; leaves rain down."""
    ground_growth = False
    eye_glow = 1.0
    painting = 'S11'
    ground = False
    vines = False
    haze_auto = False
    haze = 0.0
    wrap = 0.12
    redraw_on_camera = True
    robot_depth = 0.3
    light_az, light_el = 0, 70
    def anchor(self):
        return np.array([0, 2, 44], np.float32)
    def setup(self):
        # the moment it crosses the canopy (44 m) decides when the canopy bursts
        import anim
        tc = 0.5
        for k in range(0, 72):
            p = anim.pose_at(self.shot, k / 24.0)
            if p is not None and p['_root'][2, 3] > 30.0:
                tc = k / 24.0
                break
        fc = int(tc * 24)
        self.t_cross = tc
        self.burst = fx.LeafBurst('S15_burst', origin=(960, 470), frame0=fc, count=110, direction=(0, 1), spread=3.1,
                                  speed=(10, 30), size=(16, 34), origin_radius=300)
        self.twigs = fx.DebrisBurst('S15_twigs', origin=(960, 470), frame0=fc, count=36,
                                    kinds={'vine': 0.5, 'moss': 0.3, 'crumb': 0.2}, size=(6, 16),
                                    direction=(0, 1), spread=3.0, speed=(10, 26), gravity=0.8, origin_radius=260)
        self.fall = fx.LeafFall('S15_fall', region=(0, -300, 1920, 900), frame0=fc + 6, count=40, size=(16, 30), spiral=0.8)
        self.flames = [fx.EngineFlame(f'S15_e{i}', ignite=-40, sputters=[]) for i in range(2)]
    def compose(self, f, t, cam):
        # below the canopy the robot is in front of every painted layer; once through, behind the near leaves
        self._t = t
        return Base.compose(self, f, t, cam)
    def split_layers(self):
        names = [l['name'] for l in self.P.layers]
        if getattr(self, '_t', 0.0) < self.t_cross:
            return names, []
        return [n for n in names if n in ('sky', 'canopy_far', 'trunks')], [n for n in names if n not in ('sky', 'canopy_far', 'trunks')]
    def fx_mid(self, rgb, f, t, ctx):
        # the bells fire straight down at the camera: short flames and a blinding glow
        import anim
        pose = anim.pose_at(self.shot, t)
        cv_ = fx.new_canvas(H, W)
        lb = ctx.setdefault('lb', np.zeros((H, W, 3), np.float32))
        for fl, (noz, d, rad, z) in zip(self.flames, Engines.nozzles(pose, ctx['cam'])):
            if z < 1:
                continue
            fl.draw(cv_, f, nozzle=noz, direction=(0.0, 1.0), radius=rad * 1.0, length=rad * 2.5)
            fx.glow(lb, noz, rad * 4.0, colour=(1.0, 0.8, 0.45), intensity=0.7)
        return comp.over_straight(rgb, cv_)
    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.burst.draw(cv_, f); self.twigs.draw(cv_, f); self.fall.draw(cv_, f)
        return comp.over_straight(rgb, cv_)
    def fx_behind(self, rgb, f, t, ctx):
        # the sky glow sits behind the robot: it reads as a dark rim-lit silhouette against the gap
        g = np.zeros((H, W, 3), np.float32)
        fx.glow(g, (960, 470), 600, colour=(1.0, 0.85, 0.5), intensity=0.3 + 0.3 * ease((t - 0.6) / 0.6))
        return 1 - (1 - np.clip(rgb, 0, 1)) * (1 - np.clip(g, 0, 1))
    def light_buf(self, lb, f, t, ctx):
        if 'lb' in ctx:
            lb += ctx['lb']


class S16B(Base):
    """Golden sky: the robot climbs along a big S-curve to the sun; the trail of light and mist."""
    ground_growth = False
    eye_glow = 1.0
    painting = 'S16'
    win0 = (400.0, 0.0)
    haze_auto = False
    ground = False
    redraw_on_camera = True
    robot_depth = 0.4
    haze = 0.05
    vines = False
    light_az, light_el = 120, 22
    def anchor(self):
        return np.array([0, 0, 0], np.float32)
    def setup(self):
        self.trail = fx.LightTrail('S16_trail', width=78, life=420, mist=True, mist_size=0.7, light=(0.6, -0.8), mist_every=5)
        self.flames = [fx.EngineFlame(f'S16_e{i}', ignite=-40, sputters=[]) for i in range(2)]
    def cam2d(self, t, t_ref=None):
        return np.array([960.0, 520.0]), np.array([-40.0 * ease(t / 5.0), 0.0]), 1.0
    def head_point(self, t):
        M = SD.s16_root(t)
        return r3d.xform_points(M, np.array([[0, -3.0, 8.0]], np.float32))[0]
    def M_cel(self, t, tc, shake):
        # drawing on 3s, position on 1s along the arc
        cam = self.S.cam(0.0)
        P0 = r3d.xform_points(SD.s16_root(tc), np.array([[0, 0, 9.0]], np.float32))[0]
        P1 = r3d.xform_points(SD.s16_root(t), np.array([[0, 0, 9.0]], np.float32))[0]
        q0 = cam.project(P0[None])[0]; q1 = cam.project(P1[None])[0]
        s = (q0[2] / max(q1[2], 1e-3))
        return np.array([[s, 0, q1[0] - s * q0[0]], [0, s, q1[1] - s * q0[1]]], np.float32)
    def trail_points(self, t, cam):
        ts = np.arange(t - 6.0, t + 1e-6, 1 / 24.0)
        P = []
        for x in ts:
            M = SD.s16_root(x)
            P.append(r3d.xform_points(M, np.array([[0, -2.5, 3.0]], np.float32))[0])
        q = cam.project(np.array(P, np.float32))
        return q, len(ts)
    def fx_behind(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        lb = ctx.setdefault('lb', np.zeros((H, W, 3), np.float32))
        q, n = self.trail_points(t, ctx['cam'])
        births = np.arange(f - n + 1, f + 1)
        # perspective: the trail is wide where it passes near the camera, thin at the far robot
        sc = np.clip(230.0 / np.maximum(q[:, 2], 1.0), 0.1, 1.5)
        self.trail.draw(cv_, f, q[:, :2], births=births, light_buf=lb, scales=sc)
        # engine flames from the two bells, streaming back along the path (on 1s)
        cam = ctx['cam']
        M = SD.s16_root(t); M2 = SD.s16_root(t - 0.2)
        for fl, b in zip(self.flames, Engines.BELLS):
            P = r3d.xform_points(M, np.array([b], np.float32))[0]
            Pb = r3d.xform_points(M2, np.array([b], np.float32))[0]
            q0 = cam.project(P[None])[0]; q1 = cam.project(Pb[None])[0]
            d = q1[:2] - q0[:2]; nd = float(np.linalg.norm(d)) + 1e-6
            rad = cam.fpx * 1.0 / max(q0[2], 1.0)
            fl.draw(cv_, f, nozzle=(float(q0[0]), float(q0[1])), direction=(float(d[0] / nd), float(d[1] / nd)),
                    radius=rad * 0.9, length=rad * 7)
            fl.glow(lb, f, nozzle=(float(q0[0]), float(q0[1])), direction=(float(d[0] / nd), float(d[1] / nd)),
                    radius=rad * 0.9, length=rad * 7)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        if 'lb' in ctx:
            lb += ctx['lb']
        # far away the robot becomes a spark: an engine glint that grows as the figure shrinks
        cam = ctx['cam']
        P = r3d.xform_points(SD.s16_root(t), np.array([[0, -2.5, 4.0]], np.float32))[0]
        q = cam.project(P[None])[0]
        size = cam.fpx * 20.0 / max(q[2], 1.0)
        k = float(np.clip((140.0 - size) / 110.0, 0.0, 1.0))
        if k > 0:
            fx.glow(lb, (float(q[0]), float(q[1])), 40 + 60 * k, colour=(1.0, 0.95, 0.8), intensity=0.9 * k)
            Lc = np.zeros((H, W), np.float32)
            r = int(30 + 90 * k)
            cx, cy = int(q[0]), int(q[1])
            cv2.line(Lc, (cx - r, cy), (cx + r, cy), 1.0, 2, cv2.LINE_AA)
            cv2.line(Lc, (cx, cy - int(r * 0.7)), (cx, cy + int(r * 0.7)), 1.0, 2, cv2.LINE_AA)
            Lc = cv2.GaussianBlur(Lc, (0, 0), 1.2) * k
            lb += Lc[..., None] * np.array([1.0, 0.95, 0.85], np.float32)


class S16A(Base):
    """Tracking beside the climbing robot: it fills the frame; sky and clouds stream past."""
    ground_growth = False
    eye_glow = 1.0
    painting = 'S16A'
    fallback = ('S16', (0.0, 120.0), 1.7, 0)
    ground = False
    redraw_on_camera = True
    haze_auto = False
    haze = 0.04
    robot_depth = 0.45
    wind = 0.0
    light_az, light_el = 120, 22
    SPEED = 950.0                    # px/s of the painting's x at depth 1 (the wisps)
    TILT = 22.0                      # dutch angle: the painting's +x points up-right on screen
    SCROLL_K = {'sky': 0.18, 'cloud_bank': 0.55, 'wisps': 1.5}
    def anchor(self):
        return np.array([0.0, 0.0, 9.0], np.float32)
    def split_layers(self):
        if self.P is None or self.pname != 'S16A':
            return Base.split_layers(self)
        return ['sun_glow', 'sky', 'cloud_bank', 'wisps'], []
    def bg_layers(self, rgb, names, t, shake, opacity=None):
        if self.P is None or self.pname != 'S16A':
            return Base.bg_layers(self, rgb, names, t, shake, opacity)
        th = math.radians(self.TILT); sc = 1.45
        c, s_ = math.cos(th), math.sin(th)
        for L in self.P.layers:
            if L['name'] not in names:
                continue
            img = comp.load_rgba(os.path.join(self.P.folder, L['file']), u8=True)
            if L['name'] == 'sun_glow':
                lay = img.astype(np.float32) / 255.0
            else:
                x_off = (self.SPEED * self.SCROLL_K.get(L['name'], 1.0) * t + 700.0) % img.shape[1]
                # screen = C + sc * R * (p - (x_off + C'))  with C the frame centre and C' the painting window centre
                A = np.float32([[sc * c, sc * s_, 0], [-sc * s_, sc * c, 0]])
                pc = np.array([x_off + 960.0, 520.0], np.float32)
                A[:, 2] = np.array([960.0, 520.0], np.float32) - A[:, :2] @ pc
                lay = cv2.warpAffine(img, A, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255.0
            rgb = comp.over_straight(rgb, lay)
        return rgb
    def M_cel(self, t, tc, shake):
        return np.float32([[1, 0, 0], [0, 1, 0]])
    def setup(self):
        self.flames = [fx.EngineFlame(f'S16A_e{i}', ignite=-40, sputters=[]) for i in range(2)]
        # the trail head sits behind the robot here: a weak glow, or it glares over the body
        self.trail = fx.LightTrail('S16A_trail', width=70, life=200, mist=True, mist_size=0.9, light=(0.6, -0.8), mist_every=4,
                                   glow=0.3)
        d = (-0.93, 0.37)
        self.leaves = fx.LeafBurst('S16A_leaves', origin=(1000, 420), frame0=0, count=70, direction=d,
                                   spread=1.1, speed=(18, 34), size=(14, 28), origin_radius=260, wind=(-0.7, 0.28))
        self.leaves2 = fx.LeafBurst('S16A_leaves2', origin=(900, 500), frame0=30, count=50, direction=d,
                                    spread=1.1, speed=(18, 34), size=(14, 28), origin_radius=300, wind=(-0.7, 0.28))
        self.debris = fx.DebrisBurst('S16A_soil', origin=(980, 460), frame0=2, count=60,
                                     kinds={'clod': 0.3, 'crumb': 0.3, 'moss': 0.25, 'vine': 0.15}, size=(5, 16),
                                     direction=d, spread=0.9, speed=(16, 36), gravity=0.0, origin_radius=240)
    def _make_vines(self):
        import vines as VN, vineplan, anim, poses as PZ
        rig = SD.rig()
        vs = [v for v in vineplan.plan(rig, PZ.grounded(rig, PZ.KNEEL_DORMANT)) if v.root is None]
        cam = self.S.cam(0.0)
        wdir = -cam.r * 0.93 - cam.u * 0.37
        wdir = wdir / np.linalg.norm(wdir) * 26.0
        self.vineset = VN.VineSet(rig, vs, lambda t: anim.pose_at(self.shot, t), wind=lambda t: tuple(wdir))
    def fx_behind(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        fx.streak_lines(cv_, direction=(-0.93, 0.37), frame=f, n=26, length=(260, 760), width=(1.2, 3.5))
        cv_[..., 3] *= 0.35
        import anim
        pose = anim.pose_at(self.shot, t)
        lb = ctx.setdefault('lb', np.zeros((H, W, 3), np.float32))
        nz = Engines.nozzles(pose, ctx['cam'])
        # the trail of light and mist starts here: it streams away behind the engines
        c = np.mean([n[0] for n in nz], axis=0)
        d = np.array([-0.93, 0.37], np.float32)
        k = np.arange(0, 170)
        pts = (c[None, :] + d[None, :] * (k[:, None] * 14.0))[::-1].astype(np.float32)
        births = (f - k)[::-1]
        tr = fx.new_canvas(H, W)
        self.trail.draw(tr, f, pts, births=births, light_buf=lb)
        rgb = comp.over_straight(rgb, tr)
        for fl, (noz, dd, rad, z) in zip(self.flames, nz):
            fl.draw(cv_, f, nozzle=noz, direction=(-0.9, 0.42), radius=rad * 1.25, length=rad * 18)
        return comp.over_straight(rgb, cv_)
    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        self.debris.draw(cv_, f); self.leaves.draw(cv_, f); self.leaves2.draw(cv_, f)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        if 'lb' in ctx:
            lb += ctx['lb']


class S00(Base):
    """Establishing vista: sunrise over the misty forest; the gap in the canopy where mist rises."""
    painting = 'S00'
    ground = False
    vines = False
    fade_in = 1.5
    robot_depth = 0.5
    PAN = 240.0
    def cam2d(self, t, t_ref=None):
        u = t / 4.5
        return np.array([960.0, 520.0]), np.array([-self.PAN * (0.15 * u + 0.85 * ease(u)), 0.0]), 1.0
    def setup(self):
        self.flock = birds.circling(n=9, centre=(1050, 380), radius=(420, 90), frames=110, period=150, span=(7, 15), seed=11)
        self.motes = fx.Motes('S00_motes', (900, 250, 1900, 800), count=90)
    def sxy(self, x, y, depth, t):
        k = self.layer_k(depth)
        a, d, s_ = self.cam2d(t)
        return x + d[0] * k, y + d[1] * k
    def fx_mid(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        birds.draw_flock(cv_, self.flock.at(f) if hasattr(self.flock, 'at') else self.flock(f),
                         light=birds.Light(dir=(0.8, 0.5), depth=-0.5), style='silhouette')
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        sx, sy = self.sxy(1930.0, 300.0, 0.0, t)
        gx, gy = self.sxy(1250.0, 640.0, 0.55, t)
        ang = math.degrees(math.atan2(gy - sy, gx - sx))
        mask = fx.sunbeams(lb, src=(sx, sy), angles=[math.radians(a) for a in (ang - 2.2, ang, ang + 2.5)],
                           widths=[40, 90, 30], spread=0.02, intensity=0.2, frame=f, scale=0.5,
                           length=1.1 * math.hypot(gx - sx, gy - sy))
        if mask.shape != (H, W):
            mask = cv2.resize(mask.astype(np.float32), (W, H))
        self.motes.draw(lb, f, mask=np.clip(mask * 3, 0, 1))
        fx.glow(lb, (sx, sy), 380, colour=(1.0, 0.86, 0.6), intensity=0.35)


class S17(Base):
    """Ending: the empty clearing; leaves spiral through the beams; the bird returns; fade out."""
    painting = 'S17'
    fallback = ('S01', (0.0, 2900 - 1040), 1.0, 0)
    behind = ('sky', 'far', 'mist_far', 'mid', 'mist_mid')
    ground = False
    fade_out = (5.4, 7.5)
    grade_kw = dict(gain=(0.93, 0.9, 0.86), contrast=1.16)
    def setup(self):
        self.leaves = fx.LeafFall('S17_leaves', region=(300, -400, 1700, 1000), frame0=0, count=34, size=(14, 28),
                                  spiral=0.9, preroll=200, fall=(0.9, 1.6))
        self.motes = fx.Motes('S17_motes', (300, 0, 1700, 1000), count=220)
        self.track = birds.landing(x=1000, y=905, scale=112, facing=-1, t_flare=int(2.6 * 24), t_touch=int(3.1 * 24),
                                   t_hop=None, t_chirp=int(4.2 * 24), t_end=180)
        self.beam_mask = None
    def fx_front(self, rgb, f, t, ctx):
        cv_ = fx.new_canvas(H, W)
        if self.beam_mask is None:
            self.light_buf(np.zeros((H, W, 3), np.float32), f, t, ctx)
        bm = self.beam_mask
        self.leaves.draw(cv_, f, sunlit=(lambda x, y: float(bm[int(np.clip(y, 0, H - 1)), int(np.clip(x, 0, W - 1))]) if bm is not None else None))
        st = self.track.state(f)
        if st is not None:
            birds.draw_state(cv_, st, birds.Light(dir=(0.8, 0.5), depth=-0.4), palette_overrides=BIRD_PAL)
        return comp.over_straight(rgb, cv_)
    def light_buf(self, lb, f, t, ctx):
        if 'lb' in ctx:
            lb += ctx['lb']
        mask = fx.sunbeams(lb, src=(1500, -500), angles=[math.radians(a) for a in (110, 116, 121, 127)],
                           widths=[60, 120, 50, 70], spread=0.03, intensity=0.26, frame=f, scale=0.5)
        if mask.shape != (H, W):
            mask = cv2.resize(mask.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
        self.beam_mask = np.clip(mask * 3, 0, 1)
        self.motes.draw(lb, f, mask=self.beam_mask)
