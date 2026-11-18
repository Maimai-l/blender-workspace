# 临时授权：沙盒账号与权限方案测试包（《MCP 控制台需求》5.7）
# 在主账号的「管理员 PowerShell 7」里运行：
#   pwsh -ExecutionPolicy Bypass -File D:\Projects\mcp-console-stage\tempauth-test\aitemp_test.ps1
# 撤掉这次的全部改动（账号、权限、防火墙规则、WFP 过滤器）：同一条命令后面加 -Undo
#
# 做的事：建隐藏的标准用户 aitemp（禁止远程桌面和网络登录，密码每次随机、不落盘）→ 按 5.2 加文件权限
# → 按 5.4 加防火墙规则 → 建测试用的授权文件夹 D:\Projects\aitemp-test → 以 aitemp 身份分「断网」「联网」两轮跑检查
# → 撤销授权再查一次 → 报告写到 D:\Projects\aitemp-test\report.md（同时打印在窗口里）。
# 只影响 aitemp 这个账号：给它加的都是“拒绝”，别的账号的权限不变。
#Requires -RunAsAdministrator
param([switch]$Undo)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$grant = 'D:\Projects\aitemp-test'
$user = 'aitemp'
$py = (Get-ChildItem 'C:\Program Files\BlenderMCP\python' -Recurse -Filter python.exe | Select-Object -First 1).FullName
$denyHash = '285CBBB3E8F5694468166F3ADCA78CE0255F8241C7BED633784332F1B2A3674F'
$wfpHash = '7EC83AD429CDFBBE653F504270C2D503231F96611690690B2CD064DFD7ABC3E6'
$runnerHash = 'D9806FFCDEF95A24345929F8FC6A1F843906E323F2E92AF1ECB3C0D3E9B9085C'
$programDirs = @('Program Files', 'Program Files (x86)', 'ProgramData')
$skipDirs = @('$RECYCLE.BIN', 'System Volume Information')
$protected = @('D:\Projects\maa-cli', 'D:\Projects\skland', 'C:\ProgramData\BlenderMCP')
$profiles = @('C:\Users\Administrator', 'C:\Users\blender')
$hideKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList'

function Sid { (Get-LocalUser $user).SID.Value }
function Set-AitempAcl([string[]]$a) { $o = & icacls.exe @a 2>&1; if ($LASTEXITCODE -ne 0) { throw "icacls $($a -join ' ') 失败：$o" } }
# 给程序目录加“拒绝写入和删除”。不能用 icacls：它给任何 ACE 都自动带上 SYNCHRONIZE，拒绝了它连程序都运行不了
# （2026-11-18 两次测试）。.NET 生成非完全控制的拒绝项时会去掉 SYNCHRONIZE（实测掩码 0x00010156）。
# 程序目录的“拒绝写入和删除”交给 denywrite.ps1，用 Windows PowerShell 5.1 执行（这条路径已在电脑上实测）。
# 不能用 icacls：它给任何 ACE 都自动带上 SYNCHRONIZE，拒绝了它连程序都运行不了（2026-11-18 两次测试）。
function Set-AitempDenyWrite([string]$path, [string]$sid) {
    $o = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'denywrite.ps1') -Path $path -Sid $sid 2>&1
    if ($LASTEXITCODE -ne 0) { throw "denywrite.ps1 失败：$o" }
}
function UserRights([string]$sid, [bool]$add) {
    $inf = Join-Path $env:TEMP 'aitemp_rights.inf'; $db = Join-Path $env:TEMP 'aitemp_rights.sdb'
    secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
    $lines = Get-Content $inf -Encoding Unicode
    foreach ($right in 'SeDenyNetworkLogonRight', 'SeDenyRemoteInteractiveLogonRight') {
        $i = [array]::FindIndex([string[]]$lines, [Predicate[string]]{ param($l) $l -like "$right =*" })
        $cur = if ($i -ge 0) { ($lines[$i] -split '=', 2)[1].Trim() -split ',' | Where-Object { $_ } } else { @() }
        $cur = @($cur | Where-Object { $_ -ne "*$sid" }); if ($add) { $cur += "*$sid" }
        $line = "$right = " + ($cur -join ',')
        if ($i -ge 0) { $lines[$i] = $line } else { $j = [array]::IndexOf([string[]]$lines, '[Privilege Rights]'); $lines = $lines[0..$j] + $line + $lines[($j + 1)..($lines.Count - 1)] }
    }
    $lines | Set-Content $inf -Encoding Unicode
    secedit /configure /db $db /cfg $inf /areas USER_RIGHTS /quiet | Out-Null
    Remove-Item $inf, $db -ErrorAction SilentlyContinue
}

if ((Get-FileHash (Join-Path $here 'wfp.cs') -Algorithm SHA256).Hash -ne $wfpHash) { throw 'wfp.cs 和预期不一致，已停止。' }
if ((Get-FileHash (Join-Path $here 'denywrite.ps1') -Algorithm SHA256).Hash -ne $denyHash) { throw 'denywrite.ps1 和预期不一致，已停止。' }
Add-Type -Path (Join-Path $here 'wfp.cs')

