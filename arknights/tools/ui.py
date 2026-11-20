#!/usr/bin/env python3
"""ui.py - look at and tap the LDPlayer screen (instance 0, 1600x900) through exec, for game UI work MAA cannot do.

    python3 -I ui.py shot [name]        screenshot -> $UI_OUT/<name>.jpg (default ~/.cache/arknights-ui) (960x540; prints the path)
    python3 -I ui.py ocr [min_score]    text + coordinates on screen (agent-ocr), one "x,y  text" line each
    python3 -I ui.py tap X Y            tap at screenshot coordinates (960x540 space, scaled to 1600x900)
    python3 -I ui.py swipe X1 Y1 X2 Y2 [ms]
    python3 -I ui.py back               Android back key
Recording a uiflow flow (see .claude/skills/arknights-ui-flow/SKILL.md):
    python3 -I ui.py rec FLOW STEP [--tap-text TEXT | --tap X Y LABEL | --back]
                                        OCR the screen, save it as arknights/flows/FLOW/NN_STEP.json, then act
    python3 -I ui.py gen FLOW           draft SCREENS / ALLOW / run() from the recording
    python3 -I ui.py check FLOW MODULE  offline: does MODULE (a flow file) recognise every recorded screen, and
                                        would it allow every recorded tap?
Coordinates given here are in the 960x540 screenshot; the device is 1600x900 (x 5/3)."""
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))  # shared <repo>/tools
import execc  # noqa: E402
import pcx  # noqa: E402

ADB = '/d/leidian/LDPlayer9/adb.exe -s emulator-5554'
PY = '"/d/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe"'
PYLIB = 'PYTHONPATH="D:/Blender/Projects/awakening2/pylib"'
OUT = os.environ.get('UI_OUT') or os.path.join(os.path.expanduser('~'), '.cache', 'arknights-ui')   # screenshots land here
K = 1600 / 960


def shot(name='screen'):
    pcx.bash(f'{ADB} exec-out screencap -p > /d/Projects/maa-cli/state/ui.png && {PYLIB} {PY} -c "import cv2; '
             f"im=cv2.imread(r'D:\\Projects\\maa-cli\\state\\ui.png'); "
             f"cv2.imwrite(r'D:\\Projects\\maa-cli\\state\\ui.jpg', cv2.resize(im,(960,540),interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])\"")
    r = execc.call('Read', {'file_path': 'D:\\Projects\\maa-cli\\state\\ui.jpg'})
    j = json.loads(r['result']['content'][0]['text'])
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + '.jpg')
    open(p, 'wb').write(base64.b64decode(j['file']['base64']))
    return p


def ocr(min_score=0.5):
    """Text + coordinates of the current screen (agent-ocr on the PC, port 8767), in 960x540 screenshot space.
    A pseudo accessibility tree: one line per text item, `x,y  text`. Starts the OCR server if needed."""
    out = pcx.bash(f'{ADB} exec-out screencap -p > /d/Projects/maa-cli/state/ui.png && AGENT_OCR_PORT=8767 '
                   f'PYTHONIOENCODING=utf-8 /d/Projects/agent-ocr/.venv/Scripts/python.exe /d/Projects/agent-ocr/ocr.py '
                   f'--image D:/Projects/maa-cli/state/ui.png --min-score {min_score} --format text')
    lines = []
    for ln in out.splitlines():
        p = ln.split('\t')
        if len(p) >= 3 and p[1].startswith('['):
            x, y = (int(v) for v in p[1].strip('[]').split(','))
            lines.append(f'{round(x / K):4d},{round(y / K):4d}  {p[2]}')
    return '\n'.join(lines)


def tap(x, y):
    return pcx.bash(f'{ADB} shell input tap {round(float(x) * K)} {round(float(y) * K)} && echo ok')


def swipe(x1, y1, x2, y2, ms=400):
    return pcx.bash(f'{ADB} shell input swipe {round(float(x1) * K)} {round(float(y1) * K)} {round(float(x2) * K)} {round(float(y2) * K)} {int(ms)} && echo ok')


FLOWS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'flows')


def ocr_items(min_score=0.5):
    """[(text, x, y)] of the screen, 960x540 space, without account identifiers (the home screen's nickname and ID
    block, and any run of 6+ digits), so recordings can live in the repo."""
    out = []
    for ln in ocr(min_score).splitlines():
        m = re.match(r'\s*(-?\d+),\s*(-?\d+)  (.*)', ln)
        if not m:
            continue
        x, y, t = int(m.group(1)), int(m.group(2)), m.group(3)
        if re.search(r'\d{6,}|ID[:：]', t) or (x < 300 and 265 < y < 335):
            continue
        out.append((t, x, y))
    return out


