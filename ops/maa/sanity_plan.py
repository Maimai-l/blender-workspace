"""sanity_plan.py - runs ON THE PC before each `daily` run (called by run.ps1, after annihilation_gate.py).

Writes the sanity-farming Fight tasks of config/tasks/daily.toml (the block between `# >>> fight` and
`# <<< fight`) from sanity_plan.json. It ports the idea of MAA GUI's 库存保持 (DepotMaintain,
src/MaaWpfGui/ViewModels/UserControl/TaskQueue/DepotMaintainTaskUserControlModel.cs) to maa-cli:
  - an entry with a need: missing = target - stock (other items weighted by count_as, e.g. a dual chip counts as
    2 chip packs); if missing > 0 it becomes a Fight task with drops = {item: missing}, so MaaCore stops as soon
    as that many have dropped and the next task gets the remaining sanity;
  - an entry without a need spends whatever sanity is left; the list ends there.
Entries also have an optional `until` (ISO time) and `weekdays` (game day: it changes at 04:00 UTC+8, so a 0:00
run still counts as the previous day, as maa-cli's timezone = "Official"). Stock comes from the last Skland
export (export/skland_cultivate_latest.json). Every task: no ordinary potions, potions expiring within 2 days,
no originium, series 0 (the most the stage allows).

    python sanity_plan.py [--dry]          --dry: print the tasks, leave daily.toml alone
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
COMMON = 'medicine = 0, medicine_expire_days = 2, stone = 0, series = 0, client_type = "Official"'


def inventory():
    try:
        d = json.loads((ROOT / 'export' / 'skland_cultivate_latest.json').read_text(encoding='utf-8'))['data']
        return {x['id']: int(x['count']) for x in d['items']}
    except Exception as e:
        print(f'no Skland inventory ({e}); entries with a need are skipped')
        return None


def plan(now, inv, entries):
    """[(stage, drops or None, reason)] in order; the last one has no drops (it spends the rest)."""
    day = DAYS[(now - dt.timedelta(hours=4)).weekday()]
    out = []
    for e in entries:
        if 'until' in e and now > dt.datetime.fromisoformat(e['until']):
            continue
        if 'weekdays' in e and day not in e['weekdays']:
            continue
        n = e.get('need')
        if n:
            if inv is None:
                continue
            have = inv.get(n['item'], 0) + sum(inv.get(i, 0) * w for i, w in n.get('count_as', {}).items())
            missing = n['target'] - have
            if missing <= 0:
                continue
            out.append((e['stage'], {n['item']: missing}, f"{e['why']}（现有 {have}/{n['target']}，再刷 {missing} 个）"))
            continue
        out.append((e['stage'], None, e['why']))
        break
    return out, day


def render(tasks, now):
    lines = []
    for i, (stage, drops, why) in enumerate(tasks, 1):
        d = ('drops = { %s }, ' % ', '.join('"%s" = %d' % kv for kv in drops.items())) if drops else ''
        lines += [f'# plan {i}: {stage}, {why} (sanity_plan.py, {now:%m-%d %H:%M})',
                  '[[tasks]]', f'name = "理智作战 {stage}"', 'type = "Fight"',
                  f'params = {{ stage = "{stage}", {d}{COMMON} }}', '']
    return '\n'.join(lines)


def main():
    now = dt.datetime.fromisoformat(os.environ['PLAN_NOW']) if os.environ.get('PLAN_NOW') else dt.datetime.now(CST)
    entries = json.loads(RULES.read_text(encoding='utf-8'))['entries']
    tasks, day = plan(now, inventory(), entries)
    if not tasks:
        print('no entry applies; daily.toml unchanged')
        return
    summary = '; '.join(f"{s}{' until %s more' % sum(d.values()) if d else ''}" for s, d, _ in tasks)
    if '--dry' in sys.argv:
        print(f'{now:%m-%d %H:%M} game day {day}: {summary}')
        return
    s = TOML.read_text(encoding='utf-8')
    m = re.search(r'(# >>> fight[^\n]*\n)(.*?)(# <<< fight)', s, re.S)
    if not m:
        print('fight markers not found; daily.toml unchanged')
        return
    t = s[:m.start(2)] + render(tasks, now) + s[m.end(2):]
    if t != s:
        TOML.write_text(t, encoding='utf-8')
    print(summary)


if __name__ == '__main__':
    main()
