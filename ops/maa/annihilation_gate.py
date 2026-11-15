"""annihilation_gate.py - runs ON THE PC before each `daily` run (called by run.ps1).

daily.toml runs three times a day, and every run would fight Annihilation for 25 sanity even after the weekly
1800-orundum cap is reached. This reads the last Skland export and comments the Annihilation task out of
config/tasks/daily.toml while this week's reward is full, and back in otherwise. The weekly reset is Monday
04:00 (UTC+8); an export taken before the latest reset counts as "not full". The task block sits between the
lines `# >>> annihilation` and `# <<< annihilation`. Standard library only (Blender's bundled Python)."""
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(r'D:\Projects\maa-cli')
TOML = ROOT / 'config' / 'tasks' / 'daily.toml'
CST = dt.timezone(dt.timedelta(hours=8))

try:
    info = json.loads((ROOT / 'export' / 'skland_info_latest.json').read_text(encoding='utf-8'))['data']
    rw = info['campaign']['reward']
    ts = dt.datetime.fromtimestamp(info['currentTs'], CST)
except Exception as e:  # no export yet: leave the file alone
    print(f'no Skland data ({e}); daily.toml unchanged')
    raise SystemExit(0)

now = dt.datetime.now(CST)
reset = (now - dt.timedelta(hours=4)).replace(hour=4, minute=0, second=0, microsecond=0)
reset -= dt.timedelta(days=reset.weekday())          # latest Monday 04:00
full = ts >= reset and rw['current'] >= rw['total']

s = TOML.read_text(encoding='utf-8')
m = re.search(r'(# >>> annihilation[^\n]*\n)(.*?)(# <<< annihilation)', s, re.S)
if not m:
    print('markers not found; daily.toml unchanged')
    raise SystemExit(0)
lines = m.group(2).splitlines(keepends=True)
if full:
    body = ''.join(l if l.startswith('#') or not l.strip() else '#' + l for l in lines)
else:
    body = ''.join(l[1:] if l.startswith('#') else l for l in lines)
t = s[:m.start(2)] + body + s[m.end(2):]
if t != s:
    TOML.write_text(t, encoding='utf-8')
    print(('annihilation off: weekly reward full ({}/{})' if full else 'annihilation on ({}/{} this week)').format(rw['current'] if ts >= reset else 0, rw['total']))
