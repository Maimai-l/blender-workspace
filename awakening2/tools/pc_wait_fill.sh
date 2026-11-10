#!/bin/bash
# pc_wait_fill.sh NAME FRAMESDIR : wait for a PC render to finish; when no workers remain and
# frames are missing, launch a fill pass (4 workers, skip existing); repeat until complete.
NAME=$1; FD=$2
cd /home/user/blender-workspace/awakening2
total() { python3 tools/pc.py sh "cd /c/Users/blender/Documents/awakening2/$FD && n=0; for d in S*; do n=\$((n+\$(ls \$d | grep -c '_[0-9][0-9][0-9][0-9][.]png\$'))); done; echo TOTAL \$n" 2>&1 | grep -o "TOTAL [0-9]*" | awk '{print $2}'; }
workers() { python3 tools/pc.py sh 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/Users/blender/Documents/awakening2/procs.ps1 | wc -l' 2>&1 | grep -E '^[0-9]+$' | tail -1; }
NEED=$(python3 -c "import json; c=json.load(open('audio/cues.json')); print(sum(int(round((s['out']-s['in'])*24)) for s in c['shots']))")
fills=0
while true; do
  t=$(total); w=$(workers)
  echo "$(TZ=America/Toronto date +%H:%M) total=$t need=$NEED workers=$w"
  if [ -n "$t" ] && [ "$t" -ge "$NEED" ]; then python3 tools/pc.py kill > /dev/null 2>&1; echo DONE; break; fi
  # when the main workers start running out, help the slowest shots (once)
  if [ -n "$w" ] && [ "$w" -gt 0 ] && [ "$w" -lt 4 ] && [ -z "$STOLE" ] && [ -n "$t" ] && [ "$t" -lt "$NEED" ]; then
    inc=$(python3 tools/pc.py sh "cd /c/Users/blender/Documents/awakening2/$FD && for d in S*; do echo \$d \$(ls \$d | grep -c '_[0-9][0-9][0-9][0-9][.]png\$'); done" 2>&1 | python3 -c "
import sys, json
c = json.load(open('audio/cues.json'))
need = {s['id']: int(round((s['out'] - s['in']) * 24)) for s in c['shots']}
have = {}
for line in sys.stdin:
    p = line.split()
    if len(p) == 2 and p[0] in need and p[1].isdigit():
        have[p[0]] = int(p[1])
print(' '.join(k for k in need if have.get(k, 0) < need[k]))")
    if [ -n "$inc" ]; then
      python3 tools/pc.py steal ${NAME}auto $FD 4 $inc > /dev/null 2>&1
      echo "auto steal on: $inc"; STOLE=1
    fi
  fi
  if [ "$w" = "0" ]; then
    fills=$((fills+1)); if [ $fills -gt 3 ]; then echo GIVEUP; break; fi
    shots=$(python3 -c "import json; print(' '.join(s['id'] for s in json.load(open('audio/cues.json'))['shots']))")
    python3 tools/pc.py steal ${NAME}fill$fills $FD 4 $shots > /dev/null 2>&1
    echo "fill pass $fills launched"
  fi
  sleep 50
done
