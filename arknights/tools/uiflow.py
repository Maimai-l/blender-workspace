"""uiflow.py - the guarded engine for game UI flows that MAA cannot do (runs ON THE PC with the agent-ocr venv:
D:\\Projects\\agent-ocr\\.venv\\Scripts\\python.exe). A flow is a small Python file (see tower_sweep.py) that
declares its screens and the only places it may tap, and walks them with the helpers here.

Every flow gets, without writing anything for it:
  - screen check: each step names the screen it expects; ALL of that screen's signature texts must be on it,
    or the flow aborts (3 looks, 2 s apart, to let screens settle);
  - FORBIDDEN words: outside the home screen any of them on screen aborts (originium, gacha, shop, payment...);
  - NO_TAP areas: the orundum / originium "+" in the top bar, the sanity "+" and the home pack banner can never be
    tapped, whatever a flow asks;
  - ALLOW boxes: a tap must land inside the box the flow declared for that (screen, label), else it aborts;
  - taps only on the centre of an OCR'd text that matches exactly (or a point the flow derives from one);
  - leaving: only the Android back key, until the home screen shows (back on a dialog = cancel);
  - MAX_STEPS screens per run, a screenshot per step in state\\uiflow\\<flow>\\ for the audit, one line per
    outcome in logs\\runs.log tagged [<flow>].
Coordinates are in 960x540 screenshot space (the device is 1600x900; K = 5/3), the same as ui.py prints.

Recording a new flow: ui.py rec / ui.py gen in the cloud session (see the skill .claude/skills/arknights-ui-flow).
"""
import json
import os
import re
import subprocess
import sys
import time

ROOT = r'D:\Projects\maa-cli'
ADB = [r'D:\leidian\LDPlayer9\adb.exe', '-s', 'emulator-5554']
OCR = [sys.executable, r'D:\Projects\agent-ocr\ocr.py']
os.environ.setdefault('AGENT_OCR_PORT', '8767')
os.environ.setdefault('AGENT_OCR_DEVICE', 'cpu')
K = 1600 / 960
MAX_STEPS = 40

FORBIDDEN = ['源石', '寻访', '购买', '时装', '兑换', '¥', '充值', '礼包', '采购', '支付', '抽取', '招募']
NO_TAP = [(440, 0, 960, 62),    # top bar: orundum "+" (~760, 44) and originium "+" (~876, 32)
          (520, 100, 610, 180), # home: sanity "+" (~553, 140), opens 理智恢复 with originium
          (0, 395, 230, 540)]   # home: pack banner (礼包限时上架)
HOME = ['理智/', '仓库']         # the home screen's signature, shared by every flow


def norm(s):
    return re.sub(r'\s', '', s).upper()


def screen_of(items, screens):
    texts = [norm(t) for t, _ in items]
    for name, sig in screens.items():
        if all(any(norm(k) in t for t in texts) for k in sig):
            return name
    return None


def forbidden_in(items, extra=()):
    return sorted({w for t, _ in items for w in list(FORBIDDEN) + list(extra) if w in t})


def find(items, text, exact=True):
    k = norm(text)
    for t, c in items:
        if (norm(t) == k) if exact else (k in norm(t)):
            return c
    return None


def tap_allowed(x, y, allow, screen, label):
    if not (0 <= x <= 960 and 0 <= y <= 540) or any(a <= x <= c and b <= y <= d for a, b, c, d in NO_TAP):
        return False
    box = allow.get((screen, label))
    return box is not None and box[0] <= x <= box[2] and box[1] <= y <= box[3]


class Abort(Exception):
    pass


