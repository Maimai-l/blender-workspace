using System;
using System.Runtime.InteropServices;
using UnityEditor;

namespace DungeonEscape.EditorTools
{
    /// <summary>Win32 helpers so Play Mode keeps ticking when the editor window is minimized during unattended testing.</summary>
    public static class DEWindow
    {
        [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hWnd);
        [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);

        static IntPtr Main()
        {
            return System.Diagnostics.Process.GetCurrentProcess().MainWindowHandle;
        }

        public static string State()
        {
            var h = Main();
            return "hwnd=" + h + " minimized=" + IsIconic(h) + " visible=" + IsWindowVisible(h) + " foreground=" + (GetForegroundWindow() == h);
        }

        /// <summary>Restores the editor window if minimized (SW_RESTORE) without stealing focus where possible.</summary>
        public static string Restore()
        {
            var h = Main();
            if (IsIconic(h)) ShowWindow(h, 4); // SW_SHOWNOACTIVATE
            if (IsIconic(h)) ShowWindow(h, 9); // SW_RESTORE
            return State();
        }
    }
}
