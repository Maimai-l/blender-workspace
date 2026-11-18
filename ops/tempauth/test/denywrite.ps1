# denywrite.ps1 - 给一个目录加 aitemp 的“拒绝写入和删除”（可继承），不含 SYNCHRONIZE。
# 用 Windows PowerShell 5.1 运行（aitemp_test.ps1 调用它）；2026-11-18 在电脑上实测掩码为 0x00010156。
param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Sid)
$ErrorActionPreference = 'Stop'
function Set-AitempDenyWrite([string]$path, [string]$sid) {
    $rights = [System.Security.AccessControl.FileSystemRights]'WriteData, AppendData, WriteExtendedAttributes, WriteAttributes, Delete, DeleteSubdirectoriesAndFiles'
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule((New-Object System.Security.Principal.SecurityIdentifier($sid)), $rights, 'ContainerInherit, ObjectInherit', 'None', 'Deny')
    $di = New-Object System.IO.DirectoryInfo($path)
    $access = [System.Security.AccessControl.AccessControlSections]::Access
    # Windows PowerShell 5.1（.NET Framework）有实例方法；PowerShell 7（.NET）要用 FileSystemAclExtensions
    $native = [bool]$di.PSObject.Methods['GetAccessControl']
    if (-not $native) { Add-Type -AssemblyName System.IO.FileSystem.AccessControl -ErrorAction SilentlyContinue }
    $get = { if ($native) { $di.GetAccessControl($access) } else { [System.IO.FileSystemAclExtensions]::GetAccessControl($di, $access) } }
    $acl = & $get
    $acl.AddAccessRule($rule)
    if ($native) { $di.SetAccessControl($acl) } else { [System.IO.FileSystemAclExtensions]::SetAccessControl($di, $acl) }
    $bad = @((& $get).GetAccessRules($true, $false, [System.Security.Principal.SecurityIdentifier]) |
        Where-Object { $_.AccessControlType -eq 'Deny' -and $_.IdentityReference.Value -eq $sid -and ([int]$_.FileSystemRights -band 0x100000) })
    if ($bad) { throw "拒绝项仍含 SYNCHRONIZE：$path" }
}
Set-AitempDenyWrite $Path $Sid
