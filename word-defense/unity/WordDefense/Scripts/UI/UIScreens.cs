using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;
using WordDefense.Data;

namespace WordDefense
{
    public partial class UIRoot
    {
        RectTransform titleScreen, rulesScreen, pauseScreen, resultScreen;
        CanvasGroup titleGroup, rulesGroup, pauseGroup, resultGroup;
        TextMeshProUGUI titleStatus;
        Button startButton;
        bool rulesOpen;
        GameState resultFor = GameState.Loading;

        public Button StartButton { get { return startButton; } }
        public Button RulesButton { get; private set; }
        public Button RulesCloseButton { get; private set; }
        public bool RulesOpen { get { return rulesOpen; } }
        public Button ResultRestartButton { get; private set; }
        public Button ResultTitleButton { get; private set; }
        public Button PauseResumeButton { get; private set; }
        public Button PauseRestartButton { get; private set; }

        void BuildScreens()
        {
            BuildTitle();
            BuildRules();
            BuildPause();
            resultScreen = UIKit.Stretch(screenLayer, "Result");
            resultGroup = resultScreen.gameObject.AddComponent<CanvasGroup>();
            resultGroup.alpha = 0f;
            resultScreen.gameObject.SetActive(false);
        }

        // ------------------------------------------------------------ title: the name, one line, start
        void BuildTitle()
        {
            titleScreen = UIKit.Stretch(screenLayer, "Title");
            titleGroup = titleScreen.gameObject.AddComponent<CanvasGroup>();
            var page = UIKit.Fill(titleScreen, "Page", UIKit.PageRamp(1.4f), UIKit.A(UIKit.Paper, 0.97f), false);
            page.rectTransform.anchorMax = new Vector2(0.68f, 1f);
            var left = UIKit.Rect(titleScreen, "Column", new Vector2(0f, 0.5f), new Vector2(156f, 0f), new Vector2(900f, 600f), new Vector2(0f, 0.5f));
            UIKit.Text(left, "Name", "单词守城", 176f, UIKit.Ink, TextAlignmentOptions.Left,
                new Vector2(0f, 0.5f), new Vector2(-8f, 128f), new Vector2(900f, 210f), UIKit.SongBlack, new Vector2(0f, 0.5f));
            UIKit.Halo(UIKit.Text(left, "Line", "看单词，选释义，守住城堡", 34f, UIKit.InkA(0.82f), TextAlignmentOptions.Left,
                new Vector2(0f, 0.5f), new Vector2(0f, 4f), new Vector2(900f, 50f), UIKit.Song, new Vector2(0f, 0.5f)));
            startButton = UIKit.Button(left, "StartButton", "开始游戏", new Vector2(0f, 0.5f), new Vector2(0f, -112f), new Vector2(300f, 80f),
                UIKit.ButtonStyle.Primary, () => gm.StartGame(), 32f, new Vector2(0f, 0.5f));
            RulesButton = UIKit.Button(left, "RulesButton", "玩法", new Vector2(0f, 0.5f), new Vector2(316f, -112f), new Vector2(160f, 80f),
                UIKit.ButtonStyle.Secondary, () => rulesOpen = true, 32f, new Vector2(0f, 0.5f));
            titleStatus = UIKit.Text(left, "Status", "", 24f, UIKit.InkA(0.6f), TextAlignmentOptions.Left,
                new Vector2(0f, 0.5f), new Vector2(0f, -196f), new Vector2(900f, 36f), UIKit.Song, new Vector2(0f, 0.5f));
        }

