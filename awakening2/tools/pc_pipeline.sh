#!/bin/bash
# pc_pipeline.sh NAME WORKERS [BG shots...]  -- runs ON THE PC (Git Bash), detached:
# 1) regenerate the listed background paintings (2 at a time), 2) start render workers for job NAME.
NAME=$1; NW=$2; shift 2
cd /c/Users/blender/Documents/awakening2/code/engine
export PYTHONPATH="C:/Users/blender/Documents/awakening2/pylib" AW2_MESH_CACHE="C:/Users/blender/Documents/awakening2/cache/meshes" AW2_FRAMES="C:/Users/blender/Documents/awakening2/frames"
PY="/d/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe"
LOG=/c/Users/blender/Documents/awakening2/pipeline_$NAME.log
echo "start $(date)" > $LOG
if [ $# -gt 0 ]; then
  "$PY" -m gouache.render "$@" -j 2 >> $LOG 2>&1
  echo "bg done $(date)" >> $LOG
fi
cd /c/Users/blender/Documents/awakening2/code/tools
FD=/c/Users/blender/Documents/awakening2/frames_$NAME
mkdir -p $FD/_done
rm -f $FD/_done/${NAME}_*
for ((w=0; w<NW; w++)); do
  (nohup "$PY" pc_worker.py /c/Users/blender/Documents/awakening2/jobs/$NAME.json $w $NW > $FD/_done/${NAME}_$w.out 2>&1 &)
done
echo "workers launched $(date)" >> $LOG
