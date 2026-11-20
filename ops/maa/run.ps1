# run.ps1 - run a maa-cli task on LDPlayer instance 0, in the blender account (PC).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\maa-cli\run.ps1 [-Task daily] [-KeepEmulator]
#
# Starts the emulator if needed, waits for Android, runs `maa run <Task> --batch`, closes the emulator
# (unless -KeepEmulator), and appends one line per run to D:\Projects\maa-cli\logs\runs.log.
# Refuses to run while any MAA GUI is open (either account) or while the emulator belongs to another session:
# two drivers on one emulator would fight over the screen. Exit code: maa's, or 90+ for a refusal.
# ASCII only: Windows PowerShell 5.1 reads BOM-less scripts in the ANSI code page.
param(
    [string]$Task = "daily",
    [switch]$KeepEmulator,
    [int]$BootTimeout = 180
)
$ErrorActionPreference = "Continue"   # native tools write to stderr; "Stop" would turn that into exceptions in PS 5.1
$Root = "D:\Projects\maa-cli"
$Maa = "D:\Projects\MAA\maa.exe"
$LD = "D:\leidian\LDPlayer9"
$Adb = "$LD\adb.exe"
$Logs = "$Root\logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$env:MAA_CONFIG_DIR = "$Root\config"
$env:MAA_STATE_DIR = "$Root\state"
$env:MAA_CACHE_DIR = "$Root\cache"
$env:MAA_DATA_DIR = "$Root\data"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runLog = "$Logs\runs.log"
$t0 = Get-Date

function Say($msg) { $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Task, $msg; Write-Output $line; Add-Content -Path $runLog -Value $line -Encoding UTF8 }
function LdRunning { (& "$LD\ldconsole.exe" isrunning --index 0 2>$null) -match "running" }

# one run at a time (a scheduled run and a manual one must not overlap)
$lock = $null
try { $lock = [System.IO.File]::Open("$Root\run.lock", 'OpenOrCreate', 'ReadWrite', 'None') }
catch { Say "REFUSED: another run.ps1 is running"; exit 91 }

try {
    $me = (Get-Process -Id $PID).SessionId
    $gui = Get-Process -Name MAA -ErrorAction SilentlyContinue
    if ($gui) { Say ("REFUSED: MAA GUI is open (session {0})" -f (($gui | ForEach-Object SessionId) -join ",")); exit 92 }
    $foreign = Get-Process -Name dnplayer, Ld9BoxHeadless -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -ne $me }
    if ($foreign) { Say "REFUSED: the emulator is running in another session"; exit 93 }

    $started = $false
    if (-not (LdRunning)) {
        & "$LD\ldconsole.exe" launch --index 0 | Out-Null
        $started = $true
    }
    $deadline = (Get-Date).AddSeconds($BootTimeout)
    do {
        Start-Sleep -Seconds 2
        $boot = (& $Adb -s emulator-5554 shell getprop sys.boot_completed 2>$null | Out-String).Trim()
    } while ($boot -ne "1" -and (Get-Date) -lt $deadline)
    if ($boot -ne "1") { Say "FAILED: Android did not finish booting in $BootTimeout s"; exit 94 }
    Say ("emulator ready ({0})" -f $(if ($started) { "started" } else { "was running" }))

    # skip Annihilation while this week's orundum reward is already full (25 sanity per run otherwise)
    if ($Task -eq "daily" -and (Test-Path "$Root\annihilation_gate.py")) {
        & "D:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" "$Root\annihilation_gate.py" 2>&1 | ForEach-Object { Say "gate: $_" }
    }
    # stage of the sanity farming task: first matching rule of sanity_plan.json (date, game-day weekday, inventory)
    if ($Task -eq "daily" -and (Test-Path "$Root\sanity_plan.py")) {
        & "D:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" "$Root\sanity_plan.py" 2>&1 | ForEach-Object { Say "plan: $_" }
    }
    # side-story first clears (EX/S, normal then raid) with prts.plus copilots, before the daily task spends the
    # sanity on farming. ev_run.py navigates by OCR (agent-ocr) and stops when sanity runs short.
    $ocrPy = "D:\Projects\agent-ocr\.venv\Scripts\python.exe"
    if ($Task -eq "daily" -and (Test-Path "$Root\ev_run.py") -and (Test-Path $ocrPy)) {
        $env:PYTHONIOENCODING = "utf-8"
        # the game has to be on its home screen first (wake.toml = StartUp only)
        Start-Process -FilePath $Maa -ArgumentList @("run", "wake", "--batch") -NoNewWindow -Wait `
            -RedirectStandardOutput "$Logs\$stamp-wake.out" -RedirectStandardError "$Logs\$stamp-wake.err" | Out-Null
        & $ocrPy "$Root\ev_run.py" 2>&1 | Out-Null       # it writes its own [ev] lines to runs.log
        & $ocrPy "D:\Projects\agent-ocr\ocr.py" --stop --url http://127.0.0.1:8767 2>&1 | Out-Null   # free the GPU memory
    }
    $maaLog = "$Logs\$stamp-$Task.log"
    $asst = "$Root\state\debug\asst.log"
    $offset = 0; if (Test-Path $asst) { $offset = (Get-Item $asst).Length }
    # Start-Process keeps maa's stderr out of PowerShell's error stream (PS 5.1 wraps every stderr line of a
    # native command as an error record); stdout holds the task summary, stderr the diagnostics.
    $p = Start-Process -FilePath $Maa -ArgumentList @("run", $Task, "--batch", "--log-file=$maaLog") -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput "$Logs\$stamp-$Task.out" -RedirectStandardError "$Logs\$stamp-$Task.err"
    $code = $p.ExitCode
    # Security Deployment sweep with proxy cards that expire within 2 days (after annihilation took its cards).
    # tower_sweep.py checks every screen by OCR, never taps the top bar, and leaves by the back key only.
    if ($Task -eq "daily" -and (Test-Path "$Root\tower_sweep.py") -and (Test-Path $ocrPy)) {
        $env:PYTHONIOENCODING = "utf-8"
        & $ocrPy "$Root\tower_sweep.py" 2>&1 | Out-Null    # it writes its own [tower] lines to runs.log
    }

    if (-not $KeepEmulator) { & "$LD\ldconsole.exe" quit --index 0 | Out-Null }
    # Depot / OperBox results only exist in MaaCore's log: export them as JSON (same format as the GUI's data\)
    if (Test-Path $asst) {
        $py = "D:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
        & $py "$Root\export_data.py" $asst $offset "$Root\export" 2>&1 | ForEach-Object { Say "export: $_" }
    }
    # Skland: skills, mastery, modules, base layout and the full inventory (arknights/skland/sync.mjs).
    # Exit 3 means the saved login is gone and a new QR login (login.mjs) is needed.
    if (Test-Path "D:\Projects\skland\sync.mjs") {
        Push-Location "D:\Projects\skland"
        & "D:\Program Files\node.exe" sync.mjs 2>&1 | ForEach-Object { Say "skland: $_" }
        Pop-Location
        if (Test-Path "$Root\after_rebuild.py") {
            & "D:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" "$Root\after_rebuild.py" 2>&1 | ForEach-Object { Say "rebuild: $_" }
        }
    }
    Say ("maa exit {0} after {1:n0} s; log {2}" -f $code, ((Get-Date) - $t0).TotalSeconds, $maaLog)
    exit $code
}
finally {
    if ($lock) { $lock.Close() }
}
