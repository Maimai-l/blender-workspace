using UnityEditor;
using UnityEngine;

namespace DungeonEscape.EditorTools
{
    /// <summary>
    /// Unattended-testing helper. When the editor window sits in the background its player loop may not run,
    /// so while "Pump" is on (session-scoped, off by default) Play Mode is advanced with EditorApplication.Step()
    /// at a fixed rate. Each step advances game time by Time.fixedDeltaTime (0.02 s).
    /// </summary>
    [InitializeOnLoad]
    public static class DETicker
    {
        public static int EditorTicks;
        public static int Steps;
        public static float StepsPerSecond = 50f;
        static double lastStep;

        public static bool Pump
        {
            get { return SessionState.GetBool("DE_Pump", false); }
            set { SessionState.SetBool("DE_Pump", value); }
        }

        static DETicker()
        {
            EditorApplication.update += Tick;
        }

        static void Tick()
        {
            EditorTicks++;
            if (!Pump || !EditorApplication.isPlaying) return;
            double now = EditorApplication.timeSinceStartup;
            if (lastStep <= 0 || now - lastStep > 1.0) lastStep = now - 1.0 / StepsPerSecond;
            int n = (int)((now - lastStep) * StepsPerSecond);
            if (n <= 0) return;
            if (n > 10) { n = 10; lastStep = now; } else lastStep += n / StepsPerSecond;
            if (!EditorApplication.isPaused) EditorApplication.isPaused = true;
            for (int i = 0; i < n && EditorApplication.isPlaying; i++) { EditorApplication.Step(); Steps++; }
        }

        [MenuItem("Dungeon Escape/Test/Toggle Play Mode Pump")]
        static void Toggle() { Pump = !Pump; Debug.Log("[DE] Pump " + Pump); }

        /// <summary>Starts Play Mode with the autopilot (1 = full playthrough, 2 = defeat test).</summary>
        public static void RunAutopilot(int mode)
        {
            PlayerPrefs.SetInt("DE_AutoPilot", mode);
            PlayerPrefs.Save();
            Pump = true;
            EditorApplication.isPlaying = true;
        }
    }
}
