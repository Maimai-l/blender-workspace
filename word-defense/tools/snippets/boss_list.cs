var sb = new System.Text.StringBuilder();
var rx = new System.Text.RegularExpressions.Regex("[A-Za-z]+");
foreach (var b in WordDefense.Data.Vocabulary.BossSentences) {
  int confirmed = 0; foreach (var k in b.Keywords) { var core = WordDefense.SessionDeck.Core(k.Gloss); if (k.Entry.Verified && WordDefense.SessionDeck.Core(k.Entry.Gloss) == core) confirmed++; }
  int longRare = 0; foreach (System.Text.RegularExpressions.Match m in rx.Matches(b.English)) { var w = m.Value.ToLowerInvariant(); if (w.Length >= 11 && !WordDefense.Data.Vocabulary.Lexicon.ContainsKey(w)) longRare++; }
  sb.Append(b.Quality + " c" + confirmed + "/" + b.Keywords.Count + " r" + longRare + " | " + b.English + " |");
  foreach (var k in b.Keywords) sb.Append(" " + k.Entry.Word + "=" + k.Gloss + (k.Entry.Verified ? "(" + k.Entry.Gloss + ")" : ""));
  sb.AppendLine();
}
return sb.ToString();
