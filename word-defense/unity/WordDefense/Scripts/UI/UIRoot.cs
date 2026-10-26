using System.Collections.Generic;
using System.Linq;
using System.Text;
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
            UIKit.FontEn = gm.fontEn;
            UIKit.FontZh = gm.fontZh;
            UIKit.FontZhBold = gm.fontZhBold;
            UIKit.FontZhBlack = gm.fontZhBlack ?? gm.fontZhBold;
            foreach (var f in new[] { gm.fontEn, gm.fontZh, gm.fontZhBold, gm.fontZhBlack })
                if (f != null) MaterialReferenceManager.AddFontAsset(f);
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
            hudGroup.alpha = 0f;   // fades in when a game starts; never flashes over the title screen
            fxLayer = UIKit.Stretch(root, "Feedback");
            screenLayer = UIKit.Stretch(root, "Screens");

            BuildFrostOverlay();
            BuildHp();
            BuildWave();
            BuildScore();
            BuildTray();
            BuildSkill();
            BuildMemory();
            BuildBossPanel();
            BuildBanner();
            BuildToast();
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

        void Update()
        {
            float dt = UIKit.Dt;
            bool inGame = gm.State == GameState.Playing || gm.State == GameState.Paused;
            hudGroup.alpha = UIKit.Smooth(hudGroup.alpha, inGame ? 1f : 0f, 8f, dt);
            hudGroup.blocksRaycasts = inGame;
            if (gm.Deck != null && (inGame || gm.State == GameState.Victory || gm.State == GameState.Defeat))
            {
                UpdateHp(dt);
                UpdateWave(dt);
                UpdateScore(dt);
                UpdateTray(dt);
                UpdateSkill(dt);
                UpdateMemory(dt);
                UpdateBossPanel(dt);
                UpdateFrostOverlay(dt);
            }
            UpdateBanner(dt);
            UpdateToast(dt);
            UpdateFloaters(dt);
            UpdateScreens(dt);
            // transient feedback never shows through the result screens
            bool result = gm.State == GameState.Victory || gm.State == GameState.Defeat;
            if (result) { toastT = -1f; bannerT = -1f; }
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

        // ============================================================ castle HP
        RectTransform hpCard;
        Image hpIcon, hpFill, hpGhost, hpFlash;
        TextMeshProUGUI hpValue;
        float hpShown = 1f, hpGhostV = 1f, hpShake;
        int hpLast = -1;
        const float HpBarW = 300f;

        void BuildHp()
        {
            hpCard = UIKit.Panel(hudLayer, "CastleCard", new Vector2(0f, 1f), new Vector2(36f, -30f), new Vector2(430f, 104f), 22, null, true, new Vector2(0f, 1f));
            hpIcon = UIKit.Img(hpCard, "Icon", UIKit.Icon("castle"), UIKit.Mint, new Vector2(0f, 0.5f), new Vector2(54f, 6f), new Vector2(56f, 56f));
            UIKit.Text(hpCard, "Label", "城堡耐久", 20f, UIKit.TextLow, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(194f, -34f), new Vector2(200f, 26f), UIKit.FontZh);
            hpValue = UIKit.Text(hpCard, "Value", "100", 38f, UIKit.TextHi, TextAlignmentOptions.Right, new Vector2(1f, 1f), new Vector2(-106f, -36f), new Vector2(170f, 44f), UIKit.FontEn, FontStyles.Normal);
            var track = UIKit.Img(hpCard, "Track", UIKit.Rounded(7), new Color(1f, 1f, 1f, 0.09f), new Vector2(0f, 0f), new Vector2(94f + HpBarW / 2f, 28f), new Vector2(HpBarW, 14f), true);
            hpGhost = UIKit.Img(track.rectTransform, "Ghost", UIKit.Rounded(7), new Color(1f, 1f, 1f, 0.55f), new Vector2(0f, 0.5f), Vector2.zero, new Vector2(HpBarW, 14f), true);
            hpGhost.rectTransform.pivot = new Vector2(0f, 0.5f);
            hpFill = UIKit.Img(track.rectTransform, "Fill", UIKit.Rounded(7), UIKit.Mint, new Vector2(0f, 0.5f), Vector2.zero, new Vector2(HpBarW, 14f), true);
            hpFill.rectTransform.pivot = new Vector2(0f, 0.5f);
            for (int i = 1; i < 10; i++)
                UIKit.Img(track.rectTransform, "Tick", UIKit.White(), new Color(0.07f, 0.08f, 0.16f, 0.55f), new Vector2(0f, 0.5f), new Vector2(HpBarW * i / 10f, 0f), new Vector2(2f, 14f));
            hpFlash = UIKit.Fill(hpCard, "Flash", UIKit.Rounded(22), new Color(1f, 0.3f, 0.35f, 0f));
        }

        void UpdateHp(float dt)
        {
            if (gm.castle == null) return;
            float f = gm.castle.Hp / (float)gm.castle.MaxHp;
            if (hpLast != gm.castle.Hp)
            {
                if (hpLast > gm.castle.Hp) { hpShake = 1f; hpFlash.color = new Color(1f, 0.3f, 0.35f, 0.45f); }
                hpLast = gm.castle.Hp;
                hpValue.text = gm.castle.Hp + "<size=22><color=#7F89AA> / " + gm.castle.MaxHp + "</color></size>";
            }
            hpShown = UIKit.Smooth(hpShown, f, 14f, dt);
            if (Time.unscaledTime - gm.castle.LastHitTime > 0.5f || hpGhostV < hpShown) hpGhostV = UIKit.Smooth(hpGhostV, hpShown, 4f, dt);
            Color c = f > 0.6f ? UIKit.Mint : (f > 0.3f ? UIKit.Amber : UIKit.Coral);
            hpFill.color = c;
            hpIcon.color = c;
            hpFill.rectTransform.sizeDelta = new Vector2(Mathf.Max(14f, HpBarW * hpShown), 14f);
            hpGhost.rectTransform.sizeDelta = new Vector2(Mathf.Max(14f, HpBarW * hpGhostV), 14f);
            hpFill.enabled = f > 0.001f;
            hpShake = Mathf.MoveTowards(hpShake, 0f, dt * 3f);
            hpCard.anchoredPosition = new Vector2(36f, -30f) + (hpShake > 0f ? Random.insideUnitCircle * 7f * hpShake : Vector2.zero);
            var fc = hpFlash.color; fc.a = Mathf.MoveTowards(fc.a, 0f, dt * 1.2f); hpFlash.color = fc;
            if (f <= 0.3f && f > 0f) hpIcon.color = Color.Lerp(UIKit.Coral, Color.white, 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 8f));
        }

        // ============================================================ wave + speed
        RectTransform waveCard, speedChip;
        CanvasGroup waveGroup, speedGroup;
        TextMeshProUGUI waveTitle, waveSub, speedText;
        readonly List<Image> waveDots = new List<Image>();
        Image speedArrow;
        float lastSpeedShown = 1f, speedArrowT;
        int waveLast = -1;

        void BuildWave()
        {
            waveCard = UIKit.Panel(hudLayer, "WaveCard", new Vector2(0.5f, 1f), new Vector2(0f, -30f), new Vector2(380f, 112f), 22, null, true, new Vector2(0.5f, 1f));
            waveTitle = UIKit.Text(waveCard, "Title", "第 1 波", 32f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -34f), new Vector2(360f, 40f));
            waveSub = UIKit.Text(waveCard, "Sub", "", 17f, UIKit.TextLow, TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0f, 20f), new Vector2(360f, 22f), UIKit.FontZh);
            for (int i = 0; i < GameManager.WaveCount + 1; i++)
            {
                bool boss = i == GameManager.WaveCount;
                var d = UIKit.Img(waveCard, "Dot" + i, boss ? UIKit.Icon("crown", 64) : UIKit.Circle(32), new Color(1f, 1f, 1f, 0.2f),
                    new Vector2(0.5f, 0f), new Vector2(-64f + i * 32f, 46f), boss ? new Vector2(22f, 22f) : new Vector2(11f, 11f));
                waveDots.Add(d);
            }
            speedChip = UIKit.Panel(hudLayer, "SpeedChip", new Vector2(0.5f, 1f), new Vector2(0f, -154f), new Vector2(200f, 44f), 22, null, true, new Vector2(0.5f, 1f));
            waveGroup = waveCard.gameObject.AddComponent<CanvasGroup>();
            speedGroup = speedChip.gameObject.AddComponent<CanvasGroup>();
            UIKit.Img(speedChip, "Icon", UIKit.Icon("speed", 64), UIKit.Amber, new Vector2(0f, 0.5f), new Vector2(26f, 0f), new Vector2(24f, 24f));
            UIKit.Text(speedChip, "Label", "敌速", 19f, UIKit.TextMid, TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(76f, 0f), new Vector2(60f, 30f), UIKit.FontZh);
            speedText = UIKit.Text(speedChip, "Value", "×1.00", 24f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(140f, 0f), new Vector2(90f, 30f), UIKit.FontEn);
            speedArrow = UIKit.Img(speedChip, "Up", UIKit.Icon("pointer", 32), UIKit.Amber, new Vector2(1f, 0.5f), new Vector2(-18f, 0f), new Vector2(14f, 12f));
            speedArrow.rectTransform.localRotation = Quaternion.Euler(0f, 0f, 180f);
        }

        void UpdateWave(float dt)
        {
            bool bossPhase = gm.Phase == GamePhase.BossIntro || gm.Phase == GamePhase.Boss || gm.Wave > GameManager.WaveCount;
            // during the Boss the sentence panel takes the top of the screen
            waveGroup.alpha = UIKit.Smooth(waveGroup.alpha, bossPhase ? 0f : 1f, 8f, dt);
            speedGroup.alpha = waveGroup.alpha;
            int key = bossPhase ? 99 : gm.Wave;
            if (key != waveLast)
            {
                waveLast = key;
                waveTitle.text = bossPhase ? "<color=#FF5C6C>Boss 战</color>" : "第 " + gm.Wave + " 波<size=20><color=#7F89AA>  / 共 " + GameManager.WaveCount + " 波</color></size>";
            }
            int wave = Mathf.Min(gm.Wave, GameManager.WaveCount + 1);
            for (int i = 0; i < waveDots.Count; i++)
            {
                int w = i + 1;
                Color c;
                if (w < wave) c = UIKit.Mint;
                else if (w == wave) c = i == GameManager.WaveCount ? UIKit.Coral : Color.Lerp(Color.white, UIKit.Amber, 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 5f));
                else c = new Color(1f, 1f, 1f, 0.22f);
                waveDots[i].color = c;
            }
            string sub;
            if (gm.Phase == GamePhase.Break) sub = "准备 · 下一波即将到来";
            else if (bossPhase) sub = gm.Boss != null ? "关键词 " + Mathf.Min(gm.Boss.Current + 1, gm.Boss.Keywords.Count) + " / " + gm.Boss.Keywords.Count : "长句来袭";
            else
            {
                int left = gm.Waves[Mathf.Clamp(gm.Wave - 1, 0, GameManager.WaveCount - 1)].count;
                int alive = gm.Enemies.Count(e => e != null && e.Alive);
                sub = "场上 " + alive + " 个敌人";
            }
            if (waveSub.text != sub) waveSub.text = sub;
            float m = gm.SpeedMultiplier;
            string st = "×" + m.ToString("0.00");
            if (speedText.text != st) speedText.text = st;
            speedText.color = m >= 1.6f ? UIKit.Coral : (m >= 1.3f ? UIKit.Amber : UIKit.TextHi);
            if (m - lastSpeedShown >= 0.05f) { lastSpeedShown = m; speedArrowT = 1.2f; }
            speedArrowT = Mathf.MoveTowards(speedArrowT, 0f, dt);
            speedArrow.color = UIKit.A(UIKit.Amber, Mathf.Clamp01(speedArrowT * 2f));
            speedArrow.rectTransform.anchoredPosition = new Vector2(-18f, (1.2f - speedArrowT) * 6f);
            if (gm.SlowTimer > 0f) { speedText.text = "×" + (m * GameManager.SlowFactor).ToString("0.00"); speedText.color = UIKit.Ice; }
        }

        // ============================================================ score + combo
        RectTransform scoreCard;
        TextMeshProUGUI scoreText, comboText;
        float scoreShown;
        int comboLast = -1;
        float comboPop;

        void BuildScore()
        {
            scoreCard = UIKit.Panel(hudLayer, "ScoreCard", new Vector2(1f, 1f), new Vector2(-122f, -30f), new Vector2(300f, 104f), 22, null, true, new Vector2(1f, 1f));
            UIKit.Text(scoreCard, "Label", "得分", 20f, UIKit.TextLow, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(76f, -32f), new Vector2(110f, 26f), UIKit.FontZh);
            scoreText = UIKit.Text(scoreCard, "Value", "0", 40f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0f, 0f), new Vector2(136f, 34f), new Vector2(230f, 48f), UIKit.FontEn);
            comboText = UIKit.Text(scoreCard, "Combo", "", 22f, UIKit.Amber, TextAlignmentOptions.Right, new Vector2(1f, 1f), new Vector2(-86f, -32f), new Vector2(140f, 28f));
            var pause = UIKit.Rect(hudLayer, "PauseButton", new Vector2(1f, 1f), new Vector2(-66f, -82f), new Vector2(72f, 72f));
            pause.pivot = new Vector2(0.5f, 0.5f);
            pause.anchoredPosition = new Vector2(-70f, -82f);
            UIKit.Img(pause, "Shadow", UIKit.Shadow(36, 12), new Color(0f, 0f, 0f, 0.4f), new Vector2(0.5f, 0.5f), new Vector2(0f, -5f), new Vector2(120f, 120f), true);
            var bg = UIKit.Fill(pause, "Bg", UIKit.Circle(128), UIKit.Glass, false);
            bg.raycastTarget = true;
            UIKit.Fill(pause, "Ring", UIKit.Ring(128, 2f), UIKit.Stroke, false);
            UIKit.Img(pause, "Icon", UIKit.Icon("pause"), UIKit.TextHi, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(36f, 36f));
            var b = pause.gameObject.AddComponent<Button>();
            b.targetGraphic = bg;
            b.navigation = new Navigation { mode = Navigation.Mode.None };
            b.onClick.AddListener(() => gm.TogglePause());
            pause.gameObject.AddComponent<HoverScale>().amount = 1.08f;
        }

        void UpdateScore(float dt)
        {
            scoreShown = Mathf.Abs(scoreShown - gm.Score) < 1f ? gm.Score : UIKit.Smooth(scoreShown, gm.Score, 10f, dt);
            string s = Mathf.RoundToInt(scoreShown).ToString("N0");
            if (scoreText.text != s) scoreText.text = s;
            if (gm.Combo != comboLast)
            {
                if (gm.Combo > comboLast) comboPop = 1f;
                comboLast = gm.Combo;
                comboText.text = gm.Combo >= 2 ? "连击 <font=\"" + (UIKit.FontEn ? UIKit.FontEn.name : "") + "\">×" + gm.Combo + "</font>" : "";
            }
            comboPop = Mathf.MoveTowards(comboPop, 0f, dt * 3f);
            comboText.transform.localScale = Vector3.one * (1f + comboPop * 0.35f);
            comboText.color = gm.Combo >= 5 ? Color.Lerp(UIKit.Amber, UIKit.Coral, 0.4f) : UIKit.Amber;
        }

        // ============================================================ frost overlay
        Image frostOverlay;

        void BuildFrostOverlay()
        {
            frostOverlay = UIKit.Fill(tintLayer, "Frost", UIKit.Vignette(), UIKit.A(UIKit.Ice, 0f), false);
            damageOverlay = UIKit.Fill(tintLayer, "Damage", UIKit.EdgeGlow(), UIKit.A(UIKit.Coral, 0f), false);
        }

        Image damageOverlay;
        float damagePulse;

        void UpdateFrostOverlay(float dt)
        {
            float target = gm.SlowTimer > 0f ? 0.28f * Mathf.Clamp01(gm.SlowTimer / 1.2f) : 0f;
            var c = frostOverlay.color;
            c.a = UIKit.Smooth(c.a, target, 6f, dt);
            frostOverlay.color = c;
            damagePulse = Mathf.MoveTowards(damagePulse, 0f, dt * 1.6f);
            float low = gm.castle != null && gm.castle.Hp <= 30 && gm.castle.Hp > 0 && gm.State == GameState.Playing ? 0.22f + 0.12f * Mathf.Sin(Time.unscaledTime * 4f) : 0f;
            damageOverlay.color = UIKit.A(UIKit.Coral, Mathf.Max(damagePulse * 0.75f, low));
        }

        // ============================================================ banner
        RectTransform banner;
        TextMeshProUGUI bannerTitle, bannerSub;
        Image bannerLineL, bannerLineR;
        CanvasGroup bannerGroup;
        float bannerT = -1f, bannerDur = 2.2f;

        void BuildBanner()
        {
            banner = UIKit.Rect(fxLayer, "Banner", new Vector2(0.5f, 0.62f), Vector2.zero, new Vector2(1200f, 220f));
            bannerGroup = banner.gameObject.AddComponent<CanvasGroup>();
            bannerGroup.alpha = 0f;
            bannerGroup.blocksRaycasts = false;
            // dark backing strong enough for linear-space UI blending over the bright island
            UIKit.Img(banner, "Glow", UIKit.RadialGlow(), new Color(0.04f, 0.05f, 0.12f, 0.9f), new Vector2(0.5f, 0.5f), new Vector2(0f, -6f), new Vector2(1180f, 380f));
            bannerTitle = UIKit.Text(banner, "Title", "", 92f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0f, 26f), new Vector2(1200f, 110f), UIKit.FontZhBlack);
            bannerTitle.outlineWidth = 0.08f;
            bannerTitle.outlineColor = new Color32(12, 15, 32, 160);
            bannerSub = UIKit.Text(banner, "Sub", "", 28f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0f, -54f), new Vector2(1200f, 40f), UIKit.FontZhBold);
            bannerSub.outlineWidth = 0.15f;
            bannerSub.outlineColor = new Color32(12, 15, 32, 190);
            bannerLineL = UIKit.Img(banner, "LineL", UIKit.HGradient(), UIKit.Amber, new Vector2(0.5f, 0.5f), new Vector2(-330f, -54f), new Vector2(160f, 3f));
            bannerLineR = UIKit.Img(banner, "LineR", UIKit.HGradient(), UIKit.Amber, new Vector2(0.5f, 0.5f), new Vector2(330f, -54f), new Vector2(160f, 3f));
            bannerLineR.rectTransform.localRotation = Quaternion.Euler(0f, 0f, 180f);
        }

        public void ShowBanner(string title, string sub, Color accent, float dur = 2.2f)
        {
            bannerTitle.text = title;
            bannerSub.text = sub;
            bannerLineL.color = accent;
            bannerLineR.color = accent;
            bannerT = 0f;
            bannerDur = dur;
        }

        void UpdateBanner(float dt)
        {
            if (bannerT < 0f) { bannerGroup.alpha = 0f; return; }
            bannerT += Time.deltaTime > 0f ? Time.deltaTime : dt;
            float inK = Mathf.Clamp01(bannerT / 0.35f), outK = Mathf.Clamp01((bannerT - bannerDur) / 0.4f);
            bannerGroup.alpha = inK * (1f - outK);
            float s = Mathf.Lerp(1.18f, 1f, Ease.OutCubic(inK)) * Mathf.Lerp(1f, 0.96f, outK);
            banner.localScale = Vector3.one * s;
            float w = Mathf.Lerp(0f, 160f, Ease.OutCubic(Mathf.Clamp01((bannerT - 0.15f) / 0.4f)));
            bannerLineL.rectTransform.sizeDelta = new Vector2(w, 3f);
            bannerLineR.rectTransform.sizeDelta = new Vector2(w, 3f);
            if (bannerT > bannerDur + 0.45f) bannerT = -1f;
        }

        // ============================================================ toast (hint above the tray)
        RectTransform toast;
        TextMeshProUGUI toastText;
        Image toastIcon, toastBg;
        CanvasGroup toastGroup;
        float toastT = -1f, toastDur;

        void BuildToast()
        {
            toast = UIKit.Rect(fxLayer, "Toast", new Vector2(0.5f, 0f), new Vector2(0f, 292f), new Vector2(760f, 56f));
            toastGroup = toast.gameObject.AddComponent<CanvasGroup>();
            toastGroup.alpha = 0f;
            toastGroup.blocksRaycasts = false;
            UIKit.Img(toast, "Shadow", UIKit.Shadow(28, 12), new Color(0f, 0f, 0f, 0.35f), new Vector2(0.5f, 0.5f), new Vector2(0f, -5f), new Vector2(800f, 100f), true);
            toastBg = UIKit.Fill(toast, "Bg", UIKit.Rounded(28), UIKit.GlassLight);
            toastIcon = UIKit.Img(toast, "Icon", UIKit.Icon("star"), UIKit.Amber, new Vector2(0f, 0.5f), new Vector2(34f, 0f), new Vector2(28f, 28f));
            toastText = UIKit.Text(toast, "Text", "", 24f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(14f, 0f), new Vector2(700f, 40f), UIKit.FontZh);
        }

        public void Toast(string text, string icon, Color accent, float dur = 2.2f)
        {
            toastText.text = text;
            toastIcon.sprite = UIKit.Icon(icon);
            toastIcon.color = accent;
            float w = Mathf.Clamp(toastText.GetPreferredValues(text).x + 110f, 360f, 1100f);
            toast.sizeDelta = new Vector2(w, 56f);
            toastIcon.rectTransform.anchoredPosition = new Vector2(34f, 0f);
            toastText.rectTransform.sizeDelta = new Vector2(w - 80f, 40f);
            toastT = 0f;
            toastDur = dur;
        }

        void UpdateToast(float dt)
        {
            if (toastT < 0f) { toastGroup.alpha = 0f; return; }
            toastT += dt;
            float inK = Mathf.Clamp01(toastT / 0.2f), outK = Mathf.Clamp01((toastT - toastDur) / 0.3f);
            toastGroup.alpha = inK * (1f - outK);
            toast.anchoredPosition = new Vector2(0f, 292f + (1f - Ease.OutCubic(inK)) * -16f);
            if (toastT > toastDur + 0.35f) toastT = -1f;
        }

        // ============================================================ feedback events
        void OnFeedback(Feedback f)
        {
            switch (f.Kind)
            {
                case FeedbackKind.WaveStart:
                    ShowBanner("第 " + f.Value + " 波", f.Value == 1 ? "先点下方的释义炮弹，再点头顶单词对应的敌人" : "敌人加速  ×" + gm.SpeedAt(f.Value, gm.PlayTime).ToString("0.00"), UIKit.Amber);
                    break;
                case FeedbackKind.BossIncoming:
                    ShowBanner("<color=#FF5C6C>Boss 来袭</color>", "Boss 是一句英文长句：按顺序击中关键词的释义", UIKit.Coral, 3f);
                    break;
                case FeedbackKind.Correct:
                    Floater(f.World, "+" + f.Value, UIKit.Amber, 40f, UIKit.FontEn, new Vector2(0f, 46f));
                    Floater(f.World, "<font=\"" + FontName(UIKit.FontEn) + "\">" + f.Word.Word + "</font>  " + f.Word.Gloss, UIKit.Mint, 26f, UIKit.FontZhBold, new Vector2(0f, 6f), chip: true);
                    if (f.Homing) Floater(f.World, "★ 记忆深刻 · 自动追踪", UIKit.Amber, 22f, UIKit.FontZhBold, new Vector2(0f, 84f));
                    else if (f.Seconds < 2f) Floater(f.World, "神速", UIKit.Ice, 24f, UIKit.FontZhBold, new Vector2(0f, 84f));
                    break;
                case FeedbackKind.Wrong:
                    damagePulse = Mathf.Max(damagePulse, 0.25f);
                    Floater(f.World, "不是「" + (f.ShellWord != null ? f.ShellWord.Gloss : "?") + "」", UIKit.Coral, 26f, UIKit.FontZhBold, new Vector2(0f, -62f), chip: true);   // below the enemy: its word tag stays readable
                    Toast("答错了：<font=\"" + FontName(UIKit.FontEn) + "\">" + (f.Word != null ? f.Word.Word : "") + "</font> 的意思是「" + (f.Word != null ? f.Word.Gloss : "") + "」  ·  这个词稍后会再出现", "cross", UIKit.Coral, 2.6f);
                    break;
                case FeedbackKind.OrderWrong:
                    damagePulse = Mathf.Max(damagePulse, 0.25f);
                    var cur = gm.Boss != null ? gm.Boss.CurrentWord : null;
                    Toast("顺序不对：先击中第 " + (gm.Boss != null ? gm.Boss.Current + 1 : 1) + " 个关键词 <font=\"" + FontName(UIKit.FontEn) + "\">" + (cur != null ? cur.Word : "") + "</font>", "cross", UIKit.Coral, 2.6f);
                    Floater(f.World, "顺序不对", UIKit.Coral, 28f, UIKit.FontZhBold, new Vector2(0f, 60f), chip: true);
                    break;
                case FeedbackKind.Leak:
                    damagePulse = 1f;
                    if (gm.castle != null) Floater(gm.castle.Gate + Vector3.up * 3f, "-" + f.Value, UIKit.Coral, 44f, UIKit.FontEn, Vector2.zero);
                    if (f.Word != null) Toast("城堡受损：<font=\"" + FontName(UIKit.FontEn) + "\">" + f.Word.Word + "</font> =「" + f.Word.Gloss + "」，记住它，它还会回来", "castle", UIKit.Coral, 2.4f);
                    break;
                case FeedbackKind.Jammed:
                    Toast("装填中…答错后炮台需要片刻重新装填", "cross", UIKit.TextMid, 1.2f);
                    break;
                case FeedbackKind.NeedShell:
                    Toast("先点下方的释义炮弹（键 1–4），再点敌人", "shell", UIKit.Amber, 2f);
                    trayNudge = 1f;
                    break;
                case FeedbackKind.SkillReady:
                    Toast("连对 3 次！寒霜齐射就绪 —— 按空格或点左下角，全体减速", "flake", UIKit.Ice, 2.6f);
                    skillPop = 1f;
                    break;
                case FeedbackKind.SkillUsed:
                    ShowBanner("<color=#7FD8FF>寒霜齐射</color>", "全体敌人减速 " + GameManager.SlowDuration.ToString("0") + " 秒", UIKit.Ice, 1.4f);
                    break;
                case FeedbackKind.VividNew:
                    Toast("<font=\"" + FontName(UIKit.FontEn) + "\">" + f.Word.Word + "</font> 记忆深刻 —— 之后它的炮弹会自动追踪目标", "star", UIKit.Amber, 3f);
                    Floater(f.World, "★ 记忆深刻", UIKit.Amber, 30f, UIKit.FontZhBold, new Vector2(0f, 120f), chip: true);
                    Audio.Play(Sfx.Id.Vivid, 0.7f);
                    break;
                case FeedbackKind.BossBreak:
                    bossPop = 1f;
                    break;
                case FeedbackKind.Armed:
                    if (f.Value == 1) Toast("★ 已待命：「" + f.ShellWord.Gloss + "」的敌人一出现就自动发射", "star", UIKit.Amber, 2.2f);
                    break;
            }
        }

        public static string FontName(TMP_FontAsset f) { return f != null ? f.name : ""; }

        // ============================================================ floaters
        class FloaterItem
        {
            public RectTransform rt;
            public CanvasGroup group;
            public Vector3 world;
            public Vector2 offset;
            public float t, dur;
        }
        readonly List<FloaterItem> floaters = new List<FloaterItem>();

        void Floater(Vector3 world, string text, Color color, float size, TMP_FontAsset font, Vector2 offset, bool chip = false)
        {
            var rt = UIKit.Rect(fxLayer, "Floater", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(600f, size + 20f));
            var g = rt.gameObject.AddComponent<CanvasGroup>();
            g.blocksRaycasts = false;
            var t = UIKit.Text(rt, "T", text, size, color, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(600f, size + 20f), font);
            if (chip)
            {
                float w = t.GetPreferredValues(text).x + 36f;
                var bg = UIKit.Img(rt, "Bg", UIKit.Rounded(20), UIKit.A(UIKit.Ink, 0.94f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(w, size + 18f), true);
                bg.transform.SetAsFirstSibling();
            }
            else
            {
                t.outlineWidth = 0.18f;
                t.outlineColor = new Color32(14, 17, 36, 200);
            }
            floaters.Add(new FloaterItem { rt = rt, group = g, world = world, offset = offset, dur = chip ? 1.5f : 1.1f });
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
                Vector2 pos = p + new Vector2(0f, Ease.OutCubic(Mathf.Clamp01(k)) * 46f);
                float top = root.rect.height * 0.5f - 210f, right = root.rect.width * 0.5f - 300f;
                pos.y = Mathf.Min(pos.y, top - 80f);   // near the top the whole stack moves below the HUD, keeping its spacing
                pos += f.offset;
                pos.x = Mathf.Clamp(pos.x, -right, right);
                f.rt.anchoredPosition = pos;
                f.rt.localScale = Vector3.one * (k < 0.15f ? Mathf.Lerp(0.6f, 1f, Ease.OutBack(k / 0.15f)) : 1f);
                f.group.alpha = vis ? Mathf.Clamp01((1f - k) * 3f) : 0f;
                if (k >= 1f) { Destroy(f.rt.gameObject); floaters.RemoveAt(i); }
            }
        }
    }
}
