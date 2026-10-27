using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using WordDefense.Data;

namespace WordDefense
{
    /// <summary>
    /// Smoke-test bot. Plays through the same paths as a player: it clicks cards, word tags and enemies at screen
    /// positions through InputRouter.ClickScreen (UI first via the EventSystem, else a world ray) and presses keys through
    /// InputRouter.PressKey. Enabled with -autopilot (victory run) / -autopilot-defeat, or PlayerPrefs "WD_AutoPilot" (1/2).
    /// Every requirement is logged as PASS/FAIL to smoketest_*.txt; screenshots go next to it.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class AutoPilot : MonoBehaviour
    {
        public enum Mode { Victory, Defeat }
        public static AutoPilot Instance;
        public static string LastResult = "";
        Mode mode;
        bool quitWhenDone;
        string outDir;
        readonly List<string> log = new List<string>();
        readonly Dictionary<string, bool> checks = new Dictionary<string, bool>();
        int passed, failed;
        float startReal;
        bool finished;

        // live measurements
        int invariantFrames, invariantViolations, trayFrames, trayShort;
        float invariantGrace;
        int lastEnemyCount;
        readonly HashSet<string> wordsSeen = new HashSet<string>();
        readonly HashSet<string> glossesSeen = new HashSet<string>();
        bool sawVividNew, sawHomingShell, sawWrongFeedback, sawOrderWrong, sawLeak;
        GameManager hooked;
        float waveStartSpeed1 = -1f, waveStartSpeed4 = -1f;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (Instance != null) return;
            var args = System.Environment.GetCommandLineArgs();
            bool victory = args.Contains("-autopilot");
            bool defeat = args.Contains("-autopilot-defeat");
            int pref = PlayerPrefs.GetInt("WD_AutoPilot", 0);
            if (pref != 0) { PlayerPrefs.DeleteKey("WD_AutoPilot"); PlayerPrefs.Save(); }
            if (pref == 1) victory = true;
            if (pref == 2) defeat = true;
            if (!victory && !defeat) return;
            var go = new GameObject("AutoPilot");
            DontDestroyOnLoad(go);
            var ap = go.AddComponent<AutoPilot>();
            ap.mode = defeat ? Mode.Defeat : Mode.Victory;
            ap.quitWhenDone = !Application.isEditor;
            // tests use their own memory file, starting empty, so the player's progress is never touched
            GameManager.MemoryProfile = "autotest";
            GameManager.SharedMemory = null;
            try { File.Delete(MemoryBook.DefaultPath("autotest")); } catch { }
            if (GameManager.Instance != null && GameManager.Instance.Memory != null) GameManager.Instance.Memory = null;
        }

        void Awake()
        {
            Instance = this;
            startReal = Time.realtimeSinceStartup;
            outDir = Application.isEditor ? Path.Combine(Application.dataPath, "../Temp/SmokeTest") : Path.Combine(Application.dataPath, "../SmokeTest");
            Directory.CreateDirectory(outDir);
            Application.runInBackground = true;
            AudioListener.volume = 0f;   // unattended runs stay silent; sounds are still synthesised and played
        }

        void OnDestroy() { AudioListener.volume = 1f; }

        // any error or exception during the run fails it, even when every gameplay check passed
        int loggedErrors;
        string firstError;
        void OnEnable() { Application.logMessageReceived += OnLog; }
        void OnDisable() { Application.logMessageReceived -= OnLog; }
        void OnLog(string message, string stack, LogType type)
        {
            if (type != LogType.Error && type != LogType.Exception && type != LogType.Assert) return;
            // the player logs this at start-up when there is no mouse position yet (locked screen, no foreground window)
            if (message.StartsWith("Failed to get first mouse position")) return;
            loggedErrors++;
            if (firstError == null) firstError = message.Split('\n')[0];
        }

        // a rich-text tag TMP cannot resolve is printed as-is, e.g. <font="…" material="…">; scan what is on screen
        static readonly System.Text.RegularExpressions.Regex RawTag = new System.Text.RegularExpressions.Regex(@"</?[A-Za-z][A-Za-z0-9-]*[=\s>]");
        readonly HashSet<TMPro.TMP_Text> markupTexts = new HashSet<TMPro.TMP_Text>();
        int markupLeaks;
        string firstMarkupLeak;
        float nextMarkupScan;
        void ScanMarkup()
        {
            if (UIRoot.Instance == null || Time.realtimeSinceStartup < nextMarkupScan) return;
            nextMarkupScan = Time.realtimeSinceStartup + 0.2f;
            foreach (var t in UIRoot.Instance.GetComponentsInChildren<TMPro.TMP_Text>(false))
            {
                if (!t.isActiveAndEnabled || string.IsNullOrEmpty(t.text) || t.text.IndexOf('<') < 0) continue;
                markupTexts.Add(t);
                string shown = t.GetParsedText();
                if (!RawTag.IsMatch(shown)) continue;
                markupLeaks++;
                if (firstMarkupLeak == null) firstMarkupLeak = t.name + ": " + shown;
            }
        }

        void Start() { StartCoroutine(Run()); }

        // ------------------------------------------------------------ logging
        void Log(string msg)
        {
            string line = "[" + (Time.realtimeSinceStartup - startReal).ToString("000.0") + "s] " + msg;
            log.Add(line);
            Debug.Log("[AUTOPILOT] " + line);
        }

