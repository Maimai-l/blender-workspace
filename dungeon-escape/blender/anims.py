
# anims.py - procedural keyframe animation for the shared rig
import bpy, math
import dlib, chars

R = math.radians
LEG = 0.43

def merge(*ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            if k in out:
                out[k] = tuple(a + b for a, b in zip(out[k], v))
            else:
                out[k] = tuple(v)
    return out

def lerp_pose(a, b, t):
    keys = set(a) | set(b)
    out = {}
    for k in keys:
        va = a.get(k, (0, 0, 0)); vb = b.get(k, (0, 0, 0))
        out[k] = tuple(x + (y - x) * t for x, y in zip(va, vb))
    return out

def arm(side, fwd=0, out=0, twist=0, elbow=0, wrist=0, wtwist=0, wside=0):
    s = 1 if side == 'L' else -1
    return {"upperarm." + side: (-fwd, twist * s, -out * s), "forearm." + side: (-elbow, 0, 0), "hand." + side: (wrist, wtwist * s, wside * s)}

def leg(side, flex=0, out=0, knee=0, ankle=0, twist=0):
    s = 1 if side == 'L' else -1
    return {"thigh." + side: (-flex, twist * s, -out * s), "shin." + side: (knee, 0, 0), "foot." + side: (ankle, 0, 0)}

def torso(bend=0, side=0, twist=0):
    return {"spine": (bend * 0.5, twist * 0.5, side * 0.5), "chest": (bend * 0.5, twist * 0.5, side * 0.5)}

def headp(nod=0, turn=0, tilt=0):
    return {"neck": (nod * 0.4, turn * 0.4, tilt * 0.4), "head": (nod * 0.6, turn * 0.6, tilt * 0.6)}

def hipsp(pitch=0, yaw=0, roll=0, up=0, fwd=0, left=0):
    return {"hips": (pitch, yaw, roll), "@hips": (left, up, fwd)}

def capep(a=0, b=0, side=0):
    return {"cape1": (a, 0, side), "cape2": (b, 0, side * 0.5)}

def jawp(o=0):
    return {"jaw": (o, 0, 0)}

def ext(flex, knee):
    return LEG * math.cos(R(flex)) + LEG * math.cos(R(flex - knee))

def crouch(k, extra_flex=0):
    return merge(leg('L', flex=k / 2 + extra_flex, knee=k, ankle=-k / 2 - extra_flex), leg('R', flex=k / 2, knee=k, ankle=-k / 2),
                 hipsp(up=ext(k / 2, k) - 2 * LEG))

def apply_pose(rig, pose):
    for pb in rig.pose.bones:
        r = pose.get(pb.name, (0, 0, 0))
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (R(r[0]), R(r[1]), R(r[2]))
        pb.location = pose.get("@" + pb.name, (0, 0, 0))
        pb.scale = (1, 1, 1)

def make_action(rig, name, keys):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if rig.animation_data is None:
        rig.animation_data_create()
    rig.animation_data.action = act
    for f, pose in keys:
        apply_pose(rig, pose)
        for pb in rig.pose.bones:
            pb.keyframe_insert("rotation_euler", frame=f)
            pb.keyframe_insert("location", frame=f)
    return act

def cycle(rig, name, T, fn):
    return make_action(rig, name, [(f, fn((f % T) / T)) for f in range(0, T + 1)])

# ------------------------------------------------------------------ knight
def k_stance(t=0.0):
    b = math.sin(2 * math.pi * t)
    return merge(
        leg('L', flex=8, out=5, knee=14, ankle=-6),
        leg('R', flex=3, out=5, knee=12, ankle=-9, twist=-6),
        hipsp(up=-0.012 - 0.004 * b, roll=1.0 * b, left=0.006 * b),
        torso(bend=5 + 1.5 * b, twist=-4),
        headp(nod=-3 - 1.0 * b, turn=4),
        arm('R', fwd=14, out=14, elbow=12 + 2 * b, wrist=46, wtwist=-8, twist=-10),
        arm('L', fwd=10, out=14, elbow=24 + 3 * b, wrist=-5),
        capep(a=3 + 2 * math.sin(2 * math.pi * t + 1.2), b=2 + 1.5 * math.sin(2 * math.pi * t + 2.0)),
    )

def k_walk(u):
    pL = 2 * math.pi * u
    def lg(ph):
        flex = 5 + 24 * math.sin(ph)
        knee = 6 + 55 * max(0.0, math.cos(ph - 0.25)) ** 2
        stance = math.cos(ph) < 0
        ankle = (flex - knee) + (10 * max(0.0, -math.sin(ph)) if stance else -6 * max(0.0, math.sin(ph)))
        return flex, knee, ankle
    fL, kL, aL = lg(pL); fR, kR, aR = lg(pL + math.pi)
    up = max(ext(fL, kL), ext(fR, kR)) - 2 * LEG + 0.01
    s = math.sin(pL)
    return merge(
        leg('L', flex=fL, knee=kL, ankle=aL, out=3), leg('R', flex=fR, knee=kR, ankle=aR, out=3),
        hipsp(up=up, yaw=-5 * s, roll=1.5 * math.sin(2 * pL)),
        torso(bend=6, twist=10 * s),
        headp(nod=-4, turn=-4 * s),
        arm('L', fwd=6 - 22 * s, out=10, elbow=22 - 8 * s),
        arm('R', fwd=14 + 10 * s, out=14, elbow=16, wrist=50, wtwist=-8, twist=-10),
        capep(a=7 + 4 * math.sin(2 * pL), b=5 + 3 * math.sin(2 * pL + 1)),
    )

def k_run(u):
    pL = 2 * math.pi * u
    def lg(ph):
        flex = 14 + 40 * math.sin(ph)
        knee = 16 + 95 * max(0.0, math.cos(ph - 0.35)) ** 1.6
        ankle = (flex - knee) * 0.85 + 18 * max(0.0, -math.sin(ph)) - 8 * max(0.0, math.sin(ph))
        return flex, knee, ankle
    fL, kL, aL = lg(pL); fR, kR, aR = lg(pL + math.pi)
    up = max(ext(fL, kL), ext(fR, kR)) - 2 * LEG + 0.03 * max(0.0, math.cos(2 * pL + 0.6))
    s = math.sin(pL)
    return merge(
        leg('L', flex=fL, knee=kL, ankle=aL, out=2), leg('R', flex=fR, knee=kR, ankle=aR, out=2),
        hipsp(up=up, yaw=-8 * s),
        torso(bend=16, twist=16 * s),
        headp(nod=-12, turn=-6 * s),
        arm('L', fwd=12 - 42 * s, out=8, elbow=88 + 12 * s),
        arm('R', fwd=10 + 25 * s, out=14, elbow=35, wrist=15 + 10 * s, wtwist=180, twist=-12),
        capep(a=32 + 7 * math.sin(2 * pL), b=20 + 9 * math.sin(2 * pL + 1.1)),
    )

def k_fall(u):
    s = math.sin(2 * math.pi * u)
    return merge(
        leg('L', flex=30 + 4 * s, knee=42 + 5 * s, ankle=-10), leg('R', flex=12 - 4 * s, knee=30 - 5 * s, ankle=-5),
        torso(bend=6), headp(nod=-6),
        arm('L', fwd=30, out=55 + 5 * s, elbow=35), arm('R', fwd=30, out=45 - 5 * s, elbow=45, wrist=40),
        capep(a=55 + 6 * math.sin(4 * math.pi * u), b=35 + 8 * math.sin(4 * math.pi * u + 1)),
    )

def knight_actions(rig):
    st = k_stance(0.0)
    cycle(rig, "Idle", 60, k_stance)
    cycle(rig, "Walk", 32, k_walk)
    cycle(rig, "Run", 18, k_run)
    cycle(rig, "Fall", 20, k_fall)
    make_action(rig, "JumpUp", [
        (0, merge(leg('L', flex=10, knee=10), leg('R', flex=-5, knee=5), torso(bend=10), arm('L', fwd=-30, elbow=30), arm('R', fwd=-10, elbow=40, wrist=40), capep(10, 5))),
        (4, merge(leg('L', flex=55, knee=85, ankle=-20), leg('R', flex=35, knee=70, ankle=-25), torso(bend=12), headp(nod=-5),
                  arm('L', fwd=60, out=35, elbow=50), arm('R', fwd=45, out=30, elbow=50, wrist=40), capep(35, 25))),
        (10, k_fall(0.0)),
    ])
    land0 = merge(crouch(60), torso(bend=22), arm('L', fwd=25, out=25, elbow=40), arm('R', fwd=25, out=20, elbow=45, wrist=85), capep(25, 15), hipsp(up=-0.03))
    make_action(rig, "Land", [(0, land0), (3, merge(crouch(72), torso(bend=26), arm('L', fwd=30, out=30, elbow=45), arm('R', fwd=28, out=22, elbow=48, wrist=88), capep(10, 8), hipsp(up=-0.04))), (10, st)])
    # attack 1: horizontal slash right -> left
    a1w = merge(leg('L', flex=22, knee=18, ankle=-4, out=6), leg('R', flex=-12, knee=12, out=6, twist=-10), hipsp(up=-0.04, yaw=-20),
                torso(bend=6, twist=-30), headp(turn=25, nod=-4), arm('R', fwd=35, out=75, elbow=75, wrist=70, wtwist=-90, twist=-30),
                arm('L', fwd=35, out=10, elbow=55), capep(8, 5, side=-8))
    a1s = merge(leg('L', flex=25, knee=22, out=6), leg('R', flex=-15, knee=10, out=6), hipsp(up=-0.05, yaw=5), torso(bend=10, twist=15),
                arm('R', fwd=85, out=25, elbow=10, wrist=75, wtwist=-90), arm('L', fwd=20, out=25, elbow=40), capep(12, 8, side=4))
    a1f = merge(leg('L', flex=25, knee=22, out=6), leg('R', flex=-15, knee=10, out=6), hipsp(up=-0.05, yaw=18), torso(bend=10, twist=40), headp(turn=-12),
                arm('R', fwd=75, out=-40, elbow=25, wrist=70, wtwist=-90), arm('L', fwd=5, out=35, elbow=35), capep(10, 8, side=10))
    make_action(rig, "Attack1", [(0, st), (4, a1w), (7, a1s), (9, a1f), (13, lerp_pose(a1f, st, 0.3)), (20, st)])
    a2w = merge(leg('L', flex=20, knee=18, out=6), leg('R', flex=-10, knee=12, out=6), hipsp(up=-0.04, yaw=15), torso(bend=6, twist=32), headp(turn=-10),
                arm('R', fwd=60, out=-45, elbow=95, wrist=65, wtwist=80), arm('L', fwd=10, out=30, elbow=40), capep(8, 5, side=8))
    a2s = merge(leg('L', flex=22, knee=20, out=6), leg('R', flex=-14, knee=10, out=6), hipsp(up=-0.05, yaw=-5), torso(bend=10, twist=-10),
                arm('R', fwd=85, out=20, elbow=10, wrist=70, wtwist=80), arm('L', fwd=15, out=30, elbow=40), capep(12, 8))
    a2f = merge(leg('L', flex=22, knee=20, out=6), leg('R', flex=-14, knee=10, out=6), hipsp(up=-0.05, yaw=-18), torso(bend=10, twist=-38), headp(turn=15),
                arm('R', fwd=55, out=80, elbow=20, wrist=65, wtwist=80), arm('L', fwd=30, out=5, elbow=50), capep(10, 8, side=-10))
    make_action(rig, "Attack2", [(0, st), (4, a2w), (7, a2s), (9, a2f), (13, lerp_pose(a2f, st, 0.3)), (20, st)])
    a3w = merge(leg('L', flex=15, knee=10), leg('R', flex=-5, knee=8), hipsp(up=0.01), torso(bend=-14, twist=-8), headp(nod=-10),
                arm('R', fwd=165, out=12, elbow=75, wrist=40), arm('L', fwd=155, out=-8, elbow=70, wrist=30), capep(-5, -3))
    a3m = merge(leg('L', flex=22, knee=20), leg('R', flex=-5, knee=12), hipsp(up=-0.04), torso(bend=15),
                arm('R', fwd=100, out=8, elbow=20, wrist=60), arm('L', fwd=95, out=-15, elbow=30, wrist=30), capep(5, 3))
    a3i = merge(crouch(50, 15), hipsp(up=-0.06), torso(bend=38), headp(nod=-15),
                arm('R', fwd=48, out=5, elbow=8, wrist=75), arm('L', fwd=45, out=-20, elbow=25, wrist=40), capep(20, 15))
    a3h = merge(crouch(56, 15), hipsp(up=-0.07), torso(bend=40), headp(nod=-14),
                arm('R', fwd=44, out=5, elbow=10, wrist=78), arm('L', fwd=42, out=-20, elbow=28, wrist=40), capep(15, 18))
    make_action(rig, "Attack3", [(0, st), (6, a3w), (9, a3m), (11, a3i), (15, a3h), (26, st)])
    d0 = merge(crouch(30), torso(bend=25), arm('L', fwd=30, elbow=40), arm('R', fwd=30, elbow=45, wrist=90))
    def rootroll(th, c=0.5):
        r = math.radians(th)
        return {"root": (th, 0, 0), "@root": (0, c * (1 - math.cos(r)), -c * math.sin(r))}
    tuck = merge(leg('L', flex=100, knee=140, ankle=-40), leg('R', flex=95, knee=135, ankle=-40), hipsp(up=-0.42),
                 torso(bend=60), headp(nod=50), arm('L', fwd=60, out=10, elbow=120), arm('R', fwd=50, out=12, elbow=100, wrist=95), capep(20, 25))
    unfold = merge(crouch(70), torso(bend=30), headp(nod=10), arm('L', fwd=30, out=20, elbow=60), arm('R', fwd=30, out=20, elbow=60, wrist=95), capep(25, 20))
    make_action(rig, "Dodge", [(0, d0), (3, merge(lerp_pose(d0, tuck, 0.7), rootroll(55))), (6, merge(tuck, rootroll(150))), (9, merge(tuck, rootroll(240))),
                               (12, merge(lerp_pose(tuck, unfold, 0.4), rootroll(320))), (15, merge(unfold, rootroll(360))), (18, merge(st, rootroll(360)))])
    hit = merge(leg('L', flex=0, knee=12), leg('R', flex=14, knee=20), hipsp(fwd=-0.05, up=-0.02), torso(bend=-16, twist=12), headp(nod=-18, turn=-10),
                arm('R', fwd=10, out=30, elbow=30, wrist=30), arm('L', fwd=15, out=35, elbow=25), capep(12, 8))
    make_action(rig, "Hit", [(0, st), (3, hit), (12, st)])
    de1 = merge(leg('L', flex=-8, knee=8), leg('R', flex=20, knee=25), hipsp(fwd=-0.08), torso(bend=-22, twist=10), headp(nod=-25),
                arm('R', fwd=30, out=40, elbow=30, wrist=30), arm('L', fwd=30, out=45, elbow=20), capep(10, 6))
    de2 = merge(crouch(110), torso(bend=25), headp(nod=20), arm('R', fwd=10, out=15, elbow=20, wrist=40), arm('L', fwd=5, out=10, elbow=15), capep(5, 5))
    de3 = merge(leg('L', flex=-5, knee=10, ankle=20), leg('R', flex=0, knee=15, ankle=25), hipsp(pitch=82, up=-0.82, fwd=0.05), torso(bend=5),
                headp(turn=60, nod=-20, tilt=10), arm('L', fwd=140, out=30, elbow=20), arm('R', fwd=100, out=40, elbow=30, wrist=30), capep(-20, -10))
    de4 = merge(de3, hipsp(pitch=6, up=-0.02))
    de5 = merge(de3, hipsp(pitch=8, up=-0.02), arm('L', fwd=-10, elbow=-5), headp(nod=5))
    make_action(rig, "Death", [(0, st), (6, de1), (14, de2), (24, de3), (28, de4), (40, de5)])
    vic = lambda b: merge(leg('L', flex=10, out=8, knee=10), leg('R', flex=-4, out=8, knee=6), torso(bend=-8 + b, twist=-6), headp(nod=-14),
                          arm('R', fwd=165, out=20, elbow=8 + b, wrist=85), arm('L', fwd=15, out=30, elbow=95 + 2 * b, wrist=10), capep(4 + b, 3))
    make_action(rig, "Victory", [(0, st), (10, vic(0)), (25, vic(2)), (40, vic(0))])
    ia = merge(leg('L', flex=22, knee=16), leg('R', flex=-4, knee=10), torso(bend=12, twist=-10), headp(nod=10),
               arm('L', fwd=75, out=-5, elbow=35, wrist=-10), arm('R', fwd=20, out=14, elbow=40, wrist=70))
    make_action(rig, "Interact", [(0, st), (8, ia), (12, merge(ia, arm('L', wtwist=60))), (18, merge(ia, arm('L', wtwist=60))), (24, st)])

# ------------------------------------------------------------------ skeleton
def s_base(t=0.0, sway=1.0):
    b = math.sin(2 * math.pi * t)
    return merge(
        leg('L', flex=14, out=7, knee=24, ankle=-10), leg('R', flex=6, out=7, knee=20, ankle=-12, twist=-8),
        hipsp(up=-0.03, roll=1.5 * b * sway),
        torso(bend=20 + 2 * b * sway, twist=-6, side=2 * b * sway),
        headp(nod=-14 - 2 * b * sway, turn=8 * math.sin(2 * math.pi * t) * sway, tilt=5),
        arm('L', fwd=35, out=12, elbow=75, twist=20),
        arm('R', fwd=18, out=16, elbow=30 + 3 * b * sway, wrist=60, twist=-10),
        jawp(4 + 6 * max(0.0, math.sin(2 * math.pi * t * 3)) * sway),
    )

def s_walk(u):
    pL = 2 * math.pi * u
    def lg(ph, stiff):
        flex = 6 + 22 * math.sin(ph)
        knee = 14 + (50 - stiff) * max(0.0, math.cos(ph - 0.25)) ** 2
        ankle = (flex - knee) * 0.9
        return flex, knee, ankle
    fL, kL, aL = lg(pL, 0); fR, kR, aR = lg(pL + math.pi, 18)
    up = max(ext(fL, kL), ext(fR, kR)) - 2 * LEG
    s = math.sin(pL)
    return merge(
        leg('L', flex=fL, knee=kL, ankle=aL, out=6), leg('R', flex=fR, knee=kR, ankle=aR, out=6),
        hipsp(up=up, yaw=-7 * s, roll=3 * s),
        torso(bend=22, twist=10 * s, side=-5 * s),
        headp(nod=-14, turn=-6 * s, tilt=5 + 4 * s),
        arm('L', fwd=35, out=12, elbow=72, twist=20),
        arm('R', fwd=14 + 16 * s, out=18, elbow=30, wrist=62, twist=-10),
        jawp(4 + 4 * max(0.0, math.sin(4 * pL))),
    )

def s_run(u):
    pL = 2 * math.pi * u
    def lg(ph):
        flex = 12 + 34 * math.sin(ph)
        knee = 20 + 75 * max(0.0, math.cos(ph - 0.35)) ** 1.6
        ankle = (flex - knee) * 0.85 + 12 * max(0.0, -math.sin(ph))
        return flex, knee, ankle
    fL, kL, aL = lg(pL); fR, kR, aR = lg(pL + math.pi)
    up = max(ext(fL, kL), ext(fR, kR)) - 2 * LEG + 0.02 * max(0.0, math.cos(2 * pL + 0.6))
    s = math.sin(pL)
    return merge(
        leg('L', flex=fL, knee=kL, ankle=aL, out=5), leg('R', flex=fR, knee=kR, ankle=aR, out=5),
        hipsp(up=up, yaw=-8 * s),
        torso(bend=30, twist=14 * s),
        headp(nod=-24, turn=-5 * s),
        arm('L', fwd=40, out=10, elbow=80, twist=20),
        arm('R', fwd=-5 + 28 * s, out=18, elbow=40, wrist=70, twist=-10),
        jawp(8 + 6 * max(0.0, math.sin(4 * pL))),
    )

def skeleton_actions(rig):
    b = s_base(0.0)
    cycle(rig, "Idle", 48, s_base)
    cycle(rig, "Walk", 34, s_walk)
    cycle(rig, "Run", 22, s_run)
    aw = merge(leg('L', flex=18, knee=20, out=6), leg('R', flex=-8, knee=15, out=6), torso(bend=-6, twist=-22), headp(nod=-20, turn=10), jawp(25),
               arm('R', fwd=160, out=28, elbow=85, wrist=30), arm('L', fwd=55, out=5, elbow=70, twist=20))
    aw2 = merge(aw, torso(bend=-3), arm('R', fwd=6), jawp(4))
    asx = merge(leg('L', flex=30, knee=35, out=6), leg('R', flex=-10, knee=15, out=6), hipsp(up=-0.08), torso(bend=38, twist=14), headp(nod=10), jawp(10),
                arm('R', fwd=45, out=8, elbow=8, wrist=75), arm('L', fwd=40, out=20, elbow=60, twist=20))
    ah = merge(asx, hipsp(up=-0.01), torso(bend=3), arm('R', fwd=-4))
    make_action(rig, "Attack", [(0, b), (8, aw), (12, aw2), (15, asx), (19, ah), (36, b)])
    ht = merge(b, torso(bend=-28, twist=-18), headp(nod=-22, tilt=12), jawp(25), arm('R', out=25, fwd=-10), arm('L', out=25, fwd=-15), hipsp(fwd=-0.06))
    make_action(rig, "Hit", [(0, b), (3, ht), (12, b)])
    d1 = merge(b, torso(bend=-40), headp(nod=-30), jawp(35), arm('R', out=30), arm('L', out=30))
    d2 = merge(crouch(120), torso(bend=50), headp(nod=40), jawp(20), arm('R', fwd=5, out=15, elbow=20, wrist=30), arm('L', fwd=5, out=15, elbow=20))
    d3 = merge(leg('L', flex=70, out=30, knee=140, ankle=-20), leg('R', flex=60, out=35, knee=135, ankle=-25), hipsp(pitch=25, up=-0.78), torso(bend=75, side=10),
               headp(nod=60, tilt=20), jawp(30), arm('R', fwd=30, out=60, elbow=40, wrist=30), arm('L', fwd=20, out=70, elbow=30))
    d4 = merge(d3, hipsp(up=-0.04, pitch=5), torso(bend=10), headp(tilt=10), arm('R', out=10), arm('L', out=10))
    make_action(rig, "Death", [(0, b), (4, d1), (12, d2), (20, d3), (30, d4)])
    r1 = merge(crouch(115), torso(bend=45), headp(nod=25), jawp(15), arm('R', fwd=20, out=20, elbow=40, wrist=30), arm('L', fwd=40, out=10, elbow=70))
    r2 = merge(crouch(60), torso(bend=30), headp(nod=-5), jawp(20), arm('R', fwd=20, out=20, elbow=35, wrist=35), arm('L', fwd=40, out=12, elbow=72))
    make_action(rig, "Rise", [(0, d4), (14, r1), (26, r2), (40, b)])

# ------------------------------------------------------------------ export
def build_character(kind):
    dlib.reset()
    rig = chars.build_rig("Rig")
    if kind == "Knight":
        body = chars.knight_mesh("Knight_Body")
    elif kind == "Skeleton":
        body = chars.skeleton_mesh("Skeleton_Body")
    else:
        body = chars.skeleton_mesh("Warden_Body", warden=True)
    chars.attach(body, rig)
    rig.animation_data_create()
    if kind == "Knight":
        knight_actions(rig)
    else:
        skeleton_actions(rig)
    rig.animation_data.action = None
    apply_pose(rig, {})
    return rig, body

def export_character(kind):
    rig, body = build_character(kind)
    dlib.export_rig([rig, body], dlib.MODELS + "/Characters/" + kind + ".fbx")
    dlib.save_blend(kind.lower())
    return [a.name for a in bpy.data.actions]
