# copilot.ps1 - run prts.plus copilot jobs with maa-cli on LDPlayer instance 0, in the blender account (PC).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\maa-cli\copilot.ps1 -Uri prts://109538,prts://109554 [-Raid normal|raid|both] [-KeepEmulator]
#
# Same guards as run.ps1 (one run at a time, no MAA GUI, emulator in this session). Several URIs make maa-cli
# navigate to each stage and build the squad itself; one URI gets --formation added. Appends to logs\runs.log.
# ASCII only: Windows PowerShell 5.1 reads BOM-less scripts in the ANSI code page.
param(
    [Parameter(Mandatory = $true)][string]$Uri,
    [string]$Raid = "normal",
    [switch]$KeepEmulator,
    [int]$BootTimeout = 180
)
$ErrorActionPreference = "Continue"
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
function Say($msg) { $line = "{0} [copilot] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg; Write-Output $line; Add-Content -Path $runLog -Value $line -Encoding UTF8 }
function LdRunning { (& "$LD\ldconsole.exe" isrunning --index 0 2>$null) -match "running" }

$lock = $null
try { $lock = [System.IO.File]::Open("$Root\run.lock", 'OpenOrCreate', 'ReadWrite', 'None') }
catch { Say "REFUSED: another run is in progress"; exit 91 }
try {
    $me = (Get-Process -Id $PID).SessionId
    if (Get-Process -Name MAA -ErrorAction SilentlyContinue) { Say "REFUSED: MAA GUI is open"; exit 92 }
    if (Get-Process -Name dnplayer, Ld9BoxHeadless -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -ne $me }) { Say "REFUSED: the emulator is running in another session"; exit 93 }
    if (-not (LdRunning)) { & "$LD\ldconsole.exe" launch --index 0 | Out-Null }
    $deadline = (Get-Date).AddSeconds($BootTimeout)
    do { Start-Sleep -Seconds 2; $boot = (& $Adb -s emulator-5554 shell getprop sys.boot_completed 2>$null | Out-String).Trim() } while ($boot -ne "1" -and (Get-Date) -lt $deadline)
    if ($boot -ne "1") { Say "FAILED: Android did not finish booting"; exit 94 }

    $uris = @($Uri -split '[,\s]+' | Where-Object { $_ })
    $args2 = @("copilot") + $uris + @("--raid", $Raid, "--log-file=$Logs\$stamp-copilot.log")
    if ($uris.Count -eq 1) { $args2 += "--formation" }
    Say ("start {0} raid={1}" -f ($uris -join ","), $Raid)
    $p = Start-Process -FilePath $Maa -ArgumentList $args2 -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput "$Logs\$stamp-copilot.out" -RedirectStandardError "$Logs\$stamp-copilot.err"
    if (-not $KeepEmulator) { & "$LD\ldconsole.exe" quit --index 0 | Out-Null }
    Say ("maa exit {0} after {1:n0} s; log {2}" -f $p.ExitCode, ((Get-Date) - $t0).TotalSeconds, "$Logs\$stamp-copilot.log")
    exit $p.ExitCode
}
finally { if ($lock) { $lock.Close() } }