        bool Check(bool ok, string what)
        {
            if (ok) passed++; else failed++;
            Log((ok ? "PASS  " : "FAIL  ") + what);
            return ok;
        }

        void Shot(string name)
        {
            string path = Path.Combine(outDir, mode + "_" + name + ".png");
            try { CaptureOffscreen(path); } catch (System.Exception e) { Log("WARN  capture failed: " + e.Message); }
        }

        static float[] srgbToLinear;
        static byte[] linearToSrgb;   // 4096 steps

        /// <summary>Renders the game camera (with post-processing), then the UI alone without post-processing, twice:
        /// over black and over white. The two UI images give each pixel's exact colour and coverage, so translucent
        /// panels and overlays are composited over the scene the way the screen shows them. Works when the player
        /// window is not presented (locked screen).</summary>
        public static void CaptureOffscreen(string path)
        {
            var cam = Camera.main;
            if (cam == null) return;
            int w = Screen.width > 0 ? Screen.width : 1600, h = Screen.height > 0 ? Screen.height : 900;
            var rtScene = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var rtBlack = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var rtWhite = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var data = cam.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            bool post = data != null && data.renderPostProcessing;
            int mask = cam.cullingMask;
            var flags = cam.clearFlags;
            var bg = cam.backgroundColor;
            bool hdr = cam.allowHDR, msaa = cam.allowMSAA;
            var prevTarget = cam.targetTexture;
            var prevActive = RenderTexture.active;
            // pass 1: the scene with post-processing
            cam.cullingMask = mask & ~(1 << 5);
            cam.targetTexture = rtScene;
            cam.Render();
            // pass 2: only the UI, no post-processing, over black and then over white
            var moved = new List<Canvas>();
            foreach (var c in Object.FindObjectsByType<Canvas>())
            {
                if (!c.isRootCanvas || c.renderMode != RenderMode.ScreenSpaceOverlay || !c.isActiveAndEnabled) continue;
                c.renderMode = RenderMode.ScreenSpaceCamera;
                c.worldCamera = cam;
                c.planeDistance = cam.nearClipPlane + 0.05f;
                moved.Add(c);
            }
            Canvas.ForceUpdateCanvases();
            cam.cullingMask = 1 << 5;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.allowHDR = false;
            cam.allowMSAA = false;
            if (data != null) data.renderPostProcessing = false;
            cam.backgroundColor = new Color(0f, 0f, 0f, 0f);
            cam.targetTexture = rtBlack;
            cam.Render();
            cam.backgroundColor = new Color(1f, 1f, 1f, 1f);
            cam.targetTexture = rtWhite;
            cam.Render();
            // restore
            foreach (var c in moved) c.renderMode = RenderMode.ScreenSpaceOverlay;
            cam.targetTexture = prevTarget;
            cam.cullingMask = mask;
            cam.clearFlags = flags;
            cam.backgroundColor = bg;
            cam.allowHDR = hdr;
            cam.allowMSAA = msaa;
            if (data != null) data.renderPostProcessing = post;

            var scene = new Texture2D(w, h, TextureFormat.RGBA32, false);
            var black = new Texture2D(w, h, TextureFormat.RGBA32, false);
            var white = new Texture2D(w, h, TextureFormat.RGBA32, false);
            RenderTexture.active = rtScene; scene.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            RenderTexture.active = rtBlack; black.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            RenderTexture.active = rtWhite; white.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            RenderTexture.active = prevActive == rtScene || prevActive == rtBlack || prevActive == rtWhite ? null : prevActive;
            RenderTexture.ReleaseTemporary(rtScene);
            RenderTexture.ReleaseTemporary(rtBlack);
            RenderTexture.ReleaseTemporary(rtWhite);
            if (srgbToLinear == null)
            {
                srgbToLinear = new float[256];
                for (int i = 0; i < 256; i++) srgbToLinear[i] = Mathf.GammaToLinearSpace(i / 255f);
                linearToSrgb = new byte[4097];
                for (int i = 0; i <= 4096; i++) linearToSrgb[i] = (byte)Mathf.RoundToInt(Mathf.Clamp01(Mathf.LinearToGammaSpace(i / 4096f)) * 255f);
            }
            var S = scene.GetPixels32();
            var K = black.GetPixels32();
            var W = white.GetPixels32();
            for (int i = 0; i < S.Length; i++)
            {
                // over black the UI leaves its own colour C; over white it leaves C + (1 - coverage); blending is linear
                S[i].r = Over(K[i].r, W[i].r, S[i].r);
                S[i].g = Over(K[i].g, W[i].g, S[i].g);
                S[i].b = Over(K[i].b, W[i].b, S[i].b);
                S[i].a = 255;
            }
            scene.SetPixels32(S);
            scene.Apply();
            File.WriteAllBytes(path, scene.EncodeToPNG());
            Object.Destroy(scene);
            Object.Destroy(black);
            Object.Destroy(white);
        }

        static byte Over(byte k, byte wh, byte s)
        {
            float c = srgbToLinear[k];
            float transmit = Mathf.Clamp01(srgbToLinear[wh] - c);
            float o = Mathf.Clamp01(c + srgbToLinear[s] * transmit);
            return linearToSrgb[(int)(o * 4096f + 0.5f)];
        }

