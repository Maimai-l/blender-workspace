using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.UI;

namespace DungeonEscape
{
    /// <summary>
    /// Smoke-test bot. Drives the player through the real input path. Enabled with the command-line flags
    /// -autopilot (full playthrough) or -autopilot-defeat (die, then restart), or PlayerPrefs "DE_AutoPilot" (1/2) in the editor.
    /// </summary>
    [DefaultExecutionOrder(-200)]
    public class AutoPilot : MonoBehaviour, IPlayerInputSource
    {
        public enum Mode { Victory, Defeat }
        public static AutoPilot Instance { get; private set; }
        public static string LastResult = "";

        Mode mode;
        PlayerInputState state;
        Vector3 moveWorld;
        bool pressAttack, pressJump, pressDodge, pressInteract, pressPause;
        float nextAttack, nextDodge;
        readonly List<string> log = new List<string>();
        int checksPassed, checksFailed;
        float startReal;
        bool finished;
        bool quitWhenDone;
        string outDir;
        bool expectPause;
        float unexpectedPauseT;
        int pauseTest;              // pause/resume check, driven from Update (see Run)
        int pauseTestFrames;
        float pauseTestT;
        bool pauseOpenedOk, pauseClosedOk;
        bool benchArenaDone;
        int perfSkipUntilFrame;    // frames spent writing screenshots are left out of the worst-frame stat
        int fpsFrames;
        float fpsTime, worstFrame, playStartReal = -1f;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (Instance != null) return;
            var args = System.Environment.GetCommandLineArgs();
            bool victory = args.Contains("-autopilot");
            bool defeat = args.Contains("-autopilot-defeat");
            int pref = PlayerPrefs.GetInt("DE_AutoPilot", 0);
            if (pref != 0) { PlayerPrefs.DeleteKey("DE_AutoPilot"); PlayerPrefs.Save(); }
            if (pref == 1) victory = true;
            if (pref == 2) defeat = true;
            if (!victory && !defeat) return;
            var go = new GameObject("AutoPilot");
            DontDestroyOnLoad(go);
            var ap = go.AddComponent<AutoPilot>();
            ap.mode = defeat ? Mode.Defeat : Mode.Victory;
            ap.quitWhenDone = !Application.isEditor;
            InputHub.Override = ap;
        }

        void Awake()
        {
            Instance = this;
            startReal = Time.realtimeSinceStartup;
            outDir = Application.isEditor ? Path.Combine(Application.dataPath, "../Temp/SmokeTest") : Path.Combine(Application.dataPath, "../SmokeTest");
            Directory.CreateDirectory(outDir);
            Application.runInBackground = true;
        }

        void Start() { StartCoroutine(Run()); }

        public PlayerInputState Read() { return state; }

        // ------------------------------------------------------------ logging / checks
        void Log(string msg)
        {
            string line = "[" + (Time.realtimeSinceStartup - startReal).ToString("000.0") + "s] " + msg;
            log.Add(line);
            Debug.Log("[AUTOPILOT] " + line);
        }

        bool Check(bool ok, string what)
        {
            if (ok) checksPassed++; else checksFailed++;
            Log((ok ? "PASS  " : "FAIL  ") + what);
            return ok;
        }

        void Shot(string name)
        {
            string path = Path.Combine(outDir, mode + "_" + name + ".png");
            if (Application.isEditor) { try { ScreenCapture.CaptureScreenshot(path); } catch { } return; }
            // A player window that is not being presented (display asleep, locked session) leaves the back
            // buffer stale, so builds render the main camera offscreen with the HUD moved into camera space.
            try { CaptureOffscreen(path); } catch (System.Exception e) { Log("WARN  capture failed: " + e.Message); }
            perfSkipUntilFrame = Time.frameCount + 2;
        }

