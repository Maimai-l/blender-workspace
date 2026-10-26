using System.Collections.Generic;
using System.Linq;
using WordDefense.Data;

namespace WordDefense
{
    /// <summary>A word as used in one game: its entry, the meaning shown on shells, and what happened to it.</summary>
    public sealed class SessionWord
    {
        public WordEntry Entry;
        public string Gloss;
        public string Core;
        public bool IsKeyword;
        public int KeywordIndex = -1;
        public int Spawned, Correct, Wrong, Missed;
        public int LastSpawnIndex = -100;
        public int DueAt = -1;
        public bool VividAtStart;
        public bool BecameVivid;
        public float BestSeconds = -1f;
        public string Word { get { return Entry.Word; } }
        public override string ToString() { return Word + "=" + Gloss; }
    }

    /// <summary>
    /// The words of one game. A Boss sentence is chosen first and its keywords join the deck, so the waves teach exactly
    /// the words the Boss will test; the rest are words due for review plus new words. Spawning interleaves new words and
    /// reviews, brings a mistaken or missed word back after a few enemies, and makes sure every keyword has been met at
    /// least twice before the Boss arrives.
    /// </summary>
    public sealed class SessionDeck
    {
        public readonly List<SessionWord> Words = new List<SessionWord>();
        public readonly List<SessionWord> BossWords = new List<SessionWord>();
        public BossSentence Boss;
        int spawnIndex;
        readonly System.Random rng;

        SessionDeck(int seed) { rng = new System.Random(seed); }

        public static string Core(string gloss)
        {
            if (string.IsNullOrEmpty(gloss)) return "";
            return gloss.EndsWith("的") && gloss.Length > 2 ? gloss.Substring(0, gloss.Length - 1) : gloss;
        }

        static bool Clashes(string core, IEnumerable<string> cores)
        {
            foreach (var c in cores)
                if (c == core || c.Contains(core) || core.Contains(c)) return true;
            return false;
        }

        public static SessionDeck Build(MemoryBook mem, int seed, int extraWords = 16)
        {
            var d = new SessionDeck(seed);
            var pool = Vocabulary.Pool;
            var cores = new List<string>();
            var used = new HashSet<string>();

            // ---- boss sentence: one of the best-ranked, not the one used last time
            var ranked = Vocabulary.BossSentences;
            var choices = ranked.Take(System.Math.Min(12, ranked.Count)).Where(b => b.English != mem.LastBoss).ToList();
            if (choices.Count == 0) choices = ranked.Take(System.Math.Min(12, ranked.Count)).ToList();
            if (choices.Count > 0)
                d.Boss = choices[d.rng.Next(choices.Count)];
            else
                d.Boss = FallbackBoss(pool, d.rng);
            for (int i = 0; i < d.Boss.Keywords.Count; i++)
            {
                var k = d.Boss.Keywords[i];
                var sw = new SessionWord { Entry = k.Entry, Gloss = k.Gloss, Core = Core(k.Gloss), IsKeyword = true, KeywordIndex = i };
                d.Words.Add(sw);
                d.BossWords.Add(sw);
                cores.Add(sw.Core);
                used.Add(sw.Word);
            }

            // ---- a few vivid (记忆深刻) words to reinforce, then reviews (lapsed or fading), then new words
            var shuffled = pool.OrderBy(w => d.rng.Next()).ToList();
            int vividCount = 0;
            foreach (var e in shuffled)
            {
                if (vividCount >= 3) break;
                if (used.Contains(e.Word) || !mem.IsVivid(e)) continue;
                if (TryAdd(d, e, cores, used)) vividCount++;
            }
            int reviews = 0;
            foreach (var e in shuffled)
            {
                if (reviews >= 5) break;
                if (used.Contains(e.Word) || !mem.IsDue(e.Word)) continue;
                if (TryAdd(d, e, cores, used)) reviews++;
            }
            foreach (var e in shuffled)
            {
                if (d.Words.Count >= d.BossWords.Count + extraWords) break;
                if (used.Contains(e.Word) || mem.Get(e.Word) != null) continue;
                TryAdd(d, e, cores, used);
            }
            foreach (var e in shuffled)
            {
                if (d.Words.Count >= d.BossWords.Count + extraWords) break;
                if (used.Contains(e.Word)) continue;
                TryAdd(d, e, cores, used);
            }
            foreach (var w in d.Words) w.VividAtStart = mem.IsVivid(w.Entry);
            return d;
        }

        static bool TryAdd(SessionDeck d, WordEntry e, List<string> cores, HashSet<string> used)
        {
            string core = Core(e.Gloss);
            if (string.IsNullOrEmpty(core) || Clashes(core, cores)) return false;
            d.Words.Add(new SessionWord { Entry = e, Gloss = e.Gloss, Core = core });
            cores.Add(core);
            used.Add(e.Word);
            return true;
        }

