using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace WordDefense
{
    /// <summary>Builds the whole UI in code (uGUI + TextMeshPro) and keeps it in sync with the game every frame.</summary>
    public partial class UIRoot : MonoBehaviour
    {
        public static UIRoot Instance;
        GameManager gm;
        public Canvas Canvas;
        RectTransform root, tagLayer, tintLayer, hudLayer, fxLayer, screenLayer;
        CanvasGroup hudGroup;
        const float Margin = 48f;

        public static void Build(GameManager gm)
        {
            var go = new GameObject("UI");
            go.layer = 5;
            var ui = go.AddComponent<UIRoot>();
            ui.Init(gm);
        }

        void Init(GameManager g)
        {
            Instance = this;
            gm = g;
            UIKit.Latin = gm.fontLatin;
            UIKit.LatinItalic = gm.fontLatinItalic;
            UIKit.LatinBoldItalic = gm.fontLatinBoldItalic;
            UIKit.Song = gm.fontSong;
            UIKit.SongBold = gm.fontSongBold;
            UIKit.SongBlack = gm.fontSongBlack;
            foreach (var f in new[] { UIKit.Latin, UIKit.LatinItalic, UIKit.LatinBoldItalic, UIKit.Song, UIKit.SongBold, UIKit.SongBlack })
            {
                if (f == null) continue;
                MaterialReferenceManager.AddFontAsset(f);
                if (gm.fontHalos != null) UIKit.RegisterHalo(f, gm.fontHalos.FirstOrDefault(m => m != null && m.name == f.name + " Halo"));
            }
            if (EventSystem.current == null)
                new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
            if (gm.GetComponent<InputRouter>() == null) gm.gameObject.AddComponent<InputRouter>();

            Canvas = gameObject.AddComponent<Canvas>();
            Canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            Canvas.sortingOrder = 10;
            var scaler = gameObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            gameObject.AddComponent<GraphicRaycaster>();
            root = (RectTransform)transform;

            tagLayer = UIKit.Stretch(root, "Tags");
            tintLayer = UIKit.Stretch(root, "ScreenTint");   // frost / damage tints: over the world, under the HUD
            hudLayer = UIKit.Stretch(root, "HUD");
            hudGroup = hudLayer.gameObject.AddComponent<CanvasGroup>();
            hudGroup.alpha = 0f;
            fxLayer = UIKit.Stretch(root, "Feedback");
            screenLayer = UIKit.Stretch(root, "Screens");

            BuildTints();
            BuildCastle();
            BuildWave();
            BuildScore();
            BuildTray();
            BuildSkill();
            BuildBossStrip();
            BuildBanner();
            BuildHint();
            BuildScreens();

            gm.OnFeedback += OnFeedback;
            gm.OnStateChanged += s => RefreshScreens();
            RefreshScreens();
        }

        void OnDestroy()
        {
            if (gm != null) gm.OnFeedback -= OnFeedback;
            if (Instance == this) Instance = null;
        }

        bool FirstGame { get { return gm != null && gm.Memory != null && gm.Memory.Games == 0; } }

        void Update()
        {
            float dt = UIKit.Dt;
            bool inGame = gm.State == GameState.Playing || gm.State == GameState.Paused;
            bool result = gm.State == GameState.Victory || gm.State == GameState.Defeat;
            hudGroup.alpha = UIKit.Smooth(hudGroup.alpha, inGame ? 1f : 0f, 8f, dt);
            hudGroup.blocksRaycasts = inGame;
            if (gm.Deck != null && (inGame || result))
            {
                UpdateCastle(dt);
                UpdateWave(dt);
                UpdateScore(dt);
                UpdateTray(dt);
                UpdateSkill(dt);
                UpdateBossStrip(dt);
                UpdateTints(dt);
            }
            UpdateBanner(dt);
            UpdateHint(dt);
            UpdateFloaters(dt);
            UpdateScreens(dt);
            // transient feedback never shows through the result screens
            if (result) { bannerT = -1f; hintUntil = -1f; }
            fxLayer.gameObject.SetActive(!result);
        }

        void LateUpdate()
        {
            UpdateTags(UIKit.Dt);
        }

        // ------------------------------------------------------------ screen <-> canvas
        public Vector2 ToCanvas(Vector3 world, out bool visible)
        {
            var cam = gm.cam;
            Vector3 sp = cam.WorldToScreenPoint(world);
            visible = sp.z > 0f;
            Vector2 local;
            RectTransformUtility.ScreenPointToLocalPointInRectangle(root, sp, null, out local);
            return local;
        }

        public Vector2 ScreenOf(RectTransform rt)
        {
            return RectTransformUtility.WorldToScreenPoint(null, rt.TransformPoint(rt.rect.center));
        }

        static Image HaloIcon(Transform parent, string name, string icon, Color color, Vector2 anchor, Vector2 pos, float size)
        {
            UIKit.Img(parent, name + "Halo", UIKit.IconHalo(icon, 128), UIKit.A(UIKit.Paper, 0.85f), anchor, pos, new Vector2(size, size));
            return UIKit.Img(parent, name, UIKit.Icon(icon, 128), color, anchor, pos, new Vector2(size, size));
        }

        // ============================================================ castle (top left): icon, bar, number
        RectTransform castleRoot;
        Image castleIcon, hpFill, hpGhost;
        TextMeshProUGUI hpValue;
        float hpShown = 1f, hpGhostV = 1f, hpShake, hpFlash;
        int hpLast = -1;
        const float HpBarW = 240f, HpBarH = 6f;

        void BuildCastle()
        {
            castleRoot = UIKit.Rect(hudLayer, "Castle", new Vector2(0f, 1f), new Vector2(Margin, -Margin - 4f), new Vector2(420f, 48f), new Vector2(0f, 0.5f));
            castleIcon = HaloIcon(castleRoot, "Icon", "castle", UIKit.Ink, new Vector2(0f, 0.5f), new Vector2(20f, 2f), 40f);
            var track = UIKit.Img(castleRoot, "Track", UIKit.Rounded(3), UIKit.A(UIKit.Paper, 0.94f), new Vector2(0f, 0.5f), new Vector2(58f + HpBarW / 2f, 0f), new Vector2(HpBarW, HpBarH), true);
            UIKit.Fill(track.rectTransform, "Rule", UIKit.Rounded(3, 1f), UIKit.InkA(0.2f));
            hpGhost = UIKit.Img(track.rectTransform, "Ghost", UIKit.Rounded(3), UIKit.A(UIKit.RedPen, 0.5f), new Vector2(0f, 0.5f), Vector2.zero, new Vector2(HpBarW, HpBarH), true);
            hpGhost.rectTransform.pivot = new Vector2(0f, 0.5f);
            hpFill = UIKit.Img(track.rectTransform, "Fill", UIKit.Rounded(3), UIKit.Ink, new Vector2(0f, 0.5f), Vector2.zero, new Vector2(HpBarW, HpBarH), true);
            hpFill.rectTransform.pivot = new Vector2(0f, 0.5f);
            hpValue = UIKit.Halo(UIKit.Text(castleRoot, "Value", "100", 34f, UIKit.Ink, TextAlignmentOptions.Left,
                new Vector2(0f, 0.5f), new Vector2(58f + HpBarW + 14f, 1f), new Vector2(120f, 44f), UIKit.Latin, new Vector2(0f, 0.5f)));
        }

        void UpdateCastle(float dt)
        {
            if (gm.castle == null) return;
            int hp = Mathf.Max(0, gm.castle.Hp);
            float f = hp / (float)gm.castle.MaxHp;
            if (hpLast != hp)
            {
                if (hpLast > hp) { hpShake = 1f; hpFlash = 1f; }
                hpLast = hp;
                hpValue.text = hp.ToString();
            }
            hpShown = UIKit.Smooth(hpShown, f, 14f, dt);
            if (Time.unscaledTime - gm.castle.LastHitTime > 0.6f || hpGhostV < hpShown) hpGhostV = UIKit.Smooth(hpGhostV, hpShown, 4f, dt);
            bool low = f <= 0.3f && f > 0f;
            float pulse = low ? 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 6f) : 0f;
            Color c = low ? Color.Lerp(UIKit.RedPen, UIKit.Ink, pulse * 0.35f) : UIKit.Ink;
            hpFlash = Mathf.MoveTowards(hpFlash, 0f, dt * 2.5f);
            hpFill.color = c;
            castleIcon.color = low ? UIKit.RedPen : Color.Lerp(UIKit.Ink, UIKit.RedPen, hpFlash);
            hpValue.color = low ? UIKit.RedPen : Color.Lerp(UIKit.Ink, UIKit.RedPen, hpFlash);
            hpFill.rectTransform.sizeDelta = new Vector2(HpBarW * hpShown, HpBarH);
            hpGhost.rectTransform.sizeDelta = new Vector2(HpBarW * hpGhostV, HpBarH);
            hpFill.enabled = f > 0.001f;
            hpShake = Mathf.MoveTowards(hpShake, 0f, dt * 3f);
            castleRoot.anchoredPosition = new Vector2(Margin, -Margin - 4f) + (hpShake > 0f ? Random.insideUnitCircle * 6f * hpShake : Vector2.zero);
        }

        // ============================================================ wave (top centre): 第 N 波 and one mark per wave
        RectTransform waveRoot;
        CanvasGroup waveGroup;
        TextMeshProUGUI waveTitle;
        readonly List<Image> waveMarks = new List<Image>();
        int waveShown = -1;

        void BuildWave()
        {
            waveRoot = UIKit.Rect(hudLayer, "Wave", new Vector2(0.5f, 1f), new Vector2(0f, -Margin - 4f), new Vector2(360f, 80f), new Vector2(0.5f, 0.5f));
            waveGroup = waveRoot.gameObject.AddComponent<CanvasGroup>();
            waveGroup.blocksRaycasts = false;
            waveTitle = UIKit.Halo(UIKit.Text(waveRoot, "Title", "第 1 波", 30f, UIKit.Ink, TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), new Vector2(0f, 6f), new Vector2(360f, 40f), UIKit.SongBold));
            int n = GameManager.WaveCount + 1;
            const float step = 34f;
            for (int i = 0; i < n; i++)
            {
                float x = -(n - 1) * step / 2f + i * step;
                if (i == n - 1)
                {
                    waveMarks.Add(HaloIcon(waveRoot, "Crown", "crown", UIKit.InkA(0.3f), new Vector2(0.5f, 0.5f), new Vector2(x, -26f), 22f));
                    continue;
                }
                waveMarks.Add(UIKit.Img(waveRoot, "Mark" + i, UIKit.Rounded(3), UIKit.InkA(0.3f), new Vector2(0.5f, 0.5f), new Vector2(x, -26f), new Vector2(24f, 5f), true));
            }
        }

        void UpdateWave(float dt)
        {
            bool bossPhase = gm.Phase == GamePhase.BossIntro || gm.Phase == GamePhase.Boss || gm.Wave > GameManager.WaveCount;
            waveGroup.alpha = UIKit.Smooth(waveGroup.alpha, bossPhase ? 0f : 1f, 8f, dt);   // the Boss sentence takes this place
            int wave = Mathf.Clamp(gm.Wave, 1, GameManager.WaveCount + 1);
            if (wave != waveShown)
            {
                waveShown = wave;
                waveTitle.text = wave > GameManager.WaveCount ? "Boss" : "第 " + wave + " 波";
            }
            for (int i = 0; i < waveMarks.Count; i++)
            {
                int w = i + 1;
                waveMarks[i].color = w <= wave ? UIKit.Ink : UIKit.InkA(0.28f);
            }
        }

        // ============================================================ score and combo (top right), pause
        TextMeshProUGUI scoreText, comboText;
        float scoreShown, comboPop;
        int comboLast = -1;

        void BuildScore()
        {
            scoreText = UIKit.Halo(UIKit.Text(hudLayer, "Score", "0", 40f, UIKit.Ink, TextAlignmentOptions.Right,
                new Vector2(1f, 1f), new Vector2(-(Margin + 80f), -Margin - 4f), new Vector2(360f, 52f), UIKit.Latin, new Vector2(1f, 0.5f)));
            comboText = UIKit.Halo(UIKit.Text(hudLayer, "Combo", "", 24f, UIKit.Ink, TextAlignmentOptions.Right,
                new Vector2(1f, 1f), new Vector2(-(Margin + 80f), -Margin - 44f), new Vector2(300f, 34f), UIKit.SongBold, new Vector2(1f, 0.5f)));

            var pause = UIKit.Rect(hudLayer, "PauseButton", new Vector2(1f, 1f), new Vector2(-Margin - 22f, -Margin - 4f), new Vector2(60f, 60f));
            var hit = UIKit.Fill(pause, "Hit", UIKit.Circle(128), UIKit.A(UIKit.Paper, 0f), false);
            hit.raycastTarget = true;
            HaloIcon(pause, "Icon", "pause", UIKit.Ink, new Vector2(0.5f, 0.5f), Vector2.zero, 30f);
            var b = pause.gameObject.AddComponent<Button>();
            b.targetGraphic = hit;
            var cb = b.colors;
            cb.normalColor = new Color(1f, 1f, 1f, 0f);
            cb.highlightedColor = new Color(1f, 1f, 1f, 0.85f);
            cb.pressedColor = new Color(0.9f, 0.92f, 0.96f, 0.95f);
            cb.selectedColor = new Color(1f, 1f, 1f, 0f);
            cb.colorMultiplier = 1f;
            b.colors = cb;
            hit.color = UIKit.Paper;
            b.navigation = new Navigation { mode = Navigation.Mode.None };
            b.onClick.AddListener(() => gm.TogglePause());
        }

        void UpdateScore(float dt)
        {
            scoreShown = Mathf.Abs(scoreShown - gm.Score) < 1f ? gm.Score : UIKit.Smooth(scoreShown, gm.Score, 10f, dt);
            string s = "<mspace=0.55em>" + Mathf.RoundToInt(scoreShown).ToString("N0") + "</mspace>";
            if (scoreText.text != s) scoreText.text = s;
            if (gm.Combo != comboLast)
            {
                if (gm.Combo > comboLast) comboPop = 1f;
                comboLast = gm.Combo;
                comboText.text = gm.Combo >= 2 ? UIKit.TagHalo(UIKit.Latin, gm.Combo.ToString()) + " 连击" : "";
            }
            comboPop = Mathf.MoveTowards(comboPop, 0f, dt * 3f);
            comboText.transform.localScale = Vector3.one * (1f + comboPop * 0.18f);
        }

        // ============================================================ screen tints
        Image frostTint, damageTint;
        float damagePulse;

        void BuildTints()
        {
            frostTint = UIKit.Fill(tintLayer, "Frost", UIKit.Vignette(), UIKit.A(UIKit.Frost, 0f), false);
            damageTint = UIKit.Fill(tintLayer, "Damage", UIKit.EdgeGlow(), UIKit.A(UIKit.RedPen, 0f), false);
        }

        void UpdateTints(float dt)
        {
            float target = gm.SlowTimer > 0f ? 0.22f * Mathf.Clamp01(gm.SlowTimer / 1.2f) : 0f;
            var c = frostTint.color;
            c.a = UIKit.Smooth(c.a, target, 6f, dt);
            frostTint.color = c;
            damagePulse = Mathf.MoveTowards(damagePulse, 0f, dt * 1.6f);
            float low = gm.castle != null && gm.castle.Hp <= 30 && gm.castle.Hp > 0 && gm.State == GameState.Playing ? 0.2f + 0.1f * Mathf.Sin(Time.unscaledTime * 4f) : 0f;
            damageTint.color = UIKit.A(UIKit.RedPen, Mathf.Max(damagePulse * 0.7f, low));
        }

        // ============================================================ banner: 第 N 波 / Boss
        RectTransform banner;
        TextMeshProUGUI bannerTitle, bannerSub;
        CanvasGroup bannerGroup;
        float bannerT = -1f, bannerDur = 1.8f;

        void BuildBanner()
        {
            banner = UIKit.Rect(fxLayer, "Banner", new Vector2(0.5f, 0.5f), new Vector2(0f, 170f), new Vector2(1400f, 240f));
            bannerGroup = banner.gameObject.AddComponent<CanvasGroup>();
            bannerGroup.alpha = 0f;
            bannerGroup.blocksRaycasts = false;
            bannerTitle = UIKit.Halo(UIKit.Text(banner, "Title", "", 96f, UIKit.Ink, TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), new Vector2(0f, 26f), new Vector2(1400f, 130f), UIKit.SongBlack));
            bannerSub = UIKit.Halo(UIKit.Text(banner, "Sub", "", 30f, UIKit.Ink, TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), new Vector2(0f, -58f), new Vector2(1400f, 44f), UIKit.SongBold));
        }

        public void ShowBanner(string title, string sub = "", float dur = 1.8f)
        {
            bannerTitle.text = title;
            bannerSub.text = sub ?? "";
            bannerT = 0f;
            bannerDur = dur;
        }

        void UpdateBanner(float dt)
        {
            if (bannerT < 0f) { bannerGroup.alpha = 0f; return; }
            bannerT += Time.deltaTime > 0f ? Time.deltaTime : dt;
            float inK = Mathf.Clamp01(bannerT / 0.3f), outK = Mathf.Clamp01((bannerT - bannerDur) / 0.35f);
            bannerGroup.alpha = inK * (1f - outK);
            banner.localScale = Vector3.one * Mathf.Lerp(1.05f, 1f, Ease.OutCubic(inK));
            if (bannerT > bannerDur + 0.4f) bannerT = -1f;
        }

        // ============================================================ hint: one plain sentence where a new player would get stuck
        RectTransform hintRt;
        TextMeshProUGUI hintText;
        CanvasGroup hintGroup;
        float hintUntil = -1f;
        bool hintIntroActive;
        static bool hintSkillShown, hintVividShown;

        void BuildHint()
        {
            hintRt = UIKit.Rect(fxLayer, "Hint", new Vector2(0.5f, 0f), new Vector2(0f, 196f), new Vector2(1400f, 44f));
            hintGroup = hintRt.gameObject.AddComponent<CanvasGroup>();
            hintGroup.alpha = 0f;
            hintGroup.blocksRaycasts = false;
            hintText = UIKit.Halo(UIKit.Text(hintRt, "Text", "", 28f, UIKit.Ink, TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1400f, 44f), UIKit.SongBold));
        }

        /// <summary>Shows a hint above the shells, or next to the frost dial when nearDial is set.</summary>
        void ShowHint(string text, float seconds, bool nearDial = false)
        {
            hintText.text = text;
            if (nearDial)
            {
                hintRt.anchorMin = hintRt.anchorMax = new Vector2(0f, 0f);
                hintRt.pivot = new Vector2(0f, 0.5f);
                hintRt.anchoredPosition = new Vector2(Margin, 214f);
                hintText.alignment = TextAlignmentOptions.Left;
            }
            else
            {
                hintRt.anchorMin = hintRt.anchorMax = new Vector2(0.5f, 0f);
                hintRt.pivot = new Vector2(0.5f, 0.5f);
                hintRt.anchoredPosition = new Vector2(0f, 196f);
                hintText.alignment = TextAlignmentOptions.Center;
            }
            hintUntil = Time.unscaledTime + seconds;
        }

        void UpdateHint(float dt)
        {
            bool on = Time.unscaledTime < hintUntil && gm.State == GameState.Playing;
            hintGroup.alpha = UIKit.Smooth(hintGroup.alpha, on ? 1f : 0f, on ? 10f : 6f, dt);
            if (!hintVividShown && gm.State == GameState.Playing && gm.Tray != null && gm.Tray.Slots.Any(s => s != null && s.Vivid))
            {
                hintVividShown = true;
                ShowHint("点击金色释义，即可自动追踪目标", 6f);
            }
        }

        // ============================================================ feedback events
        void OnFeedback(Feedback f)
        {
            switch (f.Kind)
            {
                case FeedbackKind.WaveStart:
                    ShowBanner("第 " + f.Value + " 波");
                    if (f.Value == 1 && FirstGame) { ShowHint("选一个释义，再点它对应的单词", 40f); hintIntroActive = true; }
                    break;
                case FeedbackKind.BossIncoming:
                    ShowBanner("Boss", "按顺序击中句中的关键词", 3f);
                    break;
                case FeedbackKind.Correct:
                    if (hintIntroActive) { hintIntroActive = false; hintUntil = -1f; }
                    Floater(f.World, "+" + f.Value, UIKit.Ink, 34f, UIKit.Latin, new Vector2(0f, 58f), FloaterStyle.Plain);
                    Floater(f.World, UIKit.TagHalo(UIKit.Latin, f.Word.Word) + "  " + f.Word.Gloss, UIKit.Ink, 28f, UIKit.SongBold, new Vector2(0f, 12f), FloaterStyle.Plain, 1.5f);
                    break;
                case FeedbackKind.Wrong:
                    damagePulse = Mathf.Max(damagePulse, 0.25f);
                    MarkFloater(f.World, new Vector2(0f, -54f));
                    break;
                case FeedbackKind.OrderWrong:
                    damagePulse = Mathf.Max(damagePulse, 0.25f);
                    Floater(f.World, "顺序不对", UIKit.RedPen, 28f, UIKit.SongBold, new Vector2(0f, -60f), FloaterStyle.Plain);
                    break;
                case FeedbackKind.Leak:
                    damagePulse = 1f;
                    if (gm.castle != null)
                    {
                        Floater(gm.castle.Gate + Vector3.up * 3f, "−" + f.Value, UIKit.RedPen, 44f, UIKit.Latin, new Vector2(0f, 40f), FloaterStyle.Plain);
                        if (f.Word != null)
                            Floater(gm.castle.Gate + Vector3.up * 3f, UIKit.TagHalo(UIKit.Latin, f.Word.Word) + "  " + f.Word.Gloss, UIKit.RedPen, 28f, UIKit.SongBold, new Vector2(0f, -10f), FloaterStyle.Plain, 2.4f);
                    }
                    break;
                case FeedbackKind.Jammed:
                    trayShake = 1f;
                    break;
                case FeedbackKind.NeedShell:
                    trayNudge = 1f;
                    ShowHint("先选一个释义", 1.6f);
                    break;
                case FeedbackKind.SkillReady:
                    skillPop = 1f;
                    if (!hintSkillShown) { hintSkillShown = true; ShowHint("按空格，让所有敌人减速", 6f, true); }
                    break;
                case FeedbackKind.VividNew:
                    Floater(f.World, "★ 记忆深刻", UIKit.GoldInk, 28f, UIKit.SongBold, new Vector2(0f, 104f), FloaterStyle.Plain);
                    Audio.Play(Sfx.Id.Vivid, 0.7f);
                    break;
                case FeedbackKind.BossBreak:
                    bossPop = 1f;
                    break;
            }
        }

        // ============================================================ floaters
        enum FloaterStyle { Plain }

        class FloaterItem
        {
            public RectTransform rt;
            public CanvasGroup group;
            public Vector3 world;
            public Vector2 offset;
            public float t, dur;
        }
        readonly List<FloaterItem> floaters = new List<FloaterItem>();

        void Floater(Vector3 world, string text, Color color, float size, TMP_FontAsset font, Vector2 offset, FloaterStyle style, float dur = 0f)
        {
            var rt = UIKit.Rect(fxLayer, "Floater", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(600f, size + 24f));
            var g = rt.gameObject.AddComponent<CanvasGroup>();
            g.blocksRaycasts = false;
            var t = UIKit.Text(rt, "T", text, size, color, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0f, 1f), new Vector2(600f, size + 24f), font);
            UIKit.Halo(t);   // feedback is type, never paper: paper is only for things you can click
            floaters.Add(new FloaterItem { rt = rt, group = g, world = world, offset = offset, dur = dur > 0f ? dur : 1.1f });
        }

        /// <summary>A red-pen cross where a wrong shell bounced off.</summary>
        void MarkFloater(Vector3 world, Vector2 offset)
        {
            var rt = UIKit.Rect(fxLayer, "Mark", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(64f, 64f));
            var g = rt.gameObject.AddComponent<CanvasGroup>();
            g.blocksRaycasts = false;
            HaloIcon(rt, "Cross", "cross", UIKit.RedPen, new Vector2(0.5f, 0.5f), Vector2.zero, 52f);
            floaters.Add(new FloaterItem { rt = rt, group = g, world = world, offset = offset, dur = 0.9f });
        }

        void UpdateFloaters(float dt)
        {
            for (int i = floaters.Count - 1; i >= 0; i--)
            {
                var f = floaters[i];
                f.t += dt;
                bool vis;
                Vector2 p = ToCanvas(f.world, out vis);
                float k = f.t / f.dur;
                Vector2 pos = p + new Vector2(0f, Ease.OutCubic(Mathf.Clamp01(k)) * 40f);
                float top = root.rect.height * 0.5f - 210f, right = root.rect.width * 0.5f - 300f;
                pos.y = Mathf.Min(pos.y, top - 80f);   // near the top the whole stack moves below the HUD, keeping its spacing
                pos += f.offset;
                pos.x = Mathf.Clamp(pos.x, -right, right);
                f.rt.anchoredPosition = pos;
                f.rt.localScale = Vector3.one * (k < 0.12f ? Mathf.Lerp(0.85f, 1f, Ease.OutCubic(k / 0.12f)) : 1f);
                f.group.alpha = vis ? Mathf.Clamp01((1f - k) * 3f) : 0f;
                if (k >= 1f) { Destroy(f.rt.gameObject); floaters.RemoveAt(i); }
            }
        }
    }
}
