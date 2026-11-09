#!/bin/bash
# render_group.sh LOGNAME SHOT [SHOT ...] : render shots one after another (frames -> /home/user/aw2_frames)
name=$1; shift
cd /home/user/blender-workspace/awakening2/shots
for s in "$@"; do
  echo "=== $s $(TZ=America/Toronto date +%H:%M:%S)" >> /home/user/aw2_logs/$name.log
  python3 render_shot.py $s >> /home/user/aw2_logs/$name.log 2>&1 || echo "FAILED $s" >> /home/user/aw2_logs/$name.log
done
echo "=== DONE $(TZ=America/Toronto date +%H:%M:%S)" >> /home/user/aw2_logs/$name.log
