# open_game.ps1 - open LDPlayer 0 and the game to its home screen WITHOUT run.ps1 (no lock, no phone notification),
# for recording or testing UI flows (.claude/skills/arknights-ui-flow). Leaves the emulator running; close it with
#   D:\leidian\LDPlayer9\ldconsole.exe quit --index 0
# Writes state\open_game.done when the game is up. ASCII only (Windows PowerShell 5.1).
$Root = 'D:\Projects\maa-cli'
$env:MAA_CONFIG_DIR = "$Root\config"; $env:MAA_STATE_DIR = "$Root\state"
$env:MAA_CACHE_DIR = "$Root\cache"; $env:MAA_DATA_DIR = "$Root\data"
Remove-Item "$Root\state\open_game.done" -ErrorAction SilentlyContinue
if (Get-Process -Name MAA -ErrorAction SilentlyContinue) { 'MAA is running (a run.ps1 or the GUI); not touching the emulator' | Set-Content "$Root\state\open_game.done"; exit 1 }
& 'D:\leidian\LDPlayer9\ldconsole.exe' launch --index 0 | Out-Null
$deadline = (Get-Date).AddSeconds(180)
do { Start-Sleep 2; $b = (& 'D:\leidian\LDPlayer9\adb.exe' -s emulator-5554 shell getprop sys.boot_completed 2>$null | Out-String).Trim() } while ($b -ne '1' -and (Get-Date) -lt $deadline)
& 'D:\Projects\MAA\maa.exe' run wake --batch *> "$Root\logs\open_game.out"
'ok' | Set-Content "$Root\state\open_game.done"