class Flow:
    """One run of a flow: name (log tag), screens {name: [signature texts]}, allow {(screen, label): box}."""

    def __init__(self, name, screens, allow, forbidden_extra=()):
        self.name, self.allow, self.extra = name, allow, forbidden_extra
        self.screens = dict(screens)
        self.screens.setdefault('home', HOME)
        self.shots = os.path.join(ROOT, 'state', 'uiflow', name)
        os.makedirs(self.shots, exist_ok=True)
        self.n = 0

    # ---- device
    def adb(self, *a):
        return subprocess.run(ADB + list(a), capture_output=True, timeout=30)

    def look(self, tag):
        """OCR of the screen as [(text, (x, y))] in 960x540 space; keeps the screenshot."""
        self.n += 1
        if self.n > MAX_STEPS:
            raise Abort('more than %d steps' % MAX_STEPS)
        path = os.path.join(self.shots, '%s_%02d_%s.png' % (time.strftime('%Y%m%d-%H%M%S'), self.n, tag))
        with open(path, 'wb') as f:
            f.write(self.adb('exec-out', 'screencap', '-p').stdout)
        r = subprocess.run(OCR + ['--image', path, '--min-score', '0.5'], capture_output=True, timeout=600)
        j = json.loads(r.stdout.decode('utf-8'))
        if not j.get('ok'):
            raise Abort('ocr failed: %s' % j)
        return [(it['text'], (it['center'][0] / K, it['center'][1] / K)) for it in j['items']]

    def read_region(self, box, scale=3):
        """OCR one area of the last screenshot, enlarged `scale` times (small digits are often missed at full
        screen); returns [(text, (x, y))] in 960x540 space."""
        from PIL import Image
        last = sorted(f for f in os.listdir(self.shots) if f.endswith('.png') and '_zoom' not in f)[-1]
        img = Image.open(os.path.join(self.shots, last))
        x0, y0, x1, y1 = (round(v * K) for v in box)
        crop = img.crop((x0, y0, x1, y1))
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        path = os.path.join(self.shots, last.replace('.png', '_zoom.png'))
        crop.save(path)
        r = subprocess.run(OCR + ['--image', path, '--min-score', '0.4'], capture_output=True, timeout=300)
        j = json.loads(r.stdout.decode('utf-8'))
        return [(it['text'], ((x0 + it['center'][0] / scale) / K, (y0 + it['center'][1] / scale) / K))
                for it in j.get('items', [])]

    def tap_point(self, x, y, screen, label, wait=3.0):
        if not tap_allowed(x, y, self.allow, screen, label):
            raise Abort('refused tap on %s at (%d, %d): outside the area allowed for %s' % (label, x, y, screen))
        self.adb('shell', 'input', 'tap', str(round(x * K)), str(round(y * K)))
        time.sleep(wait)

    def back(self, wait=3.0):
        self.adb('shell', 'input', 'keyevent', '4')
        time.sleep(wait)

    # ---- steps
    def expect(self, want, tag=None):
        """Insist the screen is `want`; returns its OCR items."""
        name = None
        for _ in range(3):
            items = self.look(tag or want)
            name = screen_of(items, self.screens)
            bad = forbidden_in(items, self.extra) if name != 'home' else []
            if bad:
                raise Abort('forbidden text on screen (%s): %s' % (name or 'unknown', bad))
            if name == want:
                return items
            time.sleep(2)
        raise Abort('expected the %s screen, saw %s' % (want, name or 'an unknown screen'))

    def tap_text(self, items, screen, text, wait=3.0):
        c = find(items, text)
        if not c:
            raise Abort('text %r not found' % text)
        self.tap_point(*c, screen, text, wait=wait)

    def go_home(self, final=False):
        if final:                             # leaving must work even after the step cap was hit
            self.n = min(self.n, MAX_STEPS - 7)
        for i in range(6):
            if screen_of(self.look('home%d' % i), self.screens) == 'home':
                return True
            self.back()
        return False

    def say(self, msg):
        line = '%s [%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), self.name, msg)
        print(line, flush=True)
        with open(os.path.join(ROOT, 'logs', 'runs.log'), 'a', encoding='utf-8') as f:
            f.write(line + '\n')


def main(flow, body):
    """Run body(flow, dry) -> summary text; log it; always end on the home screen; stop the OCR server."""
    dry = '--dry' in sys.argv
    code = 0
    try:
        if not flow.go_home():
            raise Abort('could not reach the home screen')
        flow.say(body(flow, dry))
    except Abort as e:
        flow.say('aborted: %s' % e)
        code = 1
    except Exception as e:
        flow.say('error: %r' % e)
        code = 1
    finally:
        try:
            if not flow.go_home(final=True):
                flow.say('could not get back to the home screen')
                code = 1
        except Exception as e:
            flow.say('going home failed: %r' % e)
            code = 1
        subprocess.run(OCR + ['--stop'], capture_output=True, timeout=30)
    sys.exit(code)