        /// <summary>Measures real frame cost: for 60 frames the game camera renders into a texture through the
        /// normal player loop (with vsync off), then a read-back waits for the GPU. Used in builds because a window
        /// that is not being presented (locked screen) skips normal rendering, so the frame counter is meaningless.</summary>
        IEnumerator FrameBenchmark(string label)
        {
            var cam = Camera.main;
            if (cam == null) yield break;
            int w = Screen.width > 0 ? Screen.width : 1600, h = Screen.height > 0 ? Screen.height : 900;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
            var probe = new Texture2D(4, 4, TextureFormat.RGB24, false);
            var prevTarget = cam.targetTexture;
            int prevVsync = QualitySettings.vSyncCount, prevFps = Application.targetFrameRate;
            QualitySettings.vSyncCount = 0; Application.targetFrameRate = -1;
            cam.targetTexture = rt;
            for (int i = 0; i < 5; i++) yield return null;
            SyncGpu(rt, probe);
            const int n = 60;
            float t0 = Time.realtimeSinceStartup;
            for (int i = 0; i < n; i++) yield return null;
            SyncGpu(rt, probe);
            float ms = (Time.realtimeSinceStartup - t0) * 1000f / n;
            if (cam != null) cam.targetTexture = prevTarget;
            QualitySettings.vSyncCount = prevVsync; Application.targetFrameRate = prevFps;
            if (RenderTexture.active == rt) RenderTexture.active = null;
            rt.Release(); Object.Destroy(rt); Object.Destroy(probe);
            Log("Frame benchmark (" + label + "): " + ms.ToString("0.00") + " ms per frame at " + w + "x" + h + " (about " + (1000f / ms).ToString("0") + " fps, vsync off)");
            perfSkipUntilFrame = Time.frameCount + 2;
        }

        static void SyncGpu(RenderTexture rt, Texture2D probe)
        {
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            probe.ReadPixels(new Rect(0, 0, 4, 4), 0, 0);
            RenderTexture.active = prev == rt ? null : prev;
        }

