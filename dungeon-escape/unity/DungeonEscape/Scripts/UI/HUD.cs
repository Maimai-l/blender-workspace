using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace DungeonEscape
{
    /// <summary>Builds and drives all UI at runtime: HUD, title, pause, defeat and victory screens.</summary>
    public class HUD : MonoBehaviour
    {
        public GameObject keyModel;

        GameManager gm;
        RectTransform root;
        CanvasGroup gameplayGroup;
        Image hpFill, hpGhost;
        TextMeshProUGUI hpText;
        RawImage keyIconImage;
        Image keyBorder;
        TextMeshProUGUI keyStatus;
        KeyIcon keyIcon;
        TextMeshProUGUI objectiveText;
        RectTransform objectiveRt;
        float objectivePulse;
        CanvasGroup encounterGroup;
        TextMeshProUGUI encWave, encRemaining;
        Image[] encPips;
        CanvasGroup bossGroup;
        Image bossFill;
        TextMeshProUGUI bossName;
        CanvasGroup promptGroup;
        TextMeshProUGUI promptText;
        CanvasGroup toastGroup;
        TextMeshProUGUI toastTitle, toastSub;
        Image vignette;
        float damageFlash;
        CanvasGroup hintGroup;
        float playTimeVisible;
        readonly List<RectTransform> enemyBars = new List<RectTransform>();
        readonly List<Image> enemyBarFills = new List<Image>();

        CanvasGroup titleGroup, pauseGroup, deathGroup, victoryGroup;
        TextMeshProUGUI pressStart, pauseTime, victoryStats, victoryRating;
        Button titleBtn, pauseResume, deathRetry, deathRestart, victoryAgain;
        Image fade;
        float fadeAlpha = 1f;

        readonly Queue<string[]> toasts = new Queue<string[]>();
        bool toastRunning;
        float shownHp = 1f, ghostHp = 1f, ghostDelay;
        GameState lastState = (GameState)(-1);
        bool encounterHideScheduled;
        float encounterAlpha;

        void Awake()
        {
            gm = GameManager.Instance;
            EnsureEventSystem();
            Build();
            if (gm != null)
            {
                gm.ObjectiveChanged += OnObjective;
                gm.Toast += OnToast;
                gm.KeyCollectedEvent += OnKey;
            }
        }

        void Start()
        {
            if (gm == null) gm = GameManager.Instance;
            if (gm != null && gm.Player != null) gm.Player.health.Damaged += OnPlayerDamaged;
            if (gm != null) OnObjective(gm.Objective);
        }

        void OnDestroy()
        {
            if (gm != null)
            {
                gm.ObjectiveChanged -= OnObjective;
                gm.Toast -= OnToast;
                gm.KeyCollectedEvent -= OnKey;
                if (gm.Player != null) gm.Player.health.Damaged -= OnPlayerDamaged;
            }
        }

        static void EnsureEventSystem()
        {
            if (EventSystem.current != null) return;
            var es = FindAnyObjectByType<EventSystem>();
            if (es != null) return;
            var go = new GameObject("EventSystem", typeof(EventSystem));
            var mod = go.AddComponent<InputSystemUIInputModule>();
            mod.AssignDefaultActions();
        }

        // ================================================================ build
        void Build()
        {
            var canvasGo = new GameObject("HUDCanvas", typeof(RectTransform));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 10;
            var scaler = canvasGo.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
            canvasGo.AddComponent<GraphicRaycaster>();
            root = (RectTransform)canvasGo.transform;

            vignette = UIKit.Img(UIKit.Stretch(root, "Vignette"), UIKit.Radial(), new Color(0.75f, 0.03f, 0.02f, 0f));

            var gp = UIKit.Stretch(root, "Gameplay");
            gameplayGroup = gp.gameObject.AddComponent<CanvasGroup>();
            gameplayGroup.interactable = false; gameplayGroup.blocksRaycasts = false;
            BuildHealth(gp);
            BuildKeySlot(gp);
            BuildObjective(gp);
            BuildEncounter(gp);
            BuildBoss(gp);
            BuildPrompt(gp);
            BuildToast(gp);
            BuildHint(gp);
            for (int i = 0; i < 8; i++)
            {
                var bar = UIKit.Rect(gp, "EnemyBar" + i, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(96, 10));
                UIKit.Img(bar, UIKit.Rounded(4), new Color(0f, 0f, 0f, 0.7f), true);
                var fillRt = UIKit.Rect(bar, "Fill", new Vector2(0, 0), new Vector2(1, 1), new Vector2(0f, 0.5f), Vector2.zero, new Vector2(-4, -4));
                var f = UIKit.Img(fillRt, UIKit.White(), new Color(0.9f, 0.2f, 0.15f));
                f.type = Image.Type.Filled; f.fillMethod = Image.FillMethod.Horizontal;
                bar.gameObject.SetActive(false);
                enemyBars.Add(bar); enemyBarFills.Add(f);
            }

            BuildTitle();
            BuildPause();
            BuildDeath();
            BuildVictory();
            fade = UIKit.Img(UIKit.Stretch(root, "Fade"), UIKit.White(), Color.black);
        }

        void BuildHealth(RectTransform gp)
        {
            var box = UIKit.Rect(gp, "Health", new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, 1), new Vector2(40, -34), new Vector2(460, 60));
            var lbl = UIKit.Text(box, "Label", "HEALTH", 17, new Color(UIKit.Parchment.r, UIKit.Parchment.g, UIKit.Parchment.b, 0.8f), TextAlignmentOptions.Left,
                new Vector2(0, 1), new Vector2(0, 0), new Vector2(200, 22), true, 8);
            ((RectTransform)lbl.transform).pivot = new Vector2(0, 1);
            UIKit.Shadow(lbl);
            var bar = UIKit.Rect(box, "Bar", new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, -26), new Vector2(440, 26));
            UIKit.Img(bar, UIKit.Rounded(8), new Color(0.05f, 0.03f, 0.03f, 0.85f), true);
            var ghostRt = UIKit.Rect(bar, "Ghost", Vector2.zero, Vector2.one, new Vector2(0, 0.5f), Vector2.zero, new Vector2(-6, -6));
            hpGhost = UIKit.Img(ghostRt, UIKit.White(), new Color(1f, 0.85f, 0.75f, 0.85f));
            hpGhost.type = Image.Type.Filled; hpGhost.fillMethod = Image.FillMethod.Horizontal;
            var fillRt = UIKit.Rect(bar, "Fill", Vector2.zero, Vector2.one, new Vector2(0, 0.5f), Vector2.zero, new Vector2(-6, -6));
            hpFill = UIKit.Img(fillRt, UIKit.White(), new Color(0.8f, 0.12f, 0.1f));
            hpFill.type = Image.Type.Filled; hpFill.fillMethod = Image.FillMethod.Horizontal;
            var shine = UIKit.Rect(bar, "Shine", new Vector2(0, 0.5f), new Vector2(1, 1), new Vector2(0.5f, 1f), Vector2.zero, new Vector2(-6, -3));
            UIKit.Img(shine, UIKit.White(), new Color(1f, 1f, 1f, 0.08f));
            UIKit.Img(UIKit.Stretch(bar, "Frame"), UIKit.Rounded(8, 2), new Color(UIKit.Gold.r, UIKit.Gold.g, UIKit.Gold.b, 0.6f), true);
            hpText = UIKit.Text(bar, "Value", "100 / 100", 17, Color.white, TextAlignmentOptions.Right, new Vector2(1, 0.5f), new Vector2(-12, 0), new Vector2(200, 26), true);
            ((RectTransform)hpText.transform).pivot = new Vector2(1, 0.5f);
            UIKit.Shadow(hpText, 0.3f, 1f);
        }

        void BuildKeySlot(RectTransform gp)
        {
            var slot = UIKit.Rect(gp, "KeySlot", new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, 1), new Vector2(40, -104), new Vector2(76, 76));
            UIKit.Img(slot, UIKit.Rounded(12), new Color(0.05f, 0.04f, 0.035f, 0.82f), true);
            var iconRt = UIKit.Rect(slot, "Icon", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(84, 84));
            keyIconImage = iconRt.gameObject.AddComponent<RawImage>();
            keyIconImage.raycastTarget = false;
            keyIconImage.color = new Color(0.25f, 0.25f, 0.28f, 0.75f);
            keyBorder = UIKit.Img(UIKit.Stretch(slot, "Border"), UIKit.Rounded(12, 2), new Color(0.5f, 0.5f, 0.5f, 0.5f), true);
            var name = UIKit.Text(gp, "KeyName", "IRON KEY", 20, UIKit.Parchment, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(128, -118), new Vector2(240, 26), true, 4);
            ((RectTransform)name.transform).pivot = new Vector2(0, 1);
            UIKit.Shadow(name);
            keyStatus = UIKit.Text(gp, "KeyStatus", "NOT FOUND", 16, new Color(0.7f, 0.7f, 0.7f), TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(128, -146), new Vector2(240, 22), false, 3);
            ((RectTransform)keyStatus.transform).pivot = new Vector2(0, 1);
            UIKit.Shadow(keyStatus);
            if (keyModel != null)
            {
                keyIcon = KeyIcon.Create(keyModel);
                keyIconImage.texture = keyIcon.Texture;
            }
        }

        void BuildObjective(RectTransform gp)
        {
            objectiveRt = UIKit.Rect(gp, "Objective", new Vector2(0.5f, 1), new Vector2(0.5f, 1), new Vector2(0.5f, 1), new Vector2(0, -26), new Vector2(980, 84));
            UIKit.Img(objectiveRt, UIKit.HGradientCenter(), new Color(0.02f, 0.015f, 0.015f, 0.72f));
            var lbl = UIKit.Text(objectiveRt, "Label", "OBJECTIVE", 16, UIKit.Gold, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -8), new Vector2(400, 22), true, 10);
            ((RectTransform)lbl.transform).pivot = new Vector2(0.5f, 1);
            UIKit.Shadow(lbl);
            objectiveText = UIKit.Text(objectiveRt, "Text", "", 28, UIKit.Parchment, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -32), new Vector2(940, 40), false, 1);
            ((RectTransform)objectiveText.transform).pivot = new Vector2(0.5f, 1);
            UIKit.Shadow(objectiveText);
        }

        void BuildEncounter(RectTransform gp)
        {
            var p = UIKit.Rect(gp, "Encounter", new Vector2(1, 1), new Vector2(1, 1), new Vector2(1, 1), new Vector2(-40, -34), new Vector2(380, 150));
            encounterGroup = p.gameObject.AddComponent<CanvasGroup>();
            encounterGroup.alpha = 0f;
            UIKit.Img(p, UIKit.Rounded(14), new Color(0.05f, 0.03f, 0.03f, 0.78f), true);
            UIKit.Img(UIKit.Stretch(p, "Border"), UIKit.Rounded(14, 2), new Color(UIKit.Blood.r, UIKit.Blood.g, UIKit.Blood.b, 0.7f), true);
            var t = UIKit.Text(p, "Title", "CRYPT GUARDIANS", 19, UIKit.Gold, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -12), new Vector2(360, 24), true, 6);
            ((RectTransform)t.transform).pivot = new Vector2(0.5f, 1);
            encWave = UIKit.Text(p, "Wave", "WAVE 1 / 2", 15, new Color(0.85f, 0.8f, 0.75f), TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -38), new Vector2(360, 20), false, 5);
            ((RectTransform)encWave.transform).pivot = new Vector2(0.5f, 1);
            encRemaining = UIKit.Text(p, "Remaining", "6 REMAINING", 30, Color.white, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -60), new Vector2(360, 38), true, 3);
            ((RectTransform)encRemaining.transform).pivot = new Vector2(0.5f, 1);
            UIKit.Shadow(encRemaining);
            encPips = new Image[6];
            for (int i = 0; i < 6; i++)
            {
                var pr = UIKit.Rect(p, "Pip" + i, new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0.5f, 0.5f), new Vector2(-100 + i * 40, 26), new Vector2(26, 26));
                encPips[i] = UIKit.Img(pr, UIKit.Diamond(48), UIKit.Blood);
            }
        }

        void BuildBoss(RectTransform gp)
        {
            var p = UIKit.Rect(gp, "Boss", new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0, 56), new Vector2(800, 64));
            bossGroup = p.gameObject.AddComponent<CanvasGroup>();
            bossGroup.alpha = 0f;
            bossName = UIKit.Text(p, "Name", "THE WARDEN", 24, UIKit.Parchment, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, 0), new Vector2(600, 30), true, 12);
            ((RectTransform)bossName.transform).pivot = new Vector2(0.5f, 1);
            UIKit.Shadow(bossName);
            var bar = UIKit.Rect(p, "Bar", new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0, 6), new Vector2(780, 18));
            UIKit.Img(bar, UIKit.Rounded(6), new Color(0.03f, 0.02f, 0.02f, 0.85f), true);
            var fr = UIKit.Rect(bar, "Fill", Vector2.zero, Vector2.one, new Vector2(0, 0.5f), Vector2.zero, new Vector2(-6, -6));
            bossFill = UIKit.Img(fr, UIKit.White(), new Color(0.75f, 0.16f, 0.08f));
            bossFill.type = Image.Type.Filled; bossFill.fillMethod = Image.FillMethod.Horizontal;
            UIKit.Img(UIKit.Stretch(bar, "Frame"), UIKit.Rounded(6, 2), new Color(UIKit.Gold.r, UIKit.Gold.g, UIKit.Gold.b, 0.5f), true);
        }

        void BuildPrompt(RectTransform gp)
        {
            var p = UIKit.Rect(gp, "Prompt", new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0, 170), new Vector2(620, 54));
            promptGroup = p.gameObject.AddComponent<CanvasGroup>();
            promptGroup.alpha = 0f;
            UIKit.Img(p, UIKit.Rounded(24), new Color(0.04f, 0.03f, 0.03f, 0.8f), true);
            UIKit.Img(UIKit.Stretch(p, "Border"), UIKit.Rounded(24, 2), new Color(UIKit.Gold.r, UIKit.Gold.g, UIKit.Gold.b, 0.6f), true);
            promptText = UIKit.Text(p, "Text", "", 24, UIKit.Parchment, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(600, 50), false, 2);
        }

        void BuildToast(RectTransform gp)
        {
            var p = UIKit.Rect(gp, "Toast", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, 250), new Vector2(1400, 140));
            toastGroup = p.gameObject.AddComponent<CanvasGroup>();
            toastGroup.alpha = 0f;
            UIKit.Img(p, UIKit.HGradientCenter(), new Color(0f, 0f, 0f, 0.55f));
            toastTitle = UIKit.Text(p, "Title", "", 56, UIKit.Gold, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 22), new Vector2(1400, 70), true, 14);
            toastTitle.enableVertexGradient = true;
            toastTitle.colorGradient = new VertexGradient(new Color(1f, 0.93f, 0.7f), new Color(1f, 0.93f, 0.7f), new Color(0.95f, 0.62f, 0.25f), new Color(0.95f, 0.62f, 0.25f));
            UIKit.Shadow(toastTitle, 0.6f, 2f, 0.9f);
            toastSub = UIKit.Text(p, "Sub", "", 27, UIKit.Parchment, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -30), new Vector2(1400, 40), false, 2);
            UIKit.Shadow(toastSub);
        }

        void BuildHint(RectTransform gp)
        {
            var p = UIKit.Rect(gp, "Hint", new Vector2(0, 0), new Vector2(0, 0), new Vector2(0, 0), new Vector2(40, 30), new Vector2(1100, 70));
            hintGroup = p.gameObject.AddComponent<CanvasGroup>();
            var t = UIKit.Text(p, "Text",
                "<b>WASD</b> Move   <b>Mouse</b> Look   <b>LMB</b> Attack (x3 combo)   <b>Space</b> Jump   <b>Shift / RMB</b> Dodge roll   <b>E</b> Interact   <b>Esc</b> Pause",
                19, new Color(0.9f, 0.86f, 0.78f, 0.9f), TextAlignmentOptions.BottomLeft, new Vector2(0, 0), Vector2.zero, new Vector2(1100, 70), false, 1);
            ((RectTransform)t.transform).pivot = new Vector2(0, 0);
            UIKit.Shadow(t);
        }

        CanvasGroup Screen(string name, Color dim)
        {
            var rt = UIKit.Stretch(root, name);
            var g = rt.gameObject.AddComponent<CanvasGroup>();
            var bg = UIKit.Img(rt, UIKit.White(), dim);
            bg.raycastTarget = true;
            g.alpha = 0f; g.interactable = false; g.blocksRaycasts = false;
            return g;
        }

        TextMeshProUGUI BigTitle(Transform parent, string text, float size, Color top, Color bottom, float y, float spacing)
        {
            var t = UIKit.Text(parent, "Title", text, size, Color.white, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, y), new Vector2(1800, size * 1.4f), true, spacing);
            t.enableVertexGradient = true;
            t.colorGradient = new VertexGradient(top, top, bottom, bottom);
            UIKit.Shadow(t, 0.7f, 3f, 0.95f);
            return t;
        }

        void BuildTitle()
        {
            titleGroup = Screen("TitleScreen", new Color(0f, 0f, 0f, 0f));
            var rt = (RectTransform)titleGroup.transform;
            var top = UIKit.Rect(rt, "TopShade", new Vector2(0, 1), new Vector2(1, 1), new Vector2(0.5f, 1), Vector2.zero, new Vector2(0, 520));
            UIKit.Img(top, UIKit.VGradient(), new Color(0f, 0f, 0f, 0.85f));
            var bot = UIKit.Rect(rt, "BottomShade", new Vector2(0, 0), new Vector2(1, 0), new Vector2(0.5f, 0), Vector2.zero, new Vector2(0, 420));
            var bimg = UIKit.Img(bot, UIKit.VGradient(), new Color(0f, 0f, 0f, 0.85f));
            bot.localScale = new Vector3(1f, -1f, 1f);
            bot.pivot = new Vector2(0.5f, 1f);
            BigTitle(rt, "DUNGEON ESCAPE", 112, new Color(1f, 0.92f, 0.68f), new Color(0.85f, 0.5f, 0.18f), 300, 18);
            var line = UIKit.Rect(rt, "Line", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, 232), new Vector2(900, 3));
            UIKit.Img(line, UIKit.HGradientCenter(), UIKit.Gold);
            var sub = UIKit.Text(rt, "Subtitle", "ESCAPE THE CRYPT OF THE WARDEN", 28, new Color(0.92f, 0.88f, 0.8f, 0.9f), TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), new Vector2(0, 196), new Vector2(1400, 40), false, 14);
            UIKit.Shadow(sub);
            titleBtn = UIKit.Button(rt, "BEGIN", new Vector2(0, -250), new Vector2(320, 68), () => { if (gm != null) gm.StartGame(); });
            pressStart = UIKit.Text(rt, "Press", "PRESS ENTER, SPACE OR (A) TO BEGIN", 20, new Color(1f, 1f, 1f, 0.8f), TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), new Vector2(0, -310), new Vector2(1000, 30), false, 6);
            UIKit.Shadow(pressStart);
            var c1 = UIKit.Text(rt, "Controls", "<b>WASD</b> Move   ·   <b>Mouse</b> Look   ·   <b>Left Click</b> Attack (3-hit combo)   ·   <b>Space</b> Jump   ·   <b>Shift / Right Click</b> Dodge roll   ·   <b>E</b> Interact   ·   <b>Esc</b> Pause",
                20, new Color(0.9f, 0.87f, 0.8f, 0.85f), TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0, 92), new Vector2(1800, 30), false, 1);
            UIKit.Shadow(c1);
            var c2 = UIKit.Text(rt, "Pad", "Gamepad:  Left stick Move · Right stick Look · (X) / RB Attack · (A) Jump · (B) / LB Dodge · (Y) Interact · Start Pause",
                17, new Color(0.8f, 0.77f, 0.7f, 0.7f), TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0, 58), new Vector2(1800, 26), false, 1);
            UIKit.Shadow(c2);
            var credit = UIKit.Text(rt, "Credit", "All models, animation and sound made from scratch in Blender and Unity", 15, new Color(1f, 1f, 1f, 0.45f),
                TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0, 22), new Vector2(1600, 22), false, 3);
        }

        void BuildPause()
        {
            pauseGroup = Screen("PauseScreen", new Color(0.01f, 0.01f, 0.015f, 0.72f));
            var rt = (RectTransform)pauseGroup.transform;
            BigTitle(rt, "PAUSED", 84, new Color(1f, 0.92f, 0.68f), new Color(0.85f, 0.5f, 0.18f), 230, 20);
            pauseTime = UIKit.Text(rt, "Time", "", 22, UIKit.Parchment, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 160), new Vector2(800, 30), false, 6);
            pauseResume = UIKit.Button(rt, "RESUME", new Vector2(0, 50), new Vector2(420, 66), () => { if (gm != null) gm.Resume(); });
            UIKit.Button(rt, "RESTART", new Vector2(0, -30), new Vector2(420, 66), () => { if (gm != null) gm.Restart(false); });
            UIKit.Button(rt, "QUIT GAME", new Vector2(0, -110), new Vector2(420, 66), () => { if (gm != null) gm.QuitGame(); });
            var c = UIKit.Text(rt, "Controls", "WASD Move · Mouse Look · LMB Attack · Space Jump · Shift/RMB Dodge · E Interact · Esc Resume",
                19, new Color(0.85f, 0.82f, 0.75f, 0.8f), TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -230), new Vector2(1600, 30), false, 1);
        }

        void BuildDeath()
        {
            deathGroup = Screen("DeathScreen", new Color(0.04f, 0f, 0f, 0.55f));
            var rt = (RectTransform)deathGroup.transform;
            UIKit.Img(UIKit.Stretch(rt, "Red"), UIKit.Radial(), new Color(0.5f, 0.02f, 0.02f, 0.9f));
            BigTitle(rt, "YOU HAVE FALLEN", 96, new Color(1f, 0.35f, 0.28f), new Color(0.55f, 0.05f, 0.04f), 210, 16);
            var sub = UIKit.Text(rt, "Sub", "The dungeon claims another soul...", 28, new Color(0.95f, 0.85f, 0.8f, 0.9f), TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), new Vector2(0, 130), new Vector2(1200, 40), false, 3);
            UIKit.Shadow(sub);
            deathRetry = UIKit.Button(rt, "RETRY FROM CHECKPOINT", new Vector2(0, 20), new Vector2(520, 66), () => { if (gm != null) gm.Restart(true); });
            deathRestart = UIKit.Button(rt, "RESTART FROM BEGINNING", new Vector2(0, -60), new Vector2(520, 66), () => { if (gm != null) gm.Restart(false); });
            UIKit.Button(rt, "QUIT GAME", new Vector2(0, -140), new Vector2(520, 66), () => { if (gm != null) gm.QuitGame(); });
        }

        void BuildVictory()
        {
            victoryGroup = Screen("VictoryScreen", new Color(0.02f, 0.015f, 0.01f, 0.45f));
            var rt = (RectTransform)victoryGroup.transform;
            UIKit.Img(UIKit.Stretch(rt, "Glow"), UIKit.Radial(), new Color(0.05f, 0.03f, 0.01f, 0.85f));
            BigTitle(rt, "YOU ESCAPED", 104, new Color(1f, 0.95f, 0.75f), new Color(0.95f, 0.6f, 0.2f), 250, 20);
            var sub = UIKit.Text(rt, "Sub", "Daylight at last. The Warden's crypt lies behind you.", 28, new Color(0.95f, 0.92f, 0.85f, 0.95f),
                TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 170), new Vector2(1400, 40), false, 2);
            UIKit.Shadow(sub);
            var panel = UIKit.Rect(rt, "Stats", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, 40), new Vector2(560, 170));
            UIKit.Img(panel, UIKit.Rounded(16), new Color(0.04f, 0.03f, 0.025f, 0.8f), true);
            UIKit.Img(UIKit.Stretch(panel, "Border"), UIKit.Rounded(16, 2), new Color(UIKit.Gold.r, UIKit.Gold.g, UIKit.Gold.b, 0.55f), true);
            victoryStats = UIKit.Text(panel, "Text", "", 26, UIKit.Parchment, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 10), new Vector2(520, 130), false, 2);
            victoryRating = UIKit.Text(panel, "Rating", "", 20, UIKit.Gold, TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0, 18), new Vector2(520, 26), true, 6);
            victoryAgain = UIKit.Button(rt, "PLAY AGAIN", new Vector2(0, -110), new Vector2(420, 66), () => { if (gm != null) gm.Restart(false); });
            UIKit.Button(rt, "QUIT GAME", new Vector2(0, -190), new Vector2(420, 66), () => { if (gm != null) gm.QuitGame(); });
        }

        // ================================================================ events
        void OnObjective(string text)
        {
            if (objectiveText == null) return;
            objectiveText.text = text;
            objectivePulse = 1f;
        }

        void OnToast(string title, string sub)
        {
            toasts.Enqueue(new[] { title, sub });
            if (!toastRunning) StartCoroutine(ToastLoop());
        }

        IEnumerator ToastLoop()
        {
            toastRunning = true;
            while (toasts.Count > 0)
            {
                var t = toasts.Dequeue();
                toastTitle.text = t[0];
                toastSub.text = t[1];
                // Banners freeze and hide while the pause menu is open, then carry on.
                float a = 0f;
                while (a < 1f) { if (!ToastHeld()) a += Time.unscaledDeltaTime / 0.3f; ApplyToast(a, true); yield return null; }
                float hold = toasts.Count > 0 ? 1.6f : 2.6f;
                float h = 0f;
                while (h < hold) { if (!ToastHeld()) h += Time.unscaledDeltaTime; ApplyToast(1f, false); yield return null; }
                while (a > 0f) { if (!ToastHeld()) a -= Time.unscaledDeltaTime / 0.5f; ApplyToast(a, false); yield return null; }
                toastGroup.alpha = 0f;
            }
            toastRunning = false;
        }

        bool ToastHeld() { return gm != null && gm.State == GameState.Paused; }

        void ApplyToast(float a, bool growIn)
        {
            a = Mathf.Clamp01(a);
            toastGroup.alpha = ToastHeld() ? 0f : a;
            if (growIn) toastGroup.transform.localScale = Vector3.one * Mathf.Lerp(1.08f, 1f, a);
        }

        void OnKey()
        {
            if (keyIcon != null) keyIcon.spinFast = true;
            StartCoroutine(KeyFlash());
        }

        IEnumerator KeyFlash()
        {
            float t = 0f;
            while (t < 1.5f)
            {
                t += Time.unscaledDeltaTime;
                float s = 1f + Mathf.Sin(t * 12f) * 0.08f * (1.5f - t);
                keyIconImage.transform.localScale = Vector3.one * s;
                yield return null;
            }
            keyIconImage.transform.localScale = Vector3.one;
            if (keyIcon != null) keyIcon.spinFast = false;
        }

        void OnPlayerDamaged(DamageInfo info)
        {
            damageFlash = Mathf.Min(1f, damageFlash + (info.heavy ? 0.9f : 0.65f));
            ghostDelay = 0.45f;
        }

        // ================================================================ update
        static void Show(CanvasGroup g, bool on, float dt, float speed = 5f)
        {
            g.alpha = Mathf.MoveTowards(g.alpha, on ? 1f : 0f, dt * speed);
            bool interact = on && g.alpha > 0.5f;
            g.interactable = interact; g.blocksRaycasts = interact;
        }

        void Update()
        {
            if (gm == null) { gm = GameManager.Instance; if (gm == null) return; }
            float dt = Time.unscaledDeltaTime;
            var st = gm.State;
            if (st != lastState) OnStateChanged(st);

            fadeAlpha = Mathf.MoveTowards(fadeAlpha, 0f, dt / 1.4f);
            fade.color = new Color(0f, 0f, 0f, fadeAlpha);
            fade.raycastTarget = false;

            Show(titleGroup, st == GameState.Title, dt, 3f);
            Show(pauseGroup, st == GameState.Paused, dt, 8f);
            Show(deathGroup, st == GameState.Dead, dt, 1.5f);
            Show(victoryGroup, st == GameState.Victory, dt, 1.2f);
            gameplayGroup.alpha = Mathf.MoveTowards(gameplayGroup.alpha, (st == GameState.Playing || st == GameState.Paused) ? 1f : 0f, dt * 3f);

            if (st == GameState.Title)
            {
                pressStart.alpha = 0.45f + 0.45f * Mathf.Sin(Time.unscaledTime * 3f);
            }
            if (st == GameState.Paused) pauseTime.text = "TIME  " + FormatTime(gm.PlayTime) + "     GUARDIANS SLAIN  " + gm.Kills;

            UpdateHealth(dt);
            UpdateKey();
            UpdateEncounter(dt);
            UpdateBoss(dt);
            UpdatePrompt(dt);
            UpdateVignette(dt);
            UpdateEnemyBars();

            if (st == GameState.Playing) playTimeVisible += dt;
            if (st == GameState.Paused) hintGroup.alpha = 0f; // the pause screen has its own controls line
            else hintGroup.alpha = Mathf.MoveTowards(hintGroup.alpha, playTimeVisible < 28f ? 1f : 0f, dt * 0.6f);

            objectivePulse = Mathf.MoveTowards(objectivePulse, 0f, dt * 1.4f);
            objectiveRt.localScale = Vector3.one * (1f + 0.06f * objectivePulse * objectivePulse);
            objectiveText.color = Color.Lerp(UIKit.Parchment, UIKit.Gold, objectivePulse);
        }

        void OnStateChanged(GameState st)
        {
            lastState = st;
            var es = EventSystem.current;
            GameObject sel = null;
            if (st == GameState.Title) sel = titleBtn.gameObject;
            if (st == GameState.Paused) sel = pauseResume.gameObject;
            if (st == GameState.Dead)
            {
                bool cp = GameManager.CheckpointUnlocked;
                deathRetry.gameObject.SetActive(cp);
                sel = cp ? deathRetry.gameObject : deathRestart.gameObject;
            }
            if (st == GameState.Victory)
            {
                sel = victoryAgain.gameObject;
                victoryStats.text = "Time  <b>" + FormatTime(gm.PlayTime) + "</b>\nGuardians slain  <b>" + gm.Kills + "</b>\nDamage taken  <b>" + Mathf.RoundToInt(gm.DamageTaken) + "</b>";
                victoryRating.text = gm.PlayTime < 300f ? "ESCAPED IN UNDER FIVE MINUTES" : "THE DUNGEON IS BEHIND YOU";
            }
            if (es != null) es.SetSelectedGameObject(sel);
        }

        static string FormatTime(float s)
        {
            int m = Mathf.FloorToInt(s / 60f);
            int sec = Mathf.FloorToInt(s % 60f);
            return m.ToString("00") + ":" + sec.ToString("00");
        }

        void UpdateHealth(float dt)
        {
            var p = gm.Player;
            if (p == null) return;
            float f = p.health.Fraction;
            shownHp = Mathf.MoveTowards(shownHp, f, dt * 2.5f);
            if (f > ghostHp) ghostHp = f;
            ghostDelay -= dt;
            if (ghostDelay <= 0f) ghostHp = Mathf.MoveTowards(ghostHp, shownHp, dt * 0.6f);
            hpFill.fillAmount = shownHp;
            hpGhost.fillAmount = Mathf.Max(ghostHp, shownHp);
            Color full = new Color(0.78f, 0.12f, 0.1f), low = new Color(1f, 0.25f, 0.08f);
            hpFill.color = f < 0.3f ? Color.Lerp(low, full, 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 8f)) : full;
            hpText.text = Mathf.CeilToInt(p.health.current) + " / " + Mathf.RoundToInt(p.health.max);
        }

        void UpdateKey()
        {
            bool has = gm.HasKey;
            keyIconImage.color = has ? Color.white : new Color(0.22f, 0.22f, 0.25f, 0.7f);
            keyBorder.color = has ? new Color(UIKit.Gold.r, UIKit.Gold.g, UIKit.Gold.b, 0.9f) : new Color(0.5f, 0.5f, 0.5f, 0.45f);
            keyStatus.text = gm.DoorOpened ? "USED" : (has ? "IN HAND" : "NOT FOUND");
            keyStatus.color = has ? UIKit.Gold : new Color(0.7f, 0.7f, 0.7f);
        }

        void UpdateEncounter(float dt)
        {
            bool show = gm.EncounterStarted && (!gm.EncounterCleared || encounterAlpha > 0f);
            if (gm.EncounterCleared && !encounterHideScheduled) { encounterHideScheduled = true; StartCoroutine(HideEncounterLater()); }
            float target = gm.EncounterStarted && !encounterHideScheduled ? 1f : (encounterHideScheduled ? encounterAlpha : 0f);
            encounterGroup.alpha = Mathf.MoveTowards(encounterGroup.alpha, target, dt * 3f);
            if (!show && encounterGroup.alpha <= 0f) return;
            encWave.text = gm.EncounterCleared ? "ALL WAVES DEFEATED" : "WAVE " + gm.EncounterWave + " / " + gm.EncounterWaves;
            encRemaining.text = gm.EncounterCleared ? "CLEARED" : gm.EncounterRemaining + " REMAINING";
            encRemaining.color = gm.EncounterCleared ? new Color(0.5f, 0.9f, 1f) : Color.white;
            for (int i = 0; i < encPips.Length; i++)
            {
                bool alive = i < gm.EncounterRemaining;
                encPips[i].sprite = UIKit.Diamond(48, !alive);
                encPips[i].color = alive ? UIKit.Blood : new Color(0.6f, 0.55f, 0.5f, 0.6f);
            }
        }

        IEnumerator HideEncounterLater()
        {
            encounterAlpha = 1f;
            yield return new WaitForSecondsRealtime(4f);
            encounterAlpha = 0f;
        }

        void UpdateBoss(float dt)
        {
            var b = gm.ActiveBoss;
            bool show = b != null && !b.IsDead && gm.State == GameState.Playing;
            bossGroup.alpha = Mathf.MoveTowards(bossGroup.alpha, show ? 1f : 0f, dt * 2.5f);
            if (b != null) { bossFill.fillAmount = b.health.Fraction; bossName.text = b.displayName.ToUpper(); }
        }

        void UpdatePrompt(float dt)
        {
            var p = gm.Player;
            var it = p != null && gm.State == GameState.Playing ? p.CurrentInteractable : null;
            if (it != null)
            {
                string key = InputHub.UsingGamepad ? "(Y)" : "[E]";
                promptText.text = "<color=#FFCC6B><b>" + key + "</b></color>  " + it.Prompt;
            }
            promptGroup.alpha = Mathf.MoveTowards(promptGroup.alpha, it != null ? 1f : 0f, dt * 6f);
        }

        void UpdateVignette(float dt)
        {
            damageFlash = Mathf.MoveTowards(damageFlash, 0f, dt * 1.6f);
            float low = 0f;
            var p = gm.Player;
            if (p != null && !p.IsDead && gm.State == GameState.Playing)
            {
                float f = p.health.Fraction;
                if (f < 0.3f) low = (0.3f - f) / 0.3f * (0.35f + 0.15f * Mathf.Sin(Time.unscaledTime * 5f));
            }
            vignette.color = new Color(0.75f, 0.03f, 0.02f, Mathf.Clamp01(damageFlash * 0.8f + low));
        }

        void UpdateEnemyBars()
        {
            int used = 0;
            var cam = gm.Cam != null ? gm.Cam.GetComponent<Camera>() : Camera.main;
            if (cam != null && gm.State == GameState.Playing)
            {
                foreach (var e in gm.Enemies)
                {
                    if (used >= enemyBars.Count) break;
                    if (e == null || e.IsDead || e.isBoss || e.health.current >= e.health.max) continue;
                    Vector3 head = e.transform.position + Vector3.up * (2.15f * e.transform.localScale.y);
                    if (Vector3.Distance(cam.transform.position, head) > 22f) continue;
                    Vector3 sp = cam.WorldToScreenPoint(head);
                    if (sp.z < 0.5f) continue;
                    Vector2 local;
                    RectTransformUtility.ScreenPointToLocalPointInRectangle(root, sp, null, out local);
                    var bar = enemyBars[used];
                    bar.gameObject.SetActive(true);
                    bar.anchoredPosition = local;
                    enemyBarFills[used].fillAmount = e.health.Fraction;
                    used++;
                }
            }
            for (int i = used; i < enemyBars.Count; i++) if (enemyBars[i].gameObject.activeSelf) enemyBars[i].gameObject.SetActive(false);
        }
    }
}