if ($Undo) {
    if (-not (Get-LocalUser $user -ErrorAction SilentlyContinue)) { Write-Host '没有 aitemp 账号，不用撤销。'; return }
    $sid = Sid
    Get-NetFirewallRule -Name 'AITemp-*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Host ('WFP：' + [AitempWfp]::Remove())
    $dirs = @(Get-ChildItem D:\ -Directory -Force | Where-Object { $_.Name -notin $skipDirs } | ForEach-Object FullName) + 'D:\', 'C:\' + $protected + $profiles + $grant
    foreach ($d in $dirs) { if (Test-Path $d) { & icacls.exe $d /remove "*$sid" 2>&1 | Out-Null } }
    UserRights $sid $false
    Remove-ItemProperty $hideKey -Name $user -ErrorAction SilentlyContinue
    Remove-LocalUser $user
    Get-CimInstance Win32_UserProfile | Where-Object { $_.SID -eq $sid } | Remove-CimInstance
    Write-Host '已撤销：aitemp 账号、它的配置文件、权限和防火墙规则都删掉了。测试文件夹 D:\Projects\aitemp-test 保留，可以手动删。'
    return
}

$t0 = Get-Date
$log = [System.Collections.Generic.List[string]]::new()
function Note($m) { Write-Host $m; $log.Add($m) }

if ((Get-FileHash (Join-Path $here 'runner.py') -Algorithm SHA256).Hash -ne $runnerHash) { throw 'runner.py 和预期不一致，已停止。' }
foreach ($p in Get-NetFirewallProfile) { Note "- 防火墙 $($p.Name)：$(if ($p.Enabled) { '开启' } else { '关闭（规则不会生效）' })" }

Write-Host '1/6 账号……'
$pw = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(30))
$sec = ConvertTo-SecureString $pw -AsPlainText -Force
if (-not (Get-LocalUser $user -ErrorAction SilentlyContinue)) {
    New-LocalUser $user -Password $sec -PasswordNeverExpires -UserMayNotChangePassword -AccountNeverExpires -FullName 'AITemp' -Description 'MCP 临时授权沙盒账号' | Out-Null
    Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $user
    Note '- 新建了 aitemp'
} else { Set-LocalUser $user -Password $sec; Note '- aitemp 已存在，换了新密码' }
$sid = Sid
New-Item $hideKey -Force | Out-Null
Set-ItemProperty $hideKey -Name $user -Value 0 -Type DWord
UserRights $sid $true
Note "- 登录界面已隐藏，已禁止远程桌面和网络登录（SID $sid）"

Write-Host '2/6 文件权限（会遍历大目录，可能要几分钟）……'
# 先清掉上一次给 aitemp 加的规则，再按现在的方案重加
$targets = @(Get-ChildItem D:\ -Directory -Force | Where-Object { $_.Name -notin $skipDirs } | ForEach-Object FullName) + 'D:\', 'C:\' + $protected + $profiles
foreach ($d in $targets) { if (Test-Path $d) { & icacls.exe $d /remove "*$sid" 2>&1 | Out-Null } }
foreach ($d in Get-ChildItem D:\ -Directory -Force | Where-Object { $_.Name -notin $skipDirs }) {
    $s = Get-Date
    try {
        if ($d.Name -in $programDirs) { Set-AitempDenyWrite $d.FullName $sid; $kind = '程序：拒绝写入（不含 SYNCHRONIZE）' }
        else { Set-AitempAcl @($d.FullName, '/deny', "*${sid}:(OI)(CI)F"); $kind = '数据：拒绝读写' }
    } catch { $kind = "**没设上**：$($_.Exception.Message)" }
    Note ("- {0}  {1}  {2:N1}s" -f $d.FullName, $kind, ((Get-Date) - $s).TotalSeconds)
}
Set-AitempAcl @('D:\', '/deny', "*${sid}:(AD,WD)"); Set-AitempAcl @('D:\', '/deny', "*${sid}:(OI)(NP)(IO)F")
Set-AitempAcl @('C:\', '/deny', "*${sid}:(AD,WD)")
foreach ($p in $protected) { if (Test-Path $p) { Set-AitempAcl @($p, '/deny', "*${sid}:(OI)(CI)F") } }
foreach ($p in $profiles) { if (Test-Path $p) { Set-AitempAcl @($p, '/deny', "*${sid}:F") } }
Note '- D:\ 根目录的文件拒绝读写、根目录不能新建；C:\ 根目录不能新建；受保护位置和两个账号的用户目录拒绝'

Write-Host '3/6 联网规则……'
# 外网：防火墙按账号拦掉 aitemp 的全部直连出站，只能经 Clash 7899 出去
# 本机回环：防火墙管不到（第一次测试证实），用 WFP 过滤器拦；联网时只放行 127.0.0.1:7899
Get-NetFirewallRule -Name 'AITemp-*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name 'AITemp-Direct' -DisplayName 'AITemp：不许直连外网' -Direction Outbound -Action Block -LocalUser "D:(A;;CC;;;$sid)" | Out-Null
Note ('- WFP：' + [AitempWfp]::Apply($sid, $false))

Write-Host '4/6 测试用的授权文件夹……'
if (Test-Path $grant) { Remove-Item $grant -Recurse -Force }
New-Item $grant -ItemType Directory | Out-Null
Set-AitempAcl @($grant, '/grant', "*${sid}:(OI)(CI)M")
Copy-Item (Join-Path $here 'runner.py') $grant
$report = Join-Path $grant 'report.jsonl'

Write-Host '5/6 以 aitemp 身份跑检查……'
Start-Service seclogon -ErrorAction SilentlyContinue
$cred = [pscredential]::new("$env:COMPUTERNAME\$user", $sec)
$agentPid = (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'panel\\agent\.py' } | Select-Object -First 1).ProcessId
$dummy = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 47123); $dummy.Start(16)
$listen = (Get-NetTCPConnection -State Listen -LocalAddress 127.0.0.1 -ErrorAction SilentlyContinue | ForEach-Object LocalPort | Sort-Object -Unique) -join ', '
Note "- 本机正在监听的端口（含测试用的 47123）：$listen"
foreach ($phase in 'offline', 'online') {
    Note ("- {0}：WFP {1}" -f $phase, [AitempWfp]::Apply($sid, $phase -eq 'online'))
    $s = Get-Date
    $p = Start-Process -FilePath $py -ArgumentList (Join-Path $grant 'runner.py'), $phase, $report, "$agentPid" -Credential $cred -WorkingDirectory $grant -LoadUserProfile -WindowStyle Hidden -PassThru
    if (-not $p.WaitForExit(1200000)) { $p.Kill($true); Note "- $phase 一轮超过 20 分钟，已结束" }
    Note ("- {0} 一轮用时 {1:N0}s" -f $phase, ((Get-Date) - $s).TotalSeconds)
}
$dummy.Stop()
Note ('- 测完恢复为断网：WFP ' + [AitempWfp]::Apply($sid, $false))