        // ------------------------------------------------------------ 玩法: one plain sentence per rule, and the keys
        void BuildRules()
        {
            rulesScreen = UIKit.Stretch(screenLayer, "Rules");
            rulesGroup = rulesScreen.gameObject.AddComponent<CanvasGroup>();
            rulesGroup.alpha = 0f;
            var dim = UIKit.Fill(rulesScreen, "Dim", UIKit.White(), UIKit.InkA(0.28f), false);
            dim.raycastTarget = true;
            const float W = 900f, Pad = 72f, TextW = W - 2f * Pad;
            var sheet = UIKit.Rect(rulesScreen, "Sheet", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(W, 700f));
            UIKit.PaperShadow(sheet, 6, 1.4f);
            UIKit.Fill(sheet, "Paper", UIKit.Rounded(6), UIKit.Paper).raycastTarget = true;
            UIKit.Text(sheet, "Heading", "玩法", 52f, UIKit.Ink, TextAlignmentOptions.Left,
                new Vector2(0f, 1f), new Vector2(Pad, -84f), new Vector2(600f, 70f), UIKit.SongBlack, new Vector2(0f, 0.5f));
            string[] rules =
            {
                "点下方的一个释义，再点它对应的单词",
                "敌人走到城堡会削减耐久，耐久归零即失败",
                "连续答对 3 次后，可以让所有敌人减速",
                "又快又准答对的单词会记忆深刻：它的释义变为金色，点击后自动追踪目标",
                "Boss 是一个英文句子，要按顺序击中句中关键词的释义",
            };
            float y = -146f;
            for (int i = 0; i < rules.Length; i++)
            {
                var t = UIKit.Text(sheet, "Rule" + (i + 1), rules[i], 28f, UIKit.Ink, TextAlignmentOptions.TopLeft,
                    new Vector2(0f, 1f), new Vector2(Pad, y), new Vector2(TextW, 40f), UIKit.Song, new Vector2(0f, 1f));
                t.textWrappingMode = TextWrappingModes.Normal;
                t.lineSpacing = 6f;
                t.ForceMeshUpdate();
                float h = t.preferredHeight;
                t.rectTransform.sizeDelta = new Vector2(TextW, h);
                y -= h + 22f;
            }
            y -= 22f;
            string[][] keys = { new[] { "1 – 4", "选择释义" }, new[] { "空格", "减速" }, new[] { "Esc", "暂停" }, new[] { "右键", "取消选择" } };
            for (int i = 0; i < keys.Length; i++)
            {
                float x = Pad + (i % 2) * 340f, ky = y - (i / 2) * 56f - 19f;
                var cap = UIKit.Keycap(sheet, "Key" + i, keys[i][0], new Vector2(0f, 1f), new Vector2(x, ky), 38f, new Vector2(0f, 0.5f));
                UIKit.Text(sheet, "KeyLabel" + i, keys[i][1], 24f, UIKit.InkA(0.72f), TextAlignmentOptions.Left,
                    new Vector2(0f, 1f), new Vector2(x + cap.sizeDelta.x + 14f, ky), new Vector2(240f, 38f), UIKit.Song, new Vector2(0f, 0.5f));
            }
            y -= 2f * 56f + 24f;
            RulesCloseButton = UIKit.Button(sheet, "CloseButton", "关闭", new Vector2(1f, 0f), new Vector2(-Pad, 56f), new Vector2(160f, 64f),
                UIKit.ButtonStyle.Primary, () => rulesOpen = false, 28f, new Vector2(1f, 0f));
            sheet.sizeDelta = new Vector2(W, -y + 56f + 64f + 8f);
            rulesScreen.gameObject.SetActive(false);
        }

        // ------------------------------------------------------------ pause
        void BuildPause()
        {
            pauseScreen = UIKit.Stretch(screenLayer, "Pause");
            pauseGroup = pauseScreen.gameObject.AddComponent<CanvasGroup>();
            var dim = UIKit.Fill(pauseScreen, "Page", UIKit.White(), UIKit.A(UIKit.Paper, 0.88f), false);
            dim.raycastTarget = true;
            UIKit.Text(pauseScreen, "Title", "已暂停", 84f, UIKit.Ink, TextAlignmentOptions.Center,
                new Vector2(0.5f, 0.5f), new Vector2(0f, 160f), new Vector2(800f, 110f), UIKit.SongBlack);
            PauseResumeButton = UIKit.Button(pauseScreen, "ResumeButton", "继续", new Vector2(0.5f, 0.5f), new Vector2(0f, 20f), new Vector2(340f, 80f),
                UIKit.ButtonStyle.Primary, () => gm.Resume(), 32f);
            PauseRestartButton = UIKit.Button(pauseScreen, "RestartButton", "重新开始", new Vector2(0.5f, 0.5f), new Vector2(0f, -76f), new Vector2(340f, 72f),
                UIKit.ButtonStyle.Secondary, () => gm.Restart(true), 28f);
            UIKit.Button(pauseScreen, "TitleButton", "返回标题", new Vector2(0.5f, 0.5f), new Vector2(0f, -164f), new Vector2(340f, 72f),
                UIKit.ButtonStyle.Secondary, () => gm.Restart(false), 28f);
        }

