# 临时授权（第二阶段）安装包
# 在主账号的「管理员 PowerShell 7」里运行：
#   pwsh -ExecutionPolicy Bypass -File D:\Projects\mcp-console-stage\tempauth\install.ps1
#
# 做的事（可以重复运行，已经做过的会跳过）：
#  1 核对暂存文件的 SHA256
#  2 沙盒账号 aitemp 和基线权限：账号、隐藏、禁止远程和网络登录、文件拒绝项、防火墙规则（第三轮测试的那一套）；
#    撤掉测试包给 D:\Projects\aitemp-test 加的允许项
#  3 编译授权助手（.NET Framework 自带的 csc），装到 C:\Program Files\BlenderMCP\tempauth\，注册并启动 Windows 服务 AITempHelper
#  4 装临时授权网关 gateway.py（由 blender 账号里的 agent.py 启动）
#  5 更新控制台（panel.py、agent.py、页面文件），旧版备份在 panel.bak-<时间>
#  6 给隧道加 tmcp.maimaiqiu.work 的域名记录
# 装完：双击桌面上的「Blender MCP 控制台」，在“连接状态”页把外网访问关闭再开启一次（让隧道加载新域名），然后告诉 Claude。
# 只更新授权助手（改了 AitempHelper.cs 时）：同一条命令后面加 -HelperOnly，只做第 1、3 步。
# 只更新网关和控制台（gateway.py、panel.py、agent.py、页面文件）：加 -ConsoleOnly，只做第 1、4、5 步。
#Requires -RunAsAdministrator
param([switch]$HelperOnly, [switch]$ConsoleOnly)
$ErrorActionPreference = 'Stop'
$src = Split-Path -Parent $MyInvocation.MyCommand.Path      # D:\Projects\mcp-console-stage\tempauth
$root = 'C:\Program Files\BlenderMCP'
$dst = Join-Path $root 'tempauth'
$panel = Join-Path $root 'panel'
$tunnel = 'af64fe16-f93a-4202-ad5e-1b400e791398'
$user = 'aitemp'
$svcName = 'AITempHelper'
$manifest = [ordered]@{
    'helper\AitempHelper.cs' = '@@helper/AitempHelper.cs'
    'helper\wfp.cs' = '@@helper/wfp.cs'
    'gateway\gateway.py' = '@@gateway/gateway.py'
    'denywrite.ps1' = '@@denywrite.ps1'
    'console\console.py' = '@@console/console.py'
    'console\agent.py' = '@@console/agent.py'
    'console\static\index.html' = '@@console/static/index.html'
    'console\static\app.js' = '@@console/static/app.js'
    'console\static\app.css' = '@@console/static/app.css'
    'console\static\grants.js' = '@@console/static/grants.js'
}
$programDirs = @('Program Files', 'Program Files (x86)', 'ProgramData')
$skipDirs = @('$RECYCLE.BIN', 'System Volume Information')
$protected = @('D:\Projects\maa-cli', 'D:\Projects\skland', 'C:\ProgramData\BlenderMCP')
$profiles = @('C:\Users\Administrator', 'C:\Users\blender')
$hideKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList'

