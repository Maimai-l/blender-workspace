# ev_run.ps1 - start ev_run.py detached (agent-ocr venv); output in logs\ev_run.out / .err, summary lines in logs\runs.log.
param([switch]$Dry)
$a = @("D:\Projects\maa-cli\ev_run.py"); if ($Dry) { $a += "--dry" }
$env:PYTHONIOENCODING = "utf-8"
Start-Process -FilePath "D:\Projects\agent-ocr\.venv\Scripts\python.exe" -ArgumentList $a -WorkingDirectory "D:\Projects\maa-cli" `
    -WindowStyle Hidden -RedirectStandardOutput "D:\Projects\maa-cli\logs\ev_run.out" -RedirectStandardError "D:\Projects\maa-cli\logs\ev_run.err"
