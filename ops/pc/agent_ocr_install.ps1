# agent_ocr_install.ps1 - copy of D:\Projects\agent-ocr\install.ps1: venv from Blender's Python 3.13, packages from the Aliyun PyPI mirror.
$ErrorActionPreference = "Continue"
$D = "D:\Projects\agent-ocr"
$Log = "$D\install.log"
$Py = "D:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
$Idx = @("-i", "https://mirrors.aliyun.com/pypi/simple/", "--trusted-host", "mirrors.aliyun.com", "--extra-index-url", "https://pypi.tuna.tsinghua.edu.cn/simple/")
function Step($name, $exe, $argv) {
    Add-Content $Log ("`n===== {0} {1}" -f (Get-Date -Format "HH:mm:ss"), $name)
    $p = Start-Process -FilePath $exe -ArgumentList $argv -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$D\_o.txt" -RedirectStandardError "$D\_e.txt"
    Get-Content "$D\_o.txt", "$D\_e.txt" | Add-Content $Log
    Add-Content $Log ("exit {0}" -f $p.ExitCode)
    return $p.ExitCode
}
"start $(Get-Date)" | Set-Content $Log
if (-not (Test-Path "$D\.venv\Scripts\python.exe")) { Step "venv" $Py @("-m", "venv", "$D\.venv") | Out-Null }
$V = "$D\.venv\Scripts\python.exe"
Step "pip" $V (@("-m", "pip", "install", "-U", "pip") + $Idx) | Out-Null
Step "packages" $V (@("-m", "pip", "install", "paddleocr", "onnxruntime-gpu[cuda,cudnn]", "mss") + $Idx) | Out-Null
Step "freeze" $V @("-m", "pip", "list") | Out-Null
Add-Content $Log "INSTALL DONE"
Remove-Item "$D\_o.txt", "$D\_e.txt" -ErrorAction SilentlyContinue