function Set-AitempAcl([string[]]$a) { $o = & icacls.exe @a 2>&1; if ($LASTEXITCODE -ne 0) { throw "icacls $($a -join ' ') 失败：$o" } }
# 程序目录只拒绝写入和删除：不能用 icacls（它总带 SYNCHRONIZE，拒绝后连程序都运行不了），交给 denywrite.ps1（.NET，Windows PowerShell 5.1）
function Set-AitempDenyWrite([string]$path, [string]$sid) {
    $o = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $src 'denywrite.ps1') -Path $path -Sid $sid 2>&1
    if ($LASTEXITCODE -ne 0) { throw "denywrite.ps1 失败：$o" }
}
function Test-AitempDeny([string]$path, [string]$sid) {
    foreach ($r in (Get-Acl -LiteralPath $path).Access) {
        if ($r.IsInherited -or $r.AccessControlType -ne 'Deny') { continue }
        try { if ($r.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $sid) { return $true } } catch { }
    }
    return $false
}
function Set-AitempUserRights([string]$sid) {
    $inf = Join-Path $env:TEMP 'aitemp_rights.inf'; $db = Join-Path $env:TEMP 'aitemp_rights.sdb'
    secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
    $lines = Get-Content $inf -Encoding Unicode
    foreach ($right in 'SeDenyNetworkLogonRight', 'SeDenyRemoteInteractiveLogonRight') {
        $i = [array]::FindIndex([string[]]$lines, [Predicate[string]]{ param($l) $l -like "$right =*" })
        $cur = if ($i -ge 0) { ($lines[$i] -split '=', 2)[1].Trim() -split ',' | Where-Object { $_ } } else { @() }
        $cur = @($cur | Where-Object { $_ -ne "*$sid" }) + "*$sid"
        $line = "$right = " + ($cur -join ',')
        if ($i -ge 0) { $lines[$i] = $line } else { $j = [array]::IndexOf([string[]]$lines, '[Privilege Rights]'); $lines = $lines[0..$j] + $line + $lines[($j + 1)..($lines.Count - 1)] }
    }
    $lines | Set-Content $inf -Encoding Unicode
    secedit /configure /db $db /cfg $inf /areas USER_RIGHTS /quiet | Out-Null
    Remove-Item $inf, $db -ErrorAction SilentlyContinue
}

Write-Host '1/6 核对文件……'
foreach ($k in $manifest.Keys) {
    $f = Join-Path $src $k
    if (-not (Test-Path -LiteralPath $f)) { throw "缺少文件：$f" }
    if ((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash -ne $manifest[$k]) { throw "文件和预期不一致，已停止安装：$k" }
}

if ($HelperOnly -or $ConsoleOnly) { Write-Host '2/6 跳过' } else {
Write-Host '2/6 沙盒账号和基线权限……'
if (-not (Get-LocalUser $user -ErrorAction SilentlyContinue)) {
    $pw = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(30)) + 'aA1!'
    New-LocalUser $user -Password (ConvertTo-SecureString $pw -AsPlainText -Force) -PasswordNeverExpires -UserMayNotChangePassword `
        -AccountNeverExpires -FullName 'AITemp' -Description 'MCP 临时授权沙盒账号' | Out-Null
    Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $user
    Write-Host '    新建了 aitemp（密码由授权助手每次启动时随机重设，不落盘）'
}
$sid = (Get-LocalUser $user).SID.Value
New-Item $hideKey -Force | Out-Null
Set-ItemProperty $hideKey -Name $user -Value 0 -Type DWord
Set-AitempUserRights $sid
foreach ($d in Get-ChildItem D:\ -Directory -Force | Where-Object { $_.Name -notin $skipDirs }) {
    if (Test-AitempDeny $d.FullName $sid) { continue }
    $s = Get-Date
    if ($d.Name -in $programDirs) { Set-AitempDenyWrite $d.FullName $sid; $kind = '拒绝写入' } else { Set-AitempAcl @($d.FullName, '/deny', "*${sid}:(OI)(CI)F"); $kind = '拒绝读写' }
    Write-Host ("    {0}：{1}（{2:N1}s）" -f $d.FullName, $kind, ((Get-Date) - $s).TotalSeconds)
}
if (-not (Test-AitempDeny 'D:\' $sid)) { Set-AitempAcl @('D:\', '/deny', "*${sid}:(AD,WD)"); Set-AitempAcl @('D:\', '/deny', "*${sid}:(OI)(NP)(IO)F") }
if (-not (Test-AitempDeny 'C:\' $sid)) { Set-AitempAcl @('C:\', '/deny', "*${sid}:(AD,WD)") }
foreach ($p in $protected) { if ((Test-Path $p) -and -not (Test-AitempDeny $p $sid)) { Set-AitempAcl @($p, '/deny', "*${sid}:(OI)(CI)F") } }
foreach ($p in $profiles) { if ((Test-Path $p) -and -not (Test-AitempDeny $p $sid)) { Set-AitempAcl @($p, '/deny', "*${sid}:F") } }
if (-not (Get-NetFirewallRule -Name 'AITemp-Direct' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'AITemp-Direct' -DisplayName 'AITemp：不许直连外网' -Direction Outbound -Action Block -LocalUser "D:(A;;CC;;;$sid)" | Out-Null
}
if (Test-Path 'D:\Projects\aitemp-test') { & icacls.exe 'D:\Projects\aitemp-test' /remove:g "*$sid" 2>&1 | Out-Null }
Write-Host "    aitemp 就绪（SID $sid）"
}

if ($ConsoleOnly) { Write-Host '3/6 跳过' } else {
Write-Host '3/6 编译并安装授权助手……'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
$build = Join-Path $env:TEMP ('aitemp-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $build | Out-Null
Copy-Item (Join-Path $src 'helper\*.cs') $build
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$out = & $csc /nologo /target:exe /platform:x64 /optimize+ "/out:$build\aitemp-helper.exe" /r:System.ServiceProcess.dll /r:System.Web.Extensions.dll "$build\AitempHelper.cs" "$build\wfp.cs" 2>&1
if ($LASTEXITCODE -ne 0) { throw "编译失败：$out" }
$svc = Get-Service $svcName -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -ne 'Stopped') { Stop-Service $svcName -Force; $svc.WaitForStatus('Stopped', '00:00:20') }
Copy-Item "$build\aitemp-helper.exe" (Join-Path $dst 'aitemp-helper.exe') -Force
Copy-Item (Join-Path $src 'helper\*.cs') $dst -Force
Remove-Item $build -Recurse -Force
$bin = '"' + (Join-Path $dst 'aitemp-helper.exe') + '" --client=blender'
if (-not $svc) {
    New-Service -Name $svcName -BinaryPathName $bin -DisplayName 'MCP 临时授权助手' -StartupType Automatic `
        -Description '以沙盒账号 aitemp 执行临时授权的命令；只接受 blender 账号经命名管道 aitemp-helper 的请求。' | Out-Null
}
& sc.exe failure $svcName reset= 86400 actions= restart/5000/restart/5000/restart/60000 | Out-Null
Start-Service $svcName
(Get-Service $svcName).WaitForStatus('Running', '00:00:20')
Start-Sleep -Seconds 2
$log = 'C:\ProgramData\BlenderMCP\aitemp-helper.log'
if (Test-Path $log) { Get-Content $log -Tail 3 | ForEach-Object { Write-Host "    $_" } }
if ((Get-Content $log -Tail 5 -ErrorAction SilentlyContinue) -match 'start failed') { Write-Warning '授权助手启动时报错（见上面的日志），装完告诉 Claude。' }

}
if ($HelperOnly) { Write-Host ''; Write-Host '完成：授权助手已更新并重启。告诉 Claude 即可。'; return }

