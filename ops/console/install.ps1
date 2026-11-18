# MCP 控制台 v2 + 浏览器 MCP 安装
# 在主账号的「管理员 PowerShell 7」里运行：
#   pwsh -ExecutionPolicy Bypass -File D:\Projects\mcp-console-stage\install.ps1
# 1 核对暂存文件的 SHA256  2 装 Playwright MCP 0.0.85 到 C:\Program Files\BlenderMCP\node
# 3 关旧控制台、备份 panel  4 替换 panel.py、agent.py、static\  5 给隧道加 wmcp.maimaiqiu.work 的域名记录
# 桌面快捷方式不用改。装完后告诉 Claude，它会重启 blender 账号里的代理（agent.py）。
#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$src = 'D:\Projects\mcp-console-stage'
$root = 'C:\Program Files\BlenderMCP'
$dst = Join-Path $root 'panel'
$tunnel = 'af64fe16-f93a-4202-ad5e-1b400e791398'
$manifest = [ordered]@{
    'console.py' = 'C5DBF8968935F27E0BFDBE144128B186F07A82FE70E4D5988C468CEA651E5DDE'
    'agent.py' = 'AB198837DA70CA546E2348D459A363DD2075FC7E9252F96E497DB91F2A173EA4'
    'static\index.html' = 'D384284F86E4DF2B818C45E67DEBA64573036405564872DBD9553C8A48B32A0D'
    'static\app.js' = '144824D11A13D2A7FB617F0071D8F9E9A04B24FA8279F294099D12E609176C51'
    'static\app.css' = 'A9ADD77613E2E8206D8BB8DB255BF11A987E4A57584B4AD531F39551FAB37314'
    'static\ds\tokens.css' = '8AFD13A1B5886093DC6C26485091BDDAA0FCC084D6B92EB3CD8588D4ACEE225F'
    'static\ds\components\bundle.css' = 'A742EA4FC3A26BAB0563C4FFE1B6626A27D02E2F9CC4278171529D956154E044'
    'static\ds\components\bundle.js' = '51A6F9C1AA8DD9A81959162923F16B9B99A373E7F7F30C193DC3FA2BEDFE3706'
    'static\ds\assets\Textures\button-texture.png' = '70D26BB7B15D818D1FD7C8A23BF9F689665BC6149E41C35181C64652401C2ED0'
    'static\ds\assets\Textures\confirm-texture.png' = '1FB7268FCED3E486CF7A95B35DF53A0C606F4F44AEB1B832E7494F72D5A41AD9'
    'static\ds\assets\Textures\pag-button-texture.png' = 'D2EF4F4380FA40F63FBC5595F045F06EB0DE3F6AA22A4DA33849F8D852E089BA'
    'static\ds\assets\Textures\points-bg.png' = 'ADB12CFFDAB0600D97A6EA3BB44F32D30ECEEDACA1A7C791F18F7E21DFB1B00A'
    'static\ds\assets\Textures\wave-bg.png' = '3991C0A79DA94123660F5EBD4BFE2080380D77C3D87C9312DB1E97DBB163ECF4'
}

Write-Host '1/5 核对文件……'
foreach ($k in $manifest.Keys) {
    $f = Join-Path $src $k
    if (-not (Test-Path $f)) { throw "缺少文件：$f" }
    if ((Get-FileHash $f -Algorithm SHA256).Hash -ne $manifest[$k]) { throw "文件和预期不一致，已停止安装：$k" }
}

Write-Host '2/5 安装 Playwright MCP 0.0.85……'
$npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
if (-not $npm) { $npm = 'D:\Program Files\npm.cmd' }
& $npm install -g '@playwright/mcp@0.0.85' --prefix (Join-Path $root 'node') --no-fund --no-audit
if ($LASTEXITCODE -ne 0) { throw 'npm 安装 Playwright MCP 失败' }
$pkg = Get-Content (Join-Path $root 'node\node_modules\@playwright\mcp\package.json') -Raw | ConvertFrom-Json
if ($pkg.version -ne '0.0.85') { throw "装上的版本是 $($pkg.version)，不是 0.0.85" }

Write-Host '3/5 关闭旧控制台并备份……'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'BlenderMCP\\panel\\panel\.py' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
$bak = "$dst.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
Copy-Item $dst $bak -Recurse
Write-Host "    备份在 $bak"

Write-Host '4/5 替换文件……'
Copy-Item (Join-Path $src 'console.py') (Join-Path $dst 'panel.py') -Force
Copy-Item (Join-Path $src 'agent.py') (Join-Path $dst 'agent.py') -Force
$static = Join-Path $dst 'static'
Remove-Item $static -Recurse -Force
foreach ($k in $manifest.Keys) {
    if ($k -in 'console.py', 'agent.py') { continue }
    $to = Join-Path $dst $k
    New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
    Copy-Item (Join-Path $src $k) $to -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $static 'ds\fonts') | Out-Null
$oldFonts = Join-Path $bak 'static\fonts'
if (-not (Test-Path $oldFonts)) { $oldFonts = Join-Path $bak 'static\ds\fonts' }
Copy-Item (Join-Path $oldFonts '*.woff2') (Join-Path $static 'ds\fonts') -Force

Write-Host '5/5 添加域名 wmcp.maimaiqiu.work……'
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe' }
& $cf tunnel route dns $tunnel wmcp.maimaiqiu.work
if ($LASTEXITCODE -ne 0) { Write-Warning '域名记录没加上（如果提示已存在，可以忽略）。' }

Write-Host ''
Write-Host '完成。请双击桌面上的「Blender MCP 控制台」打开新版，然后告诉 Claude 已装好。'
Write-Host "要退回旧版：把 $bak 改回 panel 即可。"
