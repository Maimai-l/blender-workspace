// aitemp-helper：MCP 临时授权的授权助手（Windows 服务，以 SYSTEM 运行）。
// 只做五件事：以沙盒账号 aitemp 运行命令和读写文件、给文件夹加或撤权限、开关 aitemp 联网、清理临时文件、沙盒自检。
// 只接受 blender 账号经命名管道 \\.\pipe\aitemp-helper 发来的请求（一行 JSON 进，一行 JSON 出）。
//
// 隔离做法：每条授权一个本地组 AITemp-<授权编号>，授权文件夹上只加这个组的“修改”权限。要以某条授权的身份
// 运行时，把 aitemp 临时加进这个组、登录拿令牌、立刻移出；令牌里的组在登录时就定了，所以一条授权的命令
// 只带着自己的组，碰不到别的授权的文件夹。aitemp 本身的拒绝项（D 盘数据目录、受保护位置）始终有效。
// aitemp 的密码每次服务启动时随机重设，只留在内存里。
//
// 编译（.NET Framework 自带的 csc，C# 5）：
//   csc /nologo /target:exe /platform:x64 /optimize+ /out:aitemp-helper.exe
//       /r:System.ServiceProcess.dll /r:System.Web.Extensions.dll AitempHelper.cs wfp.cs
// 运行：作为服务（安装包用 sc.exe 注册）；调试时管理员命令行 aitemp-helper.exe --console。
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.ServiceProcess;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using Microsoft.Win32.SafeHandles;

public class HelperService : ServiceBase
{
    public HelperService() { ServiceName = "AITempHelper"; CanStop = true; CanShutdown = true; }
    protected override void OnStart(string[] args) { Helper.Start(); }
    protected override void OnStop() { Helper.Stop(); }
    protected override void OnShutdown() { Helper.Stop(); }

    public static int Main(string[] args)
    {
        foreach (string a in args) if (a.StartsWith("--client=")) Helper.ClientAccount = a.Substring(9);
        if (Array.IndexOf(args, "--console") >= 0)
        {
            Helper.Start();
            Console.WriteLine("aitemp-helper running in console mode; press Enter to stop");
            Console.ReadLine();
            Helper.Stop();
            return 0;
        }
        ServiceBase.Run(new HelperService());
        return 0;
    }
}

public class HelperError : Exception
{
    public string Code;
    public HelperError(string code, string msg) : base(msg) { Code = code; }
}

public static class Helper
{
    public const string Version = "1.0.2";
    public static string ClientAccount = "blender";
    const string User = "aitemp";
    const string PipeName = "aitemp-helper";
    const string GroupPrefix = "AITemp-";
    static readonly string LogFile = @"C:\ProgramData\BlenderMCP\aitemp-helper.log";

    // 不能授权的位置：系统和程序目录、用户目录、受保护位置（与《MCP 控制台需求》R4.4.2 一致）
    public static readonly string[] Protected = {
        @"C:\Users\Administrator", @"C:\Users\blender", @"C:\ProgramData\BlenderMCP", @"D:\Projects\maa-cli", @"D:\Projects\skland" };
    static readonly string[] SystemRoots = {
        @"C:\Windows", @"C:\Program Files", @"C:\Program Files (x86)", @"C:\ProgramData", @"C:\Users", @"C:\Recovery",
        @"D:\Program Files", @"D:\Program Files (x86)", @"D:\ProgramData", @"D:\$RECYCLE.BIN", @"D:\System Volume Information" };
    static readonly string[] ProgramDirsOnD = { "Program Files", "Program Files (x86)", "ProgramData" };
    static readonly string[] SkipDirsOnD = { "$RECYCLE.BIN", "System Volume Information" };

    const string Python = @"D:\ProgramData\python.exe";
    const string Cmd = @"C:\Windows\System32\cmd.exe";
    const string PowerShell = @"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe";
    const string Bash = @"C:\Program Files\Git\bin\bash.exe";
    const string ClashListener = "http://127.0.0.1:7899";