def rec(flow, step, args):
    d = os.path.join(FLOWS, flow)
    os.makedirs(d, exist_ok=True)
    n = len([f for f in os.listdir(d) if f.endswith('.json')]) + 1
    items = ocr_items()
    act = {'type': 'none'}
    if args[:1] == ['--tap-text']:
        hit = [(x, y) for t, x, y in items if t.replace(' ', '') == args[1].replace(' ', '')]
        if not hit:
            raise SystemExit('text %r not on screen' % args[1])
        act = {'type': 'tap', 'label': args[1], 'x': hit[0][0], 'y': hit[0][1]}
    elif args[:1] == ['--tap']:
        act = {'type': 'tap', 'label': args[3] if len(args) > 3 else 'point', 'x': int(args[1]), 'y': int(args[2])}
    elif args[:1] == ['--back']:
        act = {'type': 'back'}
    path = os.path.join(d, '%02d_%s.json' % (n, step))
    json.dump({'step': step, 'items': items, 'action': act}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if act['type'] == 'tap':
        tap(act['x'], act['y'])
    elif act['type'] == 'back':
        pcx.bash(f'{ADB} shell input keyevent 4 && echo ok')
    return path, act


def load(flow):
    d = os.path.join(FLOWS, flow)
    return [json.load(open(os.path.join(d, f), encoding='utf-8')) for f in sorted(os.listdir(d)) if f.endswith('.json')]


def gen(flow):
    """Draft SCREENS (texts on that screen and on no other recorded screen, no digits, longest first, 4 at most),
    ALLOW (a box around each recorded tap) and run() for a new flow file. Review it before use."""
    recs = load(flow)
    by = {}
    for r in recs:
        by.setdefault(r['step'], []).append(r)
    texts = {k: {t for r in v for t, _, _ in r['items']} for k, v in by.items()}
    out = ['SCREENS = {']
    for k, ts in texts.items():
        if k == 'home':
            continue
        others = set().union(*(v for kk, v in texts.items() if kk != k)) if len(texts) > 1 else set()
        # stable texts: present in every recording of this screen, no digits, not on other screens
        common = set.intersection(*({t for t, _, _ in r['items']} for r in by[k]))
        cand = [t for t in common if not re.search(r'\d', t) and len(t.replace(' ', '')) >= 2 and t not in others]
        cjk = [t for t in cand if re.search(r'[\u4e00-\u9fff]', t)]    # Chinese UI text OCRs reliably; the
        sig = sorted(cjk or cand, key=lambda t: -len(t))[:4]           # decorative Latin often does not
        out.append('    %r: %r,' % (k, [t.replace(' ', '') for t in sig]))
    out += ['}', 'ALLOW = {']
    for r in recs:
        a = r['action']
        if a['type'] == 'tap':
            w = max(30, 9 * len(a['label']) // 2 + 12)
            out.append('    (%r, %r): (%d, %d, %d, %d),' % (r['step'], a['label'], a['x'] - w, a['y'] - 22, a['x'] + w, a['y'] + 22))
    out += ['}', '', '', 'def run(f, dry):']
    for r in recs:
        a = r['action']
        out.append("    items = f.expect(%r)" % r['step'])
        if a['type'] == 'tap' and any(t.replace(' ', '') == a['label'] for t, _, _ in r['items']):
            out.append("    f.tap_text(items, %r, %r)   # recorded at (%d, %d)" % (r['step'], a['label'], a['x'], a['y']))
        elif a['type'] == 'tap':
            out.append("    f.tap_point(%d, %d, %r, %r)   # recorded point: derive it from a text if it can move"
                       % (a['x'], a['y'], r['step'], a['label']))
        elif a['type'] == 'back':
            out.append('    f.back()')
    out.append("    return 'done'")
    return '\n'.join(out)


def check(flow, module):
    """Offline replay of a recording against a flow file: screen recognition, forbidden words, taps vs ALLOW."""
    import importlib.util
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location('flowmod', module)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python3 -I does not add the script's folder
    import uiflow
    screens = dict(m.SCREENS)
    screens.setdefault('home', uiflow.HOME)
    bad = 0
    for i, r in enumerate(load(flow), 1):
        items = [(t, (x, y)) for t, x, y in r['items']]
        got = uiflow.screen_of(items, screens)
        forb = uiflow.forbidden_in(items) if got != 'home' else []
        a = r['action']
        ok_tap = a['type'] != 'tap' or uiflow.tap_allowed(a['x'], a['y'], m.ALLOW, r['step'], a['label'])
        good = got == r['step'] and not forb and ok_tap
        bad += not good
        print('%s %02d %-14s seen as %-14s forbidden %s tap %s' % ('ok  ' if good else 'FAIL', i, r['step'], got, forb or '-',
              'n/a' if a['type'] != 'tap' else ('allowed' if ok_tap else 'REFUSED')))
    return bad


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'shot':
        print(shot(a[1] if len(a) > 1 else 'screen'))
    elif a[0] == 'ocr':
        print(ocr(*(float(v) for v in a[1:2])))
    elif a[0] == 'tap':
        print(tap(a[1], a[2]))
    elif a[0] == 'swipe':
        print(swipe(*a[1:5], *(a[5:6] or [400])))
    elif a[0] == 'back':
        print(pcx.bash(f'{ADB} shell input keyevent 4 && echo ok'))
    elif a[0] == 'rec':
        print(*rec(a[1], a[2], a[3:]))
    elif a[0] == 'gen':
        print(gen(a[1]))
    elif a[0] == 'check':
        sys.exit(1 if check(a[1], a[2]) else 0)
