"""ev_run.py - runs ON THE PC with D:\\Projects\\agent-ocr\\.venv\\Scripts\\python.exe.

Clears side-story stages with prts.plus copilots. maa-cli's copilot list only navigates main-story stages,
so this script navigates itself: adb screenshot -> agent-ocr (text + coordinates) -> tap. For each pending
entry of QUEUE it goes home, opens the event, opens the zone, taps the stage code, reads the current sanity
and the stage cost from the stage screen, sets the stage's mode switch (set_mode), then runs
`maa copilot prts://<id> --formation`. maa-cli's `--raid` does nothing for a single copilot (it only steers its
own main-story navigation), and MaaCore just presses whichever start button the stage screen shows: before
2026-11-17 every "raid" entry was therefore fought in normal mode.
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
os.environ.setdefault('AGENT_OCR_DEVICE', 'cpu')        # GPU onnxruntime commits ~3.6 GB; CPU is enough for game screens
MIN_FREE_COMMIT_GB = 6     # skip copilots while Windows is short of memory (MAA aborts mid-battle on a failed screenshot)
ENEMY_BOX = (640, 10, 800, 64)   # device pixels: battle top bar, enemy counter "k/n" (seen at x 678-769)
LIVES_BOX = (905, 10, 1000, 64)  # life counter right of the tower icon (seen at x 938-959)
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
    # S-4（2026-11-18 加）：110102 普通、突袭都能用，按现有干员全部满足。备选（多一个 Lancet-2，她本来就没有技能，
    # 匹配脚本误报“没有 1 技能”）：普通 110143（3.4 万次浏览），突袭 110148（4.3 万次）
    ('TL-S-4', '世纪之春', 110102, 'normal'),
    ('TL-S-4', '世纪之春', 110102, 'raid'),
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


def free_commit_gb():
    """Commit charge still available (GB): what Windows can still hand out before allocations fail."""
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 2**30


def _ocr_crop(img, box, name):
    path = SHOT.replace('.png', '_%s.png' % name)
    w, h = box[2] - box[0], box[3] - box[1]
    img.crop(box).resize((w * 2, h * 2)).save(path)
    r = subprocess.run(OCR + ['--image', path, '--min-score', '0.5'], capture_output=True, timeout=120)
    try:
        return [it['text'].replace(' ', '') for it in json.loads(r.stdout.decode('utf-8'))['items']]
    except Exception:
        return []


def lives():
    """The life counter in the battle top bar, or None. Only trusted when the enemy counter "k/n" is also on
    screen (so formation and loading screens never give a false starting value)."""
    from PIL import Image
    with open(SHOT, 'wb') as f:
        f.write(adb('exec-out', 'screencap', '-p').stdout)
    img = Image.open(SHOT)
    if not any(re.fullmatch(r'\d{1,3}/\d{1,3}', t) for t in _ocr_crop(img, ENEMY_BOX, 'enemy')):
        return None
    nums = [t for t in _ocr_crop(img, LIVES_BOX, 'lives') if re.fullmatch(r'\d{1,2}', t)]
    return int(nums[0]) if nums else None


def in_battle(items):
    return any(k in norm(t) for t, _ in items for k in ('PAUSE', '暂停中', '剩余可放置角色'))


# Leaving a battle, as observed on this account (2026-11-16): the gear [MAA: LeaveOperation, ROI 41,22,78,71 at
# 1280x720 -> about (100, 72) here] opens the dialog "放弃行动将会恢复N理智（全部返还） / 是否放弃行动？" with
# buttons 返回 / 放弃行动 (lower right); then "任务失败 ... 点击画面以继续"; then the result screen "理智返还 N".
# (MAA's JieGarden give-up chain uses other ROIs: that dialog belongs to the roguelike UI.)
GEAR = (100, 72)


def _lowest(items, key):
    hits = [(c[1], c) for t, c in items if norm(key) in norm(t)]
    return max(hits)[1] if hits else None


def abandon_battle():
    """Leave a running battle. Abandoning refunds all the sanity (a 2-star clear refunds nothing)."""
    left = False
    for _ in range(6):
        items = ocr(0.5)
        if find(items, '是否放弃行动'):
            tap(*_lowest(items, '放弃行动'), wait=5)
            left = True
        elif find(items, '任务失败') or find(items, '点击画面以继续') or find(items, '理智返还'):
            tap(800, 450, wait=4)
            left = True
        elif in_battle(items):
            tap(*GEAR, wait=2)
        else:
            return left or True
    say('could not leave the battle')
    return False


def run_copilot(cid, mode, log):
    """Run maa copilot while watching the life counter. A leak means no 3 stars (and a 2-star clear refunds
    nothing), so on two consecutive readings below the starting value maa is stopped and the battle abandoned."""
    p = subprocess.Popen([MAA, 'copilot', 'prts://%d' % cid, '--formation', '--log-file=' + log],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    start, low, t0 = None, 0, time.time()
    while p.poll() is None and time.time() - t0 < 1800:
        time.sleep(3)
        try:
            n = lives()
        except Exception:
            n = None
        if n is None:
            continue
        if start is None or n > start:
            start = n
        low = low + 1 if n < start else 0
        if low >= 2:
            p.kill(); p.wait()
            say('leak detected (lives %d -> %d): abandoning so the sanity is refunded' % (start, n))
            abandon_battle()
            return 'leak'
    if p.poll() is None:
        p.kill(); p.wait()
    out = p.stdout.read().decode('utf-8', 'replace')
    return 'ok' if p.returncode == 0 and 'Completed' in out else 'error'


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
        if in_battle(items):
            abandon_battle()
            continue
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
            if find(items, '开始行动') or find(items, '开始突袭'):
                return items
            raise RuntimeError('tapped %s but the stage screen did not open' % code)
        # the stage map can be wider than the screen: look left, then right
        x1, x2 = (400, 1200) if attempt < 3 else (1200, 400)
        adb('shell', 'input', 'swipe', str(x1), '450', str(x2), '450', '600')
        time.sleep(1.5)
    raise RuntimeError('stage %s not found in %s' % (code, zone))


RAID_ON, RAID_OFF = '开始突袭', '开始行动'   # start button text in raid / normal mode
RAID_SWITCH = {'raid': '突袭模式', 'normal': '普通难度'}   # what the switch left of 演习 reads, to change INTO that mode


def set_mode(mode, items):
    """Put the side-story stage screen into normal or raid mode and confirm it from the start button text.
    Returns the OCR items of the confirmed screen, or None (then nothing is fought)."""
    want = RAID_ON if mode == 'raid' else RAID_OFF
    for _ in range(2):
        if find(items, want) and not (mode == 'normal' and find(items, RAID_ON)):
            return items
        c = find(items, RAID_SWITCH[mode])
        if not c:
            return None
        tap(*c, wait=2.5)
        items = ocr()
    return items if find(items, want) and not (mode == 'normal' and find(items, RAID_ON)) else None


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
        items = set_mode(mode, open_stage(code, zone))
        if items is None:
            say('%s: could not switch the stage screen to %s mode; stopping' % (key, mode))
            break
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
        if free_commit_gb() < MIN_FREE_COMMIT_GB:
            say('only %.1f GB of memory left (Blender or another program holds it); copilots wait for the next run' % free_commit_gb())
            break
        res = 'error'
        for attempt in (1, 2):                       # a failed screenshot or a leak is usually a one-off: retry once
            log = '%s\\logs\\%s-ev.log' % (ROOT, time.strftime('%Y%m%d-%H%M%S'))
            res = run_copilot(cid, mode, log)
            say('%s copilot %d try %d: %s' % (key, cid, attempt, res))
            if res == 'ok':
                break
            items = ocr()
            if in_battle(items):
                abandon_battle()
            if attempt == 1 and set_mode(mode, open_stage(code, zone)) is None:
                say('%s: could not switch to %s mode for the retry' % (key, mode))
                break
        if res != 'ok':
            fail[key] = fail.get(key, 0) + 1
            json.dump(fail, open(FAIL, 'w', encoding='utf-8'), ensure_ascii=False)
            if fail[key] >= 2:
                say('%s failed in two runs with copilot %d; skipped from now on (pick another copilot)' % (key, cid))
            break
        done.append(key)
        json.dump(done, open(DONE, 'w', encoding='utf-8'), ensure_ascii=False)
        if find(ocr(), '行动结束'):                  # leave the result screen
            tap(800, 450, wait=4)
    go_home()


def stop_ocr():
    subprocess.run(OCR + ['--stop'], capture_output=True, timeout=30)


if __name__ == '__main__':
    code = 0
    try:
        main()
    except Exception as e:
        say('error: %r' % e)
        code = 1
        try:
            go_home()
        except Exception:
            adb('shell', 'input', 'keyevent', '4')
    finally:
        stop_ocr()                                   # the OCR server holds memory; never leave it running
    sys.exit(code)
