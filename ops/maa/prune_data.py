"""prune_data.py - runs ON THE PC at the end of each run.ps1 (Blender's bundled Python, standard library).

Keeps the hosting data from growing without end:
  export\\  depot_*, operbox_*, skland_info_*, skland_cultivate_* snapshots (the *_latest.json copies are never
           touched): everything from the last 14 days; older ones thinned to the last snapshot of each day per
           kind, kept for 180 days (enough history for the weekly health metrics of the scheduler design);
  state\\uiflow\\<flow>\\  per-step screenshots of UI flows: 7 days;
  state\\ev_screen*.png, state\\ui.png / ui.jpg: working images, overwritten anyway; left alone.
Uses file modification times (Skland file names carry UTC stamps, MAA's local ones). Prints one summary line.

    python prune_data.py [--dry]"""
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(r'D:\Projects\maa-cli')
DAY = 86400
KEEP_ALL_DAYS, KEEP_DAILY_DAYS, SHOT_DAYS = 14, 180, 7
KIND = re.compile(r'^(depot|operbox|skland_info|skland_cultivate)_\d{8}-\d{4}\.json$')


def main(dry):
    now = time.time()
    gone, freed = [], 0
    last_of_day = {}
    snaps = [p for p in (ROOT / 'export').iterdir() if KIND.match(p.name)]
    for p in sorted(snaps, key=lambda p: p.stat().st_mtime):
        kind = KIND.match(p.name).group(1)
        day = time.strftime('%Y%m%d', time.localtime(p.stat().st_mtime))
        last_of_day[(kind, day)] = p                 # sorted by time: the last one wins
    keep = set(last_of_day.values())
    for p in snaps:
        age = (now - p.stat().st_mtime) / DAY
        if age > KEEP_DAILY_DAYS or (age > KEEP_ALL_DAYS and p not in keep):
            gone.append(p)
    shots = ROOT / 'state' / 'uiflow'
    if shots.exists():
        gone += [p for p in shots.rglob('*') if p.is_file() and (now - p.stat().st_mtime) / DAY > SHOT_DAYS]
    for p in gone:
        freed += p.stat().st_size
        if not dry:
            p.unlink()
    print('%s %d files, %.1f MB' % ('would remove' if dry else 'removed', len(gone), freed / 2**20))


if __name__ == '__main__':
    main('--dry' in sys.argv)