        // ------------------------------------------------------------ result: outcome, numbers, the sentence, the words
        void BuildResult(bool won)
        {
            for (int i = resultScreen.childCount - 1; i >= 0; i--) Destroy(resultScreen.GetChild(i).gameObject);
            resultScreen.gameObject.SetActive(true);   // text is measured below, which needs an active hierarchy (alpha is still 0)
            var page = UIKit.Fill(resultScreen, "Page", UIKit.White(), UIKit.A(UIKit.Paper, 0.95f), false);
            page.raycastTarget = true;
            var col = UIKit.Rect(resultScreen, "Column", new Vector2(0.5f, 1f), new Vector2(0f, 0f), new Vector2(1500f, 1080f), new Vector2(0.5f, 1f));
            float y = -136f;
            UIKit.Text(col, "Title", won ? "守城成功" : "城堡失守", 92f, UIKit.Ink, TextAlignmentOptions.Left,
                new Vector2(0f, 1f), new Vector2(-6f, y), new Vector2(1000f, 120f), UIKit.SongBlack, new Vector2(0f, 0.5f));

            // the numbers, as a small label/value grid
            int secs = Mathf.RoundToInt(gm.SessionSeconds);
            string[][] stats =
            {
                new[] { "得分", gm.Score.ToString("N0") },
                new[] { "正确率", gm.Accuracy + "%" },
                new[] { "最高连击", gm.BestCombo.ToString() },
                new[] { "用时", (secs / 60) + ":" + (secs % 60).ToString("00") },
            };
            y -= 104f;
            for (int i = 0; i < stats.Length; i++)
            {
                float x = i * 250f;
                UIKit.Text(col, "Label" + i, stats[i][0], 22f, UIKit.InkA(0.58f), TextAlignmentOptions.Left,
                    new Vector2(0f, 1f), new Vector2(x, y), new Vector2(240f, 30f), UIKit.Song, new Vector2(0f, 0.5f));
                UIKit.Text(col, "Value" + i, stats[i][1], 54f, UIKit.Ink, TextAlignmentOptions.Left,
                    new Vector2(0f, 1f), new Vector2(x - 2f, y - 50f), new Vector2(240f, 64f), UIKit.Latin, new Vector2(0f, 0.5f));
            }
            y -= 108f;
            Rule(col, y);

            // the Boss sentence and, once it is broken, its translation
            var bs = gm.Deck != null ? gm.Deck.Boss : null;
            if (bs != null && won)
            {
                y -= 34f;
                var en = UIKit.Text(col, "Sentence", BossMarkup(new BossSentenceView { sentence = bs, current = bs.Keywords.Count, active = false }), 34f, UIKit.Ink,
                    TextAlignmentOptions.TopLeft, new Vector2(0f, 1f), new Vector2(0f, y), new Vector2(1500f, 100f), UIKit.LatinItalic, new Vector2(0f, 1f));
                en.textWrappingMode = TextWrappingModes.Normal;
                en.lineSpacing = 4f;
                en.ForceMeshUpdate();
                float h = Mathf.Max(en.preferredHeight, 44f);
                en.rectTransform.sizeDelta = new Vector2(1500f, h);
                y -= h + 14f;
                UIKit.Text(col, "Translation", bs.Chinese, 28f, UIKit.InkA(0.78f), TextAlignmentOptions.TopLeft,
                    new Vector2(0f, 1f), new Vector2(0f, y), new Vector2(1500f, 40f), UIKit.Song, new Vector2(0f, 1f));
                y -= 70f;
                Rule(col, y);
            }

            // the words of this game: red pen for mistakes, gold for 记忆深刻
            y -= 46f;
            UIKit.Text(col, "WordsHeading", "本局单词", 28f, UIKit.Ink, TextAlignmentOptions.Left,
                new Vector2(0f, 1f), new Vector2(0f, y), new Vector2(400f, 40f), UIKit.SongBold, new Vector2(0f, 0.5f));
            y -= 54f;
            var words = gm.Deck != null
                ? gm.Deck.Words.Where(w => w.Spawned > 0 || w.IsKeyword).OrderByDescending(w => w.Wrong + w.Missed).ThenByDescending(w => gm.IsVivid(w)).ThenByDescending(w => w.Correct).Take(20).ToList()
                : new System.Collections.Generic.List<SessionWord>();
            const int perCol = 5;
            float listBottom = y - (Mathf.Min(words.Count, perCol) - 1) * 44f;
            for (int i = 0; i < words.Count; i++)
            {
                var w = words[i];
                float x = (i / perCol) * 380f;
                float wy = y - (i % perCol) * 44f;
                bool bad = w.Wrong + w.Missed > 0;
                bool vivid = gm.IsVivid(w);
                var t = UIKit.Text(col, "Word" + i, UIKit.Tag(UIKit.Latin, w.Word) + "  " + w.Gloss, 26f, UIKit.Ink, TextAlignmentOptions.Left,
                    new Vector2(0f, 1f), new Vector2(x + 30f, wy), new Vector2(340f, 40f), UIKit.Song, new Vector2(0f, 0.5f));
                if (bad) UIKit.Img(col, "Mark" + i, UIKit.Icon("cross", 64), UIKit.RedPen, new Vector2(0f, 1f), new Vector2(x + 10f, wy), new Vector2(20f, 20f));
                else if (vivid) UIKit.Img(col, "Mark" + i, UIKit.Icon("star", 64), UIKit.Gold, new Vector2(0f, 1f), new Vector2(x + 10f, wy), new Vector2(22f, 22f));
            }

            float by = Mathf.Max(listBottom - 110f, -1080f + 96f);
            ResultRestartButton = UIKit.Button(col, "AgainButton", "再来一局", new Vector2(0f, 1f), new Vector2(0f, by), new Vector2(300f, 80f),
                UIKit.ButtonStyle.Primary, () => gm.Restart(true), 32f, new Vector2(0f, 0.5f));
            ResultTitleButton = UIKit.Button(col, "TitleButton", "返回标题", new Vector2(0f, 1f), new Vector2(316f, by), new Vector2(220f, 80f),
                UIKit.ButtonStyle.Secondary, () => gm.Restart(false), 30f, new Vector2(0f, 0.5f));
        }

