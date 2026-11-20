"""tower_sweep.py - a uiflow flow (runs ON THE PC with D:\\Projects\\agent-ocr\\.venv\\Scripts\\python.exe; called by
run.ps1 after the daily task, before the emulator is closed). Needs uiflow.py next to it.

Sweeps Security Deployment (保全派驻) with the 常态事务代理卡 that are about to expire, so they are not wasted.
The confirm dialog lists the cards by expiry ("2天 2", "9天 5"); a sweep costs 2 cards and the game spends the
earliest-expiring first. This sweeps only while the earliest group expires within EXPIRE_DAYS and still holds 2+
cards, so the cards annihilation needs next week are never touched; otherwise it taps 取消.

Path, as observed on 2026-11-20 (960x540 coordinates):
  home -> 终端 -> terminal (TO-DO LIST) -> 数据增补条 (the 保全派驻 to-do card) -> tower list -> the card image of a
  tower with a full record ("6/6" label + (-68, +62); tapping the name does nothing) -> tower detail ("-2" under
  开始保全作战 = proxy on, else tap 全权委托 once) -> 开始保全作战 -> confirm dialog -> 确认使用 or 取消 -> result
  (保全作战完成) -> tap the middle -> tower detail. Back key: detail -> list -> 常态事务 page -> home.
Guards (screen checks, forbidden words, no-tap areas, ALLOW boxes, back-key exit): uiflow.py.

    python tower_sweep.py [--dry]      --dry: go up to the confirm dialog, then tap 取消
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uiflow  # noqa: E402
from uiflow import Abort, norm  # noqa: E402

EXPIRE_DAYS = 2                 # sweep only with cards expiring within this many days

SCREENS = {   # all of these texts must be present (normalised substring match); 'home' comes from uiflow
    'terminal': ['TO-DOLIST', '数据增补条', '数据增补仪'],
    'tower_list': ['派驻周期结束时间', '查看酬劳明细'],
    'tower_detail': ['周期清理记录', '全权委托', '开始保全作战'],
    'confirm': ['常态事务代理卡', '全权委托代理指挥', '确认使用', '取消'],
    'result': ['保全作战完成'],
    'affairs': ['请确认当前待办事务'],
}
ALLOW = {('home', '终端'): (650, 80, 820, 165),
         ('terminal', '数据增补条'): (700, 62, 960, 140),
         ('tower_list', 'card'): (20, 60, 520, 420),
         ('tower_detail', '全权委托'): (740, 410, 930, 462),
         ('tower_detail', '开始保全作战'): (740, 465, 930, 530),
         ('confirm', '取消'): (600, 460, 780, 530),
         ('confirm', '确认使用'): (780, 460, 960, 530),
         ('result', 'continue'): (380, 250, 580, 350)}


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
    d, n = sorted(groups)[0]
    if d > EXPIRE_DAYS:
        return False, 'no card expires within %d days (earliest: %d in %d days)' % (EXPIRE_DAYS, n, d)
    if n < 2:
        return False, 'only %d card expires within %d days; a sweep would also use a card annihilation needs' % (n, EXPIRE_DAYS)
    return True, '%d cards expire in %d days' % (n, d)


def proxy_on(items):
    return any(norm(t) == '-2' for t, _ in items)


def full_record_cards(items):
    """Tap points of tower cards whose record label reads 6/6."""
    return [(x - 68, y + 62) for t, (x, y) in items if norm(t) == '6/6']


def run(f, dry):
    items = f.expect('home', 'start')
    f.tap_text(items, 'home', '终端', wait=4)
    items = f.expect('terminal')
    f.tap_text(items, 'terminal', '数据增补条', wait=4)
    items = f.expect('tower_list')
    cards = full_record_cards(items)
    if not cards:
        return 'no tower with a full record (6/6) to sweep'
    f.tap_point(*cards[0], 'tower_list', 'card', wait=4)
    items = f.expect('tower_detail')
    if not proxy_on(items):
        f.tap_text(items, 'tower_detail', '全权委托', wait=2)
        items = f.expect('tower_detail', 'detail_proxy')
        if not proxy_on(items):
            return 'proxy (全权委托) not available on this tower'
    f.tap_text(items, 'tower_detail', '开始保全作战', wait=3)
    items = f.expect('confirm')
    groups = card_groups(items)
    labels = [c for t, c in items if re.fullmatch(r'\d+(天|小时|分钟|分)', norm(t))]
    if labels and len(groups) < len(labels):          # a count was missed: the digits are small, read them enlarged
        ys = [y for _, y in labels]
        zoom = f.read_region((min(x for x, _ in labels) - 30, min(ys) - 14, 960, max(ys) + 14))
        groups = card_groups(zoom)
    ok, why = decide(groups)
    if dry or not ok:
        f.tap_text(items, 'confirm', '取消', wait=3)
        f.expect('tower_detail', 'cancelled')
        return ('dry run: would sweep (%s)' % why) if (dry and ok) else ('not sweeping: ' + why)
    f.tap_text(items, 'confirm', '确认使用', wait=6)
    items = f.expect('result')
    got = ' '.join(norm(t) for t, _ in items if re.fullmatch(r'\+\d+', norm(t)))
    f.tap_point(480, 300, 'result', 'continue', wait=4)
    f.expect('tower_detail', 'after')
    return 'swept once (%s); rewards %s' % (why, got or '?')


if __name__ == '__main__':
    uiflow.main(uiflow.Flow('tower', SCREENS, ALLOW), run)
