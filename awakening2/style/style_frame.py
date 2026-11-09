"""Style frame: S01's final framing at full quality (BG + robot + atmosphere + photography)."""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
for p in ('engine', 'robot', 'shots'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import numpy as np, cv2
import build, r3d, cel, comp, look
import shotdefs as SD, anim

def main(out='style/style_S01.png', az=118, el=38):
    t0 = time.time()
    rig, style = build.make()
    SD._RIG = rig
    shot = SD.SHOTS[0]
    t = 7.9
    cam = SD.camera(shot, t)
    pose = anim.pose_at(shot, t)
    L = comp.light_from_screen(cam, az, el)
    P = comp.Painting(os.path.join(HERE, '..', 'bg', 'S01'))
    x0, y0 = 0.0, P.size[1] - comp.H
    layers = {l['name']: P.layer(l['name']) for l in P.layers}
    def win(name):
        L_, img = layers[name]
        return P.window(L_, img, x0, y0)
    rgb = np.zeros((comp.H, comp.W, 3), np.float32)
    for name in ('sky', 'far', 'mist_far', 'mid', 'mist_mid'):
        rgb = comp.over_straight(rgb, win(name))
    # robot + its passes
    st = dict(style); st.update(light=L, ss=2, seed=11, sky_dir=(0.0, 0.3, 1.0))
    rgba, ps = cel.render(rig, pose, cam, st, return_passes=True)
    # ground shadow (hard cel shape) on the clearing floor
    sc, _ = rig.scene(pose)
    m = ps['mask']
    Pw = ps['wpos'][m]
    sm = r3d.ShadowMap(sc, L, np.median(Pw, 0), float(np.percentile(np.abs(Pw - np.median(Pw, 0)), 99.5)) * 1.3 + 6, 2048)
    gsh = comp.ground_shadow(cam, sm).astype(np.float32)
    gsh = cv2.GaussianBlur(gsh, (0, 0), 1.0)
    shade = np.array([0.42, 0.47, 0.62], np.float32)
    rgb = rgb * (1 - 0.5 * gsh[..., None]) + rgb * shade * 0.5 * gsh[..., None]
    a = rgba[..., 3]
    robot = rgba[..., :3]
    # aerial perspective toward the mist behind the robot
    mist = cv2.GaussianBlur(rgb, (0, 0), 25)
    haze = 0.10
    robot = robot * (1 - haze) + mist * a[..., None] * haze
    robot = comp.light_wrap(robot, a, rgb, radius=16, strength=0.5)
    rgb = robot + rgb * (1 - a[..., None])
    # in front of the robot
    for name, op in (('beams', 1.0), ('near', 1.0), ('fg', 1.0)):
        lay = win(name)
        if layers[name][0].get('blend') in ('screen', 'add'):
            k = lay[..., 3:4] * op
            rgb = 1 - (1 - rgb) * (1 - lay[..., :3] * k)
        else:
            rgb = comp.over_straight(rgb, lay, op)
    rgb = comp.finish(rgb, 0)
    cv2.imwrite(os.path.join(HERE, '..', out), comp.to_u8(rgb)[..., ::-1])
    print('style frame', time.time() - t0)

if __name__ == '__main__':
    main(*sys.argv[1:2])