        static void Rule(Transform parent, float y)
        {
            var r = UIKit.Img(parent, "Rule", UIKit.White(), UIKit.InkA(0.14f), new Vector2(0f, 1f), new Vector2(0f, y), new Vector2(1500f, 2f));
            r.rectTransform.pivot = new Vector2(0f, 0.5f);
            r.rectTransform.anchoredPosition = new Vector2(0f, y);
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
            if (gm.State != GameState.Title && gm.State != GameState.Loading) rulesOpen = false;
        }

        float resultT;

        void UpdateScreens(float dt)
        {
            var kb = Keyboard.current;
            bool enter = kb != null && (kb.enterKey.wasPressedThisFrame || kb.numpadEnterKey.wasPressedThisFrame);
            bool title = gm.State == GameState.Title || gm.State == GameState.Loading;
            titleGroup.alpha = UIKit.Smooth(titleGroup.alpha, title ? 1f : 0f, 7f, dt);
            titleGroup.blocksRaycasts = title && !rulesOpen;
            titleScreen.gameObject.SetActive(titleGroup.alpha > 0.01f || title);
            if (title)
            {
                bool ready = Vocabulary.Ready;
                startButton.interactable = ready;
                string status = ready ? "" : (Vocabulary.Failed ? "<color=" + UIKit.Css(UIKit.RedPen) + ">无法读取词库</color>  请把 vocabulary.db 放在“文档”文件夹中" : "正在载入词库…");
                if (titleStatus.text != status) titleStatus.text = status;
                if (enter && ready && !rulesOpen) gm.StartGame();
            }
            rulesGroup.alpha = UIKit.Smooth(rulesGroup.alpha, rulesOpen ? 1f : 0f, 14f, dt);
            rulesGroup.blocksRaycasts = rulesOpen;
            rulesScreen.gameObject.SetActive(rulesOpen || rulesGroup.alpha > 0.01f);
            if (rulesOpen && kb != null && (kb.escapeKey.wasPressedThisFrame || enter)) rulesOpen = false;

            bool paused = gm.State == GameState.Paused;
            pauseGroup.alpha = UIKit.Smooth(pauseGroup.alpha, paused ? 1f : 0f, 14f, dt);
            pauseGroup.blocksRaycasts = paused;
            pauseScreen.gameObject.SetActive(paused || pauseGroup.alpha > 0.01f);
            if (paused && enter) gm.Resume();

            bool result = gm.State == GameState.Victory || gm.State == GameState.Defeat;
            resultScreen.gameObject.SetActive(result);
            if (result)
            {
                resultT += dt;
                resultGroup.alpha = UIKit.Smooth(resultGroup.alpha, 1f, 6f, dt);
                resultGroup.blocksRaycasts = true;
                if (enter && resultT > 0.6f) gm.Restart(true);
            }
            else resultT = 0f;
        }
    }
}