    static string password;
    public static SecurityIdentifier Sid;
    static SecurityIdentifier clientSid;
    static string desktopName;
    static IntPtr winsta, desktop;
    static volatile bool stopping;
    static Thread pipeThread;
    static Timer sweepTimer;
    static readonly object logonLock = new object(), runLock = new object(), logLock = new object(), wfpLock = new object();
    static readonly Dictionary<string, Grant> grants = new Dictionary<string, Grant>(StringComparer.OrdinalIgnoreCase);
    static readonly Dictionary<string, Job> jobs = new Dictionary<string, Job>();
    static Job current;
    static int wfpOnline = -1;
    static string startError;
    static readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 64 * 1024 * 1024 };

    // ------------------------------------------------------------------ 生命周期
    public static void Start()
    {
        Log("start " + Version);
        try
        {
            clientSid = (SecurityIdentifier)new NTAccount(ClientAccount).Translate(typeof(SecurityIdentifier));
            Sid = (SecurityIdentifier)new NTAccount(User).Translate(typeof(SecurityIdentifier));
            ResetPassword();
            LeaveAllGroups();
            ApplyWfp(false);
            CreateDesktop();
        }
        catch (Exception e) { startError = e.Message; Log("start failed: " + e); }
        try { foreach (string c in SyncTopDirs()) Log("top dir: " + c); } catch (Exception e) { Log("top dirs: " + e.Message); }
        pipeThread = new Thread(PipeLoop) { IsBackground = true, Name = "pipe" };
        pipeThread.Start();
        sweepTimer = new Timer(delegate { try { Sweep(); } catch (Exception e) { Log("sweep: " + e.Message); } }, null, 20000, 20000);
    }

    public static void Stop()
    {
        stopping = true;
        Log("stop");
        try { lock (runLock) { foreach (Job j in jobs.Values) j.Kill("stopped"); } } catch { }
        try { using (var c = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut)) c.Connect(500); } catch { }
        try { ApplyWfp(false); } catch { }
        lock (grants) { foreach (Grant g in grants.Values) g.CloseToken(); }
    }

    public static void Log(string m)
    {
        try
        {
            lock (logLock)
            {
                var fi = new FileInfo(LogFile);
                if (fi.Exists && fi.Length > 5 * 1024 * 1024) File.Copy(LogFile, LogFile + ".1", true);
                if (fi.Exists && fi.Length > 5 * 1024 * 1024) File.Delete(LogFile);
                File.AppendAllText(LogFile, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + "  " + m + Environment.NewLine, Encoding.UTF8);
            }
        }
        catch { }
    }

    // ------------------------------------------------------------------ 账号、组、令牌
    static void ResetPassword()
    {
        var b = new byte[24];
        using (var r = new RNGCryptoServiceProvider()) r.GetBytes(b);
        string pw = Convert.ToBase64String(b) + "aA1!";
        var info = new N.USER_INFO_1003 { password = pw };
        uint err; int rc = N.NetUserSetInfo(null, User, 1003, ref info, out err);
        if (rc != 0) throw new HelperError("account", "重设 aitemp 密码失败：" + rc);
        password = pw;
    }

    static void LeaveAllGroups()
    {
        foreach (string g in UserGroups())
            if (g.StartsWith(GroupPrefix, StringComparison.OrdinalIgnoreCase)) DelMember(g);
    }

    static List<string> UserGroups()
    {
        var res = new List<string>();
        IntPtr buf; int read, total;
        int rc = N.NetUserGetLocalGroups(null, User, 0, 0, out buf, -1, out read, out total);
        if (rc != 0) return res;
        try
        {
            for (int i = 0; i < read; i++)
                res.Add(Marshal.PtrToStringUni(Marshal.ReadIntPtr(buf, i * IntPtr.Size)));
        }
        finally { N.NetApiBufferFree(buf); }
        return res;
    }

    static Dictionary<string, string> LocalGroups()
    {
        var res = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        IntPtr resume = IntPtr.Zero;
        while (true)
        {
            IntPtr buf; int read, total;
            int rc = N.NetLocalGroupEnum(null, 1, out buf, -1, out read, out total, ref resume);
            if (rc != 0 && rc != 234) break;
            try
            {
                for (int i = 0; i < read; i++)
                {
                    IntPtr p = buf + i * 2 * IntPtr.Size;
                    string name = Marshal.PtrToStringUni(Marshal.ReadIntPtr(p));
                    string comment = Marshal.PtrToStringUni(Marshal.ReadIntPtr(p, IntPtr.Size));
                    if (name.StartsWith(GroupPrefix, StringComparison.OrdinalIgnoreCase)) res[name] = comment ?? "";
                }
            }
            finally { N.NetApiBufferFree(buf); }
            if (rc != 234) break;
        }
        return res;
    }

    static void AddMember(string group)
    {
        byte[] sid = new byte[Sid.BinaryLength]; Sid.GetBinaryForm(sid, 0);
        GCHandle h = GCHandle.Alloc(sid, GCHandleType.Pinned);
        try
        {
            var m = new N.LOCALGROUP_MEMBERS_INFO_0 { sid = h.AddrOfPinnedObject() };
            int rc = N.NetLocalGroupAddMembers(null, group, 0, ref m, 1);
            if (rc != 0 && rc != 1378) throw new HelperError("group", "把 aitemp 加入组 " + group + " 失败：" + rc);
        }
        finally { h.Free(); }
    }

    static void DelMember(string group)
    {
        byte[] sid = new byte[Sid.BinaryLength]; Sid.GetBinaryForm(sid, 0);
        GCHandle h = GCHandle.Alloc(sid, GCHandleType.Pinned);
        try
        {
            var m = new N.LOCALGROUP_MEMBERS_INFO_0 { sid = h.AddrOfPinnedObject() };
            int rc = N.NetLocalGroupDelMembers(null, group, 0, ref m, 1);
            if (rc != 0 && rc != 1377 && rc != 2220) Log("remove aitemp from " + group + " failed: " + rc);
        }
        finally { h.Free(); }
    }

    /// <summary>登录 aitemp 拿主令牌；group 不为空时令牌里带上这个组（登录前加入、登录后立刻移出）。</summary>
    public static IntPtr Logon(string group)
    {
        if (password == null) throw new HelperError("account", "助手没有初始化：" + startError);
        lock (logonLock)
        {
            if (group != null) AddMember(group);
            try
            {
                IntPtr tok;
                if (!N.LogonUserW(User, ".", password, 2 /*INTERACTIVE*/, 0, out tok))
                    throw new HelperError("logon", "aitemp 登录失败：" + new Win32Exception(Marshal.GetLastWin32Error()).Message);
                return tok;
            }
            finally { if (group != null) DelMember(group); }
        }
    }

    public class Grant
    {
        public string Id, Group;
        public List<string> Folders = new List<string>();
        public SecurityIdentifier GroupSid;
        IntPtr token = IntPtr.Zero, profile = IntPtr.Zero;
        readonly object tl = new object();

        public IntPtr Token()
        {
            lock (tl)
            {
                if (token != IntPtr.Zero) return token;
                token = Logon(Group);
                profile = LoadProfile(token);
                return token;
            }
        }

        public void CloseToken()
        {
            lock (tl)
            {
                if (profile != IntPtr.Zero) { N.UnloadUserProfile(token, profile); profile = IntPtr.Zero; }
                if (token != IntPtr.Zero) { N.CloseHandle(token); token = IntPtr.Zero; }
            }
        }

        public string FolderOf(string path)
        {
            foreach (string f in Folders) if (Under(path, f)) return f;
            return null;
        }
    }

    static IntPtr LoadProfile(IntPtr token)
    {
        var pi = new N.PROFILEINFO { dwSize = Marshal.SizeOf(typeof(N.PROFILEINFO)), dwFlags = 1 /*PI_NOUI*/, lpUserName = User };
        if (!N.LoadUserProfileW(token, ref pi)) { Log("LoadUserProfile failed: " + Marshal.GetLastWin32Error()); return IntPtr.Zero; }
        return pi.hProfile;
    }

    // ------------------------------------------------------------------ 路径
    public static bool Under(string path, string root)
    {
        path = path.TrimEnd('\\'); root = root.TrimEnd('\\');
        return path.Equals(root, StringComparison.OrdinalIgnoreCase) || path.StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>解析联接和符号链接后的真实路径（不带 \\?\ 前缀）。路径不存在时返回 null。</summary>
    public static string RealPath(string path)
    {
        IntPtr h = N.CreateFileW(path, 0, 7, IntPtr.Zero, 3 /*OPEN_EXISTING*/, 0x02000000 /*BACKUP_SEMANTICS*/, IntPtr.Zero);
        if (h == new IntPtr(-1)) return null;
        try
        {
            var sb = new StringBuilder(1024);
            uint n = N.GetFinalPathNameByHandleW(h, sb, 1024, 0);
            if (n == 0 || n >= 1024) return null;
            string s = sb.ToString();
            if (s.StartsWith(@"\\?\UNC\")) return @"\\" + s.Substring(8);
            if (s.StartsWith(@"\\?\")) s = s.Substring(4);
            return s;
        }
        finally { N.CloseHandle(h); }
    }

    /// <summary>检查能不能授权这个文件夹，返回真实路径；不能时抛出带原因的错误。</summary>
    public static string CheckFolder(string folder)
    {
        if (string.IsNullOrWhiteSpace(folder)) throw new HelperError("folder", "没有给文件夹");
        string full;
        try { full = Path.GetFullPath(folder); } catch (Exception e) { throw new HelperError("folder", "路径不对：" + e.Message); }
        if (full.StartsWith(@"\\")) throw new HelperError("folder", "不能授权网络路径");
        if (!Directory.Exists(full)) throw new HelperError("folder", "文件夹不存在：" + full);
        string real = RealPath(full) ?? full;
        foreach (string p in new[] { full, real })
        {
            string root = Path.GetPathRoot(p);
            var di = new DriveInfo(root);
            if (di.DriveType != DriveType.Fixed) throw new HelperError("folder", "只能授权本机硬盘上的文件夹");
            string rest = p.Substring(root.Length).Trim('\\');
            string[] parts = rest.Split(new[] { '\\' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 1)
                throw new HelperError("folder", "不能授权盘符，请选其下的文件夹：" + p);
            if (parts.Length == 1 && (Array.IndexOf(SkipDirsOnD, parts[0]) >= 0))
                throw new HelperError("folder", "系统目录不能授权：" + p);
            foreach (string s in SystemRoots)
                if (Under(p, s)) throw new HelperError("folder", "系统和程序目录不能授权：" + p);
            foreach (string s in Protected)
                if (Under(p, s) || Under(s, p)) throw new HelperError("folder", "受保护位置不能授权：" + s);
        }
        return real;
    }

    // ------------------------------------------------------------------ 授权：组和文件夹权限
    static Grant GetGrant(string id, bool must)
    {
        Grant g;
        lock (grants) grants.TryGetValue(id ?? "", out g);
        if (g == null && must) throw new HelperError("unknown_grant", "助手里没有这条授权（可能刚重启），请重新准备：" + id);
        return g;
    }

    static string GroupName(string id)
    {
        foreach (char c in id) if (!char.IsLetterOrDigit(c) && c != '-' && c != '_') throw new HelperError("grant", "授权编号只能用字母、数字");
        if (id.Length == 0 || id.Length > 40) throw new HelperError("grant", "授权编号长度不对");
        return GroupPrefix + id;
    }

    static Dictionary<string, object> Prepare(Dictionary<string, object> q)
    {
        string id = Str(q, "grant");
        string group = GroupName(id);
        var folders = new List<string>();
        foreach (object o in AsList(q, "folders")) folders.Add(CheckFolder((string)o));
        if (folders.Count == 0) throw new HelperError("folder", "至少要一个文件夹");
        var sw = Stopwatch.StartNew();
        var groups = LocalGroups();
        string comment = Comment(folders);
        if (!groups.ContainsKey(group))
        {
            var gi = new N.LOCALGROUP_INFO_1 { name = group, comment = comment };
            int parm; int rc = N.NetLocalGroupAdd(null, 1, ref gi, out parm);
            if (rc != 0 && rc != 1379 && rc != 2223) throw new HelperError("group", "建组失败：" + rc);
        }
        else if (groups[group] != comment)
        {
            // 文件夹变了：先把旧文件夹上的权限撤掉
            var gsidOld = GroupSid(group);
            foreach (string f in groups[group].Split(new[] { '|' }, StringSplitOptions.RemoveEmptyEntries))
                if (!folders.Contains(f)) try { RemoveAce(f, gsidOld); foreach (string a in Ancestors(f)) AncestorAce(a, gsidOld, false); } catch (Exception e) { Log("remove old ace: " + e.Message); }
            var gi = new N.LOCALGROUP_INFO_1002 { comment = comment };
            int parm; N.NetLocalGroupSetInfo(null, group, 1002, ref gi, out parm);
        }
        var gsid = GroupSid(group);
        foreach (string f in folders)
        {
            foreach (string a in Ancestors(f)) AncestorAce(a, gsid, true);
            AddAce(f, gsid);
            foreach (string sub in new[] { "tmp", "pip-cache", "pyuser", "npm-cache", "npm-global", "uv-cache" })
                Directory.CreateDirectory(Path.Combine(f, ".aitemp", sub));
            try { File.SetAttributes(Path.Combine(f, ".aitemp"), FileAttributes.Directory | FileAttributes.Hidden); } catch { }
        }
        Grant g = GetGrant(id, false);
        if (g != null) g.CloseToken();
        g = new Grant { Id = id, Group = group, Folders = folders, GroupSid = gsid };
        lock (grants) grants[id] = g;
        foreach (string c in SyncTopDirs()) Log("top dir: " + c);
        Log("prepare " + id + " " + comment + " " + sw.ElapsedMilliseconds + "ms");
        var r = Ok(); r["folders"] = folders; r["ms"] = sw.ElapsedMilliseconds;
        return r;
    }

    /// <summary>组说明里记下文件夹（释放时用），说明最长 256 个字符，超出的截掉（网关释放时会再把文件夹传过来）。</summary>
    static string Comment(List<string> folders)
    {
        string c = "";
        foreach (string f in folders) { string n = c.Length == 0 ? f : c + "|" + f; if (n.Length > 255) break; c = n; }
        return c;
    }

    static SecurityIdentifier GroupSid(string group)
    {
        return (SecurityIdentifier)new NTAccount(Environment.MachineName, group).Translate(typeof(SecurityIdentifier));
    }

    static void AddAce(string folder, SecurityIdentifier sid)
    {
        var di = new DirectoryInfo(folder);
        var ds = di.GetAccessControl(AccessControlSections.Access);
        foreach (FileSystemAccessRule r in ds.GetAccessRules(true, false, typeof(SecurityIdentifier)))
            if (r.IdentityReference.Equals(sid) && r.AccessControlType == AccessControlType.Allow
                && (r.FileSystemRights & FileSystemRights.Modify) == FileSystemRights.Modify) return;
        ds.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.Modify | FileSystemRights.Synchronize,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        di.SetAccessControl(ds);
    }

    /// <summary>授权文件夹和 D 盘顶层目录之间的各级目录（不含两端）。</summary>
    static List<string> Ancestors(string folder)
    {
        var res = new List<string>();
        string root = Path.GetPathRoot(folder);
        string[] parts = folder.Substring(root.Length).Split(new[] { '\\' }, StringSplitOptions.RemoveEmptyEntries);
        for (int i = 2; i < parts.Length; i++) res.Add(root + string.Join("\\", parts, 0, i));
        return res;
    }

    /// <summary>中间各级目录给授权组只加“读属性”、不继承：git 建目录时会逐级 stat 整条路径，读不到属性就失败
    /// （2026-11-18 验收发现）。看不到目录里有什么。用 SetFileSecurity 写，不遍历子目录。</summary>
    static void AncestorAce(string dir, SecurityIdentifier sid, bool add)
    {
        if (!Directory.Exists(dir)) return;
        var ds = new DirectoryInfo(dir).GetAccessControl(AccessControlSections.Access);
        if (add)
        {
            foreach (FileSystemAccessRule r in ds.GetAccessRules(true, false, typeof(SecurityIdentifier)))
                if (r.IdentityReference.Equals(sid) && r.AccessControlType == AccessControlType.Allow) return;
            ds.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.ReadAttributes | FileSystemRights.Synchronize,
                InheritanceFlags.None, PropagationFlags.None, AccessControlType.Allow));
        }
        else ds.PurgeAccessRules(sid);
        if (!N.SetFileSecurityW(dir, 4 /*DACL_SECURITY_INFORMATION*/, ds.GetSecurityDescriptorBinaryForm()))
            throw new HelperError("acl", "改 " + dir + " 的权限失败：" + Marshal.GetLastWin32Error());
    }

    /// <summary>D 盘顶层的数据目录（不含程序目录和系统目录）。这些目录上有 aitemp 的显式拒绝项。</summary>
    static bool IsTopDataDir(string f)
    {
        string root = Path.GetPathRoot(f) ?? "";
        if (!root.Equals(@"D:\", StringComparison.OrdinalIgnoreCase)) return false;
        string[] parts = f.Substring(root.Length).Split(new[] { '\\' }, StringSplitOptions.RemoveEmptyEntries);
        return parts.Length == 1 && Array.IndexOf(ProgramDirsOnD, parts[0]) < 0 && Array.IndexOf(SkipDirsOnD, parts[0]) < 0;
    }

    /// <summary>D 盘顶层数据目录的拒绝项。显式拒绝优先于同一目录上的允许，所以授权这种目录时：撤掉 aitemp 的拒绝项，
    /// 改为拒绝其他授权组（各授权之间仍互不可见）；没有授权用它时恢复 aitemp 的拒绝项、去掉授权组的拒绝项。
    /// 也给新建的、还没有拒绝项的顶层目录补上。准备、释放、自检和启动时调用。返回做了的改动。</summary>
    static List<string> SyncTopDirs()
    {
        var changes = new List<string>();
        var groups = LocalGroups();
        var gsids = new Dictionary<string, SecurityIdentifier>(StringComparer.OrdinalIgnoreCase);
        foreach (string n in groups.Keys) try { gsids[n] = GroupSid(n); } catch { }
        var allowed = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);
        Action<string, string> add = (f, grp) =>
        {
            f = f.TrimEnd('\\');
            if (!IsTopDataDir(f)) return;
            HashSet<string> set;
            if (!allowed.TryGetValue(f, out set)) allowed[f] = set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            set.Add(grp);
        };
        foreach (var kv in groups) foreach (string f in kv.Value.Split(new[] { '|' }, StringSplitOptions.RemoveEmptyEntries)) add(f, kv.Key);
        lock (grants) foreach (Grant g in grants.Values) foreach (string f in g.Folders) add(f, g.Group);
        var inh = InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit;
        foreach (string d in Directory.GetDirectories(@"D:\"))
        {
            if (!IsTopDataDir(d)) continue;
            HashSet<string> ok;
            allowed.TryGetValue(d, out ok);
            try
            {
                var di = new DirectoryInfo(d);
                var ds = di.GetAccessControl(AccessControlSections.Access);
                bool changed = false, aitempDeny = false;
                var groupDeny = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (FileSystemAccessRule r in ds.GetAccessRules(true, false, typeof(SecurityIdentifier)))
                {
                    if (r.AccessControlType != AccessControlType.Deny) continue;
                    var sid = (SecurityIdentifier)r.IdentityReference;
                    if (sid.Equals(Sid))
                    {
                        if (ok != null) { ds.RemoveAccessRuleSpecific(r); changed = true; } else aitempDeny = true;
                        continue;
                    }
                    string gname = null;
                    foreach (var kv in gsids) if (kv.Value.Equals(sid)) gname = kv.Key;
                    bool orphan = false;
                    if (gname == null && (r.FileSystemRights & FileSystemRights.FullControl) == FileSystemRights.FullControl)
                        try { sid.Translate(typeof(NTAccount)); } catch { orphan = true; }   // 已删掉的授权组留下的拒绝项
                    if (orphan || (gname != null && (ok == null || ok.Contains(gname)))) { ds.RemoveAccessRuleSpecific(r); changed = true; }
                    else if (gname != null) groupDeny.Add(gname);
                }
                if (ok == null && !aitempDeny)
                {
                    ds.AddAccessRule(new FileSystemAccessRule(Sid, FileSystemRights.FullControl, inh, PropagationFlags.None, AccessControlType.Deny));
                    changed = true;
                    changes.Add(d + "：恢复或补上 aitemp 的拒绝项");
                }
                if (ok != null)
                {
                    foreach (var kv in gsids)
                        if (!ok.Contains(kv.Key) && !groupDeny.Contains(kv.Key))
                        {
                            ds.AddAccessRule(new FileSystemAccessRule(kv.Value, FileSystemRights.FullControl, inh, PropagationFlags.None, AccessControlType.Deny));
                            changed = true;
                        }
                    if (changed) changes.Add(d + "：授权中，aitemp 的拒绝项换成拒绝其他授权组");
                }
                if (changed) di.SetAccessControl(ds);
            }
            catch (Exception e) { changes.Add(d + "：出错 " + e.Message); }
        }
        return changes;
    }

    static void RemoveAce(string folder, SecurityIdentifier sid)
    {
        if (!Directory.Exists(folder)) return;
        var di = new DirectoryInfo(folder);
        var ds = di.GetAccessControl(AccessControlSections.Access);
        ds.PurgeAccessRules(sid);
        di.SetAccessControl(ds);
    }

    static Dictionary<string, object> Release(string id) { return Release(id, new List<object>()); }

    static Dictionary<string, object> Release(string id, List<object> extra)
    {
        string group = GroupName(id);
        KillGrant(id, "revoked");
        Grant g = GetGrant(id, false);
        if (g != null) { g.CloseToken(); lock (grants) grants.Remove(id); }
        var groups = LocalGroups();
        string comment;
        var errors = new List<string>();
        if (groups.TryGetValue(group, out comment))
        {
            SecurityIdentifier gsid = null;
            try { gsid = GroupSid(group); } catch { }
            var all = new List<string>(comment.Split(new[] { '|' }, StringSplitOptions.RemoveEmptyEntries));
            foreach (object o in extra) { string f = o as string; if (f != null && !all.Contains(f)) all.Add(f); }
            foreach (string f in all)
            {
                try { if (gsid != null) RemoveAce(f, gsid); } catch (Exception e) { errors.Add(f + "：" + e.Message); }
                if (gsid != null) foreach (string a in Ancestors(f)) try { AncestorAce(a, gsid, false); } catch (Exception e) { errors.Add(a + "：" + e.Message); }
                try { CleanDir(Path.Combine(f, ".aitemp", "tmp")); } catch { }
            }
            int rc = N.NetLocalGroupDel(null, group);
            if (rc != 0 && rc != 2220) errors.Add("删组失败：" + rc);
        }
        try { foreach (string c in SyncTopDirs()) Log("top dir: " + c); } catch (Exception e) { errors.Add("顶层目录：" + e.Message); }
        Log("release " + id + (errors.Count > 0 ? " errors: " + string.Join("; ", errors) : ""));
        var r = Ok(); r["errors"] = errors;
        return r;
    }

    static Dictionary<string, object> Reconcile(Dictionary<string, object> q)
    {
        var keep = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (object o in AsList(q, "keep")) keep.Add(GroupPrefix + (string)o);
        var released = new List<string>();
        foreach (var kv in LocalGroups())
            if (!keep.Contains(kv.Key)) { Release(kv.Key.Substring(GroupPrefix.Length)); released.Add(kv.Key); }
        var r = Ok(); r["released"] = released;
        return r;
    }

    // ------------------------------------------------------------------ 联网（WFP）
    static void ApplyWfp(bool online)
    {
        lock (wfpLock)
        {
            int want = online ? 1 : 0;
            if (wfpOnline == want) return;
            AitempWfp.Apply(Sid.Value, online);
            wfpOnline = want;
        }
    }

    // ------------------------------------------------------------------ 桌面：aitemp 的进程放在单独的窗口站里
    static void CreateDesktop()
    {
        string sddl = "D:(A;;GA;;;SY)(A;;GA;;;" + Sid.Value + ")";
        IntPtr sd; uint size;
        if (!N.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, out sd, out size)) throw new Win32Exception();
        var sa = new N.SECURITY_ATTRIBUTES { nLength = Marshal.SizeOf(typeof(N.SECURITY_ATTRIBUTES)), lpSecurityDescriptor = sd };
        IntPtr orig = N.GetProcessWindowStation();
        winsta = N.CreateWindowStationW("AITempWS", 0, 0x37F | 0x00020000 | 0x00040000, ref sa);
        if (winsta == IntPtr.Zero) throw new HelperError("desktop", "建窗口站失败：" + Marshal.GetLastWin32Error());
        if (!N.SetProcessWindowStation(winsta)) throw new HelperError("desktop", "切换窗口站失败：" + Marshal.GetLastWin32Error());
        try
        {
            desktop = N.CreateDesktopW("Default", null, IntPtr.Zero, 0, 0x01FF | 0x00020000 | 0x00040000, ref sa);
            if (desktop == IntPtr.Zero) throw new HelperError("desktop", "建桌面失败：" + Marshal.GetLastWin32Error());
        }
        finally { N.SetProcessWindowStation(orig); N.LocalFree(sd); }
        desktopName = @"AITempWS\Default";
    }

    // ------------------------------------------------------------------ 运行命令
    public class Job
    {
        public string Id, GrantId, State = "running", Reason = "";
        public int ExitCode = -1;
        public DateTime Started = DateTime.Now, Ended;
        public IntPtr JobHandle, Process;
        public int Pid;
        public readonly Output Out = new Output();
        public readonly ManualResetEvent Done = new ManualResetEvent(false);

        public void Kill(string why)
        {
            lock (this)
            {
                if (State != "running") return;
                Reason = why;
                if (JobHandle != IntPtr.Zero) N.TerminateJobObject(JobHandle, 1);
            }
        }
    }

    /// <summary>输出只留开头和结尾各 96 KB。</summary>
    public class Output
    {
        const int Cap = 96 * 1024;
        readonly MemoryStream head = new MemoryStream(), tail = new MemoryStream();
        public long Total;

        public void Add(byte[] b, int n)
        {
            lock (this)
            {
                Total += n;
                int h = (int)Math.Min(n, Cap - head.Length);
                if (h > 0) head.Write(b, 0, h);
                if (n > h)
                {
                    tail.Write(b, h, n - h);
                    if (tail.Length > 2 * Cap)
                    {
                        byte[] t = tail.ToArray();
                        tail.SetLength(0);
                        tail.Write(t, t.Length - Cap, Cap);
                    }
                }
            }
        }

        public string Text()
        {
            lock (this)
            {
                byte[] t = tail.ToArray();
                int keep = Math.Min(t.Length, Cap);
                long skipped = Total - head.Length - keep;
                string s = Decode(head.ToArray(), 0, (int)head.Length);
                if (skipped > 0) s += "\n…（中间省略 " + skipped + " 字节）…\n";
                if (keep > 0) s += Decode(t, t.Length - keep, keep);
                return s;
            }
        }

        // 每行先按 UTF-8 解，不是合法 UTF-8 就按 GBK（cmd 的内部命令按系统代码页输出）
        static readonly Encoding Utf8Strict = new UTF8Encoding(false, true);
        static string Decode(byte[] b, int off, int len)
        {
            var sb = new StringBuilder();
            int start = off, end = off + len;
            for (int i = off; i <= end; i++)
            {
                if (i < end && b[i] != (byte)'\n') continue;
                int n = i - start + (i < end ? 1 : 0);
                try { sb.Append(Utf8Strict.GetString(b, start, n)); }
                catch (DecoderFallbackException) { sb.Append(Encoding.GetEncoding(936).GetString(b, start, n)); }
                start = i + 1;
            }
            return sb.ToString().Replace("\r\n", "\n");
        }
    }

    static string QuoteArg(string a)
    {
        var sb = new StringBuilder("\"");
        int bs = 0;
        foreach (char c in a)
        {
            if (c == '\\') { bs++; continue; }
            if (c == '"') { sb.Append('\\', bs * 2 + 1); sb.Append('"'); bs = 0; continue; }
            sb.Append('\\', bs); bs = 0; sb.Append(c);
        }
        sb.Append('\\', bs * 2);
        sb.Append('"');
        return sb.ToString();
    }

    static string CommandLine(string shell, string command)
    {
        switch (shell)
        {
            case "cmd":
                return "\"" + Cmd + "\" /d /s /c \"" + command + "\"";
            case "powershell":
                string script = "$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=[Text.Encoding]::UTF8;$OutputEncoding=[Text.Encoding]::UTF8;\n" + command;
                string enc = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
                return "\"" + PowerShell + "\" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand " + enc;
            case "bash":
                return "\"" + Bash + "\" -c " + QuoteArg(command);
            case "python":   // 内部用：沙盒自检
                return "\"" + Python + "\" -X utf8 -c " + QuoteArg(command);
        }
        throw new HelperError("shell", "不支持的 shell：" + shell);
    }

    static Dictionary<string, string> EnvFor(IntPtr token, string folder, bool online)
    {
        var env = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        IntPtr block;
        if (N.CreateEnvironmentBlock(out block, token, false))
        {
            try
            {
                int off = 0;
                while (true)
                {
                    string s = Marshal.PtrToStringUni(block + off);
                    if (string.IsNullOrEmpty(s)) break;
                    off += (s.Length + 1) * 2;
                    int eq = s.IndexOf('=', 1);
                    if (eq > 0) env[s.Substring(0, eq)] = s.Substring(eq + 1);
                }
            }
            finally { N.DestroyEnvironmentBlock(block); }
        }
        foreach (string k in new[] { "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY" }) env.Remove(k);
        var path = new List<string> { @"D:\ProgramData", @"D:\ProgramData\Library\mingw-w64\bin", @"D:\ProgramData\Library\usr\bin",
            @"D:\ProgramData\Library\bin", @"D:\ProgramData\Scripts", @"D:\Program Files" };
        if (folder != null)
        {
            string ait = Path.Combine(folder, ".aitemp");
            env["TEMP"] = env["TMP"] = Path.Combine(ait, "tmp");
            env["PIP_CACHE_DIR"] = Path.Combine(ait, "pip-cache");
            env["PYTHONUSERBASE"] = Path.Combine(ait, "pyuser");
            env["npm_config_cache"] = Path.Combine(ait, "npm-cache");
            env["npm_config_prefix"] = Path.Combine(ait, "npm-global");
            env["UV_CACHE_DIR"] = Path.Combine(ait, "uv-cache");
            path.Add(Path.Combine(ait, "npm-global"));
            path.Add(Path.Combine(ait, "pyuser", "Python313", "Scripts"));
        }
        path.AddRange(new[] { @"C:\Program Files\Git\cmd", @"D:\Program Files\Blender Foundation\Blender 5.2",
            @"C:\Windows\System32", @"C:\Windows", @"C:\Windows\System32\WindowsPowerShell\v1.0" });
        env["PATH"] = string.Join(";", path);
        env["npm_config_fetch_retries"] = "1";
        env["npm_config_fetch_retry_mintimeout"] = "2000";
        env["npm_config_fetch_retry_maxtimeout"] = "5000";
        env["npm_config_update_notifier"] = "false";
        env["PYTHONIOENCODING"] = "utf-8";
        env["PYTHONUTF8"] = "1";
        env["PYTHONUNBUFFERED"] = "1";
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1";
        env["GIT_TERMINAL_PROMPT"] = "0";
        env["NO_COLOR"] = "1";
        env["AITEMP"] = "1";
        if (online)
        {
            foreach (string k in new[] { "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy" }) env[k] = ClashListener;
            env["NO_PROXY"] = env["no_proxy"] = "localhost,127.0.0.1";
        }
        return env;
    }

    static IntPtr EnvBlock(Dictionary<string, string> env)
    {
        var keys = new List<string>(env.Keys);
        keys.Sort(StringComparer.OrdinalIgnoreCase);
        var sb = new StringBuilder();
        foreach (string k in keys) sb.Append(k).Append('=').Append(env[k]).Append('\0');
        sb.Append('\0');
        return Marshal.StringToHGlobalUni(sb.ToString());
    }

    static Dictionary<string, object> Run(Dictionary<string, object> q)
    {
        string id = Str(q, "grant");
        string shell = q.ContainsKey("shell") ? Str(q, "shell") : "cmd";
        string command = Str(q, "command");
        bool online = q.ContainsKey("online") && (bool)q["online"];
        int timeout = q.ContainsKey("timeout") ? Convert.ToInt32(q["timeout"]) : 600;
        timeout = Math.Max(5, Math.Min(timeout, 3600));
        IntPtr token; string cwd, folder;
        if (id == "@verify")
        {
            if (shell != "python") throw new HelperError("shell", "自检只用 python");
            token = Logon(null);
            folder = null;
            cwd = @"C:\Users\" + User;
            online = false;
        }
        else
        {
            if (shell == "python") throw new HelperError("shell", "不支持的 shell：python");
            Grant g = GetGrant(id, true);
            cwd = q.ContainsKey("cwd") ? Path.GetFullPath(Str(q, "cwd")) : g.Folders[0];
            folder = g.FolderOf(cwd);
            if (folder == null) throw new HelperError("path", "工作目录不在授权文件夹里：" + cwd);
            string real = RealPath(cwd);
            if (real == null) throw new HelperError("path", "工作目录不存在：" + cwd);
            if (g.FolderOf(real) == null) throw new HelperError("path", "工作目录经链接指到了授权文件夹外：" + real);
            token = g.Token();
        }
        string cmdline = CommandLine(shell, command);
        if (cmdline.Length > 32000) throw new HelperError("too_long", "命令太长");

        lock (runLock)
        {
            if (current != null && current.State == "running") throw new HelperError("busy", "上一条命令还在运行");
            ApplyWfp(online);
            var job = new Job { Id = "j" + Guid.NewGuid().ToString("N").Substring(0, 12), GrantId = id };
            IntPtr rd = IntPtr.Zero, wr = IntPtr.Zero, nul = IntPtr.Zero, envp = IntPtr.Zero;
            var pi = new N.PROCESS_INFORMATION();
            bool started = false;
            try
            {
                var sa = new N.SECURITY_ATTRIBUTES { nLength = Marshal.SizeOf(typeof(N.SECURITY_ATTRIBUTES)), bInheritHandle = 1 };
                if (!N.CreatePipe(out rd, out wr, ref sa, 65536)) throw new Win32Exception();
                N.SetHandleInformation(rd, 1, 0);
                nul = N.CreateFileW("NUL", 0x80000000, 3, ref sa, 3, 0, IntPtr.Zero);
                envp = EnvBlock(EnvFor(token, folder, online));
                var si = new N.STARTUPINFO { cb = Marshal.SizeOf(typeof(N.STARTUPINFO)), lpDesktop = desktopName,
                    dwFlags = 0x100 | 0x1 /*USESTDHANDLES|USESHOWWINDOW*/, wShowWindow = 0, hStdInput = nul, hStdOutput = wr, hStdError = wr };
                uint flags = 0x4 /*SUSPENDED*/ | 0x400 /*UNICODE_ENV*/ | 0x08000000 /*NO_WINDOW*/ | 0x200 /*NEW_GROUP*/ | 0x4000 /*BELOW_NORMAL*/;
                var cl = new StringBuilder(cmdline, cmdline.Length + 1);
                if (!N.CreateProcessAsUserW(token, null, cl, IntPtr.Zero, IntPtr.Zero, true, flags, envp, cwd, ref si, out pi))
                    throw new HelperError("start", "启动失败：" + new Win32Exception(Marshal.GetLastWin32Error()).Message);
                job.JobHandle = N.CreateJobObjectW(IntPtr.Zero, null);
                var info = new N.JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                info.BasicLimitInformation.LimitFlags = 0x2000 /*KILL_ON_CLOSE*/ | 0x400 /*DIE_ON_UNHANDLED*/ | 0x200 /*JOB_MEMORY*/ | 0x20 /*PRIORITY*/;
                info.BasicLimitInformation.PriorityClass = 0x4000;
                info.JobMemoryLimit = new UIntPtr(8UL * 1024 * 1024 * 1024);
                if (!N.SetInformationJobObject(job.JobHandle, 9, ref info, Marshal.SizeOf(typeof(N.JOBOBJECT_EXTENDED_LIMIT_INFORMATION))))
                    throw new HelperError("job", "设置作业对象失败：" + Marshal.GetLastWin32Error());
                if (!N.AssignProcessToJobObject(job.JobHandle, pi.hProcess))
                    throw new HelperError("job", "放进作业对象失败：" + Marshal.GetLastWin32Error());
                N.ResumeThread(pi.hThread);
                started = true;
                job.Process = pi.hProcess; job.Pid = pi.dwProcessId;
            }
            finally
            {
                if (!started)
                {
                    if (pi.hProcess != IntPtr.Zero) { N.TerminateProcess(pi.hProcess, 1); N.CloseHandle(pi.hProcess); }
                    if (job.JobHandle != IntPtr.Zero) N.CloseHandle(job.JobHandle);
                    if (rd != IntPtr.Zero) N.CloseHandle(rd);
                    if (id == "@verify") N.CloseHandle(token);
                    ApplyWfp(false);
                }
                if (pi.hThread != IntPtr.Zero) N.CloseHandle(pi.hThread);
                if (wr != IntPtr.Zero) N.CloseHandle(wr);
                if (nul != IntPtr.Zero && nul != new IntPtr(-1)) N.CloseHandle(nul);
                if (envp != IntPtr.Zero) Marshal.FreeHGlobal(envp);
            }
            jobs[job.Id] = job;
            current = job;
            var reader = new Thread(delegate ()
            {
                using (var fs = new FileStream(new SafeFileHandle(rd, true), FileAccess.Read, 4096, false))
                {
                    var buf = new byte[16384];
                    int n;
                    try { while ((n = fs.Read(buf, 0, buf.Length)) > 0) job.Out.Add(buf, n); } catch { }
                }
            }) { IsBackground = true };
            reader.Start();
            var verifyToken = id == "@verify" ? token : IntPtr.Zero;
            var waiter = new Thread(delegate () { Wait(job, timeout, reader, verifyToken); }) { IsBackground = true };
            waiter.Start();
            Log("run " + job.Id + " grant=" + id + " shell=" + shell + " online=" + online + " pid=" + job.Pid + " cwd=" + cwd);
            var r = Ok(); r["job"] = job.Id; r["pid"] = job.Pid;
            return r;
        }
    }

    static void Wait(Job job, int timeout, Thread reader, IntPtr closeToken)
    {
        uint w = N.WaitForSingleObject(job.Process, (uint)timeout * 1000);
        lock (job)
        {
            if (w != 0 && job.Reason == "") job.Reason = "timeout";
            N.TerminateJobObject(job.JobHandle, 1);   // 主进程结束后，留在后台的子进程一并结束
        }
        uint code; N.GetExitCodeProcess(job.Process, out code);
        reader.Join(5000);
        lock (job)
        {
            job.ExitCode = (int)code;
            job.State = job.Reason == "" ? "done" : (job.Reason == "timeout" ? "timeout" : "killed");
            job.Ended = DateTime.Now;
            N.CloseHandle(job.Process); job.Process = IntPtr.Zero;
            N.CloseHandle(job.JobHandle); job.JobHandle = IntPtr.Zero;
        }
        if (closeToken != IntPtr.Zero) N.CloseHandle(closeToken);
        lock (runLock)
        {
            if (current == job) current = null;
            try { ApplyWfp(false); } catch (Exception e) { Log("wfp offline: " + e.Message); }
            // 只留最近 50 条的结果
            if (jobs.Count > 50)
            {
                var old = new List<Job>(jobs.Values);
                old.Sort((a, b) => a.Started.CompareTo(b.Started));
                for (int i = 0; i < old.Count - 50; i++) if (old[i].State != "running") jobs.Remove(old[i].Id);
            }
        }
        job.Done.Set();
        Log("end " + job.Id + " state=" + job.State + " exit=" + job.ExitCode + " bytes=" + job.Out.Total);
        try { Sweep(); } catch { }
    }

    static Dictionary<string, object> Poll(Dictionary<string, object> q)
    {
        Job job;
        lock (runLock) jobs.TryGetValue(Str(q, "job"), out job);
        if (job == null) throw new HelperError("unknown_job", "没有这个任务");
        int wait = q.ContainsKey("wait") ? Math.Min(Convert.ToInt32(q["wait"]), 70000) : 0;
        if (wait > 0) job.Done.WaitOne(wait);
        var r = Ok();
        lock (job)
        {
            r["state"] = job.State; r["exit"] = job.ExitCode; r["reason"] = job.Reason;
            r["seconds"] = Math.Round(((job.State == "running" ? DateTime.Now : job.Ended) - job.Started).TotalSeconds, 1);
        }
        r["output"] = job.Out.Text(); r["bytes"] = job.Out.Total;
        return r;
    }

    static void KillGrant(string id, string why)
    {
        lock (runLock) foreach (Job j in jobs.Values) if (j.GrantId == id) j.Kill(why);
    }

    // ------------------------------------------------------------------ 读写文件（模拟 aitemp + 授权组的身份）
    static Dictionary<string, object> Fs(Dictionary<string, object> q)
    {
        Grant g = GetGrant(Str(q, "grant"), true);
        string action = Str(q, "action");
        string path = Path.GetFullPath(Str(q, "path"));
        if (g.FolderOf(path) == null) throw new HelperError("path", "路径不在授权文件夹里：" + path);
        // 先以 SYSTEM 解析真实路径（或最近一级已存在的上级），经联接指到授权文件夹外就拒绝。
        // 模拟 aitemp 之后打不开授权外的目标，解析不出来，会被当成空文件夹（2026-11-18 验收发现）。
        string probe = path;
        while (probe != null && !Directory.Exists(probe) && !File.Exists(probe)) probe = Path.GetDirectoryName(probe);
        string realp = probe == null ? null : RealPath(probe);
        if (realp == null || g.FolderOf(realp) == null) throw new HelperError("path", "经链接指到了授权文件夹外：" + (realp ?? path));
        IntPtr token = g.Token();
        using (WindowsIdentity.Impersonate(token))
        {
            try
            {
                switch (action)
                {
                    case "list": return FsList(g, path, q.ContainsKey("depth") ? Convert.ToInt32(q["depth"]) : 1);
                    case "read": return FsRead(g, path, q.ContainsKey("offset") ? Convert.ToInt64(q["offset"]) : 0,
                        q.ContainsKey("length") ? Convert.ToInt32(q["length"]) : 1024 * 1024);
                    case "write": return FsWrite(g, path, Str(q, "data"), q.ContainsKey("append") && (bool)q["append"]);
                }
                throw new HelperError("action", "不支持的操作：" + action);
            }
            catch (UnauthorizedAccessException e) { throw new HelperError("denied", "没有权限：" + e.Message); }
        }
    }

    static void CheckReal(Grant g, string path)
    {
        string real = RealPath(path);
        if (real != null && g.FolderOf(real) == null) throw new HelperError("path", "经链接指到了授权文件夹外：" + real);
    }

    static Dictionary<string, object> FsList(Grant g, string path, int depth)
    {
        depth = Math.Max(1, Math.Min(depth, 4));
        if (!Directory.Exists(path))
        {
            if (!File.Exists(path)) throw new HelperError("not_found", "不存在：" + path);
            CheckReal(g, path);
            var fi = new FileInfo(path);
            var r1 = Ok(); r1["file"] = new Dictionary<string, object> { { "p", fi.Name }, { "s", fi.Length }, { "m", Iso(fi.LastWriteTime) } };
            return r1;
        }
        CheckReal(g, path);
        var items = new List<object>();
        bool more = false;
        var queue = new Queue<KeyValuePair<string, int>>();
        queue.Enqueue(new KeyValuePair<string, int>(path, 1));
        while (queue.Count > 0)
        {
            var cur = queue.Dequeue();
            string[] dirs, files;
            try { dirs = Directory.GetDirectories(cur.Key); files = Directory.GetFiles(cur.Key); }
            catch (UnauthorizedAccessException) { continue; }
            Array.Sort(dirs, StringComparer.OrdinalIgnoreCase); Array.Sort(files, StringComparer.OrdinalIgnoreCase);
            foreach (string d in dirs)
            {
                if (items.Count >= 1000) { more = true; break; }
                var di = new DirectoryInfo(d);
                bool link = (di.Attributes & FileAttributes.ReparsePoint) != 0;
                items.Add(new Dictionary<string, object> { { "p", Rel(path, d) + "\\" }, { "d", true }, { "link", link } });
                if (!link && cur.Value < depth && di.Name != ".aitemp" && di.Name != "node_modules" && di.Name != ".git" && di.Name != ".venv")
                    queue.Enqueue(new KeyValuePair<string, int>(d, cur.Value + 1));
            }
            foreach (string f in files)
            {
                if (items.Count >= 1000) { more = true; break; }
                var fi = new FileInfo(f);
                items.Add(new Dictionary<string, object> { { "p", Rel(path, f) }, { "s", fi.Length }, { "m", Iso(fi.LastWriteTime) } });
            }
            if (more) break;
        }
        var r = Ok(); r["items"] = items; r["more"] = more;
        return r;
    }

    static Dictionary<string, object> FsRead(Grant g, string path, long offset, int length)
    {
        if (!File.Exists(path)) throw new HelperError("not_found", "文件不存在：" + path);
        CheckReal(g, path);
        length = Math.Max(0, Math.Min(length, 4 * 1024 * 1024));
        using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
        {
            fs.Seek(Math.Min(offset, fs.Length), SeekOrigin.Begin);
            var buf = new byte[(int)Math.Min(length, Math.Max(0, fs.Length - fs.Position))];
            int got = 0;
            while (got < buf.Length) { int n = fs.Read(buf, got, buf.Length - got); if (n <= 0) break; got += n; }
            var r = Ok(); r["data"] = Convert.ToBase64String(buf, 0, got); r["size"] = fs.Length; r["eof"] = fs.Position >= fs.Length;
            return r;
        }
    }

    static Dictionary<string, object> FsWrite(Grant g, string path, string data, bool append)
    {
        byte[] bytes = Convert.FromBase64String(data);
        string dir = Path.GetDirectoryName(path);
        // 先找到已存在的最近一级目录，确认它没有经链接指到外面，再建缺的目录
        string probe = dir;
        while (probe != null && !Directory.Exists(probe)) probe = Path.GetDirectoryName(probe);
        if (probe == null || g.FolderOf(probe) == null) throw new HelperError("path", "路径不在授权文件夹里：" + path);
        CheckReal(g, probe);
        Directory.CreateDirectory(dir);
        if (File.Exists(path)) CheckReal(g, path);
        using (var fs = new FileStream(path, append ? FileMode.Append : FileMode.Create, FileAccess.Write, FileShare.Read))
            fs.Write(bytes, 0, bytes.Length);
        var r = Ok(); r["bytes"] = bytes.Length;
        return r;
    }

    static string Rel(string root, string p) { return p.Substring(root.TrimEnd('\\').Length).TrimStart('\\'); }
    static string Iso(DateTime t) { return t.ToString("yyyy-MM-dd HH:mm:ss"); }

    // ------------------------------------------------------------------ 清理和巡查
    static void CleanDir(string dir)
    {
        if (!Directory.Exists(dir)) return;
        foreach (string f in Directory.GetFiles(dir)) try { File.SetAttributes(f, FileAttributes.Normal); File.Delete(f); } catch { }
        foreach (string d in Directory.GetDirectories(dir)) try { Directory.Delete(d, true); } catch { }
    }

    static Dictionary<string, object> Clean()
    {
        lock (runLock) if (current != null) throw new HelperError("busy", "有命令在运行");
        CleanDir(@"C:\Users\" + User + @"\AppData\Local\Temp");
        return Ok();
    }

    static string ProcessSid(IntPtr h)
    {
        IntPtr tok;
        if (!N.OpenProcessToken(h, 0x0008, out tok)) return null;
        try
        {
            int len;
            N.GetTokenInformation(tok, 1, IntPtr.Zero, 0, out len);
            IntPtr buf = Marshal.AllocHGlobal(len);
            try
            {
                if (!N.GetTokenInformation(tok, 1, buf, len, out len)) return null;
                return new SecurityIdentifier(Marshal.ReadIntPtr(buf)).Value;
            }
            finally { Marshal.FreeHGlobal(buf); }
        }
        finally { N.CloseHandle(tok); }
    }

    /// <summary>结束不在当前作业里的 aitemp 进程（例如经计划任务或 WMI 绕出作业的）。</summary>
    static int Sweep()
    {
        if (Sid == null) return 0;
        int killed = 0;
        // 整个巡查都持有 runLock：否则新命令正在创建（还没放进作业）时会被当成漏网进程结束掉（2026-11-18 验收发现）
        lock (runLock)
        {
        IntPtr cur = current != null && current.State == "running" ? current.JobHandle : IntPtr.Zero;
        foreach (Process p in Process.GetProcesses())
        {
            if (p.Id <= 4) continue;
            string pname = "?";
            try { pname = p.ProcessName; } catch { }
            IntPtr h = N.OpenProcess(0x1000 | 0x0001 /*QUERY_LIMITED|TERMINATE*/, false, p.Id);
            if (h == IntPtr.Zero) continue;
            try
            {
                if (ProcessSid(h) != Sid.Value) continue;
                bool inJob;
                if (cur != IntPtr.Zero && N.IsProcessInJob(h, cur, out inJob) && inJob) continue;
                N.TerminateProcess(h, 1);
                killed++;
                Log("sweep killed " + pname + " pid=" + p.Id);
            }
            finally { N.CloseHandle(h); }
        }
        }
        return killed;
    }

    // ------------------------------------------------------------------ 沙盒自检
    const string ProbeScript = @"
import json, os, socket
r = []
def chk(name, fn):
    try:
        fn(); r.append([name, False, 'allowed'])
    except Exception as e:
        r.append([name, True, type(e).__name__])
for p in [r'C:\Users\blender', r'C:\Users\Administrator', r'C:\ProgramData\BlenderMCP', r'D:\Projects', r'D:\Projects\maa-cli', r'D:\Projects\skland', r'D:\Blender']:
    chk('list ' + p, lambda p=p: os.listdir(p))
chk('read agent.token', lambda: open(r'C:\ProgramData\BlenderMCP\agent.token', 'rb').read(1))
for p in [r'D:\Program Files\aitemp_probe.txt', r'D:\ProgramData\aitemp_probe.txt', r'D:\aitemp_probe.txt', r'C:\aitemp_probe.txt']:
    def w(p=p):
        open(p, 'w').write('x'); os.remove(p)
    chk('write ' + p, w)
for port in [8766, 8765, 9876, 17860, 8086, 8087, 7897, 7899]:
    chk('connect 127.0.0.1:%d' % port, lambda port=port: socket.create_connection(('127.0.0.1', port), timeout=3).close())
chk('connect 1.1.1.1:443', lambda: socket.create_connection(('1.1.1.1', 443), timeout=4).close())
print('AITEMP-PROBE ' + json.dumps(r))
";

    static Dictionary<string, object> Verify()
    {
        var sw = Stopwatch.StartNew();
        var checks = new List<object>();
        var fixedList = new List<string>();
        // 1 D 盘顶层目录：新出现的目录按数据目录处理（拒绝读写）；程序目录缺拒绝写入就补
        foreach (string c in SyncTopDirs()) fixedList.Add(c);     // 数据目录（含授权中的）由它处理
        foreach (string d in Directory.GetDirectories(@"D:\"))
        {
            string name = Path.GetFileName(d);
            if (Array.IndexOf(SkipDirsOnD, name) >= 0) continue;
            bool program = Array.IndexOf(ProgramDirsOnD, name) >= 0;
            if (!program) continue;
            try
            {
                if (HasDeny(d)) continue;
                var di = new DirectoryInfo(d);
                var ds = di.GetAccessControl(AccessControlSections.Access);
                if (program)
                    ds.AddAccessRule(new FileSystemAccessRule(Sid, FileSystemRights.WriteData | FileSystemRights.AppendData |
                        FileSystemRights.WriteExtendedAttributes | FileSystemRights.WriteAttributes | FileSystemRights.Delete |
                        FileSystemRights.DeleteSubdirectoriesAndFiles, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                        PropagationFlags.None, AccessControlType.Deny));
                else
                    ds.AddAccessRule(new FileSystemAccessRule(Sid, FileSystemRights.FullControl,
                        InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Deny));
                di.SetAccessControl(ds);
                fixedList.Add(d + (program ? "：补上拒绝写入" : "：新目录，已按数据目录拒绝读写"));
            }
            catch (Exception e) { checks.Add(new object[] { "权限 " + d, false, e.Message }); }
        }
        foreach (string p in Protected)
            if (Directory.Exists(p) && !HasDeny(p)) checks.Add(new object[] { "受保护位置的拒绝项 " + p, false, "缺少，请重新运行安装包" });
        foreach (string p in new[] { @"D:\", @"C:\" })
            if (!HasDeny(p)) checks.Add(new object[] { "根目录的拒绝项 " + p, false, "缺少，请重新运行安装包" });
        // 2 断网
        lock (runLock) if (current == null) ApplyWfp(false);
        // 3 以 aitemp 身份实际试一遍
        var q = new Dictionary<string, object> { { "grant", "@verify" }, { "shell", "python" }, { "command", ProbeScript }, { "timeout", 90 } };
        Dictionary<string, object> run = Run(q);
        Job job; lock (runLock) job = jobs[(string)run["job"]];
        job.Done.WaitOne(100000);
        string text = job.Out.Text();
        int at = text.IndexOf("AITEMP-PROBE ");
        if (at < 0) checks.Add(new object[] { "以 aitemp 身份运行自检脚本", false, text.Length > 500 ? text.Substring(0, 500) : text });
        else
        {
            string line = text.Substring(at + 13).Split('\n')[0];
            foreach (object o in (System.Collections.IEnumerable)json.DeserializeObject(line))
            {
                var a = new List<object>();
                foreach (object x in (System.Collections.IEnumerable)o) a.Add(x);
                checks.Add(new object[] { (string)a[0] + "（应被拒绝）", (bool)a[1], (string)a[2] });
            }
        }
        bool ok = true;
        foreach (object[] c in checks) if (!(bool)c[1]) ok = false;
        var r = Ok(); r["passed"] = ok; r["checks"] = checks; r["fixed"] = fixedList; r["ms"] = sw.ElapsedMilliseconds;
        Log("verify passed=" + ok + " fixed=" + fixedList.Count);
        return r;
    }

    static bool HasDeny(string path)
    {
        var ds = new DirectoryInfo(path).GetAccessControl(AccessControlSections.Access);
        foreach (FileSystemAccessRule r in ds.GetAccessRules(true, false, typeof(SecurityIdentifier)))
            if (r.IdentityReference.Equals(Sid) && r.AccessControlType == AccessControlType.Deny) return true;
        return false;
    }

    // ------------------------------------------------------------------ 管道
    static void PipeLoop()
    {
        while (!stopping)
        {
            NamedPipeServerStream server = null;
            try
            {
                var ps = new PipeSecurity();
                ps.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null), PipeAccessRights.FullControl, AccessControlType.Allow));
                ps.AddAccessRule(new PipeAccessRule(WindowsIdentity.GetCurrent().User, PipeAccessRights.FullControl, AccessControlType.Allow));
                if (clientSid != null)
                    // Python 的 open() 以 GENERIC_READ|GENERIC_WRITE 打开管道；GENERIC_WRITE 含 FILE_APPEND_DATA（对管道就是 CreateNewInstance）
                    ps.AddAccessRule(new PipeAccessRule(clientSid, PipeAccessRights.ReadWrite | PipeAccessRights.Synchronize |
                        PipeAccessRights.CreateNewInstance, AccessControlType.Allow));
                server = new NamedPipeServerStream(PipeName, PipeDirection.InOut, NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte, PipeOptions.None, 65536, 65536, ps);
                server.WaitForConnection();
                if (stopping) { server.Dispose(); break; }
                var s = server;
                new Thread(delegate () { Serve(s); }) { IsBackground = true }.Start();
            }
            catch (Exception e)
            {
                Log("pipe: " + e.Message);
                if (server != null) server.Dispose();
                Thread.Sleep(1000);
            }
        }
    }

    static void Serve(NamedPipeServerStream s)
    {
        try
        {
            var reader = new StreamReader(s, new UTF8Encoding(false), false, 65536);
            string line = reader.ReadLine();
            if (line == null) return;
            Dictionary<string, object> resp;
            try { resp = Dispatch((Dictionary<string, object>)json.DeserializeObject(line)); }
            catch (HelperError e) { resp = Err(e.Code, e.Message); }
            catch (Exception e) { resp = Err("internal", e.GetType().Name + ": " + e.Message); Log("error: " + e); }
            byte[] b = new UTF8Encoding(false).GetBytes(json.Serialize(resp) + "\n");
            s.Write(b, 0, b.Length);
            s.Flush();
            s.WaitForPipeDrain();
        }
        catch (Exception e) { Log("serve: " + e.Message); }
        finally { try { s.Disconnect(); } catch { } s.Dispose(); }
    }

    static Dictionary<string, object> Dispatch(Dictionary<string, object> q)
    {
        string op = Str(q, "op");
        if (op != "status" && password == null) throw new HelperError("not_ready", "助手没有初始化：" + startError);
        switch (op)
        {
            case "status":
                var r = Ok();
                r["version"] = Version; r["ready"] = password != null; r["error"] = startError;
                r["sid"] = Sid == null ? null : Sid.Value; r["online"] = wfpOnline == 1;
                lock (runLock) r["running"] = current == null ? null : current.Id;
                lock (grants) r["grants"] = new List<string>(grants.Keys);
                return r;
            case "prepare": return Prepare(q);
            case "release": return Release(Str(q, "grant"), AsList(q, "folders"));
            case "reconcile": return Reconcile(q);
            case "check_folder": var c = Ok(); c["real"] = CheckFolder(Str(q, "folder")); return c;
            case "run": return Run(q);
            case "poll": return Poll(q);
            case "kill":
                Job j; lock (runLock) jobs.TryGetValue(Str(q, "job"), out j);
                if (j != null) j.Kill(q.ContainsKey("reason") ? Str(q, "reason") : "killed");
                return Ok();
            case "kill_grant": KillGrant(Str(q, "grant"), q.ContainsKey("reason") ? Str(q, "reason") : "revoked"); return Ok();
            case "fs": return Fs(q);
            case "verify": return Verify();
            case "sweep": var sres = Ok(); sres["killed"] = Sweep(); return sres;
            case "clean": return Clean();
        }
        throw new HelperError("op", "不支持的请求：" + op);
    }

    static List<object> AsList(Dictionary<string, object> q, string k)
    {
        var res = new List<object>();
        object v;
        if (q.TryGetValue(k, out v) && v is System.Collections.IEnumerable && !(v is string))
            foreach (object x in (System.Collections.IEnumerable)v) res.Add(x);
        return res;
    }

    static string Str(Dictionary<string, object> q, string k)
    {
        object v;
        if (!q.TryGetValue(k, out v) || !(v is string)) throw new HelperError("bad_request", "缺少参数 " + k);
        return (string)v;
    }

    static Dictionary<string, object> Ok() { return new Dictionary<string, object> { { "ok", true } }; }
    static Dictionary<string, object> Err(string code, string msg)
    {
        return new Dictionary<string, object> { { "ok", false }, { "error", code }, { "msg", msg } };
    }
}

// ---------------------------------------------------------------------- Win32
static class N
{
    [StructLayout(LayoutKind.Sequential)]
    public struct SECURITY_ATTRIBUTES { public int nLength; public IntPtr lpSecurityDescriptor; public int bInheritHandle; }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFO
    {
        public int cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION { public IntPtr hProcess, hThread; public int dwProcessId, dwThreadId; }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct PROFILEINFO
    {
        public int dwSize, dwFlags; public string lpUserName, lpProfilePath, lpDefaultPath, lpServerName, lpPolicyPath; public IntPtr hProfile;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit; public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize; public uint ActiveProcessLimit;
        public UIntPtr Affinity; public uint PriorityClass, SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct IO_COUNTERS { public ulong a, b, c, d, e, f; }

    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation; public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] public struct USER_INFO_1003 { public string password; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] public struct LOCALGROUP_INFO_1 { public string name, comment; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] public struct LOCALGROUP_INFO_1002 { public string comment; }
    [StructLayout(LayoutKind.Sequential)] public struct LOCALGROUP_MEMBERS_INFO_0 { public IntPtr sid; }

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool LogonUserW(string user, string domain, string password, int type, int provider, out IntPtr token);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool CreateProcessAsUserW(IntPtr token, string app, StringBuilder cmd, IntPtr pa, IntPtr ta, bool inherit,
        uint flags, IntPtr env, string cwd, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool ConvertStringSecurityDescriptorToSecurityDescriptorW(string sddl, uint rev, out IntPtr sd, out uint size);
    [DllImport("advapi32.dll", SetLastError = true)] public static extern bool OpenProcessToken(IntPtr h, uint access, out IntPtr tok);
    [DllImport("advapi32.dll", SetLastError = true)] public static extern bool GetTokenInformation(IntPtr tok, int cls, IntPtr buf, int len, out int ret);

    [DllImport("userenv.dll", CharSet = CharSet.Unicode, SetLastError = true)] public static extern bool LoadUserProfileW(IntPtr token, ref PROFILEINFO pi);
    [DllImport("userenv.dll", SetLastError = true)] public static extern bool UnloadUserProfile(IntPtr token, IntPtr profile);
    [DllImport("userenv.dll", SetLastError = true)] public static extern bool CreateEnvironmentBlock(out IntPtr env, IntPtr token, bool inherit);
    [DllImport("userenv.dll", SetLastError = true)] public static extern bool DestroyEnvironmentBlock(IntPtr env);

    [DllImport("user32.dll", SetLastError = true)] public static extern IntPtr GetProcessWindowStation();
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr CreateWindowStationW(string name, uint flags, uint access, ref SECURITY_ATTRIBUTES sa);
    [DllImport("user32.dll", SetLastError = true)] public static extern bool SetProcessWindowStation(IntPtr ws);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr CreateDesktopW(string name, string device, IntPtr devmode, uint flags, uint access, ref SECURITY_ATTRIBUTES sa);

    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CloseHandle(IntPtr h);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] public static extern bool SetFileSecurityW(string path, uint info, byte[] sd);
    [DllImport("kernel32.dll")] public static extern IntPtr LocalFree(IntPtr p);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CreatePipe(out IntPtr rd, out IntPtr wr, ref SECURITY_ATTRIBUTES sa, int size);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool SetHandleInformation(IntPtr h, uint mask, uint flags);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr CreateFileW(string name, uint access, uint share, ref SECURITY_ATTRIBUTES sa, uint disp, uint flags, IntPtr tmpl);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr CreateFileW(string name, uint access, uint share, IntPtr sa, uint disp, uint flags, IntPtr tmpl);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern uint GetFinalPathNameByHandleW(IntPtr h, StringBuilder buf, uint len, uint flags);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] public static extern IntPtr CreateJobObjectW(IntPtr sa, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetInformationJobObject(IntPtr job, int cls, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION info, int len);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr proc);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool TerminateJobObject(IntPtr job, uint code);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool IsProcessInJob(IntPtr proc, IntPtr job, out bool result);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern uint ResumeThread(IntPtr t);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool GetExitCodeProcess(IntPtr h, out uint code);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool TerminateProcess(IntPtr h, uint code);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)] public static extern int NetUserSetInfo(string server, string user, int level, ref USER_INFO_1003 buf, out uint err);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    public static extern int NetUserGetLocalGroups(string server, string user, int level, int flags, out IntPtr buf, int max, out int read, out int total);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    public static extern int NetLocalGroupEnum(string server, int level, out IntPtr buf, int max, out int read, out int total, ref IntPtr resume);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)] public static extern int NetLocalGroupAdd(string server, int level, ref LOCALGROUP_INFO_1 buf, out int parm);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)] public static extern int NetLocalGroupSetInfo(string server, string group, int level, ref LOCALGROUP_INFO_1002 buf, out int parm);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)] public static extern int NetLocalGroupDel(string server, string group);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)] public static extern int NetLocalGroupAddMembers(string server, string group, int level, ref LOCALGROUP_MEMBERS_INFO_0 buf, int n);
    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)] public static extern int NetLocalGroupDelMembers(string server, string group, int level, ref LOCALGROUP_MEMBERS_INFO_0 buf, int n);
    [DllImport("netapi32.dll")] public static extern int NetApiBufferFree(IntPtr buf);
}
