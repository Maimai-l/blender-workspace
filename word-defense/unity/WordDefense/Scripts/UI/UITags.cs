using System.Collections.Generic;
using System.Linq;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace WordDefense
{
    public partial class UIRoot
    {
        // ============================================================ word tags
        class Tag
        {
            public Enemy enemy;
            public RectTransform rt, pill;
            public Image bg, shadow, star, dot, flake, ring, pointer, revealBg;
            public TextMeshProUGUI word, reveal, chip;
            public CanvasGroup group;
            public float width, push, appear, hover, alpha = 1f;
            public Vector2 basePos;
            public bool boss;
            public string shownWord;
        }
        readonly Dictionary<Enemy, Tag> tags = new Dictionary<Enemy, Tag>();
        readonly List<Tag> tagOrder = new List<Tag>();

        public bool TagScreenPos(Enemy e, out Vector2 screen)
        {
            Tag t;
            screen = Vector2.zero;
            if (e == null || !tags.TryGetValue(e, out t) || t.rt == null) return false;
            screen = ScreenOf(t.pill);
            return true;
        }

        Tag MakeTag(Enemy e)
        {
            var t = new Tag { enemy = e, boss = e is BossEnemy };
            t.rt = UIKit.Rect(tagLayer, "Tag_" + (e.Word != null ? e.Word.Word : "?"), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(200f, 60f), new Vector2(0.5f, 0f));
            t.group = t.rt.gameObject.AddComponent<CanvasGroup>();
            t.pill = UIKit.Rect(t.rt, "Pill", new Vector2(0.5f, 0f), new Vector2(0f, 12f), new Vector2(200f, t.boss ? 58f : 46f), new Vector2(0.5f, 0f));
            t.shadow = UIKit.Img(t.pill, "Shadow", UIKit.Shadow(23, 10), new Color(0.03f, 0.04f, 0.1f, 0.45f), new Vector2(0.5f, 0.5f), new Vector2(0f, -4f), new Vector2(240f, 86f), true);
            t.shadow.rectTransform.anchorMin = Vector2.zero; t.shadow.rectTransform.anchorMax = Vector2.one;
            t.shadow.rectTransform.offsetMin = new Vector2(-20f, -24f); t.shadow.rectTransform.offsetMax = new Vector2(20f, 16f);
            t.ring = UIKit.Fill(t.pill, "Ring", UIKit.Rounded(t.boss ? 29 : 23, 3f), UIKit.A(UIKit.Amber, 0f), true, -4f);
            t.bg = UIKit.Fill(t.pill, "Bg", UIKit.Rounded(t.boss ? 29 : 23), t.boss ? UIKit.A(UIKit.Ink, 0.94f) : UIKit.Paper);
            t.bg.raycastTarget = true;
            t.pointer = UIKit.Img(t.rt, "Pointer", UIKit.Icon("pointer", 32), t.boss ? UIKit.A(UIKit.Ink, 0.94f) : UIKit.Paper, new Vector2(0.5f, 0f), new Vector2(0f, 6f), new Vector2(18f, 12f));
            t.word = UIKit.Text(t.pill, "Word", "", t.boss ? 32f : 28f, t.boss ? UIKit.Amber : UIKit.Ink, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0f, 1f), new Vector2(400f, 44f), UIKit.FontEn);
            t.star = UIKit.Img(t.pill, "Star", UIKit.Icon("star", 64), UIKit.Amber, new Vector2(0f, 0.5f), new Vector2(22f, 0f), new Vector2(20f, 20f));
            t.dot = UIKit.Img(t.pill, "Urgent", UIKit.Circle(32), UIKit.Coral, new Vector2(1f, 0.5f), new Vector2(-16f, 0f), new Vector2(10f, 10f));
            t.flake = UIKit.Img(t.pill, "Flake", UIKit.Icon("flake", 64), UIKit.Ice, new Vector2(1f, 1f), new Vector2(-4f, -2f), new Vector2(22f, 22f));
            if (t.boss)
            {
                var chipBg = UIKit.Img(t.pill, "ChipBg", UIKit.Rounded(12), UIKit.Coral, new Vector2(0.5f, 1f), new Vector2(0f, 2f), new Vector2(150f, 26f), true);
                t.chip = UIKit.Text(t.pill, "Chip", "BOSS", 16f, Color.white, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, 2f), new Vector2(150f, 26f), UIKit.FontZhBold);
            }
            t.revealBg = UIKit.Img(t.rt, "RevealBg", UIKit.Rounded(16), UIKit.A(UIKit.Coral, 0.95f), new Vector2(0.5f, 0f), new Vector2(0f, t.boss ? 108f : 92f), new Vector2(160f, 34f), true);
            t.reveal = UIKit.Text(t.rt, "Reveal", "", 20f, Color.white, TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0f, t.boss ? 108f : 92f), new Vector2(400f, 34f), UIKit.FontZhBold);
            var b = t.pill.gameObject.AddComponent<Button>();
            b.targetGraphic = t.bg;
            b.transition = Selectable.Transition.None;
            b.navigation = new Navigation { mode = Navigation.Mode.None };
            var enemy = e;
            b.onClick.AddListener(() => gm.ClickEnemy(enemy));
            t.pill.gameObject.AddComponent<TagHover>().enemy = e;
            t.appear = 0f;
            return t;
        }

        void SetTagWord(Tag t)
        {
            string w = t.enemy.Word != null ? t.enemy.Word.Word : "";
            if (t.boss)
            {
                var b = (BossEnemy)t.enemy;
                if (b.Defeated) w = "";
                if (t.chip != null) t.chip.text = b.Defeated ? "击破" : "BOSS · 关键词 " + Mathf.Min(b.Effective + 1, b.Keywords.Count) + "/" + b.Keywords.Count;
            }
            if (w == t.shownWord) return;
            t.shownWord = w;
            t.word.text = w;
            float tw = t.word.GetPreferredValues(w).x;
            t.width = tw + (t.boss ? 64f : 40f);
            if (t.boss && t.width < 210f) t.width = 210f;
        }

        void UpdateTags(float dt)
        {
            if (gm == null || gm.cam == null) return;
            // create / remove
            foreach (var e in gm.Enemies)
                if (e != null && !tags.ContainsKey(e)) { var t = MakeTag(e); tags[e] = t; tagOrder.Add(t); }
            for (int i = tagOrder.Count - 1; i >= 0; i--)
            {
                var t = tagOrder[i];
                bool gone = t.enemy == null || (!t.enemy.Alive && t.alpha <= 0.01f);
                if (gone)
                {
                    if (t.rt) Destroy(t.rt.gameObject);
                    tags.Remove(t.enemy);
                    tagOrder.RemoveAt(i);
                }
            }
            bool showTags = gm.State == GameState.Playing || gm.State == GameState.Paused;
            var hover = InputRouter.Instance != null ? InputRouter.Instance.Hover : null;
            foreach (var t in tagOrder)
            {
                var e = t.enemy;
                bool vis;
                t.basePos = ToCanvas(e.TagWorld, out vis);
                SetTagWord(t);
                t.appear = Mathf.MoveTowards(t.appear, 1f, dt / 0.3f);
                bool fading = !e.Alive || e.Doomed;
                t.alpha = Mathf.MoveTowards(t.alpha, fading ? 0f : 1f, dt / (fading ? 0.25f : 0.2f));
                t.group.alpha = showTags && vis ? t.alpha * Mathf.Clamp01(e.Emerge * 2f) : 0f;
                t.group.blocksRaycasts = showTags && e.Alive && !e.Doomed;
                bool vivid = !t.boss && e.Word != null && gm.IsVivid(e.Word);
                bool urgent = e.Progress > 0.74f && !t.boss;
                bool frozen = e.IsFrozen;
                bool hovered = hover == e && gm.SelectedSlot >= 0;
                t.hover = UIKit.Smooth(t.hover, hovered ? 1f : 0f, 18f, dt);
                float w = t.width + (vivid ? 22f : 0f);
                t.pill.sizeDelta = new Vector2(w, t.boss ? 58f : 46f);
                t.word.rectTransform.anchoredPosition = new Vector2(vivid ? 10f : 0f, t.boss ? -2f : 1f);
                t.star.enabled = vivid;
                t.dot.enabled = urgent;
                if (urgent) t.dot.color = UIKit.A(UIKit.Coral, 0.6f + 0.4f * Mathf.Sin(Time.unscaledTime * 10f));
                t.flake.enabled = frozen;
                if (!t.boss)
                {
                    Color bgc = frozen ? UIKit.Hex("#E3F6FF", 0.97f) : (urgent ? UIKit.Hex("#FFF0F1", 0.97f) : UIKit.Paper);
                    t.bg.color = bgc;
                    t.pointer.color = bgc;
                    t.word.color = urgent ? UIKit.Hex("#B3263A") : UIKit.Ink;
                }
                t.ring.color = UIKit.A(UIKit.Amber, t.hover);
                bool revealing = Time.time < e.RevealUntil && !string.IsNullOrEmpty(e.RevealText);
                if (revealing && t.reveal.text != "= " + e.RevealText)
                {
                    t.reveal.text = "= " + e.RevealText;
                    t.revealBg.rectTransform.sizeDelta = new Vector2(t.reveal.GetPreferredValues(t.reveal.text).x + 30f, 34f);
                }
                t.reveal.enabled = revealing;
                t.revealBg.enabled = revealing;
                float shake = Time.time - e.LastWrongTime < 0.4f ? Mathf.Sin(Time.time * 60f) * 8f * (1f - (Time.time - e.LastWrongTime) / 0.4f) : 0f;
                float scale = (0.6f + 0.4f * Ease.OutBack(t.appear)) * (1f + 0.12f * t.hover) * (t.boss ? 1f : Mathf.Lerp(0.9f, 1.06f, Mathf.Clamp01(e.Progress * 1.3f)));
                t.rt.localScale = Vector3.one * scale;
                t.pill.anchoredPosition = new Vector2(shake, 12f);
            }
            // declutter: tags lower on screen (closer to the castle side of the camera) keep their place
            var order = tagOrder.Where(t => t.group.alpha > 0.01f).OrderBy(t => t.basePos.y).ToList();
            var placed = new List<Rect>();
            foreach (var t in order)
            {
                float h = (t.boss ? 58f : 46f) + 10f;
                float w = t.pill.sizeDelta.x * t.rt.localScale.x;
                float want = 0f;
                for (int pass = 0; pass < 6; pass++)
                {
                    var r = new Rect(t.basePos.x - w / 2f, t.basePos.y + want, w, h);
                    bool moved = false;
                    foreach (var o in placed)
                        if (r.Overlaps(o)) { want = o.yMax - t.basePos.y + 2f; moved = true; }
                    if (!moved) break;
                }
                // keep tags below the top HUD cards
                float maxY = root.rect.height * 0.5f - 150f - h;
                if (t.basePos.y + want > maxY) want = maxY - t.basePos.y;
                t.push = UIKit.Smooth(t.push, want, 12f, dt);
                placed.Add(new Rect(t.basePos.x - w / 2f, t.basePos.y + want, w, h));
                t.rt.anchoredPosition = t.basePos + new Vector2(0f, t.push);
                t.pointer.rectTransform.anchoredPosition = new Vector2(0f, 6f);
                t.pointer.enabled = Mathf.Abs(t.push) < 8f;
            }
        }

        // ============================================================ boss sentence panel
        RectTransform bossPanel;
        CanvasGroup bossGroup;
        TextMeshProUGUI bossHeader, bossSentence, bossTranslation, bossProgress;
        Image bossCrown;
        int bossShownCurrent = -2;
        float bossPop;
        bool bossTranslationShown;

        void BuildBossPanel()
        {
            bossPanel = UIKit.Panel(hudLayer, "BossPanel", new Vector2(0.5f, 1f), new Vector2(0f, -24f), new Vector2(980f, 170f), 26, null, true, new Vector2(0.5f, 1f));
            bossGroup = bossPanel.gameObject.AddComponent<CanvasGroup>();
            bossGroup.alpha = 0f;
            bossGroup.blocksRaycasts = false;
            bossCrown = UIKit.Img(bossPanel, "Crown", UIKit.Icon("crown", 64), UIKit.Coral, new Vector2(0f, 1f), new Vector2(40f, -30f), new Vector2(28f, 28f));
            bossHeader = UIKit.Text(bossPanel, "Header", "Boss · 按顺序击中关键词的释义", 20f, UIKit.Coral, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(64f + 300f, -30f), new Vector2(600f, 28f), UIKit.FontZhBold);
            bossHeader.rectTransform.pivot = new Vector2(0f, 0.5f);
            bossHeader.rectTransform.anchoredPosition = new Vector2(64f, -30f);
            bossProgress = UIKit.Text(bossPanel, "Progress", "", 20f, UIKit.TextMid, TextAlignmentOptions.Right, new Vector2(1f, 1f), new Vector2(-150f, -30f), new Vector2(260f, 28f), UIKit.FontZh);
            bossSentence = UIKit.Text(bossPanel, "Sentence", "", 29f, new Color(1f, 1f, 1f, 0.92f), TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -84f), new Vector2(920f, 70f), UIKit.FontEn);
            bossSentence.textWrappingMode = TextWrappingModes.Normal;
            bossSentence.lineSpacing = 16f;
            bossTranslation = UIKit.Text(bossPanel, "Translation", "", 20f, UIKit.TextMid, TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0f, 24f), new Vector2(920f, 30f), UIKit.FontZh);
        }

        public static string BossMarkup(BossSentenceView v)
        {
            var s = v.sentence;
            var sb = new StringBuilder();
            int pos = 0;
            string en = UIKit.FontEn != null ? UIKit.FontEn.name : "";
            string zh = UIKit.FontZhBold != null ? UIKit.FontZhBold.name : "";
            for (int i = 0; i < s.Keywords.Count; i++)
            {
                var k = s.Keywords[i];
                if (k.CharStart < pos) continue;
                sb.Append(s.English.Substring(pos, k.CharStart - pos));
                string word = s.English.Substring(k.CharStart, k.CharLength);
                if (i < v.current)
                    sb.Append("<color=#3EE0A1>").Append(word).Append("</color><font=\"").Append(zh).Append("\"><size=62%><color=#3EE0A1> ").Append(k.Gloss).Append("</color></size></font>");
                else if (i < v.current + v.pending)
                    sb.Append("<color=#FFC34D>").Append(word).Append("</color><size=55%><voffset=0.9em><color=#FFC34D>").Append(i + 1).Append("</color></voffset></size>");
                else if (i == v.current + v.pending && v.active)
                    sb.Append("<mark=#FFC34D38><color=#FFC34D><b>").Append(word).Append("</b></color></mark><size=55%><voffset=0.9em><color=#FFC34D>").Append(i + 1).Append("</color></voffset></size>");
                else
                    sb.Append("<u>").Append(word).Append("</u><size=55%><voffset=0.9em><color=#7F89AA>").Append(i + 1).Append("</color></voffset></size>");
                pos = k.CharStart + k.CharLength;
            }
            if (pos < s.English.Length) sb.Append(s.English.Substring(pos));
            return sb.ToString();
        }

        public struct BossSentenceView
        {
            public Data.BossSentence sentence;
            public int current;
            public int pending;
            public bool active;
        }

        void UpdateBossPanel(float dt)
        {
            bool show = gm.Deck != null && gm.Deck.Boss != null && (gm.Phase == GamePhase.BossIntro || gm.Phase == GamePhase.Boss || (gm.Phase == GamePhase.Ending && gm.Boss != null)) && gm.State != GameState.Victory && gm.State != GameState.Defeat;
            bossGroup.alpha = UIKit.Smooth(bossGroup.alpha, show ? 1f : 0f, 8f, dt);
            if (!show) return;
            int current = gm.Boss != null ? gm.Boss.Current : 0;
            int pending = gm.Boss != null ? gm.Boss.Pending : 0;
            bossPop = Mathf.MoveTowards(bossPop, 0f, dt * 2f);
            if (current * 16 + pending != bossShownCurrent)
            {
                bossShownCurrent = current * 16 + pending;
                var view = new BossSentenceView { sentence = gm.Deck.Boss, current = current, pending = pending, active = true };
                bossSentence.text = BossMarkup(view);
                Vector2 pref = bossSentence.GetPreferredValues(bossSentence.text, 920f, 0f);
                float h = Mathf.Max(40f, pref.y + 4f);
                bossSentence.rectTransform.sizeDelta = new Vector2(920f, h);
                bossPanel.sizeDelta = new Vector2(980f, h + 104f);
                int n = gm.Deck.Boss.Keywords.Count;
                bossProgress.text = "<font=\"" + FontName(UIKit.FontEn) + "\">" + Mathf.Min(current, n) + " / " + n + "</font>";
                bool defeated = gm.Boss != null && gm.Boss.Defeated;
                bossTranslationShown = defeated;
                bossTranslation.text = defeated ? gm.Deck.Boss.Chinese : "<color=#7F89AA>击破 Boss 后揭晓整句译文</color>";
            }
            bossPanel.localScale = Vector3.one * (1f + bossPop * 0.04f);
            int nn = gm.Deck.Boss.Keywords.Count;
            string prog = "敌速 <font=\"" + FontName(UIKit.FontEn) + "\">×" + gm.SpeedMultiplier.ToString("0.00") + "   " + Mathf.Min(current, nn) + " / " + nn + "</font>";
            if (bossProgress.text != prog) bossProgress.text = prog;
            bossCrown.color = Color.Lerp(UIKit.Coral, Color.white, bossPop);
        }
    }
}
