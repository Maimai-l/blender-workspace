var sw = System.Diagnostics.Stopwatch.StartNew();
WordDefense.Data.Vocabulary.LoadFrom(System.IO.Path.GetFullPath("Assets/StreamingAssets/vocabulary.db"));
var st = WordDefense.Data.Vocabulary.Stats;
var sb = new System.Text.StringBuilder();
sb.AppendLine("ms=" + sw.ElapsedMilliseconds + " total=" + st.TotalRows + " bookRows=" + st.BookRows + " band=" + st.BandRows + " usable=" + st.Usable + " verified=" + st.Verified + " lexicon=" + st.Lexicon + " boss=" + st.BossSentences);
var rnd = new System.Random(4);
var pool = WordDefense.Data.Vocabulary.Pool;
for (int i = 0; i < 40; i++) { var w = pool[rnd.Next(pool.Count)]; sb.Append(w.Word + "=" + w.Gloss + "  "); if (i % 5 == 4) sb.AppendLine(); }
foreach (var name in new[]{"self","space","insist","member","sector","fierce","adorn","cost","boat","plan","adopt","year","argue","vivid","urban"}) { WordDefense.Data.WordEntry e; bool inLex = WordDefense.Data.Vocabulary.Lexicon.TryGetValue(name, out e); sb.Append(name + (inLex ? ("->" + e.Gloss + (e.Verified ? "(v)" : "")) : "->X") + "  "); }
sb.AppendLine();
var bs = WordDefense.Data.Vocabulary.BossSentences;
foreach (var b in bs) { sb.Append(b.Quality + " " + b.English + " |"); foreach (var k in b.Keywords) sb.Append(" " + k.Entry.Word + "=" + k.Gloss); sb.AppendLine(); }
return sb.ToString();
