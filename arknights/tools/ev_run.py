"""ev_run.py - runs ON THE PC with D:\\Projects\\agent-ocr\\.venv\\Scripts\\python.exe.

Clears side-story stages with prts.plus copilots. maa-cli's copilot list only navigates main-story stages,
so this script navigates itself: adb screenshot -> agent-ocr (text + coordinates) -> tap. For each pending
entry of QUEUE it goes home, opens the event, opens the zone, taps the stage code, reads the current sanity
and the stage cost from the stage screen, then runs `maa copilot prts://<id> --formation --raid <mode>`.
Stops at the first entry it cannot afford. Finished entries go to state\\ev_done.json.

    python ev_run.py [--dry]      --dry: navigate and read sanity, but do not fight
Log: D:\\Projects\\maa-cli\\logs\\runs.log (lines tagged [ev]).
"""
import json
import os
import re
import subprocess
import sys
import time

ROOT = r'D:\Projects\maa-cli'
ADB = [r'D:\leidian\LDPlayer9\adb.exe', '-s', 'emulator-5554']
MAA = r'D:\Projects\MAA\maa.exe'
OCR = [sys.executable, r'D:\Projects\agent-ocr\ocr.py']
SHOT = ROOT + r'\state\ev_screen.png'
DONE = ROOT + r'\state\ev_done.json'
FAIL = ROOT + r'\state\ev_fail.json'           # failures per entry; an entry is skipped after 2
os.environ.setdefault('AGENT_OCR_PORT', '8767')        # 8765/8766 are the panel and the agent
for k in ('CONFIG', 'STATE', 'CACHE', 'DATA'):
    os.environ['MAA_%s_DIR' % k] = ROOT + '\\' + k.lower()

EVENT_TEXT = '时间啊'                # text on the home-screen event banner
HOME_ICON = (358, 50)               # top bar house icon, opens the quick menu
# (stage code, zone tab, copilot id, mode). Copilots: reports\2026-11-15_TL活动规划.md (all usable with this box).
QUEUE = [
    ('TL-EX-2', '长冬初青', 109554, 'normal'),
    ('TL-EX-3', '长冬初青', 109557, 'normal'),
    ('TL-EX-4', '长冬初青', 109723, 'normal'),
    ('TL-EX-5', '长冬初青', 109562, 'normal'),
    ('TL-EX-6', '长冬初青', 109566, 'normal'),
    ('TL-EX-7', '长冬初青', 109569, 'normal'),
    ('TL-EX-8', '长冬初青', 109659, 'normal'),
    ('TL-S-1', '世纪之春', 110074, 'normal'),
    ('TL-S-2', '世纪之春', 110081, 'normal'),
    ('TL-S-3', '世纪之春', 110088, 'normal'),
    ('TL-EX-1', '长冬初青', 109538, 'raid'),
    ('TL-EX-2', '长冬初青', 109554, 'raid'),
    ('TL-EX-3', '长冬初青', 109557, 'raid'),
    ('TL-EX-4', '长冬初青', 109723, 'raid'),
    ('TL-EX-5', '长冬初青', 109562, 'raid'),
    ('TL-EX-6', '长冬初青', 109566, 'raid'),
    ('TL-EX-7', '长冬初青', 109569, 'raid'),
    ('TL-EX-8', '长冬初青', 109659, 'raid'),
    ('TL-S-1', '世纪之春', 110074, 'raid'),
    ('TL-S-2', '世纪之春', 110081, 'raid'),
    ('TL-S-3', '世纪之春', 110088, 'raid'),
]