Write-Host '4/6 安装临时授权网关……'
Copy-Item (Join-Path $src 'gateway\gateway.py') (Join-Path $dst 'gateway.py') -Force

Write-Host '5/6 更新控制台……'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'BlenderMCP\\panel\\panel\.py' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
$bak = "$panel.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
Copy-Item $panel $bak -Recurse
Copy-Item (Join-Path $src 'console\console.py') (Join-Path $panel 'panel.py') -Force
Copy-Item (Join-Path $src 'console\agent.py') (Join-Path $panel 'agent.py') -Force
foreach ($f in 'index.html', 'app.js', 'app.css', 'grants.js') { Copy-Item (Join-Path $src "console\static\$f") (Join-Path $panel "static\$f") -Force }
Write-Host "    旧版备份在 $bak"
if ($ConsoleOnly) { Write-Host ''; Write-Host '完成：双击桌面上的「Blender MCP 控制台」打开新版，然后告诉 Claude（它会重启网关）。'; return }

Write-Host '6/6 添加域名 tmcp.maimaiqiu.work……'
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe' }
& $cf tunnel route dns $tunnel tmcp.maimaiqiu.work
if ($LASTEXITCODE -ne 0) { Write-Warning '域名记录没加上（如果提示已存在，可以忽略）。' }

Write-Host ''
Write-Host '完成。接下来：'
Write-Host '  1. 双击桌面上的「Blender MCP 控制台」打开新版；'
Write-Host '  2. 在“连接状态”页把外网访问关闭再开启一次，让隧道加载 tmcp 这个新域名；'
Write-Host '  3. 告诉 Claude 已装好，它会重启 blender 账号里的代理并做验收测试。'
Write-Host "要退回旧版控制台：把 $bak 改回 panel。要停用临时授权：Stop-Service $svcName，并把服务设为禁用。"
