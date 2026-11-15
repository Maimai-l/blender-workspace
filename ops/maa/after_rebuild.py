"""after_rebuild.py - runs ON THE PC after each Skland sync (called by run.ps1).

While the base is rebuilt from 243 to 333 (2026-11-15), the daily task keeps its drones ("_NotUse") so the new
trade post can reach level 3. Once Skland shows three trade posts, all at level 3, this puts drones back on
trade ("Money") in config/tasks/daily.toml and infrast.toml, and prints one line. Does nothing otherwise.
Standard library only (Blender's bundled Python)."""
import json
import re
from pathlib import Path

ROOT = Path(r'D:\Projects\maa-cli')
info = json.loads((ROOT / 'export' / 'skland_info_latest.json').read_text(encoding='utf-8'))['data']
trades = info['building']['tradings']
if len(trades) >= 3 and all(t['level'] >= 3 for t in trades):
    changed = []
    for name in ('daily.toml', 'infrast.toml'):
        p = ROOT / 'config' / 'tasks' / name
        s = p.read_text(encoding='utf-8')
        t = re.sub(r'drones = "_NotUse".*', 'drones = "Money"', s)
        if t != s:
            p.write_text(t, encoding='utf-8')
            changed.append(name)
    if changed:
        print('rebuild done (3 trade posts at level 3): drones back on trade in ' + ', '.join(changed))