        /// <summary>Real frame cost: 60 frames rendered through the normal player loop into a texture, then a read-back.</summary>
        IEnumerator FrameBenchmark(string label)
        {
            var cam = Camera.main;
            if (cam == null || Application.isEditor) yield break;
            int w = Screen.width > 0 ? Screen.width : 1600, h = Screen.height > 0 ? Screen.height : 900;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
            var probe = new Texture2D(4, 4, TextureFormat.RGB24, false);
            var prev = cam.targetTexture;
            int vs = QualitySettings.vSyncCount, fps = Application.targetFrameRate;
            QualitySettings.vSyncCount = 0; Application.targetFrameRate = -1;
            cam.targetTexture = rt;
            for (int i = 0; i < 5; i++) yield return null;
            Sync(rt, probe);
            float t0 = Time.realtimeSinceStartup;
            for (int i = 0; i < 60; i++) yield return null;
            Sync(rt, probe);
            float ms = (Time.realtimeSinceStartup - t0) * 1000f / 60f;
            if (cam != null) cam.targetTexture = prev;
            QualitySettings.vSyncCount = vs; Application.targetFrameRate = fps;
            rt.Release(); Object.Destroy(rt); Object.Destroy(probe);
            Log("Frame benchmark (" + label + "): " + ms.ToString("0.00") + " ms per frame at " + w + "x" + h + " (about " + (1000f / ms).ToString("0") + " fps, vsync off)");
        }

        static void Sync(RenderTexture rt, Texture2D probe)
        {
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            probe.ReadPixels(new Rect(0, 0, 4, 4), 0, 0);
            RenderTexture.active = prev == rt ? null : prev;
        }

        void Finish(string reason)
        {
            if (finished) return;
            finished = true;
            Check(loggedErrors == 0, "no errors or exceptions logged during the run" + (loggedErrors > 0 ? " (" + loggedErrors + ", first: " + firstError + ")" : ""));
            Check(markupTexts.Count >= 5 && markupLeaks == 0, "rich-text tags render as formatting, never as raw text (" + markupTexts.Count + " tagged texts watched"
                + (markupLeaks > 0 ? ", " + markupLeaks + " raw sightings, first: " + firstMarkupLeak : "") + ")");
            bool pass = failed == 0 && string.IsNullOrEmpty(reason);
            LastResult = pass ? "PASS" : "FAIL";
            Log("RESULT: " + (pass ? "PASS" : "FAIL " + reason) + "  (checks passed " + passed + ", failed " + failed + ")");
            try { File.WriteAllLines(Path.Combine(outDir, "smoketest_" + mode + ".txt"), log.ToArray()); } catch { }
            Time.timeScale = 1f;
            if (quitWhenDone) StartCoroutine(QuitSoon());
#if UNITY_EDITOR
            else StartCoroutine(StopEditorSoon());
#endif
        }

#if UNITY_EDITOR
        IEnumerator StopEditorSoon()
        {
            for (int i = 0; i < 30; i++) yield return null;
            UnityEditor.EditorApplication.isPlaying = false;
        }
#endif

        IEnumerator QuitSoon()
        {
            yield return new WaitForSecondsRealtime(1.2f);
            Application.Quit();
        }

        // ------------------------------------------------------------ helpers
        IEnumerator WaitFor(System.Func<bool> cond, float timeout)
        {
            float t = 0f;
            while (!cond() && t < timeout) { t += Time.unscaledDeltaTime > 0f ? Time.unscaledDeltaTime : Time.deltaTime; yield return null; }
        }

        IEnumerator Frames(int n) { for (int i = 0; i < n; i++) yield return null; }

        /// <summary>Lets UI transitions finish before a screenshot. Waits on real time, not frames: a build whose window
        /// is not presented (locked screen) runs at 1000+ fps, where 40 frames are over before a fade has started.</summary>
        IEnumerator Settle(float seconds, int minFrames = 10)
        {
            float end = Time.realtimeSinceStartup + seconds;
            int f = 0;
            while (Time.realtimeSinceStartup < end || f < minFrames) { f++; yield return null; }
        }

        static GameManager GM { get { return GameManager.Instance; } }

        void Hook()
        {
            var gm = GM;
            if (gm == null || gm == hooked) return;
            hooked = gm;
            gm.OnFeedback += f =>
            {
                switch (f.Kind)
                {
                    case FeedbackKind.VividNew: sawVividNew = true; Log("event: 记忆深刻 " + f.Word.Word); break;
                    case FeedbackKind.Correct: if (f.Homing) sawHomingShell = true; break;
                    case FeedbackKind.Wrong: sawWrongFeedback = true; break;
                    case FeedbackKind.OrderWrong: sawOrderWrong = true; break;
                    case FeedbackKind.Leak: sawLeak = true; break;
                }
            };
        }

        bool ClickUI(Selectable s)
        {
            if (s == null || !s.isActiveAndEnabled || !s.interactable) return false;
            var rt = (RectTransform)s.transform;
            Vector2 p = RectTransformUtility.WorldToScreenPoint(null, rt.TransformPoint(rt.rect.center));
            return InputRouter.Instance != null && InputRouter.Instance.ClickScreen(p);
        }