Write-Host '6/6 撤销授权后再查……'
Set-AitempAcl @($grant, '/remove:g', "*$sid")
# 探测脚本放在 aitemp 读得到、但不在授权文件夹里的地方；退出码 3 = 被拒绝，0 = 还能列出，其他 = 脚本自身出错
$probeFile = 'C:\Users\Public\aitemp_probe.py'
@("import os, sys", "try:", "    os.listdir(r'$grant')", "    sys.exit(0)", "except PermissionError:", "    sys.exit(3)") | Set-Content $probeFile -Encoding UTF8
$probe = Start-Process -FilePath $py -ArgumentList $probeFile -Credential $cred -WorkingDirectory $env:SystemRoot -LoadUserProfile -WindowStyle Hidden -PassThru -Wait
Remove-Item $probeFile -ErrorAction SilentlyContinue
$revoked = $probe.ExitCode -eq 3
Add-Content $report (ConvertTo-Json -Compress @{ phase = 'revoke'; group = '吊销'; check = '吊销后列授权文件夹'; expect = 'deny'; got = ($(if ($revoked) { 'deny' } else { 'allow' })); pass = $revoked; detail = "exit $($probe.ExitCode)" })
$hidden = (Get-ItemProperty $hideKey -Name $user -ErrorAction SilentlyContinue).$user -eq 0
Add-Content $report (ConvertTo-Json -Compress @{ phase = 'account'; group = '账号'; check = '登录界面隐藏 aitemp'; expect = 'allow'; got = ($(if ($hidden) { 'allow' } else { 'deny' })); pass = $hidden; detail = '' })

$rows = Get-Content $report -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
$bad = @($rows | Where-Object { -not $_.pass })
$md = @("# aitemp 沙盒测试报告", '', "时间 $(Get-Date -Format 'yyyy-MM-dd HH:mm')，总用时 $([int]((Get-Date) - $t0).TotalSeconds) 秒；$($rows.Count) 项，未通过 $($bad.Count) 项。", '') + $log + @('', '| 轮次 | 类别 | 检查 | 应当 | 实际 | 结果 | 说明 |', '| --- | --- | --- | --- | --- | --- | --- |')
foreach ($r in $rows) { $md += "| $($r.phase) | $($r.group) | $($r.check) | $($r.expect) | $($r.got) | $(if ($r.pass) { '通过' } else { '**未通过**' }) | $(($r.detail -replace '\|', '/') -replace '\r?\n', ' ') |" }
$md | Set-Content (Join-Path $grant 'report.md') -Encoding UTF8
Write-Host ''
Write-Host "完成：$($rows.Count) 项检查，未通过 $($bad.Count) 项。报告在 $grant\report.md，告诉 Claude 去看就行。"
$bad | ForEach-Object { Write-Host "  未通过：[$($_.phase)] $($_.check) —— 应当 $($_.expect)，实际 $($_.got)" }
