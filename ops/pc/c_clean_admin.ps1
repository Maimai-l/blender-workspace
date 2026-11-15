# c_clean_admin.ps1 - delete regenerable caches on C: that the blender account cannot reach. Run once as the main
# account (an administrator PowerShell, for the ProgramData parts):
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\maa-cli\c_clean_admin.ps1 [-WinSxS]
# Only caches and temp files that programs recreate on demand, plus the remains of hermes (user request). Nothing in
# Docker, NetEase, games or other apps.
# -WinSxS also runs the Windows component store cleanup (DISM, 10-30 minutes; old update files only).
# Log: D:\Projects\maa-cli\state\c_clean.log. ASCII only (Windows PowerShell 5.1 reads BOM-less files as ANSI).
param([switch]$WinSxS)
$log = "D:\Projects\maa-cli\state\c_clean.log"
$h = $env:USERPROFILE
function Free { [math]::Round((Get-PSDrive C).Free / 1GB, 2) }
function Clean($path, $minAgeHours = 0) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    $cut = (Get-Date).AddHours(-$minAgeHours)
    $before = Free
    Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cut } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue      # files in use are skipped
    "{0}  freed {1,6:n2} GB  {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), ((Free) - $before), $path | Tee-Object -FilePath $log -Append
}
"=== c_clean_admin.ps1 as $env:USERNAME, C: free $(Free) GB" | Tee-Object -FilePath $log -Append
Clean "$h\AppData\Local\Temp" 24                       # temp files older than one day
Clean "$h\AppData\Local\CrashDumps"
Clean "$h\AppData\Local\NVIDIA\DXCache"                # shader caches: rebuilt by the driver
Clean "$h\AppData\Local\NVIDIA\GLCache"
Clean "$h\AppData\Local\D3DSCache"
Clean "C:\ProgramData\NVIDIA Corporation\Downloader"   # downloaded driver installers
Clean "$h\AppData\Local\uv\cache"                      # package caches: re-downloaded when needed
Clean "$h\AppData\Local\npm-cache"
Clean "$h\AppData\Local\pip\cache"
foreach ($u in "unityhub-updater", "obsidian-updater", "phiedit2573-updater", "kimi-desktop-updater", "dsh-desktop-updater", "claude-desktop-updater", "open-webui-updater") {
    Clean "$h\AppData\Local\$u"                        # old installer downloads
}
# hermes (AI agent installed 2026-10-04, removed on the user's request 2026-11-15): the blender account already
# deleted what it could reach; here the bundled toolchains, plus shortcuts, startup entries, tasks and PATH entries.
Get-Process | Where-Object { $_.Path -like "*\hermes\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
$before = Free
Remove-Item -LiteralPath "$h\AppData\Local\hermes" -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem "$h\AppData\Roaming\Microsoft\Windows\Start Menu", "C:\ProgramData\Microsoft\Windows\Start Menu", "$h\Desktop" `
    -Recurse -Force -Filter "*hermes*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match "hermes" } | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue
$run = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
(Get-ItemProperty $run -ErrorAction SilentlyContinue).PSObject.Properties | Where-Object { "$($_.Value)" -match "hermes" } |
    ForEach-Object { Remove-ItemProperty $run -Name $_.Name -ErrorAction SilentlyContinue }
$p = [Environment]::GetEnvironmentVariable("Path", "User")
if ($p -match "hermes") { [Environment]::SetEnvironmentVariable("Path", (($p -split ";") | Where-Object { $_ -and $_ -notmatch "hermes" }) -join ";", "User") }
"{0}  freed {1,6:n2} GB  hermes (folder {2}, shortcuts, startup, tasks, PATH)" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), ((Free) - $before), `
    $(if (Test-Path "$h\AppData\Local\hermes") { "NOT fully removed" } else { "removed" }) | Tee-Object -FilePath $log -Append

if ($WinSxS) {
    $before = Free
    Dism.exe /Online /Cleanup-Image /StartComponentCleanup | Out-Null
    "{0}  freed {1,6:n2} GB  WinSxS component cleanup" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), ((Free) - $before) | Tee-Object -FilePath $log -Append
}
"=== done, C: free $(Free) GB" | Tee-Object -FilePath $log -Append
