# start_ocr.ps1 - start the agent-ocr server in the background (port 8767; models from ModelScope).
$env:PADDLE_PDX_MODEL_SOURCE = "modelscope"
$env:AGENT_OCR_PORT = "8767"
$env:PYTHONIOENCODING = "utf-8"
$D = "D:\Projects\agent-ocr"
Start-Process -FilePath "$D\.venv\Scripts\python.exe" -ArgumentList @("$D\ocr_server.py", "--port", "8767") -WorkingDirectory $D `
    -WindowStyle Hidden -RedirectStandardOutput "$D\ocr_server.log" -RedirectStandardError "$D\ocr_server.err.log"
