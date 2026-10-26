using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using WordDefense.Data;

namespace WordDefense
{
    public partial class UIRoot
    {
        RectTransform titleScreen, pauseScreen, resultScreen;
        CanvasGroup titleGroup, pauseGroup, resultGroup;
        TextMeshProUGUI titleDbInfo, titleMemInfo, startLabel;
        Button startButton;
        GameState resultFor = GameState.Loading;

        public Button StartButton { get { return startButton; } }
        public Button ResultRestartButton { get; private set; }
        public Button ResultTitleButton { get; private set; }
        public Button PauseResumeButton { get; private set; }
        public Button PauseRestartButton { get; private set; }

        void BuildScreens()
        {
            BuildTitle();
            BuildPause();
            resultScreen = UIKit.Stretch(screenLayer, "Result");
            resultGroup = resultScreen.gameObject.AddComponent<CanvasGroup>();
            resultGroup.alpha = 0f;
            resultScreen.gameObject.SetActive(false);
        }

        // ------------------------------------------------------------ title
        void BuildTitle()
        {
            titleScreen = UIKit.Stretch(screenLayer, "Title");
            titleGroup = titleScreen.gameObject.AddComponent<CanvasGroup>();
            var shade = UIKit.Fill(titleScreen, "Shade", UIKit.HRamp(0.45f), UIKit.A(UIKit.Hex("#0B0E1F"), 0.96f), false);
            shade.rectTransform.localRotation = Quaternion.Euler(0f, 0f, 180f);
            shade.rectTransform.anchorMax = new Vector2(0.78f, 1f);
            UIKit.Fill(titleScreen, "Tint", UIKit.White(), UIKit.A(UIKit.Hex("#0B0E1F"), 0.4f), false);
            UIKit.Fill(titleScreen, "Vignette", UIKit.Vignette(), UIKit.A(UIKit.Hex("#0B0E1F"), 0.55f), false);

            var left = UIKit.Rect(titleScreen, "Left", new Vector2(0f, 0.5f), new Vector2(150f, 20f), new Vector2(860f, 760f), new Vector2(0f, 0.5f));
            UIKit.Text(left, "Kicker", "ENGLISH VOCABULARY  ·  TOWER DEFENSE", 18f, UIKit.Amber, TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(430f, 270f), new Vector2(860f, 30f), UIKit.FontEn, FontStyles.Normal, 6f);
            var logo = UIKit.Text(left, "Logo", "单词守城", 150f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(430f, 160f), new Vector2(860f, 180f), UIKit.FontZhBlack, FontStyles.Normal, 4f);
            logo.enableVertexGradient = true;
            logo.colorGradient = new VertexGradient(Color.white, Color.white, UIKit.Hex("#D8E2FF"), UIKit.Hex("#FFE3A3"));
            UIKit.Text(left, "Latin", "WORD DEFENSE", 40f, UIKit.A(Color.white, 0.75f), TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(430f, 52f), new Vector2(860f, 50f), UIKit.FontEn, FontStyles.Normal, 26f);
            UIKit.Img(left, "Rule", UIKit.HGradient(), UIKit.Amber, new Vector2(0f, 0.5f), new Vector2(110f, 12f), new Vector2(220f, 3f));
            UIKit.Text(left, "Tagline", "看英文，选释义，守住你的城堡。", 32f, UIKit.TextMid, TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(430f, -36f), new Vector2(860f, 44f), UIKit.FontZh);
            startButton = UIKit.Button(left, "StartButton", "开始守城", new Vector2(0f, 0.5f), new Vector2(180f, -150f), new Vector2(360f, 92f), UIKit.Amber, UIKit.Ink, () => gm.StartGame(), 36f);
            startLabel = startButton.transform.Find("Label").GetComponent<TextMeshProUGUI>();
            titleDbInfo = UIKit.Text(left, "DbInfo", "", 20f, UIKit.TextMid, TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(430f, -250f), new Vector2(860f, 28f), UIKit.FontZh);
            titleMemInfo = UIKit.Text(left, "MemInfo", "", 20f, UIKit.TextMid, TextAlignmentOptions.Left, new Vector2(0f, 0.5f), new Vector2(430f, -284f), new Vector2(860f, 28f), UIKit.FontZh);

            var card = UIKit.Panel(titleScreen, "HowTo", new Vector2(1f, 0.5f), new Vector2(-130f, 10f), new Vector2(640f, 600f), 30, null, true, new Vector2(1f, 0.5f));
            UIKit.Text(card, "Head", "怎么玩", 30f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(240f, -52f), new Vector2(400f, 40f));
            string[][] rows =
            {
                new[] { "shell", "点选下方的中文释义炮弹", "键 1–4，每次 3 到 4 个可选" },
                new[] { "pointer", "再点击头顶单词对应的敌人", "答对击倒；答错炮弹被弹开，炮台短暂装填" },
                new[] { "flake", "连续答对 3 次：寒霜齐射", "空格键，全体敌人减速 6 秒" },
                new[] { "star", "快速答对两次：记忆深刻", "此后它的炮弹自动追踪，不用再点敌人" },
                new[] { "crown", "Boss 是一句英文长句", "按顺序击中句中每个关键词的释义" },
            };
            Color[] tint = { UIKit.Amber, UIKit.TextHi, UIKit.Ice, UIKit.Amber, UIKit.Coral };
            for (int i = 0; i < rows.Length; i++)
            {
                float y = -126f - i * 96f;
                UIKit.Img(card, "IconBg" + i, UIKit.Circle(128), UIKit.A(tint[i], 0.14f), new Vector2(0f, 1f), new Vector2(76f, y), new Vector2(60f, 60f));
                var ic = UIKit.Img(card, "Icon" + i, UIKit.Icon(rows[i][0], 96), tint[i], new Vector2(0f, 1f), new Vector2(76f, y), new Vector2(30f, 30f));
                if (rows[i][0] == "pointer") ic.rectTransform.localScale = new Vector3(1f, 1f, 1f);
                UIKit.Text(card, "Row" + i, rows[i][1], 26f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(350f, y + 14f), new Vector2(480f, 34f));
                UIKit.Text(card, "Sub" + i, rows[i][2], 19f, UIKit.TextLow, TextAlignmentOptions.Left, new Vector2(0f, 1f), new Vector2(350f, y - 18f), new Vector2(480f, 28f), UIKit.FontZh);
            }
        }

