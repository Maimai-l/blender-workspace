"""sanity_plan.py - runs ON THE PC before each `daily` run (called by run.ps1, after annihilation_gate.py).

Chooses the stage of the 理智作战 task in config/tasks/daily.toml from the rules in sanity_plan.json: the first rule
whose time window, game-day weekday and inventory need all apply wins. The game day changes at 04:00 UTC+8, so a
0:00 run still counts as the previous day (the same convention as maa-cli's `timezone = "Official"`). Inventory
comes from the last Skland export (export/skland_cultivate_latest.json). The task block sits between the lines
`# >>> fight` and `# <<< fight`; only its `stage = "..."` value and the `# plan:` comment are rewritten.

    python sanity_plan.py [--dry]          (--dry: print the decision, leave daily.toml alone)
    PLAN_NOW=2026-11-22T08:00:00+08:00     (env, for testing: pretend it is this time)
Standard library only (Blender's bundled Python)."""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('MAA_ROOT', r'D:\Projects\maa-cli'))
TOML = ROOT / 'config' / 'tasks' / 'daily.toml'
RULES = HERE / 'sanity_plan.json'
CST = dt.timezone(dt.timedelta(hours=8))
DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def inventory():
    try:
        d = json.loads((ROOT / 'export' / 'skland_cultivate_latest.json').read_text(encoding='utf-8'))['data']
        return {x['id']: int(x['count']) for x in d['items']}
    except Exception as e:
        print(f'no Skland inventory ({e}); rules with a need are skipped')
        return None


def choose(now, inv, rules):
    game_day = DAYS[(now - dt.timedelta(hours=4)).weekday()]
    for r in rules:
        if 'until' in r and now > dt.datetime.fromisoformat(r['until']):
            continue
        if 'weekdays' in r and game_day not in r['weekdays']:
            continue
        if 'need' in r:
            if inv is None:
                continue
            have = sum(inv.get(i, 0) * w for i, w in r['need']['items'].items())
            if have >= r['need']['target']:
                continue
            return r, f"{r['why']}（现有 {have}/{r['need']['target']}）", game_day
        return r, r['why'], game_day
    return None, 'no rule applies', game_day


def main():
    now = dt.datetime.fromisoformat(os.environ['PLAN_NOW']) if os.environ.get('PLAN_NOW') else dt.datetime.now(CST)
    rules = json.loads(RULES.read_text(encoding='utf-8'))['rules']
    r, why, day = choose(now, inventory(), rules)
    if not r:
        print(f'{why}; daily.toml unchanged')
        return
    stage = r['stage']
    if '--dry' in sys.argv:
        print(f'{now:%m-%d %H:%M} game day {day}: {stage} ({why})')
        return
    s = TOML.read_text(encoding='utf-8')
    m = re.search(r'(# >>> fight[^\n]*\n)(.*?)(# <<< fight)', s, re.S)
    if not m or 'stage = "' not in m.group(2):
        print('fight markers not found; daily.toml unchanged')
        return
    body = re.sub(r'stage = "[^"]*"', f'stage = "{stage}"', m.group(2), count=1)
    body = re.sub(r'# plan:[^\n]*\n', '', body)
    body = f'# plan: {stage}, {why} (sanity_plan.py, {now:%m-%d %H:%M})\n' + body
    t = s[:m.start(2)] + body + s[m.end(2):]
    if t != s:
        TOML.write_text(t, encoding='utf-8')
    print(f'{stage}: {why}')


if __name__ == '__main__':
    main()
