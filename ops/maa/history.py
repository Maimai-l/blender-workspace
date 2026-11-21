"""history.py - runs ON THE PC (Blender's bundled Python, standard library only); called by run.ps1 after each run.

The hosting history database of the scheduler design (《MAA 智能刷图调度器设计》, tab 资源分配规则, section
"第 1 期剩余：历史库"): D:\\Projects\\maa-cli\\history.db (SQLite). Every import reads everything that is there
(runs.log, logs\\*.out, export\\ snapshots, both MaaCore logs) and writes rows keyed so that importing twice never
adds a row twice; snapshot files already imported are skipped by path + mtime + size. The first import is the
backfill.

    history.py                 import (what run.ps1 calls); prints one summary line
    history.py --stats         rows per table and the time span of each
    history.py --sql "SELECT"  read-only query (the database is opened with mode=ro), tab-separated output

Times are the PC's local time (UTC+8) as 'YYYY-MM-DD HH:MM:SS'; a game day starts at 04:00 and is named by its date.

Tables (columns follow the design's table; what a source does not carry stays NULL):
  run                one row per run.ps1 run (run_id = the run's stamp, e.g. 20261121-120001), or per refusal
  sanity             sanity readings: source 'maa' (SanityBeforeStage callbacks before every fight) and 'skland'
                     (status.ap of each Skland snapshot, brought forward to the snapshot time: +1 per 6 min)
  fight              one row per Fight sub-task of a run's summary (.out, reruns after a kick included); stage id,
                     series, sanity per round, rounds and item-id drops come from MaaCore's StageDrops / FightTimes
                     callbacks when its log still covers the run, else drops are mapped from names (item_index.json);
                     times = fights, rounds = proxy rounds (one round = `series` fights), series = that of the last
                     round, sanity_used = sum of the played rounds' sanity
  item_snapshot      MAA depot exports (source 'maa') and Skland cultivate items (source 'skland')
  operator_snapshot  MAA operbox exports ('maa': elite, level, potential) and Skland info ('skland': also skill level,
                     mastery of skills 1-3, modules as JSON {module id: level})
  base_daily         per game day: closing stock of LMD, pure gold, EXP (card value), orundum and originium from the
                     last MAA depot export of the day, and the change since the previous game day ("库存差分")
  income, approval   created empty: their sources (reward results, the approval queue) do not exist yet
"""
import datetime as dt
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r'D:\Projects\maa-cli')
DB = ROOT / 'history.db'
RUNS = ROOT / 'logs' / 'runs.log'
EXPORT = ROOT / 'export'
ASST = [ROOT / 'state' / 'debug' / 'asst.bak.log', ROOT / 'state' / 'debug' / 'asst.log']
ITEM_INDEX = Path(r'D:\Projects\MAA\resource\item_index.json')
SCHEDULE = {(0, 0), (8, 0), (12, 0)}           # the fixed start times of the scheduled task (phase 3 will change this)
EXP_VALUE = {'2001': 200, '2002': 400, '2003': 1000, '2004': 2000}