        /// <summary>Used only if the database has no usable example sentence: the Boss becomes a chain of three words.</summary>
        static BossSentence FallbackBoss(List<WordEntry> pool, System.Random rng)
        {
            var b = new BossSentence { English = "", Chinese = "" };
            var cores = new List<string>();
            var sb = new System.Text.StringBuilder();
            foreach (var e in pool.OrderBy(w => rng.Next()))
            {
                if (b.Keywords.Count >= 3) break;
                string core = Core(e.Gloss);
                if (Clashes(core, cores)) continue;
                cores.Add(core);
                if (sb.Length > 0) sb.Append(" · ");
                int start = sb.Length;
                sb.Append(e.Word);
                b.Keywords.Add(new BossKeyword { Entry = e, Gloss = e.Gloss, Pos = e.Pos, CharStart = start, CharLength = e.Word.Length });
            }
            b.English = sb.ToString();
            b.Chinese = string.Join(" · ", b.Keywords.Select(k => k.Gloss).ToArray());
            return b;
        }

        // ------------------------------------------------------------ spawning
        /// <summary>Chooses the word for the next enemy. 'spawnsLeft' counts the remaining wave enemies before the Boss.</summary>
        public SessionWord NextSpawn(ICollection<SessionWord> onField, int spawnsLeft, bool bossPhase)
        {
            spawnIndex++;
            var free = Words.Where(w => !onField.Contains(w)).ToList();
            if (free.Count == 0) free = Words.ToList();
            SessionWord pick = null;

            if (bossPhase)
            {
                // escorts: anything except the Boss keywords, weakest first
                var escorts = free.Where(w => !w.IsKeyword).ToList();
                if (escorts.Count == 0) escorts = free;
                pick = escorts.OrderBy(w => w.Correct - w.Wrong - w.Missed).ThenBy(w => w.LastSpawnIndex).ThenBy(w => rng.Next()).First();
            }
            else
            {
                int keywordNeed = BossWords.Sum(w => System.Math.Max(0, 2 - w.Spawned));
                var due = free.Where(w => w.DueAt >= 0 && w.DueAt <= spawnIndex).OrderBy(w => w.DueAt).FirstOrDefault();
                if (keywordNeed > 0 && keywordNeed >= spawnsLeft - 1)
                    pick = free.Where(w => w.IsKeyword && w.Spawned < 2).OrderBy(w => w.Spawned).ThenBy(w => w.LastSpawnIndex).FirstOrDefault();
                if (pick == null && due != null) pick = due;
                if (pick == null)
                {
                    // introduce keyword k for the first time around spawn 3 + 5k
                    pick = free.Where(w => w.IsKeyword && w.Spawned == 0 && spawnIndex >= 3 + 5 * w.KeywordIndex).FirstOrDefault();
                }
                if (pick == null && spawnIndex % 3 != 0)
                    pick = free.Where(w => w.Spawned == 0 && !w.IsKeyword).OrderBy(w => rng.Next()).FirstOrDefault();
                if (pick == null)
                    pick = free.Where(w => w.Spawned > 0 && spawnIndex - w.LastSpawnIndex >= 4)
                               .OrderBy(w => w.Correct * 2 - w.Wrong * 3 - w.Missed * 2 + (w.IsKeyword ? -1 : 0))
                               .ThenBy(w => w.LastSpawnIndex).FirstOrDefault();
                if (pick == null)
                    pick = free.OrderBy(w => w.Spawned).ThenBy(w => w.LastSpawnIndex).ThenBy(w => rng.Next()).First();
            }
            pick.Spawned++;
            pick.LastSpawnIndex = spawnIndex;
            if (pick.DueAt >= 0 && pick.DueAt <= spawnIndex) pick.DueAt = -1;
            return pick;
        }

        /// <summary>The word most likely to spawn next (used to pre-load a shell).</summary>
        public SessionWord PeekLikely(ICollection<SessionWord> onField)
        {
            var due = Words.Where(w => !onField.Contains(w) && w.DueAt >= 0).OrderBy(w => w.DueAt).FirstOrDefault();
            if (due != null) return due;
            return Words.Where(w => !onField.Contains(w)).OrderBy(w => w.Spawned).ThenBy(w => w.LastSpawnIndex).FirstOrDefault();
        }

        public void OnWrong(SessionWord w) { w.Wrong++; w.DueAt = spawnIndex + 3; }
        public void OnMissed(SessionWord w) { w.Missed++; w.DueAt = spawnIndex + 2; }

        /// <summary>A word for a distractor shell whose meaning clashes with nothing in 'avoidCores'.</summary>
        public SessionWord PickDistractor(ICollection<string> avoidCores, ICollection<SessionWord> avoidWords, SessionWord prefer)
        {
            if (prefer != null && !avoidWords.Contains(prefer) && !Clashes(prefer.Core, avoidCores)) return prefer;
            var options = Words.Where(w => !avoidWords.Contains(w) && !Clashes(w.Core, avoidCores)).ToList();
            if (options.Count == 0) return null;
            // favour words the player has already met, so the choice is a real test
            var met = options.Where(w => w.Spawned > 0).ToList();
            var from = met.Count > 0 && rng.NextDouble() < 0.7 ? met : options;
            return from[rng.Next(from.Count)];
        }

        public int Next(int max) { return rng.Next(max); }
    }
}
