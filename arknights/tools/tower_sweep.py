"""tower_sweep.py - runs ON THE PC with D:\\Projects\\agent-ocr\\.venv\\Scripts\\python.exe (called by run.ps1 after
the daily task, before the emulator is closed).

Sweeps Security Deployment (保全派驻) with the 常态事务代理卡 that are about to expire, so they are not wasted.
The confirm dialog lists the cards by expiry ("2天 2", "9天 5"); a sweep costs 2 cards and the game spends the
earliest-expiring first. This sweeps only while the earliest group expires within EXPIRE_DAYS and still holds 2+
cards, so the cards annihilation needs next week are never touched; otherwise it taps 取消.

Path, as observed on 2026-11-20 (960x540 screenshot coordinates; device = x5/3):
  home (理智/ + 仓库)  -> tap 终端
  terminal (TO-DO LIST, 数据增补条, 数据增补仪)  -> tap 数据增补条 (the 保全派驻 to-do card)
  tower list (派驻周期结束时间, 查看酬劳明细)  -> tap the card image of a tower with a full record: its "6/6" label
      + (-68, +62); tapping the tower name does nothing
  tower detail (周期清理记录, 全权委托, 开始保全作战; "-2" under the button = proxy on, else tap 全权委托 once)
      -> tap 开始保全作战
  confirm dialog (确认使用2张常态事务代理卡 / 执行一次保全派驻全权委托代理指挥？; rows "N天" + count; 取消 / 确认使用)
      -> 确认使用 only when the rule above holds, else 取消
  result (保全作战完成, +N per reward)  -> tap the middle of the screen -> tower detail
  back key: tower detail -> tower list -> 常态事务 page (AFFAIR RECORD) -> home

Safety: every step first checks that ALL signature texts of the expected screen are on it; it only taps the
centre of an OCR'd text that matches exactly, and only inside the small box ALLOW gives that (screen, button);
the orundum / originium "+" in the top bar, the sanity "+" and the pack banner are refused on every screen
(NO_TAP); outside the home screen any FORBIDDEN word aborts.
Aborting only presses the Android back key (on a dialog that means cancel) until the home screen shows.

    python tower_sweep.py [--dry]      --dry: go up to the confirm dialog, then tap 取消
Log: D:\\Projects\\maa-cli\\logs\\runs.log (lines tagged [tower]); a screenshot per step in state\\tower\\.
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
SHOTS = ROOT + r'\state\tower'
os.environ.setdefault('AGENT_OCR_PORT', '8767')
os.environ.setdefault('AGENT_OCR_DEVICE', 'cpu')
K = 1600 / 960                  # 960x540 layout coordinates -> device pixels
EXPIRE_DAYS = 2                 # sweep only with cards expiring within this many days
MAX_STEPS = 40                  # hard cap on screens visited in one run

# words that must never appear on a screen this script acts on (home is exempt: it shows 采购中心 / 干员寻访)
FORBIDDEN = ['源石', '寻访', '购买', '时装', '兑换', '¥', '充值', '礼包', '采购', '支付', '抽取', '招募']
# areas (960x540 space, x0, y0, x1, y1) where a tap is never allowed, on any screen
NO_TAP = [(440, 0, 960, 62),    # top bar: orundum "+" (~760, 44) and originium "+" (~876, 32)
          (520, 100, 610, 180), # home: sanity "+" (~553, 140), opens 理智恢复 with originium
          (0, 395, 230, 540)]   # home: pack banner (礼包限时上架)
# the only place each tap may land (screen, label): (x0, y0, x1, y1) in 960x540 space
ALLOW = {('home', '终端'): (650, 80, 820, 165),
         ('terminal', '数据增补条'): (700, 62, 960, 140),
         ('tower_list', 'card'): (20, 60, 520, 420),
         ('tower_detail', '全权委托'): (740, 410, 930, 462),
         ('tower_detail', '开始保全作战'): (740, 465, 930, 530),
         ('confirm', '取消'): (600, 460, 780, 530),
         ('confirm', '确认使用'): (780, 460, 960, 530),
         ('result', 'continue'): (380, 250, 580, 350)}

SCREENS = {   # all of these texts must be present (normalised substring match)
    'home': ['理智/', '仓库'],
    'terminal': ['TO-DOLIST', '数据增补条', '数据增补仪'],
    'tower_list': ['派驻周期结束时间', '查看酬劳明细'],
    'tower_detail': ['周期清理记录', '全权委托', '开始保全作战'],
    'confirm': ['常态事务代理卡', '全权委托代理指挥', '确认使用', '取消'],
    'result': ['保全作战完成'],
    'affairs': ['请确认当前待办事务'],
}


def norm(s):
    return re.sub(r'\s', '', s).upper()


def screen_of(items):
    texts = [norm(t) for t, _ in items]
    for name, sig in SCREENS.items():
        if all(any(norm(k) in t for t in texts) for k in sig):
            return name
    return None


def forbidden_in(items):
    return sorted({w for t, _ in items for w in FORBIDDEN if w in t})


def find(items, text, exact=True):
    """Centre (960 space) of the first OCR item equal to text (or containing it)."""
    k = norm(text)
    for t, c in items:
        if (norm(t) == k) if exact else (k in norm(t)):
            return c
    return None


def tap_allowed(x, y, screen=None, label=None):
    if not (0 <= x <= 960 and 0 <= y <= 540) or any(a <= x <= c and b <= y <= d for a, b, c, d in NO_TAP):
        return False
    box = ALLOW.get((screen, label))
    return box is not None and box[0] <= x <= box[2] and box[1] <= y <= box[3]


def card_groups(items):
    """[(days, count)] from the confirm dialog's expiry rows ("2天" or "5小时" with its count on the same line)."""
    days = []
    for t, c in items:
        if m := re.fullmatch(r'(\d+)天', norm(t)):
            days.append((int(m.group(1)), c))
        elif re.fullmatch(r'\d+(小时|分钟|分)', norm(t)):      # under a day the dialog may count hours
            days.append((0, c))
    out = []
    for d, (x, y) in sorted(days, key=lambda v: v[1][1]):
        nums = [(cx - x, int(t)) for t, (cx, cy) in items
                if re.fullmatch(r'\d{1,3}', norm(t)) and abs(cy - y) <= 8 and 0 < cx - x <= 60]
        if nums:
            out.append((d, min(nums)[1]))
    return out


