// AitempWfp: block the sandbox account aitemp from loopback (127.0.0.0/8, ::1) with Windows Filtering Platform
// filters, optionally permitting only 127.0.0.1:7899 (the Clash browser listener). Windows Firewall rules do not
// apply to loopback (2026-11-18 test), WFP filters at the ALE connect layers do.
// Filters are persistent (survive reboots) and live in their own provider and sublayer, so Remove() takes out
// exactly what Apply() added. Needs administrator / SYSTEM. Used by aitemp_test.ps1 (Add-Type) and later by the helper.
using System;
using System.Runtime.InteropServices;

public static class AitempWfp
{
    static readonly Guid Provider = new Guid("5c0a9f3e-7a61-4b8e-9c2d-41a7e0f2b001");
    static readonly Guid SubLayer = new Guid("5c0a9f3e-7a61-4b8e-9c2d-41a7e0f2b002");
    static readonly Guid FBlockV4 = new Guid("5c0a9f3e-7a61-4b8e-9c2d-41a7e0f2b101");
    static readonly Guid FBlockV6 = new Guid("5c0a9f3e-7a61-4b8e-9c2d-41a7e0f2b102");
    static readonly Guid FPermitClash = new Guid("5c0a9f3e-7a61-4b8e-9c2d-41a7e0f2b103");
    static readonly Guid LayerV4 = new Guid("c38d57d1-05a7-4c33-904f-7fbceee60e82");   // FWPM_LAYER_ALE_AUTH_CONNECT_V4
    static readonly Guid LayerV6 = new Guid("4a72393b-319f-44bc-84c3-ba54dcb3b6b4");   // FWPM_LAYER_ALE_AUTH_CONNECT_V6
    static readonly Guid CondUser = new Guid("af043a0a-b34d-4f86-979c-c90371af6e66");  // FWPM_CONDITION_ALE_USER_ID
    static readonly Guid CondRAddr = new Guid("b235ae9a-1d64-49b8-a44c-5ff3d9095045"); // FWPM_CONDITION_IP_REMOTE_ADDRESS
    static readonly Guid CondRPort = new Guid("c35a604d-d22b-4e1a-91b4-68f674ee674b"); // FWPM_CONDITION_IP_REMOTE_PORT

    const uint FWP_UINT8 = 1, FWP_UINT16 = 2, FWP_BYTE_ARRAY16 = 11, FWP_SECURITY_DESCRIPTOR = 14, FWP_V4_ADDR_MASK = 0x100;
    const uint FWP_MATCH_EQUAL = 0, ACTION_BLOCK = 0x1001, ACTION_PERMIT = 0x1002, PERSISTENT = 1;
    const uint E_ALREADY_EXISTS = 0x80320009, E_FILTER_NOT_FOUND = 0x80320003, E_SUBLAYER_NOT_FOUND = 0x80320007,
               E_PROVIDER_NOT_FOUND = 0x80320005;

    [StructLayout(LayoutKind.Sequential)] public struct DISPLAY { public IntPtr name; public IntPtr description; }
    [StructLayout(LayoutKind.Sequential)] public struct BLOB { public uint size; public IntPtr data; }
    [StructLayout(LayoutKind.Sequential)] public struct V4MASK { public uint addr; public uint mask; }
    [StructLayout(LayoutKind.Explicit, Size = 16)]
    public struct VALUE { [FieldOffset(0)] public uint type; [FieldOffset(8)] public ulong u64; [FieldOffset(8)] public IntPtr ptr; }
    [StructLayout(LayoutKind.Explicit, Size = 40)]
    public struct CONDITION { [FieldOffset(0)] public Guid fieldKey; [FieldOffset(16)] public uint matchType; [FieldOffset(24)] public VALUE value; }
    [StructLayout(LayoutKind.Explicit, Size = 64)]
    public struct PROVIDER {
        [FieldOffset(0)] public Guid key; [FieldOffset(16)] public DISPLAY display; [FieldOffset(32)] public uint flags;
        [FieldOffset(40)] public BLOB data; [FieldOffset(56)] public IntPtr serviceName; }
    [StructLayout(LayoutKind.Explicit, Size = 72)]
    public struct SUBLAYER {
        [FieldOffset(0)] public Guid key; [FieldOffset(16)] public DISPLAY display; [FieldOffset(32)] public uint flags;
        [FieldOffset(40)] public IntPtr providerKey; [FieldOffset(48)] public BLOB data; [FieldOffset(64)] public ushort weight; }
    [StructLayout(LayoutKind.Explicit, Size = 200)]
    public struct FILTER {
        [FieldOffset(0)] public Guid key; [FieldOffset(16)] public DISPLAY display; [FieldOffset(32)] public uint flags;
        [FieldOffset(40)] public IntPtr providerKey; [FieldOffset(48)] public BLOB data; [FieldOffset(64)] public Guid layerKey;
        [FieldOffset(80)] public Guid subLayerKey; [FieldOffset(96)] public VALUE weight; [FieldOffset(112)] public uint numConditions;
        [FieldOffset(120)] public IntPtr conditions; [FieldOffset(128)] public uint actionType; [FieldOffset(132)] public Guid actionGuid;
        [FieldOffset(152)] public ulong rawContext; [FieldOffset(168)] public IntPtr reserved; [FieldOffset(176)] public ulong filterId;
        [FieldOffset(184)] public VALUE effectiveWeight; }

