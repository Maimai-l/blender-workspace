"""export_data.py - runs ON THE PC after a maa-cli run: pull the Depot / OperBox results out of MaaCore's log.

    python export_data.py <asst.log> <start byte offset> <export dir>

maa-cli only logs these results; MaaCore writes them to asst.log as SubTaskExtraInfo callbacks ("what":
"DepotInfo" / "OperBoxInfo"). This reads the part of the log written during the run (from the offset; from 0
if the log was rotated) and writes the last finished result of each kind, in the same format as the MAA GUI's
data/DepotData.json and data/OperBoxData.json:

    <export dir>/depot_<yyyymmdd-HHMM>.json      {"done": true, "data": {"<item id>": count}, "syncTime": ...}
    <export dir>/operbox_<yyyymmdd-HHMM>.json    {"done": true, "own_opers": [...], "syncTime": ...}
    <export dir>/depot_latest.json, operbox_latest.json  (copies of the newest)

Standard library only (run with Blender's bundled Python). Prints one line per file written.
"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone

log_path, offset, out_dir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
os.makedirs(out_dir, exist_ok=True)
if os.path.getsize(log_path) < offset:
    offset = 0                      # the log was rotated during the run

found = {}
with open(log_path, 'rb') as f:
    f.seek(offset)
    for raw in f:
        if b'SubTaskExtraInfo' not in raw or (b'DepotInfo' not in raw and b'OperBoxInfo' not in raw):
            continue
        line = raw.decode('utf-8', 'replace')
        try:
            msg = json.loads(line[line.index('{', line.index('SubTaskExtraInfo')):])
        except ValueError:
            continue
        what, det = msg.get('what'), msg.get('details') or {}
        if what in ('DepotInfo', 'OperBoxInfo') and det.get('done'):
            found[what] = det       # keep the last finished one

now = datetime.now(timezone.utc).astimezone()
stamp = now.strftime('%Y%m%d-%H%M')
sync = now.isoformat()
if 'DepotInfo' in found:
    data = found['DepotInfo'].get('data')
    if isinstance(data, str):
        data = json.loads(data)
    out = {'done': True, 'data': data, 'syncTime': sync}
    p = os.path.join(out_dir, 'depot_%s.json' % stamp)
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    shutil.copyfile(p, os.path.join(out_dir, 'depot_latest.json'))
    print('depot', len(data), 'items ->', p)
if 'OperBoxInfo' in found:
    own = found['OperBoxInfo'].get('own_opers', [])
    out = {'done': True, 'own_opers': own, 'source': 'maa-cli', 'syncTime': sync}
    p = os.path.join(out_dir, 'operbox_%s.json' % stamp)
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    shutil.copyfile(p, os.path.join(out_dir, 'operbox_latest.json'))
    print('operbox', len(own), 'operators ->', p)
if not found:
    print('no finished Depot/OperBox result in this run')
