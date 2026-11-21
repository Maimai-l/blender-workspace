"""forecast_update.py - runs ON THE PC after history.py (Blender's bundled Python, standard library).

Refreshes the measured fields of D:\\Projects\\maa-cli\\forecast_inputs.json from history.db and the latest
exports, runs forecast.py on it, and saves the result as export\\forecast_latest.md (plus a dated copy). Once per
game day (04:00 boundary) unless --force. Fields it does not measure keep the values in the JSON (first copy:
the planning session's initial values, ops/maa/forecast_inputs.json); `_source` records where each value came from.

    forecast_update.py [--force]

Measured now:
  today             local date
  stock.lmd / gold / rock   last MAA depot export (4001 / 3003 / 30012)
  stock.shards      Skland cultivate items (3141; MAA's depot export does not list it)
  lmd_income_per_day   mean daily LMD change over the last 14 game days (history.db base_daily). While no shards
                    are made this is the income; once the shard line runs, LMD spent on shards (1,600 each) has to
                    be added back, or forecast.py counts it twice (see _source)."""
import datetime as dt
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(r'D:\Projects\maa-cli')
INPUTS = ROOT / 'forecast_inputs.json'
OUT = ROOT / 'export' / 'forecast_latest.md'


def game_day(t):
    return (t - dt.timedelta(hours=4)).strftime('%Y-%m-%d')


def main(force):
    now = dt.datetime.now()
    if not force and OUT.exists() and ('game day %s' % game_day(now)) in OUT.read_text(encoding='utf-8')[:300]:
        print('already ran for game day %s' % game_day(now))
        return
    p = json.loads(INPUTS.read_text(encoding='utf-8'))
    src = p.setdefault('_source', {})
    con = sqlite3.connect('file:%s?mode=ro' % (ROOT / 'history.db').as_posix(), uri=True)
    ts = con.execute("SELECT MAX(ts) FROM item_snapshot WHERE source='maa'").fetchone()[0]
    depot = dict(con.execute("SELECT item_id, count FROM item_snapshot WHERE source='maa' AND ts=?", (ts,)))
    sts = con.execute("SELECT MAX(ts) FROM item_snapshot WHERE source='skland'").fetchone()[0]
    sk = dict(con.execute("SELECT item_id, count FROM item_snapshot WHERE source='skland' AND ts=?", (sts,)))
    deltas = [r[0] for r in con.execute(
        'SELECT lmd_delta FROM base_daily WHERE lmd_delta IS NOT NULL ORDER BY game_day DESC LIMIT 14')]
    con.close()

    p['today'] = now.strftime('%Y-%m-%d')
    for key, iid in (('lmd', '4001'), ('gold', '3003'), ('rock', '30012')):
        if iid in depot:
            p['stock'][key] = depot[iid]
            src['stock.' + key] = 'MAA depot export %s' % ts
    if '3141' in sk:
        p['stock']['shards'] = sk['3141']
        src['stock.shards'] = 'Skland cultivate %s' % sts
    if deltas:
        p['lmd_income_per_day'] = round(sum(deltas) / len(deltas) / 1000) * 1000
        src['lmd_income_per_day'] = ('mean LMD change of the last %d game days (history.db base_daily), current '
                                     'layout without a shard station; add back 1,600 per shard once shards are made'
                                     % len(deltas))
    INPUTS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')

    r = subprocess.run([sys.executable, '-I', str(ROOT / 'forecast.py'), str(INPUTS)],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print('forecast.py failed: %s' % r.stderr.strip()[-300:])
        return
    head = ['# 抽卡资源预测（game day %s，%s 运行）' % (game_day(now), now.strftime('%Y-%m-%d %H:%M')), '',
            '输入：forecast_inputs.json；实测字段的来源：', '']
    head += ['- %s：%s' % (k, v) for k, v in sorted(src.items())]
    text = '\n'.join(head) + '\n\n' + r.stdout
    OUT.write_text(text, encoding='utf-8')
    (ROOT / 'export' / ('forecast_%s.md' % now.strftime('%Y%m%d'))).write_text(text, encoding='utf-8')
    m = re.findall(r'^\| (\d+) \|.*?\| (\d+) 抽 \| [^|]+ \| [^|]+ \|$', r.stdout, re.M)
    print('forecast written: %s' % ', '.join('%s days %s pulls' % x for x in m))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main('--force' in sys.argv)