    [DllImport("fwpuclnt.dll", CharSet = CharSet.Unicode)] static extern uint FwpmEngineOpen0(string server, uint authn, IntPtr ident, IntPtr session, out IntPtr engine);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmEngineClose0(IntPtr engine);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmTransactionBegin0(IntPtr engine, uint flags);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmTransactionCommit0(IntPtr engine);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmTransactionAbort0(IntPtr engine);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmProviderAdd0(IntPtr engine, ref PROVIDER p, IntPtr sd);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmSubLayerAdd0(IntPtr engine, ref SUBLAYER s, IntPtr sd);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmFilterAdd0(IntPtr engine, ref FILTER f, IntPtr sd, out ulong id);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmFilterDeleteByKey0(IntPtr engine, ref Guid key);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmSubLayerDeleteByKey0(IntPtr engine, ref Guid key);
    [DllImport("fwpuclnt.dll")] static extern uint FwpmProviderDeleteByKey0(IntPtr engine, ref Guid key);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool ConvertStringSecurityDescriptorToSecurityDescriptorW(string sddl, uint rev, out IntPtr sd, out uint size);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr p);

    static void Check(uint rc, string what, params uint[] ok) {
        if (rc == 0) return;
        foreach (var o in ok) if (rc == o) return;
        throw new Exception(string.Format("{0} failed: 0x{1:X8}", what, rc));
    }

    static IntPtr Guid1(Guid g) { IntPtr p = Marshal.AllocHGlobal(16); Marshal.StructureToPtr(g, p, false); return p; }

    static IntPtr Conditions(CONDITION[] c) {
        IntPtr p = Marshal.AllocHGlobal(40 * c.Length);
        for (int i = 0; i < c.Length; i++) Marshal.StructureToPtr(c[i], p + 40 * i, false);
        return p;
    }

    static void AddFilter(IntPtr engine, Guid key, string name, Guid layer, byte weight, uint action, CONDITION[] conds, IntPtr providerKey) {
        var f = new FILTER();
        f.key = key; f.flags = PERSISTENT; f.providerKey = providerKey; f.layerKey = layer; f.subLayerKey = SubLayer;
        f.display.name = Marshal.StringToHGlobalUni(name);
        f.weight.type = FWP_UINT8; f.weight.u64 = weight;
        f.numConditions = (uint)conds.Length; f.conditions = Conditions(conds);
        f.actionType = action;
        try { ulong id; Check(FwpmFilterAdd0(engine, ref f, IntPtr.Zero, out id), "FwpmFilterAdd0 " + name); }
        finally { Marshal.FreeHGlobal(f.conditions); Marshal.FreeHGlobal(f.display.name); }
    }

    static IntPtr Open() {
        IntPtr engine;
        Check(FwpmEngineOpen0(null, 10 /* RPC_C_AUTHN_WINNT */, IntPtr.Zero, IntPtr.Zero, out engine), "FwpmEngineOpen0");
        return engine;
    }

    static void DeleteFilters(IntPtr engine) {
        foreach (var k in new[] { FBlockV4, FBlockV6, FPermitClash }) { var g = k; Check(FwpmFilterDeleteByKey0(engine, ref g), "delete filter", E_FILTER_NOT_FOUND); }
    }

    /// <summary>Block all loopback connections made by the account with this SID; if allowClash, still permit 127.0.0.1:7899.</summary>
    public static string Apply(string sid, bool allowClash) {
        IntPtr engine = Open(), sd = IntPtr.Zero, sdBlob = IntPtr.Zero, v4 = IntPtr.Zero, v6 = IntPtr.Zero, prov = IntPtr.Zero;
        IntPtr pname = IntPtr.Zero, sname = IntPtr.Zero;
        bool inTx = false;
        try {
            uint sdSize;
            if (!ConvertStringSecurityDescriptorToSecurityDescriptorW("O:LSD:(A;;CC;;;" + sid + ")", 1, out sd, out sdSize))
                throw new Exception("bad SID " + sid + " (error " + Marshal.GetLastWin32Error() + ")");
            sdBlob = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(BLOB)));
            Marshal.StructureToPtr(new BLOB { size = sdSize, data = sd }, sdBlob, false);
            v4 = Marshal.AllocHGlobal(8);
            Marshal.StructureToPtr(new V4MASK { addr = 0x7F000000, mask = 0xFF000000 }, v4, false);
            v6 = Marshal.AllocHGlobal(16);
            byte[] loop6 = new byte[16]; loop6[15] = 1;
            Marshal.Copy(loop6, 0, v6, 16);
            prov = Guid1(Provider);

            Check(FwpmTransactionBegin0(engine, 0), "FwpmTransactionBegin0"); inTx = true;
            pname = Marshal.StringToHGlobalUni("AITemp sandbox");
            var p = new PROVIDER { key = Provider, flags = PERSISTENT }; p.display.name = pname;
            Check(FwpmProviderAdd0(engine, ref p, IntPtr.Zero), "FwpmProviderAdd0", E_ALREADY_EXISTS);
            sname = Marshal.StringToHGlobalUni("AITemp loopback");
            var s = new SUBLAYER { key = SubLayer, flags = PERSISTENT, providerKey = prov, weight = 0xFFFF }; s.display.name = sname;
            Check(FwpmSubLayerAdd0(engine, ref s, IntPtr.Zero), "FwpmSubLayerAdd0", E_ALREADY_EXISTS);
            DeleteFilters(engine);

            var user = new CONDITION { fieldKey = CondUser, matchType = FWP_MATCH_EQUAL }; user.value.type = FWP_SECURITY_DESCRIPTOR; user.value.ptr = sdBlob;
            var addr4 = new CONDITION { fieldKey = CondRAddr, matchType = FWP_MATCH_EQUAL }; addr4.value.type = FWP_V4_ADDR_MASK; addr4.value.ptr = v4;
            var addr6 = new CONDITION { fieldKey = CondRAddr, matchType = FWP_MATCH_EQUAL }; addr6.value.type = FWP_BYTE_ARRAY16; addr6.value.ptr = v6;
            AddFilter(engine, FBlockV4, "AITemp: block loopback v4", LayerV4, 1, ACTION_BLOCK, new[] { user, addr4 }, prov);
            AddFilter(engine, FBlockV6, "AITemp: block loopback v6", LayerV6, 1, ACTION_BLOCK, new[] { user, addr6 }, prov);
            if (allowClash) {
                var port = new CONDITION { fieldKey = CondRPort, matchType = FWP_MATCH_EQUAL }; port.value.type = FWP_UINT16; port.value.u64 = 7899;
                AddFilter(engine, FPermitClash, "AITemp: permit Clash 7899", LayerV4, 10, ACTION_PERMIT, new[] { user, addr4, port }, prov);
            }
            Check(FwpmTransactionCommit0(engine), "FwpmTransactionCommit0"); inTx = false;
            return allowClash ? "loopback blocked except 127.0.0.1:7899" : "loopback blocked";
        } finally {
            if (inTx) FwpmTransactionAbort0(engine);
            FwpmEngineClose0(engine);
            foreach (var m in new[] { sdBlob, v4, v6, prov, pname, sname }) if (m != IntPtr.Zero) Marshal.FreeHGlobal(m);
            if (sd != IntPtr.Zero) LocalFree(sd);
        }
    }

    /// <summary>Remove the filters, sublayer and provider that Apply() added.</summary>
    public static string Remove() {
        IntPtr engine = Open();
        try {
            DeleteFilters(engine);
            var s = SubLayer; Check(FwpmSubLayerDeleteByKey0(engine, ref s), "delete sublayer", E_SUBLAYER_NOT_FOUND);
            var p = Provider; Check(FwpmProviderDeleteByKey0(engine, ref p), "delete provider", E_PROVIDER_NOT_FOUND);
            return "removed";
        } finally { FwpmEngineClose0(engine); }
    }

    /// <summary>Struct sizes and offsets, to compare with the SDK headers (no admin needed).</summary>
    public static string Layout() {
        return string.Format("FILTER {0} (weight@{1} cond@{2} action@{3} raw@{4} eff@{5}), CONDITION {6}, VALUE {7}, SUBLAYER {8}, PROVIDER {9}, BLOB {10}",
            Marshal.SizeOf(typeof(FILTER)), Marshal.OffsetOf(typeof(FILTER), "weight"), Marshal.OffsetOf(typeof(FILTER), "conditions"),
            Marshal.OffsetOf(typeof(FILTER), "actionType"), Marshal.OffsetOf(typeof(FILTER), "rawContext"), Marshal.OffsetOf(typeof(FILTER), "effectiveWeight"),
            Marshal.SizeOf(typeof(CONDITION)), Marshal.SizeOf(typeof(VALUE)), Marshal.SizeOf(typeof(SUBLAYER)), Marshal.SizeOf(typeof(PROVIDER)),
            Marshal.SizeOf(typeof(BLOB)));
    }
}