        bool ClickCard(int slot)
        {
            var ui = UIRoot.Instance;
            var rt = ui != null ? ui.CardRect(slot) : null;
            if (rt == null) return false;
            Vector2 p = RectTransformUtility.WorldToScreenPoint(null, rt.TransformPoint(new Vector3(0f, rt.rect.height * 0.45f, 0f)));
            return InputRouter.Instance.ClickScreen(p);
        }

        int clickToggle;
        /// <summary>Clicks an enemy: mostly on its word tag, sometimes on its body when nothing in the UI covers it.</summary>
        bool ClickEnemy(Enemy e)
        {
            var ui = UIRoot.Instance;
            var gm = GM;
            clickToggle++;
            Vector2 tagPos;
            if (clickToggle % 3 == 0 && gm.cam != null)
            {
                Vector3 sp = gm.cam.WorldToScreenPoint(e.AimPoint);
                if (sp.z > 0f && !UiAt(sp) && InputRouter.Instance.RayEnemy(sp) == e) { InputRouter.Instance.ClickScreen(sp); return true; }
            }
            if (ui != null && ui.TagScreenPos(e, out tagPos) && TopUiEnemy(tagPos) == e) { InputRouter.Instance.ClickScreen(tagPos); return true; }
            if (gm.cam != null)
            {
                Vector3 sp = gm.cam.WorldToScreenPoint(e.AimPoint);
                if (sp.z > 0f && !UiAt(sp) && InputRouter.Instance.RayEnemy(sp) == e) { InputRouter.Instance.ClickScreen(sp); return true; }
            }
            return false;
        }

        readonly List<RaycastResult> hits = new List<RaycastResult>();
        bool UiAt(Vector2 p)
        {
            var es = EventSystem.current;
            if (es == null) return false;
            hits.Clear();
            es.RaycastAll(new PointerEventData(es) { position = p }, hits);
            return hits.Count > 0;
        }

        Enemy TopUiEnemy(Vector2 p)
        {
            var es = EventSystem.current;
            if (es == null) return null;
            hits.Clear();
            es.RaycastAll(new PointerEventData(es) { position = p }, hits);
            foreach (var h in hits)
            {
                var th = h.gameObject.GetComponentInParent<TagHover>();
                if (th != null) return th.enemy;
                if (h.gameObject.GetComponentInParent<Button>() != null) return null;
            }
            return null;
        }

        SessionWord TargetWord(Enemy e) { var b = e as BossEnemy; return b != null ? b.TargetWord : e.Word; }

        // ------------------------------------------------------------ pause test (runs in Update)
        int pauseStep, pauseFrames;
        float pauseShownAt;
        bool pauseExit;

        void StepPauseTest(GameManager gm)
        {
            pauseFrames++;
            switch (pauseStep)
            {
                case 1: InputRouter.PressKey(InputRouter.Key2.Pause); pauseStep = 2; pauseFrames = 0; break;
                case 2:
                    if (gm.State == GameState.Paused) { Check(Time.timeScale == 0f, "Esc pauses the game (time stops)"); pauseStep = 3; pauseFrames = 0; pauseShownAt = Time.realtimeSinceStartup; }
                    else if (pauseFrames > 90) { Check(false, "Esc pauses the game"); pauseStep = 0; }
                    break;
                case 3:
                    if (pauseFrames >= 25 && Time.realtimeSinceStartup - pauseShownAt >= 0.6f)
                    {
                        if (!pauseExit) Shot("03_pause");
                        Button b = pauseExit
                            ? UIRoot.Instance.transform.GetComponentsInChildren<Button>(true).FirstOrDefault(x => x.name == "TitleButton" && x.isActiveAndEnabled)
                            : UIRoot.Instance.PauseResumeButton;
                        Check(ClickUI(b), pauseExit ? "pause menu -> 返回标题" : "clicked 继续 in the pause menu");
                        pauseStep = pauseExit ? 0 : 4;
                        pauseFrames = 0;
                    }
                    break;
                case 4:
                    if (gm.State == GameState.Playing) { Check(Time.timeScale == 1f, "继续 resumes the game"); pauseStep = 0; }
                    else if (pauseFrames > 90) { Check(false, "继续 resumes the game"); pauseStep = 0; }
                    break;
            }
        }

        // ------------------------------------------------------------ per-frame monitors
        void Update()
        {
            var gm = GM;
            if (gm == null || finished) return;
            Hook();
            ScanMarkup();
            if (pauseStep > 0) StepPauseTest(gm);
            if (gm.State != GameState.Playing || gm.Phase == GamePhase.Ending) return;
            var targets = gm.Enemies.Where(e => e != null && e.Targetable).ToList();
            int count = gm.Enemies.Count;
            if (count != lastEnemyCount) { invariantGrace = 0.6f; lastEnemyCount = count; }
            invariantGrace -= Time.deltaTime;
            if (targets.Count > 0 && invariantGrace <= 0f)
            {
                invariantFrames++;
                if (!gm.Tray.Slots.Any(s => s != null && targets.Any(e => gm.Tray.Matches(s, e)))) invariantViolations++;
            }
            trayFrames++;
            int filled = gm.Tray.Slots.Count(s => s != null);
            if (filled < 3) trayShort++;
            foreach (var e in gm.Enemies) if (e != null && e.Word != null) wordsSeen.Add(e.Word.Word);
            foreach (var s in gm.Tray.Slots) if (s != null) glossesSeen.Add(s.Word.Word + "|" + s.Word.Gloss);
        }

