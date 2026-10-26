#!/usr/bin/env python3
"""Fetch images from the Windows machine (resized to JPEG there) into a local folder: getimg.py OUTDIR REMOTE_GLOB [MAXW]"""
import base64, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import mcpc
out, pattern = sys.argv[1], sys.argv[2]
maxw = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
os.makedirs(out, exist_ok=True)
ps = r'''
Add-Type -AssemblyName System.Drawing
$files = Get-ChildItem -Path "%PAT%" -ErrorAction SilentlyContinue | Sort-Object Name
foreach ($f in $files) {
  $img = [System.Drawing.Image]::FromFile($f.FullName)
  $w = [Math]::Min(%MAXW%, $img.Width); $h = [int]($img.Height * $w / $img.Width)
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.DrawImage($img, 0, 0, $w, $h)
  $ms = New-Object System.IO.MemoryStream
  $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
  $ep = New-Object System.Drawing.Imaging.EncoderParameters 1
  $ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), 86L
  $bmp.Save($ms, $codec, $ep)
  Write-Output ("IMG " + $f.BaseName + " " + [Convert]::ToBase64String($ms.ToArray()))
  $g.Dispose(); $bmp.Dispose(); $img.Dispose()
}
'''.replace('%PAT%', pattern).replace('%MAXW%', str(maxw))
listing = mcpc.run_exec('Get-ChildItem -Path "%s" -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object { "F " + $_.FullName }' % pattern)
files = [l[2:].strip() for l in listing.splitlines() if l.startswith("F ")]
n = 0
for f in files:
    res = mcpc.run_exec(ps.replace(pattern, f), timeout_ms=85000)
    for line in res.splitlines():
        if line.startswith("IMG "):
            _, name, b64 = line.split(" ", 2)
            p = os.path.join(out, name + ".jpg")
            open(p, "wb").write(base64.b64decode(b64.strip()))
            print(p, os.path.getsize(p))
            n += 1
if n == 0:
    print(listing[:2000])
