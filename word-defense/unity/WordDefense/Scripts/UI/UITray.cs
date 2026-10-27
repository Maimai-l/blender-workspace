using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace WordDefense
{
    public partial class UIRoot
    {
        // ============================================================ sense slips: the four meanings, numbered like dictionary senses (and keys 1–4)
        class Slip
        {
            public RectTransform rt, body;
            public Image shadow, paper, goldEdge, star;
            public TextMeshProUGUI num, sense, state;
            public CanvasGroup group;
            public Button button;
            public int shellId = -1;
            public float lift, appear = 1f, flip = 1f;
            public bool hovered;
        }
        readonly Slip[] slips = new Slip[ShellTray.Size];
        RectTransform trayRoot;
        Image jamLine;
        float trayNudge, trayShake;
        const float SlipW = 272f, SlipH = 122f, SlipGap = 16f, TrayBottom = 40f;
        static float TrayW { get { return 4 * SlipW + 3 * SlipGap; } }

        public RectTransform CardRect(int i) { return slips[i] != null ? slips[i].rt : null; }

        void BuildTray()
        {
            trayRoot = UIKit.Rect(hudLayer, "Senses", new Vector2(0.5f, 0f), new Vector2(0f, TrayBottom), new Vector2(TrayW, SlipH + 40f), new Vector2(0.5f, 0f));
            for (int i = 0; i < ShellTray.Size; i++)
            {
                var c = new Slip();
                float x = -TrayW / 2f + SlipW / 2f + i * (SlipW + SlipGap);
                c.rt = UIKit.Rect(trayRoot, "Sense" + (i + 1), new Vector2(0.5f, 0f), new Vector2(x, 0f), new Vector2(SlipW, SlipH), new Vector2(0.5f, 0f));
                c.group = c.rt.gameObject.AddComponent<CanvasGroup>();
                c.body = UIKit.Stretch(c.rt, "Body");
                c.shadow = UIKit.PaperShadow(c.body, 6);
                c.paper = UIKit.Fill(c.body, "Paper", UIKit.Rounded(6), UIKit.Paper);
                c.paper.raycastTarget = true;
                c.goldEdge = UIKit.Img(c.body, "GoldEdge", UIKit.Rounded(2), UIKit.Gold, new Vector2(0.5f, 1f), new Vector2(0f, -3f), new Vector2(SlipW - 12f, 4f), true);
                // a hairline under the number row, like the ruled head of an index card
                UIKit.Img(c.body, "Rule", UIKit.White(), UIKit.InkA(0.1f), new Vector2(0.5f, 1f), new Vector2(0f, -44f), new Vector2(SlipW - 40f, 1.5f));
                c.num = UIKit.Text(c.body, "Number", (i + 1).ToString(), 24f, UIKit.InkA(0.7f), TextAlignmentOptions.Left,
                    new Vector2(0f, 1f), new Vector2(20f, -24f), new Vector2(40f, 30f), UIKit.Latin, new Vector2(0f, 0.5f));
                c.star = UIKit.Img(c.body, "Star", UIKit.Icon("star", 64), UIKit.Gold, new Vector2(0f, 1f), new Vector2(31f, -24f), new Vector2(22f, 22f));
                c.state = UIKit.Text(c.body, "State", "待命", 20f, UIKit.GoldInk, TextAlignmentOptions.Right,
                    new Vector2(1f, 1f), new Vector2(-18f, -24f), new Vector2(120f, 28f), UIKit.SongBold, new Vector2(1f, 0.5f));
                c.sense = UIKit.Text(c.body, "Sense", "", 48f, UIKit.Ink, TextAlignmentOptions.BottomLeft,
                    new Vector2(0f, 0f), new Vector2(20f, 16f), new Vector2(SlipW - 40f, 74f), UIKit.SongBold, new Vector2(0f, 0f));
                c.sense.textWrappingMode = TextWrappingModes.Normal;
                c.sense.enableAutoSizing = true;
                c.sense.fontSizeMin = 26f;
                c.sense.fontSizeMax = 48f;
                c.sense.lineSpacing = -12f;
                c.button = c.rt.gameObject.AddComponent<Button>();
                c.button.targetGraphic = c.paper;
                c.button.transition = Selectable.Transition.None;
                c.button.navigation = new Navigation { mode = Navigation.Mode.None };
                int idx = i;
                c.button.onClick.AddListener(() => gm.ActivateSlot(idx));
                var hover = c.rt.gameObject.AddComponent<PointerHover>();
                var slip = c;
                hover.changed = over => slip.hovered = over;
                slips[i] = c;
            }
            // after a wrong answer the cannon reloads: a red-pen line drains across the top of the senses
            jamLine = UIKit.Img(trayRoot, "Reload", UIKit.Rounded(2), UIKit.RedPen, new Vector2(0.5f, 0f), new Vector2(0f, SlipH + 14f), new Vector2(TrayW, 4f), true);
        }

        void UpdateTray(float dt)
        {
            float now = Time.time;
            bool jammed = gm.Jammed;
            float jamK = jammed ? Mathf.Clamp01((gm.JamUntil - now) / GameManager.JamSeconds) : 0f;
            trayNudge = Mathf.MoveTowards(trayNudge, 0f, dt * 2f);
            trayShake = Mathf.MoveTowards(trayShake, 0f, dt * 4f);
            jamLine.enabled = jammed;
            jamLine.rectTransform.sizeDelta = new Vector2(TrayW * jamK, 4f);
            float shakeX = trayShake > 0f ? Mathf.Sin(Time.unscaledTime * 70f) * 6f * trayShake : 0f;
            trayRoot.anchoredPosition = new Vector2(shakeX, TrayBottom);
            float pulse = 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 6f);
            for (int i = 0; i < ShellTray.Size; i++)
            {
                var c = slips[i];
                var s = gm.Tray.Slots[i];
                int id = s != null ? s.Id : -1;
                if (id != c.shellId)
                {
                    if (s != null)
                    {
                        if (s.Swapped) c.flip = 0f; else c.appear = 0f;
                        c.sense.text = s.Word.Gloss;
                        Audio.Play(Sfx.Id.Card, 0.25f, 1f + i * 0.05f);
                    }
                    else c.sense.text = "";
                    c.shellId = id;
                }
                bool selected = gm.SelectedSlot == i && s != null;
                bool vivid = s != null && s.Vivid;
                bool armed = vivid && s.Armed;
                bool dim = s == null || (jammed && !vivid);
                c.appear = Mathf.MoveTowards(c.appear, 1f, dt / 0.25f);
                c.flip = Mathf.MoveTowards(c.flip, 1f, dt / 0.28f);
                c.lift = UIKit.Smooth(c.lift, selected ? 16f : (c.hovered && !dim ? 6f : 0f), 18f, dt);
                float nudge = trayNudge > 0f ? Mathf.Sin(Time.unscaledTime * 30f + i) * 5f * trayNudge : 0f;
                float ap = Ease.OutCubic(c.appear);
                c.body.anchoredPosition = new Vector2(0f, c.lift + (1f - ap) * -28f + nudge);
                c.body.localScale = new Vector3(Mathf.Lerp(0.02f, 1f, Ease.OutCubic(c.flip)), 1f, 1f);
                c.group.alpha = s == null ? 0.5f : ap;
                // paper, or ink once chosen
                c.paper.color = selected ? UIKit.Ink : (dim ? UIKit.Mist : UIKit.Paper);
                c.shadow.color = UIKit.InkA(dim ? 0.08f : (selected ? 0.32f : 0.2f));
                c.sense.color = selected ? UIKit.Paper : (dim ? UIKit.InkA(0.4f) : UIKit.Ink);
                c.num.enabled = !vivid;
                c.num.color = selected ? UIKit.A(UIKit.Paper, 0.7f) : UIKit.InkA(dim ? 0.3f : 0.7f);
                c.star.enabled = vivid;
                c.goldEdge.enabled = vivid;
                c.goldEdge.color = UIKit.A(UIKit.Gold, armed ? 0.45f + 0.55f * pulse : 1f);
                c.state.enabled = armed;
                c.state.color = selected ? UIKit.Gold : UIKit.GoldInk;
            }
        }

        // ============================================================ frost dial: three steps of charge, then 空格
        RectTransform skillRoot, skillKey;
        Image skillPaper, skillIcon, skillDrain;
        readonly Image[] skillSeg = new Image[3];
        Button skillButton;
        float skillPop;
        const float DialSize = 116f;

        void BuildSkill()
        {
            skillRoot = UIKit.Rect(hudLayer, "Frost", new Vector2(0f, 0f), new Vector2(Margin + DialSize / 2f, TrayBottom + DialSize / 2f - 2f), new Vector2(DialSize, DialSize));
            UIKit.PaperShadow(skillRoot, (int)(DialSize / 2f) - 4);
            skillPaper = UIKit.Fill(skillRoot, "Paper", UIKit.Circle(256), UIKit.Paper, false);
            skillPaper.raycastTarget = true;
            for (int k = 0; k < 3; k++)
            {
                float a0 = k * 120f + 9f, a1 = (k + 1) * 120f - 9f;
                skillSeg[k] = UIKit.Img(skillRoot, "Step" + (k + 1), UIKit.Arc(256, 18f, a0, a1), UIKit.InkA(0.2f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(DialSize - 14f, DialSize - 14f));
            }
            skillDrain = UIKit.Img(skillRoot, "Drain", UIKit.Ring(256, 18f), UIKit.Frost, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(DialSize - 14f, DialSize - 14f));
            skillDrain.type = Image.Type.Filled;
            skillDrain.fillMethod = Image.FillMethod.Radial360;
            skillDrain.fillOrigin = (int)Image.Origin360.Top;
            skillDrain.fillClockwise = true;
            skillIcon = UIKit.Img(skillRoot, "Flake", UIKit.Icon("flake", 128), UIKit.InkA(0.55f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(48f, 48f));
            skillButton = skillRoot.gameObject.AddComponent<Button>();
            skillButton.targetGraphic = skillPaper;
            skillButton.transition = Selectable.Transition.None;
            skillButton.navigation = new Navigation { mode = Navigation.Mode.None };
            skillButton.onClick.AddListener(() => gm.UseSkill());
            skillKey = UIKit.Keycap(hudLayer, "SpaceKey", "空格", new Vector2(0f, 0f), new Vector2(Margin + DialSize + 16f, TrayBottom + DialSize / 2f - 2f), 36f, new Vector2(0f, 0.5f));
        }

        public RectTransform SkillRect { get { return skillButton != null ? (RectTransform)skillButton.transform : null; } }

        void UpdateSkill(float dt)
        {
            bool active = gm.SlowTimer > 0f;
            bool ready = gm.SkillReady && !active;
            skillPop = Mathf.MoveTowards(skillPop, 0f, dt * 1.5f);
            int charge = Mathf.Clamp(gm.SkillCharge, 0, 3);
            for (int k = 0; k < 3; k++)
            {
                skillSeg[k].enabled = !active;
                skillSeg[k].color = k < charge || ready ? UIKit.Frost : UIKit.InkA(0.2f);
            }
            skillDrain.enabled = active;
            if (active) skillDrain.fillAmount = gm.SlowTimer / GameManager.SlowDuration;
            skillIcon.color = active || ready ? UIKit.Frost : UIKit.InkA(0.55f);
            skillIcon.rectTransform.localRotation = active ? Quaternion.Euler(0f, 0f, -Time.unscaledTime * 50f) : Quaternion.identity;
            skillRoot.localScale = Vector3.one * (1f + skillPop * 0.1f);
            skillKey.gameObject.SetActive(ready);
        }
    }
}
