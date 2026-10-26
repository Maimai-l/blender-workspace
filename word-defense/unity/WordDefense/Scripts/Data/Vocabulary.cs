using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace WordDefense.Data
{
    public sealed class Sense
    {
        public string Pos;
        public string Text;
        public int Line;
        public int Order;
    }

    /// <summary>One usable row of the Words table.</summary>
    public sealed class WordEntry
    {
        public int Id;
        public string Word;
        public string Pos;          // part of speech of the gloss, e.g. "n." (may be empty)
        public string Gloss;        // short Chinese meaning shown on a shell
        public string Definition;   // original definition text from the database
        public string Example;
        public string ExampleZh;
        public float Difficulty;
        public string Books;
        public double DbStability;  // FSRS stability from the database (0 = never reviewed there)
        public string DbLastReview;
        public List<Sense> Senses;
        public bool Verified;       // the gloss appears in the Chinese translation of the word's own example

        public override string ToString() { return Word + " " + Pos + Gloss; }
    }

    public sealed class BossKeyword
    {
        public WordEntry Entry;
        public string Pos;
        public string Gloss;        // the sense used in this sentence (found in its Chinese translation)
        public int CharStart;
        public int CharLength;
    }

    public sealed class BossSentence
    {
        public int SourceId;
        public string English;
        public string Chinese;
        public List<BossKeyword> Keywords = new List<BossKeyword>();
        public int Quality;
    }

    public sealed class VocabStats
    {
        public int TotalRows, BandRows, BookRows, Usable, Verified, Lexicon, BossSentences;
        public long LoadMs;
        public string Band;
    }

    /// <summary>
    /// Loads the vocabulary straight from vocabulary.db. Selection rules (medium difficulty):
    /// difficulty 0.4–0.6 (the database stores word length / 10), words from the CET-4/6 or TOEFL books, and
    /// definitions that survive a quality filter: many rows of the auto-generated book carry the definition of a
    /// derived word (argue → "不容置疑地" from arguably, urban → "城市化" from urbanize), so senses are checked
    /// against the word's morphology and against the Chinese translation of its example sentence.
    /// </summary>
    public static class Vocabulary
    {
        public const float MinDifficulty = 0.4f, MaxDifficulty = 0.6f;
            static readonly string[] Books = { "3", "4" };   // CET_4+6_edited, TOEFL
        static readonly string[] SentenceBooks = { "3", "4", "5" };

        public static volatile bool Ready;
        public static volatile bool Failed;
        public static string Error = "";
        public static string SourcePath = "";
        public static List<WordEntry> Pool = new List<WordEntry>();
        public static Dictionary<string, WordEntry> Lexicon = new Dictionary<string, WordEntry>();
        public static List<BossSentence> BossSentences = new List<BossSentence>();
        public static VocabStats Stats = new VocabStats();
        static Thread worker;

        // ------------------------------------------------------------ loading
        /// <summary>Database locations in priority order: -vocab path, the user's Documents folder, the bundled copy.</summary>
        public static List<string> CandidatePaths(string streamingAssets)
        {
            var list = new List<string>();
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-vocab") list.Add(args[i + 1]);
            try
            {
                string docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                if (!string.IsNullOrEmpty(docs)) list.Add(Path.Combine(docs, "vocabulary.db"));
            }
            catch { }
            list.Add(Path.Combine(streamingAssets, "vocabulary.db"));
            return list;
        }

        public static void BeginLoad(string streamingAssets)
        {
            if (Ready || worker != null) return;
            var paths = CandidatePaths(streamingAssets);
            worker = new Thread(() =>
            {
                Exception last = null;
                foreach (var p in paths)
                {
                    try
                    {
                        if (!File.Exists(p)) continue;
                        LoadFrom(p);
                        return;
                    }
                    catch (Exception e) { last = e; }
                }
                Error = last != null ? last.Message : "vocabulary.db not found";
                Failed = true;
            });
            worker.IsBackground = true;
            worker.Start();
        }

        public static void LoadFrom(string path)
        {
            var sw = Stopwatch.StartNew();
            var db = SqliteReader.Open(path);
            var words = db.GetTable("Words");
            if (words == null) throw new InvalidDataException("table Words not found");
            int cVocab = words.Col("vocab"), cDef = words.Col("definition"), cEx = words.Col("example"),
                cZh = words.Col("example_chinese"), cDiff = words.Col("difficulty"), cBooks = words.Col("book_identities"),
                cStab = words.Col("stability"), cLast = words.Col("last_review"), cId = words.Col("word_id");
            if (cVocab < 0 || cDef < 0 || cDiff < 0 || cBooks < 0) throw new InvalidDataException("unexpected Words schema");

            var stats = new VocabStats { Band = MinDifficulty.ToString("0.0") + "–" + MaxDifficulty.ToString("0.0") };
            var firstLineOwners = new Dictionary<long, List<string>>();
            var candidates = new List<WordEntry>();
            var sentenceRows = new List<KeyValuePair<string, string>>();
            var sentenceIds = new List<int>();

            db.ForEachRow(words, row =>
            {
                stats.TotalRows++;
                string vocab = row.GetText(cVocab) ?? "";
                string def = row.GetText(cDef) ?? "";
                long h = Fnv(FirstLine(def));
                List<string> owners;
                if (!firstLineOwners.TryGetValue(h, out owners)) { owners = new List<string>(1); firstLineOwners[h] = owners; }
                owners.Add(vocab);

                string books = row.GetText(cBooks) ?? "";
                if (cEx >= 0 && cZh >= 0 && InBooks(books, SentenceBooks))
                {
                    sentenceRows.Add(new KeyValuePair<string, string>(row.GetText(cEx) ?? "", row.GetText(cZh) ?? ""));
                    sentenceIds.Add((int)row.RowId);
                }
                if (!InBooks(books, Books)) return;
                stats.BookRows++;
                double diff = row.GetDouble(cDiff);
                if (diff < MinDifficulty - 0.001 || diff > MaxDifficulty + 0.001) return;
                stats.BandRows++;
                candidates.Add(new WordEntry
                {
                    Id = cId >= 0 ? (int)row.GetInt(cId) : (int)row.RowId,
                    Word = vocab,
                    Definition = def,
                    Example = cEx >= 0 ? row.GetText(cEx) ?? "" : "",
                    ExampleZh = cZh >= 0 ? row.GetText(cZh) ?? "" : "",
                    Difficulty = (float)diff,
                    Books = books,
                    DbStability = cStab >= 0 ? row.GetDouble(cStab) : 0,
                    DbLastReview = cLast >= 0 ? row.GetText(cLast) : null,
                });
            });

            // second pass: definitions of longer words built on each candidate's stem (self → selfless, space → spacious)
            var stems = new HashSet<string>();
            foreach (var w in candidates) stems.Add(Stem(w.Word));
            var derived = new Dictionary<string, List<KeyValuePair<string, string>>>();
            db.ForEachRow(words, row =>
            {
                string v = row.GetText(cVocab) ?? "";
                for (int k = 4; k < v.Length && k <= 12; k++)
                {
                    string pre = v.Substring(0, k);
                    if (!stems.Contains(pre)) continue;
                    List<KeyValuePair<string, string>> list;
                    if (!derived.TryGetValue(pre, out list)) { list = new List<KeyValuePair<string, string>>(); derived[pre] = list; }
                    list.Add(new KeyValuePair<string, string>(v, row.GetText(cDef) ?? ""));
                }
            });

            var pool = new List<WordEntry>();
            var lexicon = new Dictionary<string, WordEntry>();
            foreach (var w in candidates)
            {
                if (!Regex.IsMatch(w.Word, "^[a-z]+$") || Stop.Contains(w.Word)) continue;
                var senses = ParseSenses(w.Word, w.Definition);
                if (senses == null) continue;
                senses.RemoveAll(s => !SenseFitsWord(w.Word, s.Pos, s.Text));
                if (senses.Count == 0) continue;
                if (CopiedFromDerivedWord(w.Word, w.Definition, firstLineOwners)) continue;
                RemoveBorrowedSenses(w.Word, senses, derived);
                if (senses.Count == 0) continue;
                w.Senses = senses;
                stats.Usable++;
                lexicon[w.Word] = w;
                var hit = FindSense(senses, Clean(w.ExampleZh));
                if (hit != null)
                {
                    w.Pos = hit.Pos; w.Gloss = hit.Text; w.Verified = true;
                    pool.Add(w);
                }
                else
                {
                    w.Pos = senses[0].Pos; w.Gloss = senses[0].Text;
                }
            }
            stats.Verified = pool.Count;
            stats.Lexicon = lexicon.Count;

            var boss = new List<BossSentence>();
            for (int i = 0; i < sentenceRows.Count; i++)
            {
                var b = MakeBossSentence(sentenceIds[i], sentenceRows[i].Key, sentenceRows[i].Value, lexicon);
                if (b != null) boss.Add(b);
            }
            // the same sentence can belong to several rows; best sentences first
            var seen = new HashSet<string>();
            boss.RemoveAll(b => !seen.Add(b.English));
            boss.Sort((a, b) => b.Quality.CompareTo(a.Quality));
            stats.BossSentences = boss.Count;
            stats.LoadMs = sw.ElapsedMilliseconds;

            Pool = pool;
            Lexicon = lexicon;
            BossSentences = boss;
            Stats = stats;
            SourcePath = path;
            Ready = true;
        }

        static bool InBooks(string books, string[] wanted)
        {
            foreach (var b in books.Split(','))
                foreach (var want in wanted)
                    if (b.Trim() == want) return true;
            return false;
        }

        // ------------------------------------------------------------ definition parsing
        static readonly HashSet<string> Stop = new HashSet<string>((
            "a an the and or but if of to in on at by for with from as is are was were be been being am do does did done have has had " +
            "i you he she it we they me him her us them my your his its our their this that these those there here where when what which who whom whose why how " +
            "not no nor so too very can could will would shall should may might must about above after again against all any both each few more most other " +
            "some such only own same than then once also just into over under until while out off up down through during before between because " +
            "yes oh hey okay ok mr mrs ms dr st etc vs").Split(' '));

        static readonly HashSet<string> AdverbsWithoutLy = new HashSet<string>((
            "often never always soon quite rather almost already also ever perhaps maybe seldom abroad ahead aside apart away back forth hence thus indeed " +
            "instead later late fast hard well still yet even once twice again anyway afar alike aloud alone around behind beyond below above inside outside " +
            "upward downward forward toward overseas meanwhile otherwise somewhat nowhere anywhere everywhere elsewhere sideways").Split(' '));

        static readonly Regex PosRe = new Regex(@"^\s*(n|v|vt|vi|adj|adv|a|prep|conj|pron|int|interj|num|art|aux|abbr)\s*[\.．]\s*", RegexOptions.IgnoreCase);
        static readonly Regex BadLine = new Regex("人名|姓氏|地名|城市|品牌|公司|国名|州名|河名|缩写|abbr|首字母|简称|商标|电影|乐队|歌曲|小说|球队");
        static readonly Regex Inflect = new Regex(@"[（(]\s*([A-Za-z\-]+)\s*的\s*(复数|第三人称单数|过去式|过去分词|现在分词|ing\s*形式|名词复数|比较级|最高级)");
        static readonly Regex Brackets = new Regex(@"（[^（）]*）|\([^()]*\)|\[[^\[\]]*\]|<[^<>]*>|【[^【】]*】|《[^《》]*》");
        static readonly Regex Latin = new Regex("[A-Za-z0-9=]");
        static readonly char[] GroupSep = { '；', ';' };
        static readonly char[] SenseSep = { '，', ',', '、' };
        static readonly char[] TrimChars = " 　.。:：\"“”'‘’".ToCharArray();

        static string FirstLine(string def)
        {
            string d = def.Replace("\\n", "\n");
            int nl = d.IndexOf('\n');
            string first = nl >= 0 ? d.Substring(0, nl) : d;
            var sb = new StringBuilder(first.Length);
            foreach (char c in first) if (!char.IsWhiteSpace(c)) sb.Append(c);
            return sb.ToString();
        }

        static long Fnv(string s)
        {
            unchecked
            {
                ulong h = 14695981039346656037UL;
                foreach (char c in s) { h ^= c; h *= 1099511628211UL; }
                return (long)h;
            }
        }

        public static List<Sense> ParseSenses(string vocab, string definition)
        {
            var result = new List<Sense>();
            string[] lines = definition.Replace("\\n", "\n").Split('\n');
            for (int li = 0; li < lines.Length; li++)
            {
                string l = lines[li].Trim();
                if (l.Length == 0) continue;
                if (BadLine.IsMatch(l) || l[0] == '[' || l[0] == '【' || l[0] == '·') continue;
                var m = Inflect.Match(l);
                if (m.Success && !string.Equals(m.Groups[1].Value, vocab, StringComparison.OrdinalIgnoreCase)) return null;
                string pos = "";
                var pm = PosRe.Match(l);
                if (pm.Success)
                {
                    pos = pm.Groups[1].Value.ToLowerInvariant();
                    l = l.Substring(pm.Length);
                }
                if (pos == "abbr") continue;
                if (pos == "a") pos = "adj";
                if (pos == "vt" || pos == "vi") pos = "v";
                if (pos == "int") pos = "interj";
                string body = Brackets.Replace(l, "").Replace("…", "").Replace("...", "");
                foreach (var grp in body.Split(GroupSep))
                    foreach (var raw in grp.Split(SenseSep))
                    {
                        string s = raw.Trim(TrimChars);
                        if (s.Length == 0 || s.Length > 8 || Latin.IsMatch(s) || !HasCjk(s)) continue;
                        result.Add(new Sense { Pos = pos, Text = s, Line = li, Order = result.Count });
                    }
            }
            return result;
        }

        static bool HasCjk(string s)
        {
            foreach (char c in s) if (c >= 0x4E00 && c <= 0x9FFF) return true;
            return false;
        }

        /// <summary>Rejects senses that belong to a derived word (an -ly adverb, an agent noun, an -ism ...).</summary>
        public static bool SenseFitsWord(string w, string pos, string g)
        {
            if (g.EndsWith("地") && !w.EndsWith("ly")) return false;
            if (pos == "adv" && !w.EndsWith("ly") && !AdverbsWithoutLy.Contains(w)) return false;
            if ((g.EndsWith("者") || g.EndsWith("贩")) && !Regex.IsMatch(w, "(er|or|ar|ist|ant|ent|ee|an|ian)$")) return false;
            if (g.EndsWith("论") && !w.EndsWith("ism")) return false;
            if (g.EndsWith("化") && pos == "v" && !Regex.IsMatch(w, "(ize|ise|ify|en)$")) return false;
            if (g.EndsWith("性") && pos == "n" && !Regex.IsMatch(w, "(ity|ness|ty|ce|cy)$")) return false;
            if (g.StartsWith("女") && pos == "n" && !w.EndsWith("ess")) return false;
            if (g.StartsWith("最") && !w.EndsWith("est") && !w.EndsWith("most")) return false;
            if ((g.StartsWith("未") || g.StartsWith("不") || g.StartsWith("无") || g.StartsWith("非")) &&
                !Regex.IsMatch(w, "^(un|in|im|il|ir|dis|non|mis|de)")) return false;
            if (g.EndsWith("的") && (pos == "n" || pos == "v" || pos == "adv")) return false;
            return true;
        }

        /// <summary>True when the definition's first line is identical to that of a longer derived word (botany → botanist),
        /// ignoring plain inflections (secret → secrets), which share the meaning.</summary>
        static bool CopiedFromDerivedWord(string w, string def, Dictionary<long, List<string>> owners)
        {
            List<string> list;
            if (!owners.TryGetValue(Fnv(FirstLine(def)), out list)) return false;
            string stem = w.Substring(0, Math.Max(3, w.Length - 2));
            foreach (var o in list)
            {
                if (o == w || o.Length <= w.Length || !o.StartsWith(stem)) continue;
                if (IsInflection(w, o)) continue;
                return true;
            }
            return false;
        }

        static string Stem(string w) { return w.Length >= 5 ? w.Substring(0, w.Length - 1) : w; }

        /// <summary>Drops senses that a longer derived word also lists (insist "坚持的" belongs to insistent).</summary>
        static void RemoveBorrowedSenses(string w, List<Sense> senses, Dictionary<string, List<KeyValuePair<string, string>>> derived)
        {
            List<KeyValuePair<string, string>> list;
            if (!derived.TryGetValue(Stem(w), out list)) return;
            var borrowed = new HashSet<string>();
            foreach (var kv in list)
            {
                string o = kv.Key;
                if (o.Length <= w.Length || o == w || IsInflection(w, o)) continue;
                var os = ParseSenses(o, kv.Value);
                if (os == null) continue;
                foreach (var s in os) borrowed.Add(Core(s.Text));
            }
            if (borrowed.Count > 0) senses.RemoveAll(s => borrowed.Contains(Core(s.Text)));
        }

        static bool IsInflection(string w, string o)
        {
            string last = w.Substring(w.Length - 1), cut = w.Substring(0, w.Length - 1);
            foreach (var suf in new[] { "s", "es", "d", "ed", "r", "er", "st", "est", "ing" })
                if (o == w + suf) return true;
            foreach (var suf in new[] { "ies", "ied", "ier", "iest", "ing" })
                if (o == cut + suf) return true;
            foreach (var suf in new[] { "ed", "ing", "er", "est" })
                if (o == w + last + suf) return true;
            return false;
        }

        static string Core(string s) { return s.EndsWith("的") && s.Length > 2 ? s.Substring(0, s.Length - 1) : s; }

        /// <summary>Picks the sense that appears in a Chinese sentence. A part-of-speech hint from the English context
        /// ("the mirror" → noun, "to launch" → verb) wins first, then exact matches over matches without the trailing 的,
        /// then longer matches, then the sense listed first.</summary>
        public static Sense FindSense(List<Sense> senses, string zh, string posHint = null)
        {
            if (string.IsNullOrEmpty(zh)) return null;
            Sense best = null;
            int bestScore = int.MinValue;
            foreach (var s in senses)
            {
                int kind = -1, len = 0;
                if (s.Text.Length >= 2 && zh.Contains(s.Text)) { kind = 2; len = s.Text.Length; }
                else
                {
                    string c = Core(s.Text);
                    if (c.Length >= 2 && zh.Contains(c)) { kind = 1; len = c.Length; }
                    else if (s.Text.Length == 1 && zh.Contains(s.Text)) { kind = 0; len = 1; }
                }
                if (kind < 0) continue;
                int score = (posHint != null && s.Pos == posHint ? 1000 : 0) + kind * 100 + len * 10 - Math.Min(9, s.Order);
                if (score > bestScore) { bestScore = score; best = s; }
            }
            return best;
        }

        static readonly HashSet<string> Basic = new HashSet<string>(("good like feel year book friend night time make take come give know think want find tell work " +
            "seem call need keep show hear play move live hold bring happen write stand meet learn change lead watch follow read allow " +
            "grow open walk offer love appear wait serve send expect build stay fall reach remain month week today people thing").Split(' '));

        static readonly HashSet<string> NounCue = new HashSet<string>("a an the this that these those my your his her its our their some any every each no".Split(' '));
        static readonly HashSet<string> VerbCue = new HashSet<string>("to will would can could should may might must did does do not".Split(' '));

        static string PosHint(string prevToken)
        {
            if (prevToken == null) return null;
            string p = prevToken.ToLowerInvariant();
            if (NounCue.Contains(p)) return "n";
            if (VerbCue.Contains(p)) return "v";
            return null;
        }

        // ------------------------------------------------------------ boss sentences
        static readonly Regex Marker = new Regex(@"^\s*\[\d+\]\s*");
        static readonly Regex SentenceShape = new Regex(@"^[A-Z][A-Za-z ,'\-;:""!?]+[\.!?]""?$");
        static readonly Regex Token = new Regex(@"[A-Za-z]+(?:'[A-Za-z]+)?");

        public static string Clean(string s)
        {
            if (s == null) return "";
            s = Marker.Replace(s, "");
            return s.Replace('’', '\'').Replace('‘', '\'').Trim();
        }

        static BossSentence MakeBossSentence(int id, string ex, string zh, Dictionary<string, WordEntry> lexicon)
        {
            ex = Clean(ex); zh = Clean(zh);
            ex = ex.Replace('“', '"').Replace('”', '"');
            if (ex.Length < 30 || ex.Length > 120 || !SentenceShape.IsMatch(ex) || ex.Contains("  ")) return null;
            if (zh.Length < 6 || zh.Length > 50 || Latin.IsMatch(zh)) return null;
            var tokens = Token.Matches(ex);
            if (tokens.Count < 7 || tokens.Count > 20) return null;
            var kws = new List<BossKeyword>();
            var used = new HashSet<string>();
            string prev = null;
            foreach (Match t in tokens)
            {
                string w = t.Value.ToLowerInvariant();
                string hint = PosHint(prev);
                prev = t.Value;
                if (w.Contains("'") || used.Contains(w)) continue;
                WordEntry e;
                if (!lexicon.TryGetValue(w, out e)) continue;
                var s = FindSense(e.Senses, zh, hint);
                if (s == null) continue;
                bool clash = false;
                foreach (var k in kws)
                    if (k.Gloss.Contains(Core(s.Text)) || s.Text.Contains(Core(k.Gloss))) clash = true;
                if (clash) continue;
                used.Add(w);
                kws.Add(new BossKeyword { Entry = e, Pos = s.Pos, Gloss = s.Text, CharStart = t.Index, CharLength = t.Length });
            }
            if (kws.Count < 3) return null;
            if (kws.Count > 4)
            {
                // keep four: prefer words whose own example also confirms the sense, then longer words
                var ranked = new List<BossKeyword>(kws);
                ranked.Sort((a, b) =>
                {
                    int va = a.Entry.Verified ? 1 : 0, vb = b.Entry.Verified ? 1 : 0;
                    if (va != vb) return vb - va;
                    return b.Entry.Word.Length - a.Entry.Word.Length;
                });
                var keep = new HashSet<BossKeyword>(ranked.GetRange(0, 4));
                kws.RemoveAll(k => !keep.Contains(k));
            }
            var b2 = new BossSentence { SourceId = id, English = ex, Chinese = zh };
            b2.Keywords.AddRange(kws);
            int q = 10 * kws.Count - 2 * Math.Abs(tokens.Count - 12);
            foreach (Match t in tokens)   // long words outside the word list are usually jargon or names
                if (t.Value.Length >= 11 && !lexicon.ContainsKey(t.Value.ToLowerInvariant())) q -= 8;
            foreach (var k in kws)
            {
                if (k.Entry.Verified && Core(k.Entry.Gloss) == Core(k.Gloss)) q += 6;   // confirmed by two sentences
                if (k.Gloss.Length >= 2) q += 3;
                if (Basic.Contains(k.Entry.Word)) q -= 5;
            }
            b2.Quality = q;
            return b2;
        }
    }
}
