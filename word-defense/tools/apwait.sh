#!/bin/bash
# wait for the editor autopilot to finish (RESULT line) or time out; print its log lines
cd "$(dirname "$0")"
LIMIT=${1:-600}
start=$(date +%s)
while true; do
  out=$(timeout 60 python3 mcpc.py tool unity read_console '{"action":"get","types":["log","error","warning"],"count":200,"filter_text":"AUTOPILOT"}' 2>/dev/null)
  if echo "$out" | grep -q "RESULT:"; then break; fi
  now=$(date +%s); if [ $((now-start)) -gt $LIMIT ]; then echo "TIMEOUT after $LIMIT s"; break; fi
  sleep 15
done
echo "$out" | python3 -c "
import sys,json
try:
  d=json.loads(sys.stdin.read())
  for e in reversed(d.get('data',[])): print(e.strip().split(chr(10))[0][:320])
except Exception as ex: print('parse error', ex)"
timeout 60 python3 mcpc.py tool unity read_console '{"action":"get","types":["error"],"count":8,"include_stacktrace":true,"format":"detailed"}' | head -c 3000