def decide(groups):
    """(sweep?, reason) for the confirm dialog."""
    if not groups:
        return False, 'could not read the card list'
    groups = sorted(groups)
    d, n = groups[0]
    if d > EXPIRE_DAYS:
        return False, 'no card expires within %d days (earliest: %d in %d days)' % (EXPIRE_DAYS, n, d)
    if n < 2:
        return False, 'only %d card expires within %d days; a sweep would also use a card annihilation needs' % (n, EXPIRE_DAYS)
    return True, '%d cards expire in %d days' % (n, d)


def proxy_on(items):
    return any(norm(t) == '-2' for t, _ in items)


def full_record_cards(items):
    """Tap points (960 space) of tower cards whose record label reads 6/6."""
    return [(x - 68, y + 62) for t, (x, y) in items if norm(t) == '6/6']


# ---------------------------------------------------------------- device side
def say(msg):
    line = '%s [tower] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line, flush=True)
    with open(ROOT + r'\logs\runs.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')


class Abort(Exception):
    pass


class Device:
    def __init__(self):
        os.makedirs(SHOTS, exist_ok=True)
        self.n = 0

    def adb(self, *a):
        return subprocess.run(ADB + list(a), capture_output=True, timeout=30)

    def look(self, tag):
        """OCR of the current screen as [(text, (x, y))] in 960x540 space; keeps the screenshot for the audit."""
        self.n += 1
        if self.n > MAX_STEPS:
            raise Abort('more than %d steps' % MAX_STEPS)
        path = os.path.join(SHOTS, '%s_%02d_%s.png' % (time.strftime('%Y%m%d-%H%M%S'), self.n, tag))
        with open(path, 'wb') as f:
            f.write(self.adb('exec-out', 'screencap', '-p').stdout)
        r = subprocess.run(OCR + ['--image', path, '--min-score', '0.5'], capture_output=True, timeout=600)
        j = json.loads(r.stdout.decode('utf-8'))
        if not j.get('ok'):
            raise Abort('ocr failed: %s' % j)
        return [(it['text'], (it['center'][0] / K, it['center'][1] / K)) for it in j['items']]

    def tap(self, x, y, screen, label, wait=3.0):
        if not tap_allowed(x, y, screen, label):
            raise Abort('refused tap on %s at (%d, %d): outside the area allowed for %s' % (label, x, y, screen))
        self.adb('shell', 'input', 'tap', str(round(x * K)), str(round(y * K)))
        time.sleep(wait)

    def back(self, wait=3.0):
        self.adb('shell', 'input', 'keyevent', '4')
        time.sleep(wait)


