var dir = System.IO.Path.GetFullPath("Temp/SmokeTest");
var sb = new System.Text.StringBuilder();
sb.AppendLine("playing=" + EditorApplication.isPlaying + " result=" + WordDefense.AutoPilot.LastResult);
var gm = WordDefense.GameManager.Instance;
if (gm != null) sb.AppendLine("state=" + gm.State + " phase=" + gm.Phase + " wave=" + gm.Wave + " t=" + gm.PlayTime.ToString("0") + " hp=" + (gm.castle ? gm.castle.Hp : -1) + " score=" + gm.Score + " hits=" + gm.Hits + " wrong=" + gm.Wrongs + " leaks=" + gm.Leaks);
foreach (var f in System.IO.Directory.Exists(dir) ? System.IO.Directory.GetFiles(dir, "*.txt") : new string[0]) { sb.AppendLine("== " + System.IO.Path.GetFileName(f)); sb.AppendLine(System.IO.File.ReadAllText(f)); }
return sb.ToString();
