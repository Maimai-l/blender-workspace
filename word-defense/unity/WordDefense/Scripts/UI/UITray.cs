using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace WordDefense
{
    public partial class UIRoot
    {
        // ============================================================ shell cards
        class Card
        {
            public RectTransform rt, body;
            public Image bg, border, glow, vividFrame, jam, jamBar, badgeBg, icon;
            public TextMeshProUGUI gloss, key, tag, foot;
            public CanvasGroup group;
            public Button button;
            public int shellId = -1;
            public float lift, appear = 1f, flip = 1f, shake;
        }
        readonly Card[] cards = new Card[ShellTray.Size];
        RectTransform trayRoot;
        TextMeshProUGUI trayHint;
        Image trayHintBg;
        float trayNudge;
        const float CardW = 236f, CardH = 136f, CardGap = 20f;

        public RectTransform CardRect(int i) { return cards[i] != null ? cards[i].rt : null; }

        void BuildTray()
        {
            trayRoot = UIKit.Rect(hudLayer, "Tray", new Vector2(0.5f, 0f), new Vector2(0f, 34f), new Vector2(4 * CardW + 3 * CardGap, CardH + 60f), new Vector2(0.5f, 0f));
            trayHintBg = UIKit.Img(trayRoot, "HintBg", UIKit.Rounded(17), UIKit.A(UIKit.Glass, 0.9f), new Vector2(0.5f, 1f), new Vector2(0f, -8f), new Vector2(300f, 34f), true);
            trayHint = UIKit.Text(trayRoot, "Hint", "", 19f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -8f), new Vector2(900f, 28f), UIKit.FontZh);
            for (int i = 0; i < ShellTray.Size; i++)
            {
                var c = new Card();
                float x = -((4 * CardW + 3 * CardGap) / 2f) + CardW / 2f + i * (CardW + CardGap);
                c.rt = UIKit.Rect(trayRoot, "Card" + (i + 1), new Vector2(0.5f, 0f), new Vector2(x, 0f), new Vector2(CardW, CardH), new Vector2(0.5f, 0f));
                c.group = c.rt.gameObject.AddComponent<CanvasGroup>();
                c.body = UIKit.Stretch(c.rt, "Body");
                c.glow = UIKit.Img(c.body, "Glow", UIKit.RadialGlow(), UIKit.A(UIKit.Amber, 0f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(CardW + 120f, CardH + 120f));
                var sh = UIKit.Img(c.body, "Shadow", UIKit.Shadow(24, 14), new Color(0.02f, 0.03f, 0.08f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0f, -7f), new Vector2(CardW + 56f, CardH + 56f), true);
                c.bg = UIKit.Fill(c.body, "Bg", UIKit.Rounded(24), UIKit.Glass);
                c.bg.raycastTarget = true;
                c.vividFrame = UIKit.Fill(c.body, "Vivid", UIKit.Rounded(24, 3f), UIKit.A(UIKit.Amber, 0f));
                c.border = UIKit.Fill(c.body, "Border", UIKit.Rounded(24, 1.5f), UIKit.Stroke);
                c.icon = UIKit.Img(c.body, "Shell", UIKit.Icon("shell"), UIKit.A(UIKit.Amber, 0.85f), new Vector2(0f, 0f), new Vector2(28f, 24f), new Vector2(22f, 22f));
                c.foot = UIKit.Text(c.body, "Foot", "释义炮弹", 15f, UIKit.TextLow, TextAlignmentOptions.Left, new Vector2(0f, 0f), new Vector2(108f, 24f), new Vector2(140f, 20f), UIKit.FontZh);
                c.badgeBg = UIKit.Img(c.body, "KeyBg", UIKit.Rounded(8), new Color(1f, 1f, 1f, 0.1f), new Vector2(0f, 1f), new Vector2(28f, -26f), new Vector2(30f, 30f), true);
                c.key = UIKit.Text(c.body, "Key", (i + 1).ToString(), 18f, UIKit.TextMid, TextAlignmentOptions.Center, new Vector2(0f, 1f), new Vector2(28f, -26f), new Vector2(30f, 30f), UIKit.FontEn);
                c.tag = UIKit.Text(c.body, "Tag", "", 15f, UIKit.Amber, TextAlignmentOptions.Right, new Vector2(1f, 1f), new Vector2(-70f, -26f), new Vector2(150f, 22f), UIKit.FontZhBold);
                c.gloss = UIKit.Text(c.body, "Gloss", "", 36f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0f, 4f), new Vector2(CardW - 26f, 72f), UIKit.FontZhBold);
                c.gloss.textWrappingMode = TextWrappingModes.Normal;
                c.gloss.enableAutoSizing = true;
                c.gloss.fontSizeMin = 22f;
                c.gloss.fontSizeMax = 38f;
                c.jam = UIKit.Fill(c.body, "Jam", UIKit.Rounded(24), new Color(0.04f, 0.05f, 0.1f, 0f));
                c.jamBar = UIKit.Img(c.body, "JamBar", UIKit.Rounded(3), UIKit.A(UIKit.Coral, 0f), new Vector2(0f, 0f), new Vector2(18f, 10f), new Vector2(CardW - 36f, 6f), true);
                c.jamBar.rectTransform.pivot = new Vector2(0f, 0.5f);
                c.button = c.rt.gameObject.AddComponent<Button>();
                c.button.targetGraphic = c.bg;
                c.button.transition = Selectable.Transition.None;
                c.button.navigation = new Navigation { mode = Navigation.Mode.None };
                int idx = i;
                c.button.onClick.AddListener(() => gm.ActivateSlot(idx));
                c.rt.gameObject.AddComponent<HoverScale>().amount = 1.03f;
                cards[i] = c;
            }
        }

        void UpdateTray(float dt)
        {
            float now = Time.time;
            bool jammed = gm.Jammed;
            float jamK = jammed ? Mathf.Clamp01((gm.JamUntil - now) / GameManager.JamSeconds) : 0f;
            trayNudge = Mathf.MoveTowards(trayNudge, 0f, dt * 2f);
            for (int i = 0; i < ShellTray.Size; i++)
            {
                var c = cards[i];
                var s = gm.Tray.Slots[i];
                int id = s != null ? s.Id : -1;
                if (id != c.shellId)
                {
                    if (s != null)
                    {
                        if (s.Swapped) c.flip = 0f; else c.appear = 0f;
                        c.gloss.text = s.Word.Gloss;
                        Audio.Play(Sfx.Id.Card, 0.25f, 1f + i * 0.05f);
                    }
                    c.shellId = id;
                }
                bool selected = gm.SelectedSlot == i;
                bool vivid = s != null && s.Vivid;
                c.appear = Mathf.MoveTowards(c.appear, 1f, dt / 0.28f);
                c.flip = Mathf.MoveTowards(c.flip, 1f, dt / 0.3f);
                c.lift = UIKit.Smooth(c.lift, selected ? 18f : 0f, 16f, dt);
                float nudge = trayNudge > 0f ? Mathf.Sin(Time.unscaledTime * 30f + i) * 5f * trayNudge : 0f;
                float ap = Ease.OutBack(c.appear);
                c.body.anchoredPosition = new Vector2(0f, c.lift + (1f - ap) * -40f + nudge);
                c.body.localScale = new Vector3(Mathf.Lerp(0f, 1f, Ease.OutCubic(c.flip)) * (0.86f + 0.14f * ap), 0.86f + 0.14f * ap, 1f);
                c.group.alpha = s == null ? 0.35f : Mathf.Clamp01(c.appear * 3f);
                if (s == null) c.gloss.text = "装填…";
                // states
                Color bg = UIKit.Glass;
                if (selected) bg = Color.Lerp(UIKit.Glass, UIKit.Hex("#2A2F55"), 0.9f);
                c.bg.color = bg;
                c.border.color = selected ? UIKit.Amber : (vivid ? UIKit.A(UIKit.Amber, 0.5f) : UIKit.Stroke);
                float pulse = 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 6f);
                c.vividFrame.color = vivid ? UIKit.A(UIKit.Amber, s.Armed ? 0.45f + 0.5f * pulse : 0.85f) : UIKit.A(UIKit.Amber, 0f);
                c.glow.color = UIKit.A(UIKit.Amber, selected ? 0.28f : (vivid ? 0.14f + (s.Armed ? 0.12f * pulse : 0f) : 0f));
                c.tag.text = vivid ? (s.Armed ? "★ 待命中" : "★ 记忆深刻") : "";
                c.foot.text = vivid ? "点击即自动追踪" : (selected ? "点击敌人发射" : "释义炮弹");
                c.foot.color = vivid || selected ? UIKit.Amber : UIKit.TextLow;
                c.icon.color = vivid ? UIKit.Amber : UIKit.A(UIKit.Amber, 0.75f);
                c.key.color = selected ? UIKit.Ink : UIKit.TextMid;
                c.badgeBg.color = selected ? UIKit.Amber : new Color(1f, 1f, 1f, 0.1f);
                c.jam.color = new Color(0.04f, 0.05f, 0.1f, jammed && !vivid ? 0.55f : 0f);
                c.jamBar.color = UIKit.A(UIKit.Coral, jammed && !vivid ? 0.9f : 0f);
                c.jamBar.rectTransform.sizeDelta = new Vector2((CardW - 36f) * jamK, 6f);
            }
            string hint;
            if (gm.SelectedSlot >= 0 && gm.Tray.Slots[gm.SelectedSlot] != null) hint = "已选「" + gm.Tray.Slots[gm.SelectedSlot].Word.Gloss + "」—— 点击对应的敌人发射（右键取消）";
            else if (gm.Jammed) hint = "<color=#FF5C6C>装填中…</color>";
            else hint = "选择释义炮弹 <color=#7F89AA>· 键 1–4</color>";
            if (trayHint.text != hint)
            {
                trayHint.text = hint;
                trayHintBg.rectTransform.sizeDelta = new Vector2(trayHint.GetPreferredValues(hint).x + 40f, 34f);
            }
        }

        // ============================================================ frost skill
        RectTransform skillRoot;
        Image skillRing, skillFill, skillGlow, skillIcon, skillCenter;
        TextMeshProUGUI skillTitle, skillState;
        Button skillButton;
        float skillPop;
        readonly Image[] skillSeg = new Image[3];

        void BuildSkill()
        {
            skillRoot = UIKit.Rect(hudLayer, "Skill", new Vector2(0f, 0f), new Vector2(40f, 34f), new Vector2(420f, 150f), new Vector2(0f, 0f));
            var bgPanel = UIKit.Panel(skillRoot, "Panel", new Vector2(0f, 0.5f), new Vector2(70f, 0f), new Vector2(330f, 108f), 26, null, true, new Vector2(0f, 0.5f));
            skillTitle = UIKit.Text(bgPanel, "Title", "寒霜齐射", 26f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(205f, -36f), new Vector2(210f, 34f));
            skillState = UIKit.Text(bgPanel, "State", "", 19f, UIKit.TextMid, TextAlignmentOptions.Left, new Vector2(0f, 0f), new Vector2(210f, 32f), new Vector2(220f, 26f), UIKit.FontZh);
            var dial = UIKit.Rect(skillRoot, "Dial", new Vector2(0f, 0.5f), new Vector2(75f, 0f), new Vector2(140f, 140f));
            dial.pivot = new Vector2(0.5f, 0.5f);
            dial.anchoredPosition = new Vector2(75f, 0f);
            skillGlow = UIKit.Img(dial, "Glow", UIKit.RadialGlow(), UIKit.A(UIKit.Ice, 0f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(240f, 240f));
            UIKit.Img(dial, "Shadow", UIKit.Shadow(66, 12), new Color(0f, 0f, 0f, 0.45f), new Vector2(0.5f, 0.5f), new Vector2(0f, -6f), new Vector2(190f, 190f), true);
            skillCenter = UIKit.Img(dial, "Center", UIKit.Circle(256), UIKit.Glass, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(132f, 132f));
            skillCenter.raycastTarget = true;
            skillRing = UIKit.Img(dial, "Track", UIKit.Ring(256, 14f), new Color(1f, 1f, 1f, 0.1f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(132f, 132f));
            skillFill = UIKit.Img(dial, "Fill", UIKit.Ring(256, 14f), UIKit.Ice, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(132f, 132f));
            skillFill.type = Image.Type.Filled;
            skillFill.fillMethod = Image.FillMethod.Radial360;
            skillFill.fillOrigin = (int)Image.Origin360.Top;
            skillFill.fillClockwise = true;
            for (int k = 0; k < 3; k++)
            {
                var sep = UIKit.Img(dial, "Sep" + k, UIKit.White(), UIKit.Hex("#11152A"), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(4f, 16f));
                float a = k * 120f;
                sep.rectTransform.localRotation = Quaternion.Euler(0f, 0f, -a);
                sep.rectTransform.anchoredPosition = Quaternion.Euler(0f, 0f, -a) * new Vector3(0f, 59f, 0f);
                skillSeg[k] = sep;
            }
            skillIcon = UIKit.Img(dial, "Icon", UIKit.Icon("flake", 128), UIKit.A(Color.white, 0.4f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(64f, 64f));
            skillButton = dial.gameObject.AddComponent<Button>();
            skillButton.targetGraphic = skillCenter;
            skillButton.transition = Selectable.Transition.None;
            skillButton.navigation = new Navigation { mode = Navigation.Mode.None };
            skillButton.onClick.AddListener(() => gm.UseSkill());
            dial.gameObject.AddComponent<HoverScale>().amount = 1.05f;
        }

        public RectTransform SkillRect { get { return skillButton != null ? (RectTransform)skillButton.transform : null; } }

        void UpdateSkill(float dt)
        {
            bool active = gm.SlowTimer > 0f;
            bool ready = gm.SkillReady;
            skillPop = Mathf.MoveTowards(skillPop, 0f, dt * 1.5f);
            float pulse = 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 4f);
            if (active)
            {
                skillFill.fillAmount = gm.SlowTimer / GameManager.SlowDuration;
                skillFill.color = UIKit.Ice;
                skillState.text = "<color=#7FD8FF>减速中</color> " + gm.SlowTimer.ToString("0.0") + " 秒";
                skillIcon.color = UIKit.Ice;
                skillIcon.rectTransform.localRotation = Quaternion.Euler(0f, 0f, -Time.unscaledTime * 60f);
                skillGlow.color = UIKit.A(UIKit.Ice, 0.3f);
            }
            else
            {
                float target = gm.SkillCharge / (float)GameManager.SkillCost;
                skillFill.fillAmount = UIKit.Smooth(skillFill.fillAmount, target, 12f, dt);
                skillFill.color = ready ? UIKit.Ice : UIKit.A(UIKit.Ice, 0.75f);
                skillIcon.rectTransform.localRotation = Quaternion.identity;
                skillIcon.color = ready ? Color.Lerp(UIKit.Ice, Color.white, pulse * 0.6f) : UIKit.A(Color.white, 0.35f);
                skillGlow.color = UIKit.A(UIKit.Ice, ready ? 0.25f + 0.25f * pulse + skillPop * 0.4f : 0f);
                skillState.text = ready ? "<color=#7FD8FF>就绪</color> · 按 <font=\"" + FontName(UIKit.FontEn) + "\">Space</font>" : "连对 " + gm.SkillCharge + " / " + GameManager.SkillCost + " 充能";
            }
            skillCenter.color = ready && !active ? Color.Lerp(UIKit.Glass, UIKit.Hex("#1E3A55"), 0.6f + 0.4f * pulse) : UIKit.Glass;
            skillRoot.localScale = Vector3.one * (1f + skillPop * 0.08f);
        }

        // ============================================================ memory widget
        RectTransform memCard;
        TextMeshProUGUI memVivid, memSeen;
        Image memBar;

        void BuildMemory()
        {
            memCard = UIKit.Panel(hudLayer, "MemoryCard", new Vector2(1f, 0f), new Vector2(-40f, 34f), new Vector2(300f, 136f), 24, null, true, new Vector2(1f, 0f));
            UIKit.Text(memCard, "Title", "本局单词", 22f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(118f, -28f), new Vector2(200f, 30f));
            UIKit.Img(memCard, "Star", UIKit.Icon("star"), UIKit.Amber, new Vector2(0f, 1f), new Vector2(34f, -66f), new Vector2(26f, 26f));
            memVivid = UIKit.Text(memCard, "Vivid", "", 21f, UIKit.TextMid, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(176f, -66f), new Vector2(240f, 30f), UIKit.FontZh);
            var track = UIKit.Img(memCard, "Track", UIKit.Rounded(4), new Color(1f, 1f, 1f, 0.09f), new Vector2(0f, 0f), new Vector2(150f, 50f), new Vector2(256f, 8f), true);
            memBar = UIKit.Img(track.rectTransform, "Bar", UIKit.Rounded(4), UIKit.Mint, new Vector2(0f, 0.5f), Vector2.zero, new Vector2(0f, 8f), true);
            memBar.rectTransform.pivot = new Vector2(0f, 0.5f);
            memSeen = UIKit.Text(memCard, "Seen", "", 17f, UIKit.TextLow, TextAlignmentOptions.Left, new Vector2(0f, 0f), new Vector2(150f, 26f), new Vector2(256f, 24f), UIKit.FontZh);
        }

        void UpdateMemory(float dt)
        {
            var words = gm.Deck.Words;
            int vivid = words.Count(w => gm.IsVivid(w));
            int seen = words.Count(w => w.Spawned > 0);
            int known = words.Count(w => w.Correct > 0);
            string v = "记忆深刻 <font=\"" + FontName(UIKit.FontEn) + "\"><size=26><color=#FFC34D>" + vivid + "</color></size></font> 个";
            if (memVivid.text != v) memVivid.text = v;
            string s = "答对 " + known + " · 遇见 " + seen + " / " + words.Count;
            if (memSeen.text != s) memSeen.text = s;
            float f = words.Count > 0 ? known / (float)words.Count : 0f;
            memBar.rectTransform.sizeDelta = new Vector2(UIKit.Smooth(memBar.rectTransform.sizeDelta.x, 256f * f, 8f, dt), 8f);
        }
    }
}
