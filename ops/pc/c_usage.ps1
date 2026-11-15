# c_usage.ps1 - READ-ONLY size report of C: for the main (Administrator) account. Deletes nothing.
# The blender account cannot read most of C:\Users\Administrator\AppData, so run this once as the main account:
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\maa-cli\c_usage.ps1
# Writes D:\Projects\maa-cli\state\c_usage.txt (the maintenance session reads it from there). ASCII only.
$out = "D:\Projects\maa-cli\state\c_usage.txt"
function Size($p) {
    $s = 0
    try { $s = (Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum } catch {}
    if (-not $s) { $s = 0 }
    return [math]::Round($s / 1GB, 2)
}
function Report($title, $dirs) {
    "== $title" | Add-Content $out -Encoding UTF8
    $dirs | ForEach-Object { [pscustomobject]@{ GB = (Size $_.FullName); Path = $_.FullName } } |
        Sort-Object GB -Descending | Select-Object -First 25 | ForEach-Object { "{0,8:n2}  {1}" -f $_.GB, $_.Path } | Add-Content $out -Encoding UTF8
}
"C: usage report $(Get-Date)  run as $env:USERNAME" | Set-Content $out -Encoding UTF8
$d = Get-PSDrive C; "C: used {0:n1} GB, free {1:n1} GB" -f ($d.Used / 1GB), ($d.Free / 1GB) | Add-Content $out -Encoding UTF8
$h = $env:USERPROFILE
Report "AppData\Local" (Get-ChildItem "$h\AppData\Local" -Directory -Force -ErrorAction SilentlyContinue)
Report "AppData\Roaming" (Get-ChildItem "$h\AppData\Roaming" -Directory -Force -ErrorAction SilentlyContinue)
Report "AppData\LocalLow" (Get-ChildItem "$h\AppData\LocalLow" -Directory -Force -ErrorAction SilentlyContinue)
Report "C:\ProgramData" (Get-ChildItem "C:\ProgramData" -Directory -Force -ErrorAction SilentlyContinue)
Report "C:\Program Files" (Get-ChildItem "C:\Program Files" -Directory -Force -ErrorAction SilentlyContinue)
Report "C:\Program Files (x86)" (Get-ChildItem "C:\Program Files (x86)" -Directory -Force -ErrorAction SilentlyContinue)
Report "C:\Users" (Get-ChildItem "C:\Users" -Directory -Force -ErrorAction SilentlyContinue)
"== Windows components" | Add-Content $out -Encoding UTF8
foreach ($p in "C:\Windows\SoftwareDistribution\Download", "C:\Windows\Temp", "C:\Windows\Installer", "C:\Windows\WinSxS", "C:\Windows\Logs") {
    "{0,8:n2}  {1}" -f (Size $p), $p | Add-Content $out -Encoding UTF8
}
"== WSL / Docker disks" | Add-Content $out -Encoding UTF8
Get-ChildItem "$h\AppData\Local" -Recurse -Force -Include *.vhdx -ErrorAction SilentlyContinue |
    ForEach-Object { "{0,8:n2}  {1}" -f ($_.Length / 1GB), $_.FullName } | Add-Content $out -Encoding UTF8
"DONE" | Add-Content $out -Encoding UTF8