        // ------------------------------------------------------------ scenario
        IEnumerator Run()
        {
            Log("AutoPilot " + mode + " | Unity " + Application.unityVersion + " | " + (Application.isEditor ? "editor" : "player") + " | " + Screen.width + "x" + Screen.height);
            yield return WaitFor(() => GM != null && (GM.State == GameState.Title || Vocabulary.Failed), 60f);
            if (!Check(GM != null && GM.State == GameState.Title && Vocabulary.Ready, "title screen reached and vocabulary.db loaded"))
            { Finish("vocabulary did not load: " + Vocabulary.Error); yield break; }
            var st = Vocabulary.Stats;
            Log("vocabulary: " + Vocabulary.SourcePath + " | rows " + st.TotalRows + ", medium band " + st.Band + " rows " + st.BandRows + ", usable " + st.Usable + ", pool " + Vocabulary.Pool.Count + ", boss sentences " + Vocabulary.BossSentences.Count + ", " + st.LoadMs + " ms");
            Check(st.TotalRows > 90000 && Vocabulary.Pool.Count > 500 && Vocabulary.BossSentences.Count >= 10, "word pool and boss sentences built from the local database");
            Check(Vocabulary.Pool.All(w => w.Difficulty >= 0.39f && w.Difficulty <= 0.61f), "every pool word has medium difficulty (0.4-0.6)");
            yield return Settle(0.8f);
            Shot("01_title");
            // 玩法: the rules sheet opens from the title screen and closes again
            Check(ClickUI(UIRoot.Instance.RulesButton), "clicked 玩法 on the title screen");
            yield return Settle(0.6f);
            Check(UIRoot.Instance.RulesOpen, "the 玩法 sheet is open");
            Shot("01b_rules");
            Check(ClickUI(UIRoot.Instance.RulesCloseButton), "clicked 关闭 on the 玩法 sheet");
            yield return Settle(0.5f);
            Check(!UIRoot.Instance.RulesOpen, "the 玩法 sheet is closed");
            Check(ClickUI(UIRoot.Instance.StartButton), "clicked 开始游戏 on the title screen");
            yield return WaitFor(() => GM.State == GameState.Playing, 5f);
            Check(GM.State == GameState.Playing && GM.Wave == 1 && GM.castle.Hp == GM.castle.MaxHp, "game started: wave 1, castle at full health");
            Hook();
            if (mode == Mode.Victory) yield return VictoryRun();
            else yield return DefeatRun();
        }

