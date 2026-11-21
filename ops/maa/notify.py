"""notify.py - runs ON THE PC (Blender's bundled Python, standard library); called by run.ps1.

Pushes the hosting status to the user's iPhone through Bark (https://api.day.app), so they know when not to log
in: the game allows one login per account, and a phone login during a run kicks MAA off (and MAA logging back in
kicks the phone). The device key lives only on the PC, in C:\\Users\\blender\\.bark\\key (one line).

    notify.py start <task>                     run begins: expected end time from recent runs of the same task
    notify.py end <task> <exit code> <stamp>   run ended: farming, sanity left, tower sweep, problems
    notify.py refused <task> <exit code>       run.ps1 refused to start (91-94)
    notify.py test                             one test message
Never raises: a failed push is written to runs.log and the run goes on."""
import datetime as dt
import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r'D:\Projects\maa-cli')
KEY_FILE = Path.home() / '.bark' / 'key'
RUNS = ROOT / 'logs' / 'runs.log'
GROUP = '明日方舟托管'
TASK_NAME = {'daily': '日常', 'wake': '打开游戏', 'infrast': '基建换班', 'inventory': '仓库识别', 'chips': '芯片本'}
REFUSED = {91: '上一次托管还没结束', 92: 'MAA 界面版开着', 93: '模拟器在另一个账号的会话里运行', 94: '模拟器 3 分钟内没开机'}


def log(msg):
    with open(RUNS, 'a', encoding='utf-8') as f:
        f.write('%s [notify] %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))


def push(title, body, level='active'):
    try:
        key = KEY_FILE.read_text(encoding='utf-8').strip()
    except OSError:
        return                                          # not set up: stay silent
    data = json.dumps({'title': title, 'body': body, 'group': GROUP, 'level': level,
                       'isArchive': 1}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request('https://api.day.app/' + key, data=data, method='POST',
                                 headers={'Content-Type': 'application/json; charset=utf-8'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if json.loads(r.read().decode('utf-8')).get('code') == 200:
                    return
        except Exception as e:
            err = e
            time.sleep(3)
    log('push failed: %r' % (err if 'err' in locals() else 'bad reply'))


def recent_durations(task, n=3):
    """Seconds of the last n finished runs of this task, from the runs.log summary lines."""
    pat = re.compile(r'\[%s\] maa exit \d+ after ([\d,]+) s' % re.escape(task))
    try:
        lines = RUNS.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    return [int(m.group(1).replace(',', '')) for m in map(pat.search, lines) if m][-n:]


def run_lines(since):
    """runs.log lines written since `since` (datetime)."""
    out = []
    for line in RUNS.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            t = dt.datetime.strptime(line[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if t >= since:
            out.append(line[20:])
    return out


def sanity():
    try:
        info = json.loads((ROOT / 'export' / 'skland_info_latest.json').read_text(encoding='utf-8'))['data']
        ap = info['status']['ap']
        t = dt.datetime.fromtimestamp(ap['completeRecoveryTime'])
        days = (t.date() - dt.date.today()).days
        when = ('' if days <= 0 else '明天 ' if days == 1 else t.strftime('%m-%d ')) + t.strftime('%H:%M')
        return '理智 %s/%s，%s 回满' % (ap['current'], ap['max'], when)
    except Exception:
        return None


def summary(txt):
    """(what was farmed, sub-tasks that did not complete) from a maa-cli task summary (.out)."""
    parts, bad = [], []
    for block in txt.split('-' * 40):
        h = re.search(r'\[(.+?)\] [\d:]+ - [\d:]+ \([^)]*\) (\w+)', block)
        if not h:
            continue
        name, status = h.group(1), h.group(2)
        if status != 'Completed':
            bad.append('%s %s' % (name, status))
        for m in re.finditer(r'Fight (\S+) (\d+) times(?:, used (\d+) medicine)?', block):
            stage = '剿灭（%s）' % m.group(1) if name == '剿灭' else m.group(1)
            parts.append('%s %s 次%s' % (stage, m.group(2), '，吃药 %s' % m.group(3) if m.group(3) else ''))
    return parts, bad


def kicked_since(started):
    """How often MaaCore met the "登录认证已失效，请重新登录" popup (task OfflineConfirm) since `started`. MAA still
    reports such a sub-task as Completed in the .out summary, so only asst.log shows it (tested 2026-11-21)."""
    path = ROOT / 'state' / 'debug' / 'asst.log'
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, path.stat().st_size - 30 * 2**20))       # the last 30 MB cover any single run
            data = f.read().decode('utf-8', 'replace')
    except OSError:
        return 0
    n = 0
    for line in data.splitlines():
        if 'SubTaskStart' not in line or 'OfflineConfirm' not in line:
            continue
        try:
            t = dt.datetime.strptime(line[1:20], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if t >= started and re.search(r'"task":"[^"]*OfflineConfirm"', line):
            n += 1
    return n


def start(task):
    d = recent_durations(task)
    name = TASK_NAME.get(task, task)
    if d:
        end = dt.datetime.now() + dt.timedelta(seconds=statistics.median(d))
        body = '%s运行中，预计 %s 结束。期间请不要登录游戏。' % (name, end.strftime('%H:%M'))
    else:
        body = '%s运行中。期间请不要登录游戏。' % name
    push('托管开始', body)


def end(task, code, stamp):
    name = TASK_NAME.get(task, task)
    started = dt.datetime.strptime(stamp, '%Y%m%d-%H%M%S')
    lines = run_lines(started)
    parts = []
    out = ROOT / 'logs' / ('%s-%s.out' % (stamp, task))
    problems = []
    try:
        parts, bad = summary(out.read_text(encoding='utf-8', errors='replace'))
        problems += bad
    except OSError:
        pass
    for l in lines:
        if '[tower] swept' in l:
            parts.append('保全派驻扫荡 1 次')
    problems += [re.sub(r'^\[\w+\] ', '', l) for l in lines
                 if re.search(r'FAILED|aborted|error|could not|REFUSED', l) and '[notify]' not in l]
    k = kicked_since(started)
    if k:
        problems.insert(0, '遇到「登录认证已失效」%d 次（手机上登录了游戏）' % k)
    if any('skland' in l and 'exit 3' in l for l in lines):
        problems.append('森空岛登录失效，需要扫码')
    s = sanity()
    body = '；'.join(parts) if parts else '没有刷图'
    if s:
        body += '。' + s
    if code != 0 or problems:
        body += '。问题：' + ('；'.join(problems[:3]) if problems else 'maa 退出码 %d' % code)
        push('%s出错，可以登录了' % name, body, level='timeSensitive')
    else:
        push('%s结束，可以登录了' % name, body)


def main(a):
    try:
        if a[0] == 'start':
            start(a[1])
        elif a[0] == 'end':
            end(a[1], int(a[2]), a[3])
        elif a[0] == 'refused':
            push('托管没有运行', '%s没有开始：%s。' % (TASK_NAME.get(a[1], a[1]), REFUSED.get(int(a[2]), '退出码 %s' % a[2])),
                 level='timeSensitive')
        elif a[0] == 'test':
            push('托管通知测试', '能收到这条，说明推送已接通。' + (sanity() or ''))
    except Exception as e:                              # never break run.ps1
        try:
            log('notify %s failed: %r' % (a[:1], e))
        except Exception:
            pass


if __name__ == '__main__':
    main(sys.argv[1:])
