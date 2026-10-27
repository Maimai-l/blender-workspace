using System.Collections.Generic;
using System.Linq;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace WordDefense
{
    public partial class UIRoot
    {
        // ============================================================ headword labels above the enemies
        class Tag
        {
            public Enemy enemy;
            public RectTransform rt, label;
            public Image shadow, paper, outline, pointer, underline, star, flake, crown, crownHalo;
            public TextMeshProUGUI word, reveal;
            public CanvasGroup group;
            public float wordW, revealW, revealK, push, appear, hover, alpha = 1f;
            public Vector2 basePos;
            public bool boss;
            public string shownWord, shownReveal;
        }
        readonly Dictionary<Enemy, Tag> tags = new Dictionary<Enemy, Tag>();
        readonly List<Tag> tagOrder = new List<Tag>();
        const float TagH = 48f, BossTagH = 54f, TagPad = 18f;

        public bool TagScreenPos(Enemy e, out Vector2 screen)
        {
            Tag t;
            screen = Vector2.zero;
            if (e == null || !tags.TryGetValue(e, out t) || t.rt == null) return false;
            screen = ScreenOf(t.label);
            return true;
        }

        Tag MakeTag(Enemy e)
        {
            var t = new Tag { enemy = e, boss = e is BossEnemy };
            float h = t.boss ? BossTagH : TagH;
            Color paper = t.boss ? UIKit.Ink : UIKit.Paper;
            t.rt = UIKit.Rect(tagLayer, "Headword_" + (e.Word != null ? e.Word.Word : "?"), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(200f, h + 14f), new Vector2(0.5f, 0f));
            t.group = t.rt.gameObject.AddComponent<CanvasGroup>();
            t.label = UIKit.Rect(t.rt, "Label", new Vector2(0.5f, 0f), new Vector2(0f, 12f), new Vector2(200f, h), new Vector2(0.5f, 0f));
            t.shadow = UIKit.PaperShadow(t.label, 6);
            t.outline = UIKit.Fill(t.label, "Target", UIKit.Rounded(8, 3f), UIKit.InkA(0f), true, -5f);
            t.paper = UIKit.Fill(t.label, "Paper", UIKit.Rounded(6), paper);
            t.paper.raycastTarget = true;
            t.pointer = UIKit.Img(t.rt, "Pointer", UIKit.Icon("pointer", 32), paper, new Vector2(0.5f, 0f), new Vector2(0f, 6f), new Vector2(18f, 12f));
            t.underline = UIKit.Img(t.label, "Urgent", UIKit.Rounded(2), UIKit.RedPen, new Vector2(0.5f, 0f), new Vector2(0f, 7f), new Vector2(40f, 3f), true);
            t.star = UIKit.Img(t.label, "Star", UIKit.Icon("star", 64), UIKit.Gold, new Vector2(0f, 0.5f), new Vector2(TagPad + 9f, 1f), new Vector2(20f, 20f));
            t.flake = UIKit.Img(t.label, "Frozen", UIKit.Icon("flake", 64), UIKit.Frost, new Vector2(1f, 1f), new Vector2(-2f, -2f), new Vector2(22f, 22f));
            t.word = UIKit.Text(t.label, "Word", "", t.boss ? 34f : 32f, t.boss ? UIKit.Paper : UIKit.Ink, TextAlignmentOptions.Left,
                new Vector2(0f, 0.5f), new Vector2(TagPad, 2f), new Vector2(400f, h), UIKit.Latin, new Vector2(0f, 0.5f));
            t.reveal = UIKit.Text(t.label, "Meaning", "", 26f, UIKit.RedPen, TextAlignmentOptions.Left,
                new Vector2(0f, 0.5f), new Vector2(TagPad, 1f), new Vector2(400f, h), UIKit.SongBold, new Vector2(0f, 0.5f));
            if (t.boss)
            {
                t.crownHalo = UIKit.Img(t.rt, "CrownHalo", UIKit.IconHalo("crown", 128), UIKit.A(UIKit.Paper, 0.85f), new Vector2(0.5f, 0f), new Vector2(0f, 12f + h + 16f), new Vector2(30f, 30f));
                t.crown = UIKit.Img(t.rt, "Crown", UIKit.Icon("crown", 128), UIKit.GoldInk, new Vector2(0.5f, 0f), new Vector2(0f, 12f + h + 16f), new Vector2(30f, 30f));
            }
            var b = t.label.gameObject.AddComponent<Button>();
            b.targetGraphic = t.paper;
            b.transition = Selectable.Transition.None;
            b.navigation = new Navigation { mode = Navigation.Mode.None };
            var enemy = e;
            b.onClick.AddListener(() => gm.ClickEnemy(enemy));
            t.label.gameObject.AddComponent<TagHover>().enemy = e;
            t.appear = 0f;
            return t;
        }

        void SetTagWord(Tag t)
        {
            string w = t.enemy.Word != null ? t.enemy.Word.Word : "";
            if (t.boss)
            {
                var b = (BossEnemy)t.enemy;
                w = b.Defeated || b.TargetWord == null ? "" : b.TargetWord.Word + "<sup><color=" + UIKit.Css(UIKit.Gold) + ">" + Mathf.Min(b.Effective + 1, b.Keywords.Count) + "</color></sup>";
            }
            if (w == t.shownWord) return;
            t.shownWord = w;
            t.word.text = w;
            t.wordW = t.word.GetPreferredValues(w).x;
        }

        void UpdateTags(float dt)
        {
            if (gm == null || gm.cam == null) return;
            foreach (var e in gm.Enemies)
                if (e != null && !tags.ContainsKey(e)) { var t = MakeTag(e); tags[e] = t; tagOrder.Add(t); }
            for (int i = tagOrder.Count - 1; i >= 0; i--)
            {
                var t = tagOrder[i];
                if (t.enemy == null || (!t.enemy.Alive && t.alpha <= 0.01f))
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
                t.appear = Mathf.MoveTowards(t.appear, 1f, dt / 0.25f);
                bool fading = !e.Alive || e.Doomed;
                t.alpha = Mathf.MoveTowards(t.alpha, fading ? 0f : 1f, dt / (fading ? 0.25f : 0.2f));
                t.group.alpha = showTags && vis ? t.alpha * Mathf.Clamp01(e.Emerge * 2f) : 0f;
                t.group.blocksRaycasts = showTags && e.Alive && !e.Doomed;
                bool vivid = !t.boss && e.Word != null && gm.IsVivid(e.Word);
                bool urgent = e.Progress > 0.74f && !t.boss;
                bool frozen = e.IsFrozen;
                bool targeted = hover == e && gm.SelectedSlot >= 0;
                t.hover = UIKit.Smooth(t.hover, targeted ? 1f : 0f, 18f, dt);

                // after a wrong answer the label shows the word's real meaning in red, like a correction in the margin
                bool revealing = Time.time < e.RevealUntil && !string.IsNullOrEmpty(e.RevealText);
                if (revealing && t.shownReveal != e.RevealText)
                {
                    t.shownReveal = e.RevealText;
                    t.reveal.text = e.RevealText;
                    t.reveal.color = t.boss ? UIKit.Hex("#FF9AA4") : UIKit.RedPen;   // on the Boss's ink label the red pen needs to be lighter
                    t.revealW = t.reveal.GetPreferredValues(e.RevealText).x;
                }
                t.revealK = UIKit.Smooth(t.revealK, revealing ? 1f : 0f, 14f, dt);
                t.reveal.enabled = t.revealK > 0.02f;
                t.reveal.alpha = Mathf.Clamp01(t.revealK * 1.6f - 0.4f);

                float starW = vivid ? 26f : 0f;
                float w = TagPad * 2f + starW + t.wordW + t.revealK * (14f + t.revealW);
                float h = t.boss ? BossTagH : TagH;
                t.label.sizeDelta = new Vector2(w, h);
                t.word.rectTransform.anchoredPosition = new Vector2(TagPad + starW, 2f);
                t.reveal.rectTransform.anchoredPosition = new Vector2(TagPad + starW + t.wordW + 14f, 1f);
                t.star.enabled = vivid;
                t.flake.enabled = frozen;
                t.underline.enabled = urgent;
                if (urgent)
                {
                    t.underline.rectTransform.sizeDelta = new Vector2(t.wordW, 3f);
                    t.underline.rectTransform.anchoredPosition = new Vector2(-w / 2f + TagPad + starW + t.wordW / 2f, 8f);
                }
                if (!t.boss)
                {
                    Color pc = frozen ? UIKit.Hex("#E6F2FB") : UIKit.Paper;
                    t.paper.color = pc;
                    t.pointer.color = pc;
                }
                t.outline.color = UIKit.InkA(t.hover);
                float shake = Time.time - e.LastWrongTime < 0.4f ? Mathf.Sin(Time.time * 60f) * 7f * (1f - (Time.time - e.LastWrongTime) / 0.4f) : 0f;
                float scale = (0.85f + 0.15f * Ease.OutCubic(t.appear)) * (1f + 0.06f * t.hover) * (t.boss ? 1f : Mathf.Lerp(0.92f, 1.04f, Mathf.Clamp01(e.Progress * 1.3f)));
                t.rt.localScale = Vector3.one * scale;
                t.label.anchoredPosition = new Vector2(shake, 12f);
            }
            // declutter: labels lower on screen keep their place, the others step up out of the way
            var order = tagOrder.Where(t => t.group.alpha > 0.01f).OrderBy(t => t.basePos.y).ToList();
            var placed = new List<Rect>();
            foreach (var t in order)
            {
                float h = (t.boss ? BossTagH : TagH) + 10f;
                float w = t.label.sizeDelta.x * t.rt.localScale.x;
                float want = 0f;
                for (int pass = 0; pass < 6; pass++)
                {
                    var r = new Rect(t.basePos.x - w / 2f, t.basePos.y + want, w, h);
                    bool moved = false;
                    foreach (var o in placed)
                        if (r.Overlaps(o)) { want = o.yMax - t.basePos.y + 2f; moved = true; }
                    if (!moved) break;
                }
                float maxY = root.rect.height * 0.5f - 130f - h;   // stay below the top line of the HUD
                if (t.basePos.y + want > maxY) want = maxY - t.basePos.y;
                t.push = UIKit.Smooth(t.push, want, 12f, dt);
                placed.Add(new Rect(t.basePos.x - w / 2f, t.basePos.y + want, w, h));
                t.rt.anchoredPosition = t.basePos + new Vector2(0f, t.push);
                t.pointer.enabled = Mathf.Abs(t.push) < 8f;
            }
        }

        // ============================================================ the Boss: an example sentence, keywords numbered in reading order
        RectTransform bossStrip;
        CanvasGroup bossGroup;
        TextMeshProUGUI bossSentence, bossTranslation;
        int bossShownKey = -2;
        float bossPop;

        void BuildBossStrip()
        {
            bossStrip = UIKit.Rect(hudLayer, "BossSentence", new Vector2(0.5f, 1f), new Vector2(0f, -28f), new Vector2(1100f, 110f), new Vector2(0.5f, 1f));
            bossGroup = bossStrip.gameObject.AddComponent<CanvasGroup>();
            bossGroup.alpha = 0f;
            bossGroup.blocksRaycasts = false;
            UIKit.PaperShadow(bossStrip, 6);
            UIKit.Fill(bossStrip, "Paper", UIKit.Rounded(6), UIKit.Paper);
            bossSentence = UIKit.Text(bossStrip, "Sentence", "", 30f, UIKit.Ink, TextAlignmentOptions.Center,
                new Vector2(0.5f, 1f), new Vector2(0f, -22f), new Vector2(1040f, 60f), UIKit.LatinItalic, new Vector2(0.5f, 1f));
            bossSentence.textWrappingMode = TextWrappingModes.Normal;
            bossSentence.lineSpacing = 6f;
            bossTranslation = UIKit.Text(bossStrip, "Translation", "", 24f, UIKit.InkA(0.78f), TextAlignmentOptions.Center,
                new Vector2(0.5f, 0f), new Vector2(0f, 20f), new Vector2(1040f, 34f), UIKit.Song, new Vector2(0.5f, 0f));
        }

        public struct BossSentenceView
        {
            public Data.BossSentence sentence;
            public int current;
            public int pending;
            public bool active;
        }

        /// <summary>The sentence with its keywords set in bold italic and numbered; hit keywords turn gold and carry their meaning.</summary>
        public static string BossMarkup(BossSentenceView v)
        {
            var s = v.sentence;
            var sb = new StringBuilder();
            int pos = 0;
            string gold = UIKit.Css(UIKit.GoldInk), faint = UIKit.Css(UIKit.InkA(0.5f));
            for (int i = 0; i < s.Keywords.Count; i++)
            {
                var k = s.Keywords[i];
                if (k.CharStart < pos) continue;
                sb.Append(s.English.Substring(pos, k.CharStart - pos));
                string word = UIKit.Tag(UIKit.LatinBoldItalic, s.English.Substring(k.CharStart, k.CharLength));
                string num = "<sup>" + (i + 1) + "</sup>";
                if (i < v.current)
                    sb.Append("<color=").Append(gold).Append(">").Append(word).Append(num).Append(UIKit.Tag(UIKit.SongBold, "<size=72%> " + k.Gloss + "</size>")).Append("</color>");
                else if (i < v.current + v.pending)
                    sb.Append("<color=").Append(gold).Append(">").Append(word).Append(num).Append("</color>");
                else if (i == v.current + v.pending && v.active)
                    sb.Append("<u>").Append(word).Append("</u>").Append(num);
                else
                    sb.Append(word).Append("<color=").Append(faint).Append(">").Append(num).Append("</color>");
                pos = k.CharStart + k.CharLength;
            }
            if (pos < s.English.Length) sb.Append(s.English.Substring(pos));
            return sb.ToString();
        }

        void UpdateBossStrip(float dt)
        {
            bool show = gm.Deck != null && gm.Deck.Boss != null && (gm.Phase == GamePhase.BossIntro || gm.Phase == GamePhase.Boss || (gm.Phase == GamePhase.Ending && gm.Boss != null))
                        && gm.State != GameState.Victory && gm.State != GameState.Defeat;
            bossGroup.alpha = UIKit.Smooth(bossGroup.alpha, show ? 1f : 0f, 8f, dt);
            if (!show) return;
            int current = gm.Boss != null ? gm.Boss.Current : 0;
            int pending = gm.Boss != null ? gm.Boss.Pending : 0;
            bool defeated = gm.Boss != null && gm.Boss.Defeated;
            bossPop = Mathf.MoveTowards(bossPop, 0f, dt * 2f);
            int key = current * 16 + pending + (defeated ? 1000 : 0);
            if (key != bossShownKey)
            {
                bossShownKey = key;
                bossSentence.text = BossMarkup(new BossSentenceView { sentence = gm.Deck.Boss, current = current, pending = pending, active = !defeated });
                bossSentence.ForceMeshUpdate();
                Vector2 pref = new Vector2(bossSentence.preferredWidth, bossSentence.preferredHeight);
                float h = Mathf.Max(40f, pref.y + 4f);
                bossSentence.rectTransform.sizeDelta = new Vector2(1040f, h);
                bossTranslation.text = defeated ? gm.Deck.Boss.Chinese : "";
                float w = Mathf.Clamp(pref.x + 80f, 520f, 1100f);
                bossStrip.sizeDelta = new Vector2(w, h + 44f + (defeated ? 44f : 0f));
            }
            bossStrip.localScale = Vector3.one * (1f + bossPop * 0.03f);
        }
    }
}