        // ------------------------------------------------------------ victory scenario
        IEnumerator VictoryRun()
        {
            var gm = GM;
            Log("boss sentence: " + gm.Deck.Boss.English + " | keywords " + string.Join(", ", gm.Deck.BossWords.Select(w => w.Word + "=" + w.Gloss).ToArray()));
            bool wrongTested = false, leakTested = false, skillTested = false, pauseTested = false, homingTested = false, orderTested = false;
            int correctShots = 0;
            float nextAct = 0f;
            Enemy skipEnemy = null;
            bool skipChosen = false;
            int hpBeforeLeak = -1;
            waveStartSpeed1 = gm.SpeedMultiplier;
            int lastWave = 1;
            bool shotWave = false, shotBoss = false, benchDone = false;
            while (gm != null && gm.State != GameState.Victory && gm.State != GameState.Defeat)
            {
                gm = GM;
                if (gm.State == GameState.Paused) { yield return null; continue; }
                if (gm.Wave != lastWave)
                {
                    lastWave = gm.Wave;
                    Log("wave " + gm.Wave + " | speed x" + gm.SpeedMultiplier.ToString("0.00") + " | score " + gm.Score + " | hp " + gm.castle.Hp);
                    if (gm.Wave == GameManager.WaveCount) waveStartSpeed4 = gm.SpeedMultiplier;
                }
                if (!benchDone && gm.Wave == 3 && gm.Enemies.Count(e => e && e.Alive) >= 3)
                {
                    benchDone = true;
                    yield return FrameBenchmark("wave 3, " + gm.Enemies.Count(e => e && e.Alive) + " enemies on the field");
                }
                if (!shotWave && gm.Wave == 2 && gm.Enemies.Count(e => e && e.Alive) >= 3) { shotWave = true; Shot("02_wave2"); }

                // pause / resume once, in wave 2 (driven from Update: coroutines stall while time is stopped)
                if (!pauseTested && gm.Wave == 2 && gm.Phase == GamePhase.Waves)
                {
                    pauseTested = true;
                    pauseStep = 1;
                    pauseExit = false;
                    yield return WaitFor(() => pauseStep == 0, 30f);
                }

                if (gm.Phase == GamePhase.Boss && gm.Boss != null && !shotBoss && gm.Boss.Emerge >= 1f && Time.time - gm.Boss.SpawnTime > 2.5f) { shotBoss = true; Shot("06_boss"); }

                if (Time.time >= nextAct && !gm.Jammed && gm.Phase != GamePhase.Ending)
                {
                    var targets = gm.Enemies.Where(e => e != null && e.Targetable).OrderByDescending(e => e is BossEnemy ? 0.5f + e.Progress * 0.5f : e.Progress).ToList();
                    // 1. leak test: let the first wave-1 enemy walk into the castle
                    if (!leakTested && !skipChosen && targets.Count > 0 && gm.Wave == 1) { skipEnemy = targets[0]; skipChosen = true; hpBeforeLeak = gm.castle.Hp; Log("letting '" + skipEnemy.Word.Word + "' reach the castle on purpose"); }
                    if (skipChosen && !leakTested)
                    {
                        if (skipEnemy == null || !skipEnemy.Alive)
                        {
                            // the enemy leaps at the gate first; wait on game time, not frames (a build can run 1000+ fps)
                            float until = Time.time + 1.5f;
                            while (gm.castle.Hp >= hpBeforeLeak && Time.time < until) yield return null;
                            leakTested = true;
                            Check(gm.castle.Hp < hpBeforeLeak && sawLeak, "an enemy reaching the castle damages it (" + hpBeforeLeak + " -> " + gm.castle.Hp + ")");
                            yield return Settle(0.3f);
                            Shot("04_castle_hit");
                            continue;
                        }
                        targets.Remove(skipEnemy);
                    }
                    // 2. skill: once ready, fire it when enemies are on the field
                    if (gm.SkillReady && targets.Count >= 1 && !skillTested)
                    {
                        var probe = targets[0];
                        float before = probe.CurrentSpeed;
                        InputRouter.PressKey(InputRouter.Key2.Skill);
                        yield return Frames(2);
                        float after = probe != null ? probe.CurrentSpeed : 0f;
                        bool all = gm.Enemies.Where(e => e && e.Alive).All(e => gm.SlowFactorFor(e) < 1f);
                        skillTested = Check(gm.SlowTimer > 0f && after < before * 0.6f && all, "3 correct in a row charge 寒霜齐射; Space slows every enemy (" + before.ToString("0.00") + " -> " + after.ToString("0.00") + " m/s)");
                        yield return Settle(0.45f);
                        Shot("05_frost");
                        nextAct = Time.time + 0.3f;
                        yield return null;
                        continue;
                    }
                    // 3. homing: a vivid shell fires itself
                    int vividSlot = -1;
                    for (int i = 0; i < ShellTray.Size; i++)
                    {
                        var s = gm.Tray.Slots[i];
                        if (s != null && s.Vivid && targets.Any(e => gm.Tray.Matches(s, e))) { vividSlot = i; break; }
                    }
                    if (vividSlot >= 0)
                    {
                        var s = gm.Tray.Slots[vividSlot];
                        var target = targets.First(e => gm.Tray.Matches(s, e));
                        int vh = gm.VividHits;
                        ClickCard(vividSlot);
                        yield return Frames(2);
                        bool flying = Object.FindObjectsByType<Projectile>().Any(p => p.name == "HomingShell");
                        yield return WaitFor(() => gm.VividHits > vh || gm.State != GameState.Playing, 4f);
                        if (!homingTested)
                            homingTested = Check(flying && gm.VividHits > vh, "记忆深刻 shell '" + s.Word.Word + "' fired itself and homed in on its enemy (one click, no aiming)");
                        nextAct = Time.time + 0.25f;
                        continue;
                    }
                    // 4. boss order test
                    var boss = targets.OfType<BossEnemy>().FirstOrDefault();
                    if (boss != null && !orderTested && boss.Pending == 0 && boss.Current < boss.Keywords.Count - 1)
                    {
                        int later = -1;
                        for (int i = 0; i < ShellTray.Size; i++)
                        {
                            var s = gm.Tray.Slots[i];
                            if (s != null && !s.Vivid && boss.KeywordIndexOf(s.Word) > boss.Effective) { later = i; break; }
                        }
                        if (later >= 0)
                        {
                            int cur = boss.Current, wr = gm.Wrongs;
                            ClickCard(later);
                            yield return Frames(2);
                            ClickEnemy(boss);
                            yield return WaitFor(() => gm.Wrongs > wr, 3f);
                            orderTested = Check(gm.Wrongs > wr && boss.Current == cur && sawOrderWrong, "boss: a later keyword's meaning out of order is rejected (顺序不对), progress kept");
                            nextAct = Time.time + 1.1f;
                            continue;
                        }
                    }
                    // 5. one deliberate wrong match on a normal enemy
                    if (!wrongTested && correctShots >= 2 && targets.Count > 0)
                    {
                        var victim = targets.FirstOrDefault(e => !(e is BossEnemy));
                        int wrongSlot = -1;
                        for (int i = 0; victim != null && i < ShellTray.Size; i++)
                        {
                            var s = gm.Tray.Slots[i];
                            if (s != null && !s.Vivid && !gm.Tray.Matches(s, victim)) { wrongSlot = i; break; }
                        }
                        if (victim != null && wrongSlot >= 0)
                        {
                            var shell = gm.Tray.Slots[wrongSlot];
                            int wr = gm.Wrongs, combo = gm.Combo;
                            ClickCard(wrongSlot);
                            yield return Frames(2);
                            bool clicked = ClickEnemy(victim);
                            yield return Frames(2);
                            bool jam = gm.Jammed;
                            yield return WaitFor(() => gm.Wrongs > wr, 3f);
                            yield return Frames(3);
                            wrongTested = Check(clicked && gm.Wrongs > wr && gm.Combo == 0 && victim != null && victim.Alive && jam && !string.IsNullOrEmpty(victim.RevealText)
                                                && gm.Tray.Slots.Any(s => s == shell) && sawWrongFeedback,
                                "wrong match: shell bounces off, combo resets (" + combo + " -> 0), cannon jams, the shell stays, the enemy shows its meaning '" + (victim ? victim.RevealText : "") + "'");
                            yield return Settle(0.35f);
                            Shot("04b_wrong");
                            nextAct = Time.time + 1.0f;
                            continue;
                        }
                    }
                    // 6. normal play: select the matching shell, then click its enemy
                    bool acted = false;
                    foreach (var e in targets)
                    {
                        int slot = -1;
                        for (int i = 0; i < ShellTray.Size; i++)
                        {
                            var s = gm.Tray.Slots[i];
                            if (s != null && !s.Vivid && gm.Tray.Matches(s, e)) { slot = i; break; }
                        }
                        if (slot < 0) continue;
                        // answer Boss keywords slowly during the waves so they stay ordinary (not 记忆深刻) and the
                        // order rule can be tested with them at the Boss
                        if (e.Word != null && e.Word.IsKeyword && !(e is BossEnemy) && e.Progress < 0.6f &&
                            Time.time - Mathf.Max(e.SpawnTime + 0.5f, gm.Tray.Slots[slot].CreatedAt) < 6.8f) continue;
                        int hits = gm.Hits, kills = gm.Enemies.Count(x => x && x.Alive);
                        var bossT = e as BossEnemy;
                        int bossBefore = bossT != null ? bossT.Current : -1;
                        ClickCard(slot);
                        yield return Frames(2);
                        if (gm.SelectedSlot != slot) break;
                        if (!ClickEnemy(e)) { InputRouter.PressKey(InputRouter.Key2.Cancel); break; }
                        acted = true;
                        correctShots++;
                        yield return WaitFor(() => gm.Hits > hits || gm.State != GameState.Playing, 3f);
                        if (bossT != null)
                        {
                            yield return WaitFor(() => bossT == null || bossT.Pending == 0, 3f);
                            Check(bossT == null || bossT.Current >= bossBefore + 1 || bossT.Defeated, "boss keyword " + (bossBefore + 1) + " broken in order (" + (bossT ? bossT.Current : -1) + "/" + (bossT ? bossT.Keywords.Count : -1) + ")");
                        }
                        break;
                    }
                    nextAct = Time.time + (acted ? 0.2f : 0.15f);
                }
                yield return null;
            }
            gm = GM;
            bool won = gm.State == GameState.Victory;
            Check(won, "boss sentence broken -> victory screen");
            Check(leakTested, "castle damage tested");
            Check(wrongTested, "wrong-answer feedback tested");
            Check(skillTested, "slow-all skill tested");
            Check(orderTested, "boss order rule tested");
            Check(sawVividNew, "a word became 记忆深刻 after fast correct answers");
            Check(waveStartSpeed4 > waveStartSpeed1 + 0.2f, "enemy speed rises with progress (x" + waveStartSpeed1.ToString("0.00") + " at wave 1 -> x" + waveStartSpeed4.ToString("0.00") + " at wave 4 -> x" + gm.SpeedMultiplier.ToString("0.00") + " at the boss)");
            Check(invariantFrames > 200 && invariantViolations == 0, "a shell always matched an enemy on the field (" + invariantFrames + " frames, " + invariantViolations + " violations)");
            Check(trayShort <= trayFrames / 50, "3-4 shells in the tray (" + trayShort + " of " + trayFrames + " frames below 3 during refills)");
            bool fromDb = wordsSeen.All(w => Vocabulary.Lexicon.ContainsKey(w)) && glossesSeen.All(g => { var p = g.Split('|'); WordEntry e; return Vocabulary.Lexicon.TryGetValue(p[0], out e) && e.Senses.Any(s => s.Text == p[1]); });
            Check(fromDb && wordsSeen.Count >= 10, "all " + wordsSeen.Count + " enemy words and " + glossesSeen.Count + " shell meanings come from vocabulary.db");
            Log("result: score " + gm.Score + ", accuracy " + gm.Accuracy + "%, best combo " + gm.BestCombo + ", hits " + gm.Hits + ", wrong " + gm.Wrongs + ", leaks " + gm.Leaks + ", homing hits " + gm.VividHits + ", time " + gm.PlayTime.ToString("0") + " s");
            yield return Settle(1.4f);
            Shot("07_victory");
            yield return FrameBenchmark("victory screen");

            // restart from the victory screen; the memory file now holds vivid words, which return in the next deck
            Check(ClickUI(UIRoot.Instance.ResultRestartButton), "clicked 再来一局 on the victory screen");
            yield return WaitFor(() => GM != null && GM != gm && GM.State == GameState.Playing, 15f);
            gm = GM;
            Hook();
            Check(gm != null && gm.State == GameState.Playing && gm.Wave == 1 && gm.Score == 0 && gm.castle.Hp == gm.castle.MaxHp && gm.Enemies.Count == 0,
                "restart: fresh game (wave 1, score 0, full castle)");
            int vividInDeck = gm.Deck.Words.Count(w => gm.IsVivid(w));
            Check(vividInDeck > 0, "memory carried over: " + vividInDeck + " 记忆深刻 word(s) in the new deck");
            if (!homingTested)
            {
                // play the new game until a vivid shell meets its enemy
                float until = Time.time + 90f;
                while (!homingTested && Time.time < until && gm.State == GameState.Playing)
                {
                    var targets = gm.Enemies.Where(e => e != null && e.Targetable).ToList();
                    int vs = -1;
                    for (int i = 0; i < ShellTray.Size; i++) { var s = gm.Tray.Slots[i]; if (s != null && s.Vivid && targets.Any(e => gm.Tray.Matches(s, e))) { vs = i; break; } }
                    if (vs >= 0)
                    {
                        var word = gm.Tray.Slots[vs].Word.Word;
                        int vh = gm.VividHits;
                        ClickCard(vs);
                        yield return Frames(2);
                        bool flying = Object.FindObjectsByType<Projectile>().Any(p => p.name == "HomingShell");
                        yield return WaitFor(() => gm.VividHits > vh, 4f);
                        homingTested = Check(flying && gm.VividHits > vh, "记忆深刻 shell '" + word + "' fired itself and homed in (second game)");
                        yield return Settle(0.3f);
                        Shot("08_homing");
                        break;
                    }
                    // otherwise keep the field clear with normal shots
                    foreach (var e in targets)
                    {
                        int slot = -1;
                        for (int i = 0; i < ShellTray.Size; i++) { var s = gm.Tray.Slots[i]; if (s != null && !s.Vivid && gm.Tray.Matches(s, e)) { slot = i; break; } }
                        if (slot < 0 || gm.Jammed) continue;
                        ClickCard(slot);
                        yield return Frames(2);
                        ClickEnemy(e);
                        yield return Frames(12);
                        break;
                    }
                    yield return null;
                }
            }
            Check(homingTested && sawHomingShell, "记忆深刻 shells track their target automatically");
            Finish("");
        }