def expect(dev, want, tag):
    """Look at the screen and insist it is `want`; returns its OCR items."""
    for _ in range(3):                       # screens can take a moment to settle
        items = dev.look(tag)
        name = screen_of(items)
        bad = forbidden_in(items) if name != 'home' else []
        if bad:
            raise Abort('forbidden text on screen (%s): %s' % (name or 'unknown', bad))
        if name == want:
            return items
        time.sleep(2)
    raise Abort('expected the %s screen, saw %s' % (want, name or 'an unknown screen'))


def tap_text(dev, items, screen, text, wait=3.0):
    c = find(items, text)
    if not c:
        raise Abort('text %r not found' % text)
    dev.tap(*c, screen, text, wait=wait)


def go_home(dev):
    """Back key only, until the home screen shows (back on a dialog = cancel, so nothing is ever confirmed)."""
    for i in range(6):
        items = dev.look('home%d' % i)
        if screen_of(items) == 'home':
            return True
        dev.back()
    return False


def run(dev, dry):
    if not go_home(dev):                     # the daily task may end on the depot or operator screens
        raise Abort('could not reach the home screen')
    items = expect(dev, 'home', 'start')
    tap_text(dev, items, 'home', '终端', wait=4)
    items = expect(dev, 'terminal', 'terminal')
    tap_text(dev, items, 'terminal', '数据增补条', wait=4)
    items = expect(dev, 'tower_list', 'list')
    cards = full_record_cards(items)
    if not cards:
        return 'no tower with a full record (6/6) to sweep'
    dev.tap(*cards[0], 'tower_list', 'card', wait=4)
    items = expect(dev, 'tower_detail', 'detail')
    if not proxy_on(items):
        tap_text(dev, items, 'tower_detail', '全权委托', wait=2)
        items = expect(dev, 'tower_detail', 'detail_proxy')
        if not proxy_on(items):
            return 'proxy (全权委托) not available on this tower'
    tap_text(dev, items, 'tower_detail', '开始保全作战', wait=3)
    items = expect(dev, 'confirm', 'confirm')
    ok, why = decide(card_groups(items))
    if dry or not ok:
        tap_text(dev, items, 'confirm', '取消', wait=3)
        expect(dev, 'tower_detail', 'cancelled')
        return ('dry run: would sweep (%s)' % why) if (dry and ok) else ('not sweeping: ' + why)
    tap_text(dev, items, 'confirm', '确认使用', wait=6)
    items = expect(dev, 'result', 'result')
    got = ' '.join(norm(t) for t, _ in items if re.fullmatch(r'\+\d+', norm(t)))
    dev.tap(480, 300, 'result', 'continue', wait=4)
    expect(dev, 'tower_detail', 'after')
    return 'swept once (%s); rewards %s' % (why, got or '?')


def main():
    dry = '--dry' in sys.argv
    dev = Device()
    code = 0
    try:
        say(run(dev, dry))
    except Abort as e:
        say('aborted: %s' % e)
        code = 1
    except Exception as e:
        say('error: %r' % e)
        code = 1
    finally:
        try:
            if not go_home(dev):
                say('could not get back to the home screen')
                code = 1
        except Exception as e:
            say('going home failed: %r' % e)
            code = 1
        subprocess.run(OCR + ['--stop'], capture_output=True, timeout=30)
    sys.exit(code)


if __name__ == '__main__':
    main()