        // ------------------------------------------------------------ pause
        void BuildPause()
        {
            pauseScreen = UIKit.Stretch(screenLayer, "Pause");
            pauseGroup = pauseScreen.gameObject.AddComponent<CanvasGroup>();
            var dim = UIKit.Fill(pauseScreen, "Dim", UIKit.White(), new Color(0.03f, 0.04f, 0.1f, 0.8f), false);
            dim.raycastTarget = true;
            var p = UIKit.Panel(pauseScreen, "Panel", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(540f, 500f), 32);
            UIKit.Text(p, "Title", "已暂停", 60f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -86f), new Vector2(500f, 80f), UIKit.FontZhBlack);
            UIKit.Text(p, "Sub", "按 Esc 继续", 22f, UIKit.TextLow, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -140f), new Vector2(500f, 30f), UIKit.FontZh);
            PauseResumeButton = UIKit.Button(p, "ResumeButton", "继续", new Vector2(0.5f, 0.5f), new Vector2(0f, -10f), new Vector2(360f, 76f), UIKit.Amber, UIKit.Ink, () => gm.Resume(), 30f);
            PauseRestartButton = UIKit.Button(p, "RestartButton", "重新开始", new Vector2(0.5f, 0.5f), new Vector2(0f, -102f), new Vector2(360f, 70f), UIKit.GlassLight, UIKit.TextHi, () => gm.Restart(true), 28f);
            UIKit.Button(p, "TitleButton", "返回标题", new Vector2(0.5f, 0.5f), new Vector2(0f, -188f), new Vector2(360f, 70f), UIKit.GlassLight, UIKit.TextHi, () => gm.Restart(false), 28f);
        }

        // ------------------------------------------------------------ result
        void BuildResult(bool won)
        {
            for (int i = resultScreen.childCount - 1; i >= 0; i--) Destroy(resultScreen.GetChild(i).gameObject);
            var dim = UIKit.Fill(resultScreen, "Dim", UIKit.Vignette(), new Color(0.03f, 0.04f, 0.1f, 0.8f), false);
            dim.raycastTarget = true;
            UIKit.Fill(resultScreen, "Dim2", UIKit.White(), new Color(0.03f, 0.04f, 0.1f, 0.7f), false);
            var p = UIKit.Panel(resultScreen, "Panel", new Vector2(0.5f, 0.5f), new Vector2(0f, 0f), new Vector2(1280f, 960f), 34);
            Color accent = won ? UIKit.Mint : UIKit.Coral;
            UIKit.Img(p, "Glow", UIKit.RadialGlow(), UIKit.A(accent, 0.16f), new Vector2(0.5f, 1f), new Vector2(0f, -40f), new Vector2(900f, 300f));
            UIKit.Text(p, "Kicker", won ? "VICTORY" : "DEFEAT", 20f, accent, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -48f), new Vector2(600f, 30f), UIKit.FontEn, FontStyles.Normal, 14f);
            UIKit.Text(p, "Title", won ? "守城成功" : "城堡失守", 76f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -110f), new Vector2(900f, 96f), UIKit.FontZhBlack);
            UIKit.Text(p, "Sub", won ? "长句 Boss 已被击破，城堡安然无恙。" : "别灰心：答错和漏掉的词，下一局会优先再出现。", 23f, UIKit.TextMid, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -168f), new Vector2(1000f, 32f), UIKit.FontZh);

            // stats
            int secs = Mathf.RoundToInt(gm.SessionSeconds);
            string[][] stats =
            {
                new[] { "得分", gm.Score.ToString("N0") },
                new[] { "正确率", gm.Accuracy + "%" },
                new[] { "最佳连击", "×" + gm.BestCombo },
                new[] { "用时", (secs / 60) + ":" + (secs % 60).ToString("00") },
            };
            for (int i = 0; i < stats.Length; i++)
            {
                float x = -435f + i * 290f;
                var tile = UIKit.Panel(p, "Stat" + i, new Vector2(0.5f, 1f), new Vector2(x, -262f), new Vector2(270f, 104f), 22, UIKit.GlassLight, false);
                UIKit.Text(tile, "Label", stats[i][0], 20f, UIKit.TextLow, TextAlignmentOptions.Center, new Vector2(0.5f, 1f), new Vector2(0f, -26f), new Vector2(250f, 28f), UIKit.FontZh);
                UIKit.Text(tile, "Value", stats[i][1], 44f, UIKit.TextHi, TextAlignmentOptions.Center, new Vector2(0.5f, 0f), new Vector2(0f, 36f), new Vector2(250f, 54f), UIKit.FontEn);
            }

            // boss sentence
            var bs = gm.Deck != null ? gm.Deck.Boss : null;
            var box = UIKit.Panel(p, "Sentence", new Vector2(0.5f, 1f), new Vector2(0f, -410f), new Vector2(1140f, 140f), 22, UIKit.GlassLight, false);
            if (bs != null)
            {
                int cur = gm.Boss != null ? gm.Boss.Current : 0;
                if (won) cur = bs.Keywords.Count;
                var t = UIKit.Text(box, "En", BossMarkup(new BossSentenceView { sentence = bs, current = cur, active = false }), 27f, UIKit.TextHi, TextAlignmentOptions.Center,
                    new Vector2(0.5f, 1f), new Vector2(0f, -50f), new Vector2(1080f, 70f), UIKit.FontEn);
                t.textWrappingMode = TextWrappingModes.Normal;
                t.enableAutoSizing = true; t.fontSizeMin = 18f; t.fontSizeMax = 27f;
                UIKit.Text(box, "Zh", won ? bs.Chinese : "Boss 未被击破 · 关键词 " + cur + " / " + bs.Keywords.Count, 22f, won ? UIKit.TextMid : UIKit.TextLow, TextAlignmentOptions.Center,
                    new Vector2(0.5f, 0f), new Vector2(0f, 28f), new Vector2(1080f, 32f), UIKit.FontZh);
            }

            // words
            UIKit.Text(p, "WordsHead", "本局单词", 24f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0.5f, 1f), new Vector2(-470f, -520f), new Vector2(200f, 32f));
            UIKit.Text(p, "Legend", "<color=#FFC34D>★</color> 记忆深刻   <color=#3EE0A1>●</color> 答对   <color=#FF5C6C>●</color> 答错或漏掉   条形 = 记忆强度", 18f, UIKit.TextLow, TextAlignmentOptions.Right,
                new Vector2(0.5f, 1f), new Vector2(285f, -520f), new Vector2(600f, 28f), UIKit.FontZh);
            var words = gm.Deck != null ? gm.Deck.Words.Where(w => w.Spawned > 0 || w.IsKeyword).OrderByDescending(w => w.Wrong + w.Missed).ThenByDescending(w => w.Correct).Take(20).ToList() : new System.Collections.Generic.List<SessionWord>();
            for (int i = 0; i < words.Count; i++)
            {
                var w = words[i];
                int col = i / 10, row = i % 10;
                float x = col == 0 ? -285f : 285f;
                float y = -560f - row * 28f;
                bool bad = w.Wrong + w.Missed > 0;
                bool good = w.Correct > 0;
                Color dot = bad ? UIKit.Coral : (good ? UIKit.Mint : UIKit.TextLow);
                UIKit.Img(p, "Dot", UIKit.Circle(32), dot, new Vector2(0.5f, 1f), new Vector2(x - 255f, y), new Vector2(10f, 10f));
                UIKit.Text(p, "W", w.Word, 21f, UIKit.TextHi, TextAlignmentOptions.Left, new Vector2(0.5f, 1f), new Vector2(x - 150f, y), new Vector2(190f, 28f), UIKit.FontEn);
                UIKit.Text(p, "G", w.Gloss, 19f, UIKit.TextMid, TextAlignmentOptions.Left, new Vector2(0.5f, 1f), new Vector2(x + 40f, y), new Vector2(170f, 28f), UIKit.FontZh);
                float strength = gm.Memory != null ? gm.Memory.Strength(w.Word) : 0f;
                UIKit.Img(p, "Track", UIKit.Rounded(3), new Color(1f, 1f, 1f, 0.08f), new Vector2(0.5f, 1f), new Vector2(x + 180f, y), new Vector2(90f, 6f), true);
                var bar = UIKit.Img(p, "Bar", UIKit.Rounded(3), gm.IsVivid(w) ? UIKit.Amber : UIKit.Mint, new Vector2(0.5f, 1f), new Vector2(x + 135f, y), new Vector2(Mathf.Max(6f, 90f * strength), 6f), true);
                bar.rectTransform.pivot = new Vector2(0f, 0.5f);
                if (gm.IsVivid(w)) UIKit.Img(p, "Star", UIKit.Icon("star", 64), UIKit.Amber, new Vector2(0.5f, 1f), new Vector2(x + 245f, y), new Vector2(18f, 18f));
            }

            ResultRestartButton = UIKit.Button(p, "AgainButton", "再来一局", new Vector2(0.5f, 0f), new Vector2(-150f, 58f), new Vector2(270f, 74f), UIKit.Amber, UIKit.Ink, () => gm.Restart(true), 30f);
            ResultTitleButton = UIKit.Button(p, "TitleButton", "返回标题", new Vector2(0.5f, 0f), new Vector2(150f, 58f), new Vector2(270f, 74f), UIKit.GlassLight, UIKit.TextHi, () => gm.Restart(false), 28f);
        }

        // ------------------------------------------------------------ state
        void RefreshScreens()
        {
            if (gm.State == GameState.Victory || gm.State == GameState.Defeat)
            {
                if (resultFor != gm.State)
                {
                    resultFor = gm.State;
                    BuildResult(gm.State == GameState.Victory);
                    resultGroup.alpha = 0f;
                }
            }
        }

        float resultT;

        void UpdateScreens(float dt)
        {
            bool title = gm.State == GameState.Title || gm.State == GameState.Loading;
            titleGroup.alpha = UIKit.Smooth(titleGroup.alpha, title ? 1f : 0f, 7f, dt);
            titleGroup.blocksRaycasts = title;
            titleScreen.gameObject.SetActive(titleGroup.alpha > 0.01f || title);
            if (title)
            {
                bool ready = Vocabulary.Ready;
                startButton.interactable = ready;
                startLabel.text = ready ? "开始守城" : (Vocabulary.Failed ? "词库读取失败" : "词库加载中…");
                if (ready)
                {
                    var st = Vocabulary.Stats;
                    string src = System.IO.Path.GetFileName(Vocabulary.SourcePath);
                    bool docs = Vocabulary.SourcePath.IndexOf("StreamingAssets", System.StringComparison.OrdinalIgnoreCase) < 0;
                    titleDbInfo.text = "词库  " + src + (docs ? "（文档文件夹）" : "（随游戏附带）") + "  ·  中等难度 difficulty " + st.Band + "  ·  " + Vocabulary.Pool.Count.ToString("N0") + " 个单词  ·  " + Vocabulary.BossSentences.Count + " 个 Boss 长句";
                    var mem = gm.Memory;
                    if (mem != null)
                        titleMemInfo.text = mem.Games > 0 ? "学习记录：已玩 " + mem.Games + " 局，胜 " + mem.Wins + " 局，练过 " + mem.Count + " 个词" : "学习记录：第一次守城，祝你好运！";
                }
                else if (Vocabulary.Failed) titleDbInfo.text = "<color=#FF5C6C>" + Vocabulary.Error + "</color>";
            }
            bool paused = gm.State == GameState.Paused;
            pauseGroup.alpha = UIKit.Smooth(pauseGroup.alpha, paused ? 1f : 0f, 12f, dt);
            pauseGroup.blocksRaycasts = paused;
            pauseScreen.gameObject.SetActive(paused || pauseGroup.alpha > 0.01f);
            bool result = gm.State == GameState.Victory || gm.State == GameState.Defeat;
            resultScreen.gameObject.SetActive(result);
            if (result)
            {
                resultT += dt;
                resultGroup.alpha = UIKit.Smooth(resultGroup.alpha, 1f, 6f, dt);
                resultGroup.blocksRaycasts = true;
                resultScreen.localScale = Vector3.one * Mathf.Lerp(1.04f, 1f, Ease.OutCubic(Mathf.Clamp01(resultT / 0.5f)));
            }
            else resultT = 0f;
        }
    }
}