        // ------------------------------------------------------------ defeat scenario
        IEnumerator DefeatRun()
        {
            var gm = GM;
            int wrongShots = 0;
            int hpPrev = gm.castle.Hp, damageEvents = 0;
            float nextAct = Time.time + 2f;
            bool shot = false;
            while (gm.State == GameState.Playing)
            {
                if (gm.castle.Hp < hpPrev) { damageEvents++; hpPrev = gm.castle.Hp; }
                if (!shot && gm.castle.Hp <= 50) { shot = true; yield return Settle(0.3f); Shot("02_damaged"); }
                // a few deliberate wrong matches to show the feedback, then just watch the castle fall
                if (wrongShots < 3 && Time.time >= nextAct && !gm.Jammed)
                {
                    var victim = gm.Enemies.FirstOrDefault(e => e != null && e.Targetable);
                    int slot = -1;
                    for (int i = 0; victim != null && i < ShellTray.Size; i++) { var s = gm.Tray.Slots[i]; if (s != null && !s.Vivid && !gm.Tray.Matches(s, victim)) { slot = i; break; } }
                    if (slot >= 0)
                    {
                        int wr = gm.Wrongs;
                        ClickCard(slot);
                        yield return Frames(2);
                        ClickEnemy(victim);
                        yield return WaitFor(() => gm.Wrongs > wr, 3f);
                        if (gm.Wrongs > wr) wrongShots++;
                        nextAct = Time.time + 1.5f;
                    }
                }
                yield return null;
            }
            yield return WaitFor(() => gm.State == GameState.Defeat, 10f);
            Check(wrongShots >= 1 && sawWrongFeedback, "wrong matches give feedback (" + wrongShots + " tried)");
            Check(damageEvents >= 3 && sawLeak, "enemies reaching the castle damage it (" + damageEvents + " hits)");
            Check(gm.State == GameState.Defeat && gm.castle.Hp <= 0, "castle destroyed -> defeat screen");
            Log("result: score " + gm.Score + ", wrong " + gm.Wrongs + ", leaks " + gm.Leaks + ", time " + gm.PlayTime.ToString("0") + " s");
            yield return Settle(1.4f);
            Shot("03_defeat");
            Check(ClickUI(UIRoot.Instance.ResultRestartButton), "clicked 再来一局 on the defeat screen");
            yield return WaitFor(() => GM != null && GM != gm && GM.State == GameState.Playing, 15f);
            var g2 = GM;
            Check(g2 != null && g2 != gm && g2.State == GameState.Playing && g2.Wave == 1 && g2.castle.Hp == g2.castle.MaxHp && g2.Score == 0, "restart after defeat: fresh game, castle repaired");
            // and back to the title through the pause menu
            yield return Frames(30);
            pauseStep = 1;
            pauseExit = true;
            yield return WaitFor(() => pauseStep == 0, 30f);
            yield return WaitFor(() => GM != null && GM != g2 && GM.State == GameState.Title, 15f);
            Check(GM != null && GM.State == GameState.Title, "back on the title screen");
            Finish("");
        }
    }
}