def say(msg):
    line = '%s [ev] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line, flush=True)
    with open(ROOT + r'\logs\runs.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def adb(*a):
    return subprocess.run(ADB + list(a), capture_output=True, timeout=30)


def tap(x, y, wait=2.5):
    adb('shell', 'input', 'tap', str(int(x)), str(int(y)))
    time.sleep(wait)


def ocr(min_score=0.6):
    """[(text, (cx, cy))] of the current screen, in device pixels (1600x900)."""
    with open(SHOT, 'wb') as f:
        f.write(adb('exec-out', 'screencap', '-p').stdout)
    r = subprocess.run(OCR + ['--image', SHOT, '--min-score', str(min_score)], capture_output=True, timeout=600)
    j = json.loads(r.stdout.decode('utf-8'))
    if not j.get('ok'):
        raise RuntimeError('ocr: %s' % j)
    return [(it['text'], tuple(it['center'])) for it in j['items']]


def norm(s):
    return re.sub(r'\s', '', s).upper().replace('一', '-').replace('—', '-').replace('_', '-')


def find(items, key, exact=False):
    k = norm(key)
    for t, c in items:
        if (norm(t) == k) if exact else (k in norm(t)):
            return c
    return None


def go_home():
    for _ in range(6):
        items = ocr()
        if find(items, '仓库') and find(items, '理智/'):      # the quick menu also shows 终端/采购中心
            return
        if find(items, '首页'):
            tap(*find(items, '首页'), wait=4)
            continue
        tap(*HOME_ICON, wait=2)
    raise RuntimeError('could not reach the home screen')


def open_stage(code, zone):
    """Only taps text that OCR found on the expected screen; anything unexpected raises (no blind taps)."""
    go_home()
    c = find(ocr(0.3), EVENT_TEXT)
    if not c:
        raise RuntimeError('event banner not found on the home screen')
    tap(*c, wait=6)
    items = ocr()
    c = find(items, zone)
    if not c:
        raise RuntimeError('zone %s not on screen after opening the event' % zone)
    tap(*c, wait=4)
    for attempt in range(6):
        items = ocr()
        if not any(norm(t).startswith('TL-') for t, _ in items):
            raise RuntimeError('not on a stage map after opening %s' % zone)
        c = find(items, code, exact=True)
        if c:
            tap(*c, wait=3)
            items = ocr()
            if find(items, '开始行动'):
                return items
            raise RuntimeError('tapped %s but the stage screen did not open' % code)
        # the stage map can be wider than the screen: look left, then right
        x1, x2 = (400, 1200) if attempt < 3 else (1200, 400)
        adb('shell', 'input', 'swipe', str(x1), '450', str(x2), '450', '600')
        time.sleep(1.5)
    raise RuntimeError('stage %s not found in %s' % (code, zone))


def sanity_and_cost(items):
    cur = cost = None
    for t, (x, y) in items:
        m = re.fullmatch(r'(\d{1,3})/(\d{3})', norm(t))
        if m and y < 120:
            cur = int(m.group(1))
        m = re.fullmatch(r'-(\d{1,2})', norm(t))
        if m and y > 780:
            cost = int(m.group(1))
    return cur, cost


def main():
    dry = '--dry' in sys.argv
    done = json.load(open(DONE, encoding='utf-8')) if os.path.exists(DONE) else []
    fail = json.load(open(FAIL, encoding='utf-8')) if os.path.exists(FAIL) else {}
    pending = [q for q in QUEUE if '%s/%s' % (q[0], q[3]) not in done and fail.get('%s/%s' % (q[0], q[3]), 0) < 2]
    if not pending:
        say('queue empty (done %d, skipped after failures: %s)' % (len(done), [k for k, v in fail.items() if v >= 2]))
        return
    for code, zone, cid, mode in pending:
        key = '%s/%s' % (code, mode)
        items = open_stage(code, zone)               # raid: maa switches the mode itself (ChangeToRaidDifficulty)
        cur, cost = sanity_and_cost(items)
        say('%s: sanity %s, cost %s' % (key, cur, cost))
        if cur is None or cost is None:
            say('could not read sanity or cost; stopping')
            break
        if cur < cost:
            say('not enough sanity for %s; stopping' % key)
            break
        if dry:
            say('dry run: not fighting')
            break
        p = subprocess.run([MAA, 'copilot', 'prts://%d' % cid, '--formation', '--raid', mode,
                            '--log-file=%s\\logs\\%s-ev.log' % (ROOT, time.strftime('%Y%m%d-%H%M%S'))],
                           capture_output=True, timeout=1800)
        out = p.stdout.decode('utf-8', 'replace')
        ok = p.returncode == 0 and 'Completed' in out
        say('%s copilot %d: exit %d %s' % (key, cid, p.returncode, 'ok' if ok else 'FAILED'))
        if not ok:
            fail[key] = fail.get(key, 0) + 1
            json.dump(fail, open(FAIL, 'w', encoding='utf-8'), ensure_ascii=False)
            if fail[key] >= 2:
                say('%s failed twice with copilot %d; skipped from now on (pick another copilot)' % (key, cid))
            break
        done.append(key)
        json.dump(done, open(DONE, 'w', encoding='utf-8'), ensure_ascii=False)
        if find(ocr(), '行动结束'):                  # leave the result screen
            tap(800, 450, wait=4)
    go_home()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        say('error: %r' % e)
        try:
            go_home()
        except Exception:
            adb('shell', 'input', 'keyevent', '4')
        sys.exit(1)
