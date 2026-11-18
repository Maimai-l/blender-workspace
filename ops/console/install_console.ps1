# MCP 控制台 v2 安装（第一阶段：连接状态 + Clash 联动）
# 在主账号的「管理员 PowerShell 7」里运行：
#   pwsh -ExecutionPolicy Bypass -File D:\Projects\mcp-console-stage\install_console.ps1
# 做的事：核对暂存文件的 SHA256 → 关掉正在运行的旧控制台 → 备份 C:\Program Files\BlenderMCP\panel
# → 用新文件替换 panel.py 和 static\（字体从旧版 static\fonts 复制，内容相同）。桌面快捷方式不用改。
#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$src = 'D:\Projects\mcp-console-stage'
$dst = 'C:\Program Files\BlenderMCP\panel'
$manifest = [ordered]@{
    'console.py' = 'D8A2D0E857039E4084043981F5ED3014BEFAD2B64B139A7D26586CF042E2FCED'
    'static\index.html' = '161DAD00CF60DBFEA4A45C536137504DA19F65FDA4B253D7C80F3A8CA3CA7F2B'
    'static\app.js' = '8B509BAC9A31EF9CFA38B5DA2692473463C70644FFF839E256376BD134667DDE'
    'static\app.css' = '97608801AC3C0F2ED702986197C63567D80D18780BE80378704E721CCEB83DB7'
    'static\ds\tokens.css' = '8AFD13A1B5886093DC6C26485091BDDAA0FCC084D6B92EB3CD8588D4ACEE225F'
    'static\ds\components\bundle.css' = 'A742EA4FC3A26BAB0563C4FFE1B6626A27D02E2F9CC4278171529D956154E044'
    'static\ds\components\bundle.js' = '51A6F9C1AA8DD9A81959162923F16B9B99A373E7F7F30C193DC3FA2BEDFE3706'
    'static\ds\assets\Textures\button-texture.png' = '70D26BB7B15D818D1FD7C8A23BF9F689665BC6149E41C35181C64652401C2ED0'
    'static\ds\assets\Textures\confirm-texture.png' = '1FB7268FCED3E486CF7A95B35DF53A0C606F4F44AEB1B832E7494F72D5A41AD9'
    'static\ds\assets\Textures\pag-button-texture.png' = 'D2EF4F4380FA40F63FBC5595F045F06EB0DE3F6AA22A4DA33849F8D852E089BA'
    'static\ds\assets\Textures\points-bg.png' = 'ADB12CFFDAB0600D97A6EA3BB44F32D30ECEEDACA1A7C791F18F7E21DFB1B00A'
    'static\ds\assets\Textures\wave-bg.png' = '3991C0A79DA94123660F5EBD4BFE2080380D77C3D87C9312DB1E97DBB163ECF4'
}

Write-Host '1/4 核对文件……'
foreach ($k in $manifest.Keys) {
    $f = Join-Path $src $k
    if (-not (Test-Path $f)) { throw "缺少文件：$f" }
    $h = (Get-FileHash $f -Algorithm SHA256).Hash
    if ($h -ne $manifest[$k]) { throw "文件和预期不一致，已停止安装：$k" }
}

Write-Host '2/4 关闭正在运行的控制台……'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'BlenderMCP\\panel\\panel\.py' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

Write-Host '3/4 备份旧版……'
$bak = "$dst.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
Copy-Item $dst $bak -Recurse
Write-Host "    备份在 $bak"

Write-Host '4/4 安装新版……'
Copy-Item (Join-Path $src 'console.py') (Join-Path $dst 'panel.py') -Force
$static = Join-Path $dst 'static'
$fonts = Join-Path $bak 'static\fonts'
Remove-Item $static -Recurse -Force
foreach ($k in $manifest.Keys) {
    if ($k -eq 'console.py') { continue }
    $to = Join-Path $dst $k
    New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
    Copy-Item (Join-Path $src $k) $to -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $static 'ds\fonts') | Out-Null
Copy-Item (Join-Path $fonts '*.woff2') (Join-Path $static 'ds\fonts') -Force
Write-Host ''
Write-Host '完成。请双击桌面上的「Blender MCP 控制台」打开新版。'
Write-Host "要退回旧版：把 $bak 改回 panel 即可。"