SCHEMA = """
CREATE TABLE IF NOT EXISTS run (
  run_id TEXT PRIMARY KEY, task TEXT, started TEXT, ended TEXT, trigger TEXT,
  exit_code INTEGER, result TEXT, failure TEXT, kicked_retries INTEGER, log TEXT);
CREATE TABLE IF NOT EXISTS sanity (
  ts TEXT, source TEXT, current INTEGER, max INTEGER, PRIMARY KEY (ts, source));
CREATE TABLE IF NOT EXISTS fight (
  run_id TEXT, idx INTEGER, stage TEXT, stage_id TEXT, times INTEGER, rounds INTEGER, series INTEGER,
  sanity_per_fight INTEGER, sanity_used INTEGER, medicine INTEGER, medicine_expiring INTEGER, drops TEXT,
  PRIMARY KEY (run_id, idx));
CREATE TABLE IF NOT EXISTS item_snapshot (
  ts TEXT, source TEXT, item_id TEXT, count INTEGER, PRIMARY KEY (ts, source, item_id));
CREATE TABLE IF NOT EXISTS operator_snapshot (
  ts TEXT, source TEXT, char_id TEXT, elite INTEGER, level INTEGER, potential INTEGER, skill_level INTEGER,
  mastery1 INTEGER, mastery2 INTEGER, mastery3 INTEGER, modules TEXT, PRIMARY KEY (ts, source, char_id));
CREATE TABLE IF NOT EXISTS base_daily (
  game_day TEXT PRIMARY KEY, snapshot_ts TEXT, lmd INTEGER, lmd_delta INTEGER, gold INTEGER, gold_delta INTEGER,
  exp INTEGER, exp_delta INTEGER, orundum INTEGER, orundum_delta INTEGER, originium INTEGER,
  orders INTEGER, drone_target TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS income (
  game_day TEXT, source TEXT, orundum INTEGER, originium INTEGER, permits INTEGER, permits10 INTEGER,
  green INTEGER, yellow INTEGER, note TEXT, PRIMARY KEY (game_day, source));
CREATE TABLE IF NOT EXISTS approval (
  id TEXT PRIMARY KEY, kind TEXT, content TEXT, proposed TEXT, decided TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS imported (path TEXT PRIMARY KEY, mtime REAL, size INTEGER);
CREATE INDEX IF NOT EXISTS item_by_id ON item_snapshot (item_id, ts);
CREATE INDEX IF NOT EXISTS oper_by_id ON operator_snapshot (char_id, ts);
"""


def fmt(t):
    return t.strftime('%Y-%m-%d %H:%M:%S')


def local_ts(iso):
    """'2026-11-21T04:16:39.599Z' / '...+08:00' -> local 'YYYY-MM-DD HH:MM:SS'."""
    return fmt(dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone().replace(tzinfo=None))


