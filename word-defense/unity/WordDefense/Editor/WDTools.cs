using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace WordDefense.EditorTools
{
    /// <summary>
    /// Unattended-testing helper. When the editor window is in the background its player loop does not run, so while
    /// "Pump" is on (session-scoped, off by default) Play Mode is advanced with EditorApplication.Step() at a fixed rate.
    /// </summary>
    [InitializeOnLoad]
    public static class WDTicker
    {
        public static int Steps;
        public static float StepsPerSecond = 50f;
        static double lastStep;

        public static bool Pump
        {
            get { return SessionState.GetBool("WD_Pump", false); }
            set { SessionState.SetBool("WD_Pump", value); }
        }

        static WDTicker()
        {
            EditorApplication.update += Tick;
            EditorApplication.playModeStateChanged += s => { if (s == PlayModeStateChange.EnteredEditMode) Pump = false; };
            EditorApplication.playModeStateChanged += OnPlayMode;
        }

        static void Tick()
        {
            if (!Pump || !EditorApplication.isPlaying) return;
            double now = EditorApplication.timeSinceStartup;
            if (lastStep <= 0 || now - lastStep > 1.0) lastStep = now - 1.0 / StepsPerSecond;
            int n = (int)((now - lastStep) * StepsPerSecond);
            if (n <= 0) return;
            if (n > 10) { n = 10; lastStep = now; } else lastStep += n / StepsPerSecond;
            if (!EditorApplication.isPaused) EditorApplication.isPaused = true;
            for (int i = 0; i < n && EditorApplication.isPlaying; i++) { EditorApplication.Step(); Steps++; }
        }

        [MenuItem("Word Defense/Test/Toggle Play Mode Pump")]
        static void Toggle() { Pump = !Pump; Debug.Log("[WD] Pump " + Pump); }

        /// <summary>Starts Play Mode with the autopilot (1 = victory run, 2 = defeat run).</summary>
        public static void RunAutopilot(int mode)
        {
            PlayerPrefs.SetInt("WD_AutoPilot", mode);
            PlayerPrefs.Save();
            if (EditorApplication.isPlaying)
            {
                // leave the running session first, then start a fresh one
                SessionState.SetInt("WD_PendingAutopilot", mode);
                EditorApplication.isPlaying = false;
                return;
            }
            Pump = true;
            EditorApplication.isPlaying = true;
        }

        static void OnPlayMode(PlayModeStateChange s)
        {
            if (s != PlayModeStateChange.EnteredEditMode) return;
            int pending = SessionState.GetInt("WD_PendingAutopilot", 0);
            if (pending == 0) return;
            SessionState.SetInt("WD_PendingAutopilot", 0);
            EditorApplication.CallbackFunction cb = null;
            cb = () => { EditorApplication.update -= cb; RunAutopilot(pending); };
            EditorApplication.update += cb;
        }
    }

    public static class WDBuild
    {
        public const string Output = "Builds/Windows/WordDefense.exe";

        [MenuItem("Word Defense/Build Windows Player")]
        public static string BuildWindows()
        {
            RefreshBundledVocabulary();
            var opts = new BuildPlayerOptions
            {
                scenes = new[] { WDSetup.ScenePath },
                locationPathName = Output,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None,
            };
            var report = BuildPipeline.BuildPlayer(opts);
            var s = report.summary;
            string msg = "[WD] build " + s.result + " errors=" + s.totalErrors + " warnings=" + s.totalWarnings + " size=" + (s.totalSize / (1024 * 1024)) + "MB time=" + s.totalTime.TotalSeconds.ToString("0") + "s -> " + s.outputPath;
            Debug.Log(msg);
            return msg;
        }

        /// <summary>The build carries a copy of vocabulary.db for machines without one; refresh it from Documents first.</summary>
        public static void RefreshBundledVocabulary()
        {
            try
            {
                string docs = Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.MyDocuments), "vocabulary.db");
                string dst = Path.Combine(Application.dataPath, "StreamingAssets/vocabulary.db");
                if (File.Exists(docs) && (!File.Exists(dst) || File.GetLastWriteTimeUtc(docs) > File.GetLastWriteTimeUtc(dst) || new FileInfo(docs).Length != new FileInfo(dst).Length))
                {
                    File.Copy(docs, dst, true);
                    AssetDatabase.ImportAsset("Assets/StreamingAssets/vocabulary.db");
                    Debug.Log("[WD] refreshed bundled vocabulary.db from Documents");
                }
            }
            catch (System.Exception e) { Debug.LogWarning("[WD] could not refresh vocabulary.db: " + e.Message); }
        }
    }
}