        static void CaptureOffscreen(string path)
        {
            var cam = Camera.main;
            if (cam == null) return;
            int w = Screen.width > 0 ? Screen.width : 1600, h = Screen.height > 0 ? Screen.height : 900;
            var rt = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32);
            var moved = new List<Canvas>();
            foreach (var c in Object.FindObjectsByType<Canvas>())
            {
                if (!c.isRootCanvas || c.renderMode != RenderMode.ScreenSpaceOverlay || !c.isActiveAndEnabled) continue;
                c.renderMode = RenderMode.ScreenSpaceCamera;
                c.worldCamera = cam;
                c.planeDistance = cam.nearClipPlane + 0.02f;
                moved.Add(c);
            }
            Canvas.ForceUpdateCanvases();
            var prevTarget = cam.targetTexture;
            var prevActive = RenderTexture.active;
            cam.targetTexture = rt;
            cam.Render();
            cam.targetTexture = prevTarget;
            foreach (var c in moved) c.renderMode = RenderMode.ScreenSpaceOverlay;
            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = prevActive == rt ? null : prevActive;
            RenderTexture.ReleaseTemporary(rt);
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.Destroy(tex);
        }

        void Finish(string reason)
        {
            if (finished) return;
            finished = true;
            InputHub.Override = null;
            if (fpsTime > 0f) Log("Performance: average " + (fpsFrames / fpsTime).ToString("0") + " fps, worst frame " + (worstFrame * 1000f).ToString("0") + " ms, " + Screen.width + "x" + Screen.height);
            bool pass = checksFailed == 0 && string.IsNullOrEmpty(reason);
            LastResult = pass ? "PASS" : "FAIL";
            Log("RESULT: " + (pass ? "PASS" : "FAIL " + reason) + "  (checks passed " + checksPassed + ", failed " + checksFailed + ")");
            try { File.WriteAllLines(Path.Combine(outDir, "smoketest_" + mode + ".txt"), log.ToArray()); } catch { }
            if (quitWhenDone) StartCoroutine(QuitSoon());
        }

        IEnumerator QuitSoon()
        {
            yield return new WaitForSecondsRealtime(1.5f);
            Application.Quit();
        }

        IEnumerator WaitFor(System.Func<bool> cond, float timeout)
        {
            float t = 0f;
            while (!cond() && t < timeout) { t += Time.unscaledDeltaTime; yield return null; }
        }

        static bool Click(string buttonName)
        {
            var go = GameObject.Find(buttonName);
            if (go == null) return false;
            var b = go.GetComponent<Button>();
            if (b == null || !b.isActiveAndEnabled) return false;
            b.onClick.Invoke();
            return true;
        }

        void StepPauseTest(GameManager gm)
        {
            pauseTestFrames++;
            pauseTestT += Time.unscaledDeltaTime;
            switch (pauseTest)
            {
                case 1: pressPause = true; pauseTest = 2; pauseTestFrames = 0; break;
                case 2:
                    if (gm.State == GameState.Paused) { pauseOpenedOk = Time.timeScale == 0f; pauseTest = 3; pauseTestFrames = 0; pauseTestT = 0f; }
                    else if (pauseTestFrames > 60) pauseTest = 6;
                    break;
                case 3:
                    // let the menu fade in before the screenshot (frame count as a fallback: unscaled time
                    // stands still while the editor steps frames)
                    if (pauseTestT >= 0.4f || pauseTestFrames >= 30) { Shot("03_pause"); pauseTest = 4; pauseTestFrames = 0; }
                    break;
                case 4: pressPause = true; pauseTest = 5; pauseTestFrames = 0; break;
                case 5:
                    if (gm.State == GameState.Playing) { pauseClosedOk = Time.timeScale == 1f; pauseTest = 6; }
                    else if (pauseTestFrames > 60) pauseTest = 6;
                    break;
            }
        }

        // ------------------------------------------------------------ per-frame input synthesis
        void Update()
        {
            var gm = GameManager.Instance;
            var s = new PlayerInputState();
            if (gm != null && pauseTest > 0 && pauseTest < 6) StepPauseTest(gm);
            if (gm != null && !finished)
            {
                if (gm.State == GameState.Paused && !expectPause)
                {
                    unexpectedPauseT += Time.unscaledDeltaTime;
                    if (unexpectedPauseT > 0.6f) { unexpectedPauseT = 0f; Log("WARN  unexpected pause from stray input, resuming"); gm.Resume(); }
                }
                else unexpectedPauseT = 0f;
                if (gm.State == GameState.Playing)
                {
                    if (playStartReal < 0f) playStartReal = Time.realtimeSinceStartup;
                    if (Time.realtimeSinceStartup - playStartReal > 3f)
                    {
                        fpsFrames++; fpsTime += Time.unscaledDeltaTime;
                        if (Time.frameCount > perfSkipUntilFrame) worstFrame = Mathf.Max(worstFrame, Time.unscaledDeltaTime);
                    }
                }
            }
            if (gm != null && gm.Player != null && gm.Cam != null)
            {
                Transform cam = gm.Cam.transform;
                Vector3 f = cam.forward; f.y = 0f; f.Normalize();
                Vector3 r = cam.right; r.y = 0f; r.Normalize();
                Vector3 mw = moveWorld; mw.y = 0f;
                if (mw.sqrMagnitude > 1f) mw.Normalize();
                s.move = new Vector2(Vector3.Dot(mw, r), Vector3.Dot(mw, f));
                // keep the camera behind the direction of travel so screenshots read well
                Vector3 face = mw.sqrMagnitude > 0.05f ? mw : gm.Player.transform.forward;
                float desiredYaw = Mathf.Atan2(face.x, face.z) * Mathf.Rad2Deg;
                float dy = Mathf.DeltaAngle(gm.Cam.Yaw, desiredYaw) * Mathf.Min(1f, 2.5f * Time.unscaledDeltaTime);
                float sens = Mathf.Max(0.0001f, gm.Cam.mouseSensitivity);
                s.lookDelta = new Vector2(dy / sens, (gm.Cam.Pitch - 17f) * Mathf.Min(1f, 2f * Time.unscaledDeltaTime) / sens);
            }
            s.attack = pressAttack; s.jump = pressJump; s.dodge = pressDodge; s.interact = pressInteract; s.pause = pressPause;
            pressAttack = pressJump = pressDodge = pressInteract = pressPause = false;
            state = s;
        }

        // ------------------------------------------------------------ main script
        struct Wp { public Vector3 pos; public string action; public string name; }

        List<Wp> Route()
        {
            var list = new List<Wp>();
            var root = GameObject.Find("AutoPilotRoute");
            if (root == null) return list;
            var kids = new List<Transform>();
            foreach (Transform t in root.transform) kids.Add(t);
            kids.Sort((a, b) => string.CompareOrdinal(a.name, b.name));
            foreach (var t in kids)
            {
                var parts = t.name.Split('_');
                list.Add(new Wp { pos = t.position, action = parts.Length > 2 ? parts[2] : "Move", name = t.name });
            }
            return list;
        }

        IEnumerator Run()
        {
            Log("Autopilot started, mode " + mode + ", scene " + UnityEngine.SceneManagement.SceneManager.GetActiveScene().name);
            yield return WaitFor(() => GameManager.Instance != null, 30f);
            var gm = GameManager.Instance;
            if (!Check(gm != null, "GameManager present")) { Finish("no GameManager"); yield break; }
            yield return new WaitForSecondsRealtime(2f);
            Check(gm.State == GameState.Title, "Title screen shown at launch");
            Shot("01_title");
            Check(Click("Btn_BEGIN"), "Clicked BEGIN on the title screen");
            yield return WaitFor(() => gm.State == GameState.Playing, 5f);
            if (!Check(gm.State == GameState.Playing, "Gameplay started from title")) { Finish("could not start"); yield break; }
            var spawn = gm.Player.transform.position;
            yield return new WaitForSeconds(2.5f);
            Shot("02_spawn");
            if (!Application.isEditor) yield return FrameBenchmark("start cell");

            // pause / resume through the real input path. Driven from Update: while time is stopped,
            // coroutines may not resume when the editor steps frames, but Update always runs.
            expectPause = true;
            pauseTest = 1;
            float pauseGuard = 0f;
            while (pauseTest != 6 && pauseGuard < 15f) { pauseGuard += Time.unscaledDeltaTime; yield return null; }
            Check(pauseOpenedOk, "Pause menu opens (time stopped)");
            Check(pauseClosedOk, "Pause menu closes");
            expectPause = false;

            var route = Route();
            Check(route.Count > 0, "Autopilot route found (" + route.Count + " markers)");
            float runStart = Time.time;
            foreach (var wp in route)
            {
                if (mode == Mode.Defeat && wp.action == "Key") break;
                yield return Goto(wp);
                if (finished) yield break;
                if (gm.Player.IsDead)
                {
                    if (mode == Mode.Victory) { Check(false, "Player survived the run (died at " + wp.name + ")"); Finish("player died"); yield break; }
                    break;
                }
                if (Time.time - runStart > 420f) { Check(false, "Run finished within time limit"); Finish("timeout"); yield break; }
            }

            if (mode == Mode.Victory)
            {
                yield return WaitFor(() => gm.State == GameState.Victory, 12f);
                Check(gm.State == GameState.Victory, "Victory screen reached after the exit");
                Log("Playtime " + gm.PlayTime.ToString("0.0") + "s, kills " + gm.Kills + ", damage taken " + gm.DamageTaken.ToString("0"));
                Check(gm.PlayTime < 300f, "Completed in under five minutes (" + gm.PlayTime.ToString("0") + "s)");
                yield return new WaitForSecondsRealtime(1.5f);
                Shot("09_victory");
                Check(Click("Btn_PLAY AGAIN"), "Clicked PLAY AGAIN on the victory screen");
                yield return VerifyRestart(gm, spawn);
                Finish(null);
            }
            else
            {
                // stand still and let the guards win
                moveWorld = Vector3.zero;
                Log("Waiting near the guards to be defeated");
                float waited = 0f;
                while (!gm.Player.IsDead && waited < 150f)
                {
                    var e = gm.Enemies.Where(x => x != null && !x.IsDead).OrderBy(x => Vector3.Distance(x.transform.position, gm.Player.transform.position)).FirstOrDefault();
                    if (e != null && Vector3.Distance(e.transform.position, gm.Player.transform.position) > 2.2f)
                        moveWorld = (e.transform.position - gm.Player.transform.position).normalized;
                    else moveWorld = Vector3.zero;
                    waited += Time.deltaTime;
                    yield return null;
                }
                moveWorld = Vector3.zero;
                Check(gm.Player.IsDead, "Player can be killed by enemies (health reached 0)");
                yield return WaitFor(() => gm.State == GameState.Dead, 8f);
                Check(gm.State == GameState.Dead, "Defeat screen shown");
                yield return new WaitForSecondsRealtime(1.5f);
                Shot("05_defeat");
                var retry = GameObject.Find("Btn_RETRY FROM CHECKPOINT");
                Check(retry == null, "Checkpoint retry hidden before the door was opened");
                Check(Click("Btn_RESTART FROM BEGINNING"), "Clicked RESTART on the defeat screen");
                yield return VerifyRestart(gm, spawn);
                Finish(null);
            }
        }

        IEnumerator VerifyRestart(GameManager oldGm, Vector3 spawn)
        {
            yield return WaitFor(() => GameManager.Instance != null && GameManager.Instance != oldGm, 15f);
            var gm = GameManager.Instance;
            if (!Check(gm != null && gm != oldGm, "Scene reloaded after restart")) yield break;
            yield return WaitFor(() => gm.State == GameState.Playing, 5f);
            Check(gm.State == GameState.Playing, "Restart drops straight into gameplay");
            yield return new WaitForSeconds(1f);
            Check(!gm.HasKey && !gm.DoorOpened && !gm.EncounterStarted, "Progress reset after restart");
            Check(gm.Player != null && gm.Player.health.current >= gm.Player.health.max - 0.01f, "Health full after restart");
            Check(gm.Player != null && Vector3.Distance(gm.Player.transform.position, spawn) < 2.5f, "Player back at the spawn point");
            Shot("10_after_restart");
        }

        EnemyAI PickEnemy(GameManager gm, float range)
        {
            var p = gm.Player.transform.position;
            EnemyAI best = null; float bd = float.MaxValue;
            foreach (var e in gm.Enemies)
            {
                if (e == null || e.IsDead || !e.isActiveAndEnabled) continue;
                float d = Vector3.Distance(e.transform.position, p);
                if (Mathf.Abs(e.transform.position.y - p.y) > 2.5f) continue;
                bool relevant = d < 4.5f || (e.IsAggro && d < range);
                if (relevant && d < bd) { bd = d; best = e; }
            }
            return best;
        }

        IEnumerator Goto(Wp wp)
        {
            var gm = GameManager.Instance;
            Log("-> " + wp.name);
            float arrive = wp.action == "Jump" ? 0.45f : 0.9f;
            float t = 0f, lastProgressT = 0f, bestDist = float.MaxValue;
            Vector3[] corners = null; int ci = 0; float nextPath = 0f;
            bool jumped = false;
            while (true)
            {
                if (finished || gm.Player.IsDead) { moveWorld = Vector3.zero; yield break; }
                t += Time.deltaTime;
                var p = gm.Player.transform.position;

                if (wp.action == "Key" && gm.HasKey) { Log("Key collected at " + gm.PlayTime.ToString("0.0") + "s"); Shot("04_key"); break; }
                if (wp.action == "Door" && gm.DoorOpened) { Log("Door opened at " + gm.PlayTime.ToString("0.0") + "s"); Shot("05_door"); if (!Application.isEditor) yield return FrameBenchmark("great hall"); break; }
                if (wp.action == "Arena" && gm.EncounterCleared) { Log("Arena cleared at " + gm.PlayTime.ToString("0.0") + "s"); Shot("07_cleared"); break; }
                if (wp.action == "Exit" && gm.State == GameState.Victory) { Log("Exit reached at " + gm.PlayTime.ToString("0.0") + "s"); break; }

                if (mode == Mode.Victory && wp.action != "Jump")
                {
                    var e = PickEnemy(gm, wp.action == "Arena" ? 40f : 11f);
                    if (e != null) { Fight(gm, e); yield return null; nextPath = 0f; lastProgressT = t; continue; }
                }
                else if (mode == Mode.Defeat)
                {
                    var e = PickEnemy(gm, 8f);
                    if (e != null) { moveWorld = Vector3.zero; break; }
                }

                Vector3 target = wp.pos;
                if (wp.action == "Arena" && gm.EncounterStarted && !gm.EncounterCleared)
                {
                    if (gm.EncounterWave >= 1 && Time.frameCount % 240 == 0) Shot("06_arena_" + gm.EncounterWave);
                    if (!Application.isEditor && !benchArenaDone && gm.EncounterWave >= 2 && gm.ActiveBoss != null) { benchArenaDone = true; yield return FrameBenchmark("arena, boss wave"); }
                }
                float flatDist = Vector2.Distance(new Vector2(p.x, p.z), new Vector2(target.x, target.z));
                bool arrived = flatDist < arrive;
                if (arrived)
                {
                    if (wp.action == "Move" || wp.action == "Jump") break;
                    if (wp.action == "Door")
                    {
                        moveWorld = Vector3.zero;
                        if (gm.Player.CurrentInteractable != null && Time.frameCount % 20 == 0) pressInteract = true;
                        yield return null;
                        if (t > 25f) { Check(false, "Door could be unlocked"); Finish("door"); yield break; }
                        continue;
                    }
                    if (wp.action == "Arena") { moveWorld = Vector3.zero; if (t > 200f) { Check(false, "Arena cleared in time"); Finish("arena"); yield break; } yield return null; continue; }
                }

                if (Time.time >= nextPath)
                {
                    nextPath = Time.time + 0.4f;
                    var path = new NavMeshPath();
                    NavMeshHit a, b;
                    corners = null; ci = 0;
                    if (NavMesh.SamplePosition(p, out a, 1.5f, NavMesh.AllAreas) && NavMesh.SamplePosition(target, out b, 1.5f, NavMesh.AllAreas)
                        && NavMesh.CalculatePath(a.position, b.position, NavMesh.AllAreas, path) && path.status == NavMeshPathStatus.PathComplete && path.corners.Length > 1)
                    { corners = path.corners; ci = 1; }
                }
                Vector3 steer = target;
                if (corners != null)
                {
                    while (ci < corners.Length - 1 && Vector2.Distance(new Vector2(p.x, p.z), new Vector2(corners[ci].x, corners[ci].z)) < 0.6f) ci++;
                    steer = corners[Mathf.Min(ci, corners.Length - 1)];
                }
                Vector3 dir = steer - p; dir.y = 0f;
                moveWorld = dir.sqrMagnitude > 0.0001f ? dir.normalized : Vector3.zero;

                if (wp.action == "Jump" && !jumped && flatDist < 1.1f && gm.Player.IsGrounded)
                {
                    pressJump = true; jumped = true;
                    Log("Jumping at " + wp.name);
                }

                if (flatDist < bestDist - 0.3f) { bestDist = flatDist; lastProgressT = t; }
                if (t - lastProgressT > 3f)
                {
                    lastProgressT = t;
                    Log("Stuck near " + p.ToString("F1") + ", nudging");
                    pressJump = true;
                    moveWorld = Quaternion.Euler(0f, Random.value < 0.5f ? 70f : -70f, 0f) * moveWorld;
                    yield return new WaitForSeconds(0.4f);
                }
                if (t > 120f) { Check(false, "Reached " + wp.name); Finish("stuck at " + wp.name); yield break; }
                yield return null;
            }
            moveWorld = Vector3.zero;
        }

        void Fight(GameManager gm, EnemyAI e)
        {
            var p = gm.Player.transform.position;
            Vector3 to = e.transform.position - p; to.y = 0f;
            float d = to.magnitude;
            float reach = 1.7f + e.radius;
            if (e.IsWindingUp && d < 3.4f && Time.time >= nextDodge)
            {
                nextDodge = Time.time + 1.2f;
                if (Random.value < 0.65f)
                {
                    Vector3 side = Vector3.Cross(Vector3.up, to.normalized) * (Random.value < 0.5f ? 1f : -1f);
                    moveWorld = (side - to.normalized * 0.6f).normalized;
                    pressDodge = true;
                    return;
                }
            }
            if (d > reach) { moveWorld = to.normalized; }
            else
            {
                moveWorld = to.normalized * 0.05f;
                if (Time.time >= nextAttack) { nextAttack = Time.time + 0.16f; pressAttack = true; }
            }
        }
    }
}
