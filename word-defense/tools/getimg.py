#!/usr/bin/env python3
"""Fetch images from the Windows machine (resized to JPEG there) into a local folder: getimg.py OUTDIR REMOTE_GLOB [MAXW]"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import mcpc

out, pattern = sys.argv[1], sys.argv[2]
maxw = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
os.makedirs(out, exist_ok=True)
tmp = r"C:\Users\blender\ExecMCP\shots"
ps = r'''
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path "%TMP%" | Out-Null
Get-ChildItem -Path "%TMP%" -Filter *.jpg | Remove-Item
$codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq "image/jpeg" }
$ep = New-Object System.Drawing.Imaging.EncoderParameters 1
$ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), 86L
foreach ($f in (Get-ChildItem -Path "%PAT%" -ErrorAction SilentlyContinue | Sort-Object Name)) {
  $img = [System.Drawing.Image]::FromFile($f.FullName)
  $w = [Math]::Min(%MAXW%, $img.Width); $h = [int]($img.Height * $w / $img.Width)
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.DrawImage($img, 0, 0, $w, $h)
  $p = Join-Path "%TMP%" ($f.BaseName + ".jpg")
  $bmp.Save($p, $codec, $ep)
  Write-Output ("JPG " + $p)
  $g.Dispose(); $bmp.Dispose(); $img.Dispose()
}
'''.replace("%PAT%", pattern).replace("%MAXW%", str(maxw)).replace("%TMP%", tmp)
res = mcpc.run_ps(ps, 110000)
files = [l[4:].strip() for l in res.splitlines() if l.startswith("JPG ")]
if not files:
    print(res[:2000])
for f in files:
    name = f.split("\\")[-1]
    mcpc.pull(f, os.path.join(out, name))
