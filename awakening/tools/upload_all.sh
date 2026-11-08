#!/bin/bash
# upload every painted texture to the PC (skips unchanged files)
cd "$(dirname "$0")"
for f in ../paint/out/*.png; do
  b=$(basename "$f")
  python3 -I upload_mcp.py "$f" "C:\\Users\\blender\\Documents\\awakening\\tex\\$b" || echo "FAILED $b"
done
echo UPLOAD_DONE