def game_day(ts):
    return (dt.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S') - dt.timedelta(hours=4)).strftime('%Y-%m-%d')


def stamp_time(stamp):
    return dt.datetime.strptime(stamp, '%Y%m%d-%H%M%S')


# ---------------------------------------------------------------- sources: logs

def runs_log():
    """[(datetime, task, message)] of runs.log."""
    out = []
    try:
        text = RUNS.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[(\w+)\] (.*)', line.lstrip('\ufeff'))
        if m:
            out.append((dt.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S'), m.group(2), m.group(3)))
    return out


PROBLEM = re.compile(r'FAILED|REFUSED|aborted|error|could not|giving up')


def runs(lines):
    """Run rows from the 'maa exit' line of each run (and REFUSED lines, which have no run)."""
    rows = []
    for t, task, msg in lines:
        m = re.match(r'maa exit (-?\d+) after ([\d,]+) s; log .*?(\d{8}-\d{6})-\w+\.log', msg)
        if m:
            stamp = m.group(3)
            start = stamp_time(stamp)
            inside = [(tt, k, mm) for tt, k, mm in lines if start <= tt <= t]
            problems = [mm for tt, k, mm in inside if PROBLEM.search(mm) and k not in ('notify', 'ev')]
            kicked = sum(1 for tt, k, mm in inside if k == task and mm.startswith('kicked off ('))
            code = int(m.group(1))
            rows.append(dict(run_id=stamp, task=task, started=fmt(start), ended=fmt(t),
                             trigger='schedule' if (start.hour, start.minute) in SCHEDULE else 'manual',
                             exit_code=code, result='ok' if code == 0 and not problems else 'problem',
                             failure='; '.join(problems[:3]) or None, kicked_retries=kicked,
                             log='%s-%s' % (stamp, task)))
        elif msg.startswith('REFUSED') or msg.startswith('FAILED: Android'):
            rows.append(dict(run_id='refused-%s-%s' % (t.strftime('%Y%m%d-%H%M%S'), task), task=task,
                             started=fmt(t), ended=fmt(t), trigger=None, exit_code=None, result='refused',
                             failure=msg, kicked_retries=0, log=None))
    return rows


def out_fights(text):
    """Fight sub-tasks of a maa-cli summary: [(label, stage, times, medicine, {name: qty})]."""
    res = []
    for block in text.split('-' * 40):
        h = re.search(r'\[(.+?)\] [\d:]+ - [\d:]+ \([^)]*\) (\w+)', block)
        m = re.search(r'Fight (\S+) (\d+) times(?:, used (\d+) medicine)?', block)
        if not h or not m:
            continue
        drops = {}
        d = re.search(r'total drops: (.*)', block)
        if d:
            for name, q in re.findall(r'([^,]+?) × (\d+)', d.group(1)):
                drops[name.strip()] = drops.get(name.strip(), 0) + int(q)
        res.append((h.group(1), m.group(1), int(m.group(2)), int(m.group(3) or 0), drops))
    return res


def asst_events():
    """MaaCore callbacks we use, from both logs: [(datetime, what, details, group key)]."""
    ev = []
    for path in ASST:
        try:
            f = open(path, 'rb')
        except OSError:
            continue
        with f:
            for raw in f:
                if b'SubTaskExtraInfo' not in raw or not (b'"StageDrops"' in raw or b'"FightTimes"' in raw
                                                          or b'"SanityBeforeStage"' in raw):
                    continue
                line = raw.decode('utf-8', 'replace')
                try:
                    t = dt.datetime.strptime(line[1:20], '%Y-%m-%d %H:%M:%S')
                    j = json.loads(line[line.index('{'):])
                except (ValueError, KeyError):
                    continue
                ev.append((t, j.get('what'), j.get('details') or {}, (j.get('uuid'), j.get('taskid'))))
    ev.sort(key=lambda e: e[0])
    return ev


def fight_groups(ev, start, end):
    """Per Fight task inside [start, end]: stage code, id, rounds, series, sanity per round, drops by item id."""
    # MaaCore reports FightTimes (chosen series, sanity of that round) before every attempt, again with a smaller
    # series when sanity is short, and once more before the attempt that finds too little sanity; the round that
    # was actually played is the last FightTimes before its StageDrops (checked 2026-11-22: 134 -> 8 = 126 = 6 x 21)
    groups, pending = {}, {}
    for t, what, d, key in ev:
        if not (start <= t <= end):
            continue
        if what == 'FightTimes':
            pending[key] = d
        elif what == 'StageDrops':
            st = d.get('stage') or {}
            g = groups.setdefault((key, st.get('stageCode')), dict(first=t, stage=st.get('stageCode'),
                                                                  stage_id=st.get('stageId'), rounds=0,
                                                                  fights=0, used=0, series=None))
            ft = pending.pop(key, None) or {}
            g['rounds'] += 1
            g['series'] = ft.get('series', g['series'])
            g['used'] = None if g['used'] is None or 'sanity_cost' not in ft else g['used'] + ft['sanity_cost']
            g['per_fight'] = ft['sanity_cost'] // ft['series'] if ft.get('series') and 'sanity_cost' in ft else None
            g['drops'] = {s['itemId']: s['quantity'] for s in d.get('stats', []) if 'itemId' in s}
    return sorted(groups.values(), key=lambda g: g['first'])


def item_names():
    try:
        idx = json.loads(ITEM_INDEX.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    names = {}
    for iid, v in idx.items():
        names.setdefault(v.get('name'), iid)
    return names


def fights(run_rows, ev):
    names = item_names()
    rows = []
    for r in run_rows:
        if r['result'] == 'refused':
            continue
        logs = ROOT / 'logs'
        outs = [logs / ('%s.out' % r['log'])] + sorted(logs.glob('%s-retry*.out' % r['log']))
        parsed = []
        for o in outs:
            try:
                parsed += out_fights(o.read_text(encoding='utf-8', errors='replace'))
            except OSError:
                pass
        groups = fight_groups(ev, stamp_time(r['run_id']), dt.datetime.strptime(r['ended'], '%Y-%m-%d %H:%M:%S'))
        for i, (label, stage, times, med, drops) in enumerate(parsed):
            g = next((g for g in groups if g['stage'] == stage), None)
            if g:
                groups.remove(g)
                item_drops = g['drops']
            else:
                item_drops = {names.get(n, n): q for n, q in drops.items()}
            g = g or {}
            rows.append(dict(run_id=r['run_id'], idx=i, stage=stage, stage_id=g.get('stage_id'),
                             times=times, rounds=g.get('rounds'), series=g.get('series'),
                             sanity_per_fight=g.get('per_fight'), sanity_used=g.get('used'),
                             medicine=med, medicine_expiring=None,
                             drops=json.dumps(item_drops, ensure_ascii=False, sort_keys=True)))
    return rows


# ---------------------------------------------------------------- sources: export snapshots

SNAP = re.compile(r'^(depot|operbox|skland_info|skland_cultivate)_\d{8}-\d{4}\.json$')


def snapshot(con, path):
    kind = SNAP.match(path.name).group(1)
    j = json.loads(path.read_text(encoding='utf-8'))
    items, opers, sanity = [], [], []
    if kind == 'depot':
        ts = local_ts(j['syncTime'])
        items = [(ts, 'maa', k, int(v)) for k, v in j['data'].items()]
    elif kind == 'operbox':
        ts = local_ts(j['syncTime'])
        opers = [(ts, 'maa', o['id'], o.get('elite'), o.get('level'), o.get('potential'),
                  None, None, None, None, None) for o in j['own_opers'] if o.get('own', True)]
    elif kind == 'skland_cultivate':
        ts = local_ts(j['syncTime'])
        items = [(ts, 'skland', i['id'], int(i['count'])) for i in j['data']['items']]
    else:
        d = j['data']
        now = d['currentTs']
        ts = fmt(dt.datetime.fromtimestamp(now))
        for c in d['chars']:
            m = [s.get('specializeLevel') for s in c.get('skills', [])] + [None] * 3
            mods = {e['id']: e.get('level') for e in c.get('equip', []) if not e.get('locked')}
            opers.append((ts, 'skland', c['charId'], c.get('evolvePhase'), c.get('level'), c.get('potentialRank'),
                          c.get('mainSkillLvl'), m[0], m[1], m[2], json.dumps(mods, sort_keys=True)))
        ap = d['status']['ap']
        cur = ap['current']
        if cur < ap['max']:
            cur = min(ap['max'], cur + max(0, now - ap['lastApAddTime']) // 360)
        sanity.append((ts, 'skland', cur, ap['max']))
    con.executemany('INSERT OR IGNORE INTO item_snapshot VALUES (?,?,?,?)', items)
    con.executemany('INSERT OR IGNORE INTO operator_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?)', opers)
    con.executemany('INSERT OR IGNORE INTO sanity VALUES (?,?,?,?)', sanity)
    return len(items) + len(opers)


def base_daily(con):
    """Closing stock per game day from the last MAA depot export of the day, and the change since the day before."""
    last = {}
    for (ts,) in con.execute("SELECT DISTINCT ts FROM item_snapshot WHERE source='maa' ORDER BY ts"):
        last[game_day(ts)] = ts
    prev = None
    for day in sorted(last):
        ts = last[day]
        c = dict(con.execute("SELECT item_id, count FROM item_snapshot WHERE source='maa' AND ts=?", (ts,)))
        row = dict(lmd=c.get('4001'), gold=c.get('3003'), orundum=c.get('4003'), originium=c.get('4002'),
                   exp=sum(c.get(k, 0) * v for k, v in EXP_VALUE.items()))
        delta = {k: (row[k] - prev[k] if prev and row[k] is not None and prev[k] is not None else None)
                 for k in ('lmd', 'gold', 'exp', 'orundum')}
        con.execute('INSERT OR REPLACE INTO base_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (day, ts, row['lmd'], delta['lmd'], row['gold'], delta['gold'], row['exp'], delta['exp'],
                     row['orundum'], delta['orundum'], row['originium'], None, None, 'maa depot'))
        prev = row
    return len(last)


# ---------------------------------------------------------------- commands

def upsert(con, table, rows):
    if not rows:
        return
    cols = list(rows[0])
    con.executemany('INSERT OR REPLACE INTO %s (%s) VALUES (%s)' % (table, ','.join(cols), ','.join('?' * len(cols))),
                    [tuple(r[c] for c in cols) for r in rows])


def import_all():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    with con:
        lines = runs_log()
        run_rows = runs(lines)
        upsert(con, 'run', run_rows)
        ev = asst_events()
        con.executemany('INSERT OR IGNORE INTO sanity VALUES (?,?,?,?)',
                        [(d['report_time'][:19], 'maa', d['current_sanity'], d['max_sanity'])
                         for t, what, d, k in ev if what == 'SanityBeforeStage' and 'report_time' in d])
        # a run's fights are rewritten as a whole: MaaCore's log may have rotated since the last import, so
        # keep rows that were enriched from it when the log no longer covers the run
        new = fights(run_rows, ev)
        old = {(r[0], r[1]): r[2] for r in con.execute('SELECT run_id, idx, stage_id FROM fight')}
        new = [f for f in new if not (f['stage_id'] is None and old.get((f['run_id'], f['idx'])))]
        upsert(con, 'fight', new)
        n_snap = 0
        seen = dict((r[0], (r[1], r[2])) for r in con.execute('SELECT path, mtime, size FROM imported'))
        for p in sorted(EXPORT.iterdir()):
            if not SNAP.match(p.name):
                continue
            st = p.stat()
            if seen.get(p.name) == (st.st_mtime, st.st_size):
                continue
            try:
                snapshot(con, p)
            except (ValueError, KeyError, TypeError) as e:
                print('skipped %s: %r' % (p.name, e))
                continue
            con.execute('INSERT OR REPLACE INTO imported VALUES (?,?,?)', (p.name, st.st_mtime, st.st_size))
            n_snap += 1
        days = base_daily(con)
    counts = {t: con.execute('SELECT COUNT(*) FROM %s' % t).fetchone()[0] for t in ('run', 'fight', 'sanity')}
    con.close()
    print('imported %d runs, %d fights, %d new snapshots; %d game days; db has %d runs, %d fights, %d sanity readings'
          % (len(run_rows), len(new), n_snap, days, counts['run'], counts['fight'], counts['sanity']))


def readonly():
    return sqlite3.connect('file:%s?mode=ro' % DB.as_posix(), uri=True)


def stats():
    con = readonly()
    spans = {'run': 'started', 'sanity': 'ts', 'fight': None, 'item_snapshot': 'ts', 'operator_snapshot': 'ts',
             'base_daily': 'game_day', 'income': 'game_day', 'approval': 'proposed'}
    for t, col in spans.items():
        n = con.execute('SELECT COUNT(*) FROM %s' % t).fetchone()[0]
        span = con.execute('SELECT MIN(%s), MAX(%s) FROM %s' % (col, col, t)).fetchone() if col else ('', '')
        print('%-18s %7d  %s .. %s' % (t, n, span[0] or '', span[1] or ''))


def sql(q):
    con = readonly()
    cur = con.execute(q)
    print('\t'.join(c[0] for c in cur.description))
    for row in cur:
        print('\t'.join('' if v is None else str(v) for v in row))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if a[:1] == ['--stats']:
        stats()
    elif a[:1] == ['--sql']:
        sql(a[1])
    else:
        import_all()
