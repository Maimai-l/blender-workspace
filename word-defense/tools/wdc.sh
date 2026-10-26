#!/bin/bash
# push changed Unity sources, recompile, print errors (and warnings with -w)
cd "$(dirname "$0")"
timeout 200 python3 mcpc.py push ../unity/WordDefense "D:\\Unity\\Projects\\Word Defence\\Assets\\WordDefense" | grep -v "^EXIT_CODE\|^STDOUT\|^$"
timeout 300 python3 mcpc.py tool unity refresh_unity '{"mode":"force","scope":"all","compile":"request","wait_for_ready":true}' > /dev/null
sleep ${WAIT:-6}
TYPES='["error"]'; [ "$1" == "-w" ] && TYPES='["error","warning"]'
timeout 300 python3 mcpc.py tool unity read_console "{\"action\":\"get\",\"types\":$TYPES,\"count\":60}" | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
seen=set()
for e in d.get('data',[]):
    s=e.strip().split('\n')[0][:260]
    if s in seen: continue
    seen.add(s); print(s)
print('--', d.get('message'))"
