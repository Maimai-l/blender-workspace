var gm = WordDefense.GameManager.Instance;
if (gm == null) return "no GameManager; playing=" + EditorApplication.isPlaying + " paused=" + EditorApplication.isPaused;
var sb = new System.Text.StringBuilder();
sb.Append("state=" + gm.State + " phase=" + gm.Phase + " wave=" + gm.Wave + " t=" + gm.PlayTime.ToString("0.0") + " speed=" + gm.SpeedMultiplier.ToString("0.00") + " hp=" + (gm.castle ? gm.castle.Hp : -1) + " score=" + gm.Score + " hits=" + gm.Hits + " wrong=" + gm.Wrongs + " leaks=" + gm.Leaks + " combo=" + gm.Combo + " charge=" + gm.SkillCharge + " vocabReady=" + WordDefense.Data.Vocabulary.Ready + " frame=" + Time.frameCount + "\n");
sb.Append("enemies: ");
foreach (var e in gm.Enemies) if (e) sb.Append(e.Kind + ":" + (e.Word != null ? e.Word.Word : "?") + "@" + e.Progress.ToString("0.00") + (e.Alive ? "" : "(dead)") + " ");
sb.Append("\ntray: ");
for (int i = 0; i < 4; i++) { var s = gm.Tray.Slots[i]; sb.Append(i + "=" + (s != null ? s.Word.Word + "/" + s.Word.Gloss + (s.Vivid ? "*" : "") : "-") + " "); }
if (gm.Deck != null) sb.Append("\nboss: " + gm.Deck.Boss.English + " | " + string.Join(",", gm.Deck.BossWords.ConvertAll(w => w.Word + "=" + w.Gloss).ToArray()));
return sb.ToString();
