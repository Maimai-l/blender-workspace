#!/bin/bash
# pc_tidy.sh scan|clean  -- runs ON THE PC (Git Bash, blender account); ops/tidy.py sends it through exec.
# Finds what the cloud tools leave behind in the PC work area and, with "clean", deletes it and appends
# every removal to D:\Blender\Projects\_迁移日志\cleanup_<date>.log.
# Only by-products of the tools are touched (see ops/README.md); anything else is reported for a person to decide.
MODE=${1:-scan}
MIN_AGE_MIN=${MIN_AGE_MIN:-60}            # leave files younger than this alone: a job may still use them
P=/d/Blender/Projects
LOGDIR="$P/_迁移日志"
LOG="$LOGDIR/cleanup_$(date +%F).log"
TOTAL=0

busy() {
  # Blender jobs and render workers that may still be writing into the project folders
  powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { (\$_.Name -eq 'blender.exe' -and \$_.CommandLine -match ' -b | --background') -or (\$_.Name -eq 'python.exe' -and \$_.CommandLine -match 'pc_worker|gouache.render|brelay.py|pack.py') -or \$_.Name -eq 'ffmpeg.exe' } | ForEach-Object { '{0} {1}' -f \$_.ProcessId, ((\$_.CommandLine -replace '\s+',' ').Substring(0, [Math]::Min(150, \$_.CommandLine.Length))) }" 2>/dev/null | tr -d '\r'
}

kb() { du -sk "$1" 2>/dev/null | cut -f1; }

hit() {   # hit <path> <reason>
  local f="$1" why="$2" k
  k=$(kb "$f"); k=${k:-0}
  TOTAL=$((TOTAL + k))
  if [ "$MODE" = clean ]; then
    if rm -rf -- "$f" 2>/dev/null && [ ! -e "$f" ]; then
      printf '%-90s %8s kB  %s\n' "$(cygpath -w "$f")" "$k" "$why" >> "$LOG"
      echo "removed  $f  (${k} kB, $why)"
    else
      echo "kept     $f  (could not be removed: held open by a running program)"
    fi
  else
    echo "would rm $f  (${k} kB, $why)"
  fi
}

old() { find "$@" -mmin +"$MIN_AGE_MIN" 2>/dev/null; }

B=$(busy)
if [ -n "$B" ]; then
  echo "BUSY: background jobs are running, nothing is deleted:"; echo "$B"
  [ "$MODE" = clean ] && MODE=scan
fi
if [ "$MODE" = clean ]; then
  mkdir -p "$LOGDIR"
  printf '\n%s  end-of-session cleanup (ops/pc_tidy.sh), files older than %s min\n' "$(date '+%F %T')" "$MIN_AGE_MIN" >> "$LOG"
fi

# 1. transfer and relay scratch of pcx.py / putbig.py / rdefer.py: <project>\tmp\*
for t in "$P"/*/tmp; do
  [ -d "$t" ] || continue
  old "$t" -mindepth 1 -maxdepth 1 | while read -r f; do hit "$f" "tool scratch (tmp)"; done
done
# 2. deferred-job outputs and done-markers next to renders
old "$P"/*/renders -maxdepth 1 -type f \( -name 'job_*.txt' -o -name '*.done' -o -name '*.tmp' \) | while read -r f; do hit "$f" "deferred-job output/marker"; done
# 3. half-written frames left by killed workers
old "$P" -maxdepth 4 -type f -name '*.tmp.png' | while read -r f; do hit "$f" "partial frame"; done
# 4. render-farm by-products in a project root (Awakening II pc.py): encode/pipeline logs, upload archive
old "$P"/* -maxdepth 1 -type f \( -name 'enc_*.done' -o -name 'enc_*.log' -o -name 'list_v*.txt' -o -name 'pipeline_*.log' \
    -o -name 'pipeline_*.out' -o -name 'bg_S*.log' -o -name '*code.tgz' -o -name 'pip*.log' -o -name 'build.log' \) | while read -r f; do hit "$f" "render-farm log/archive"; done
# 5. helper frame folders that only hold worker bookkeeping (_done)
for d in "$P"/*/frames_*; do
  [ -d "$d" ] || continue
  if [ -z "$(find "$d" -type f ! -path '*/_done/*' -print -quit)" ]; then hit "$d" "helper frames folder, only _done"; fi
done
# 6. temp of the blender account: *.tmp older than 7 days
find /c/Users/blender/AppData/Local/Temp -maxdepth 1 -type f -name '*.tmp' -mtime +7 2>/dev/null | while read -r f; do hit "$f" "old temp file"; done

[ "$MODE" = clean ] && echo "done; log: $(cygpath -w "$LOG")"

echo
echo "== for a person to look at (not deleted) =="
echo "-- exec working dir C:\\Users\\blender\\ExecMCP (should be empty between sessions):"
ls -A /c/Users/blender/ExecMCP 2>/dev/null | sed 's/^/   /'
echo "-- Documents (only vocabulary.db and junctions belong here):"
find /c/Users/blender/Documents -maxdepth 1 -mindepth 1 ! -name desktop.ini ! -name vocabulary.db ! -type l 2>/dev/null | sed 's/^/   /'
echo "-- C:\\Users\\blender (entries beyond the known set):"
KNOWN='|.claude|.claude.json|.thumbnails|.unity-mcp|AppData|Application Data|BlenderMCP-run|Contacts|Cookies|Desktop|Documents|Downloads|ExecMCP|ExecMCP-run|Favorites|Links|Local Settings|Music|My Documents|NetHood|OneDrive|Pictures|PrintHood|Recent|Saved Games|Searches|SendTo|Templates|Unity user templates|UnityMCP-run|Videos|blender-mcp-secret.txt|exec-mcp-secret.txt|unity-mcp-secret.txt|「开始」菜单|'
ls -A /c/Users/blender | while read -r n; do
  case "$n" in NTUSER.DAT*|ntuser.*) continue;; esac
  case "$KNOWN" in *"|$n|"*) ;; *) echo "   $n";; esac
done
echo "-- Desktop / Downloads:"
ls -A /c/Users/blender/Desktop /c/Users/blender/Downloads 2>/dev/null | grep -vE '^(desktop.ini|Blender 5.2.lnk|MCP 代理.lnk|)$|:$' | sed 's/^/   /'
echo "-- background processes:"; [ -n "$B" ] && echo "$B" | sed 's/^/   /' || echo "   none"
echo "-- service logs:"; for f in BlenderMCP-run ExecMCP-run UnityMCP-run; do printf '   %-15s %s\n' "$f" "$(du -h /c/Users/blender/$f/proxy.log 2>/dev/null | cut -f1)"; done
echo "-- disks:"; df -h /c /d 2>/dev/null | awk 'NR>1{print "   "$6" free "$4" of "$2}'
