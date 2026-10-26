using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace WordDefense
{
    public sealed class Shell
    {
        static int nextId;
        public readonly int Id = ++nextId;
        public SessionWord Word;
        public float CreatedAt;
        public bool Vivid;          // 记忆深刻: fires itself and homes in
        public bool Armed;          // vivid shell waiting for its enemy to appear
        public bool Swapped;        // replaced to keep the tray answerable (UI flips the card)
        public float LastMatchTime;
    }

    /// <summary>
    /// The four meaning shells at the bottom of the screen. Rules:
    ///  • whenever an enemy is on the field, at least one shell matches an enemy (if not, the stalest distractor is swapped);
    ///  • during the Boss fight the current keyword's meaning is always present;
    ///  • refills favour enemies that have no shell yet, then the meaning of the enemy most likely to appear next,
    ///    then distractors taken from words the player has already met, never clashing with a meaning on the field;
    ///  • a distractor that has matched nothing for 14 s is rotated out when an enemy still lacks a shell.
    /// </summary>
    public sealed class ShellTray
    {
        public const int Size = 4;
        public readonly Shell[] Slots = new Shell[Size];
        readonly float[] refillAt = new float[Size];
        float lastRotate;
        GameManager gm;

        public ShellTray(GameManager g) { gm = g; }

        public void Clear()
        {
            for (int i = 0; i < Size; i++) { Slots[i] = null; refillAt[i] = 0f; }
        }

        public static bool Matches(SessionWord shellWord, SessionWord enemyWord)
        {
            if (shellWord == null || enemyWord == null) return false;
            return shellWord == enemyWord || shellWord.Core == enemyWord.Core;
        }

        public bool Matches(Shell s, Enemy e)
        {
            if (s == null || e == null || !e.Targetable) return false;
            var boss = e as BossEnemy;
            return Matches(s.Word, boss != null ? boss.TargetWord : e.Word);
        }

        IEnumerable<Enemy> Targets() { return gm.Enemies.Where(e => e != null && e.Targetable); }

        SessionWord TargetWord(Enemy e)
        {
            var b = e as BossEnemy;
            return b != null ? b.TargetWord : e.Word;
        }

        public int MatchingCount()
        {
            int n = 0;
            foreach (var s in Slots) if (s != null && Targets().Any(e => Matches(s, e))) n++;
            return n;
        }

        public bool AnyMatch() { return MatchingCount() > 0; }

        public void Consume(int slot, float refillDelay = 0.28f)
        {
            Slots[slot] = null;
            refillAt[slot] = Time.time + refillDelay;
        }

        public void Tick()
        {
            float now = Time.time;
            var targets = Targets().OrderByDescending(e => e is BossEnemy ? 2f : e.Progress).ToList();
            foreach (var s in Slots)
                if (s != null && targets.Any(e => Matches(s, e))) s.LastMatchTime = now;

            // refill empty slots
            for (int i = 0; i < Size; i++)
                if (Slots[i] == null && now >= refillAt[i]) Slots[i] = Make(Choose(targets, i));

            if (targets.Count == 0) return;

            // boss: the current keyword must be in the tray
            var boss = targets.OfType<BossEnemy>().FirstOrDefault();
            if (boss != null && boss.TargetWord != null && !Slots.Any(s => s != null && Matches(s.Word, boss.TargetWord)))
                Replace(Victim(targets, true), boss.TargetWord);
            // ...and the next keyword too, so every Boss shot is a choice of order
            if (boss != null && boss.Effective + 1 < boss.Keywords.Count)
            {
                var next = boss.Keywords[boss.Effective + 1];
                if (!Slots.Any(s => s != null && Matches(s.Word, next)))
                {
                    int free = -1;
                    for (int i = 0; i < Size; i++)
                    {
                        var s = Slots[i];
                        if (s == null || i == gm.SelectedSlot || s.Armed) continue;
                        if (targets.Any(e => Matches(s, e))) continue;
                        free = i;
                        break;
                    }
                    if (free >= 0) Replace(free, next);
                }
            }

            // invariant: at least one shell matches an enemy on the field
            if (!Slots.Any(s => s != null && targets.Any(e => Matches(s, e))))
            {
                var unmatched = targets.FirstOrDefault();
                if (unmatched != null) Replace(Victim(targets, false), TargetWord(unmatched));
            }

            // keep the tray fresh: rotate a long-idle distractor if some enemy still has no shell
            if (now - lastRotate > 2f)
            {
                var lacking = targets.FirstOrDefault(e => !Slots.Any(s => s != null && Matches(s, e)));
                if (lacking != null)
                {
                    for (int i = 0; i < Size; i++)
                    {
                        var s = Slots[i];
                        if (s == null || i == gm.SelectedSlot || s.Armed) continue;
                        if (now - s.LastMatchTime > 14f && now - s.CreatedAt > 14f)
                        {
                            Replace(i, TargetWord(lacking));
                            lastRotate = now;
                            break;
                        }
                    }
                }
            }
        }

        int Victim(List<Enemy> targets, bool forBoss)
        {
            int best = -1;
            float bestScore = float.MinValue;
            for (int i = 0; i < Size; i++)
            {
                var s = Slots[i];
                if (s == null) return i;
                bool matches = targets.Any(e => Matches(s, e));
                float score = (matches ? -100f : 0f) + (i == gm.SelectedSlot ? -50f : 0f) + (s.Armed ? -30f : 0f) + (Time.time - s.CreatedAt);
                if (forBoss && matches && !(targets.Any(e => e is BossEnemy && Matches(s, e)))) score += 60f;   // escorts can give way
                if (score > bestScore) { bestScore = score; best = i; }
            }
            return best;
        }

        void Replace(int slot, SessionWord w)
        {
            if (slot < 0 || w == null) return;
            if (slot == gm.SelectedSlot) gm.SelectedSlot = -1;
            var s = Make(w);
            s.Swapped = true;
            Slots[slot] = s;
        }

        Shell Make(SessionWord w)
        {
            if (w == null) return null;
            return new Shell { Word = w, CreatedAt = Time.time, LastMatchTime = Time.time, Vivid = gm.IsVivid(w) };
        }

        SessionWord Choose(List<Enemy> targets, int slot)
        {
            var inTray = new HashSet<SessionWord>(Slots.Where(s => s != null).Select(s => s.Word));
            var lacking = targets.Where(e => !Slots.Any(s => s != null && Matches(s, e))).ToList();
            int matching = Slots.Count(s => s != null && targets.Any(e => Matches(s, e)));
            if (lacking.Count > 0 && (matching < 2 || gm.Deck.Next(100) < 30))
                return TargetWord(lacking[0]);
            // distractor
            var avoidCores = new List<string>();
            foreach (var s in Slots) if (s != null) avoidCores.Add(s.Word.Core);
            var onField = new HashSet<SessionWord>(gm.Enemies.Where(e => e != null && e.Alive).Select(e => TargetWord(e)).Where(w => w != null));
            foreach (var w in onField) avoidCores.Add(w.Core);
            var avoidWords = new HashSet<SessionWord>(inTray);
            avoidWords.UnionWith(onField);
            SessionWord prefer = gm.Phase == GamePhase.Boss ? null : gm.Deck.PeekLikely(onField);
            if (gm.Phase == GamePhase.Boss && gm.Boss != null)
            {
                // later keywords make good distractors: they test the order
                var later = gm.Boss.Keywords.Skip(gm.Boss.Effective + 1).Where(k => !avoidWords.Contains(k) && !avoidCores.Contains(k.Core)).ToList();
                if (later.Count > 0 && gm.Deck.Next(100) < 50) prefer = later[gm.Deck.Next(later.Count)];
            }
            var d = gm.Deck.PickDistractor(avoidCores, avoidWords, prefer);
            if (d != null) return d;
            if (lacking.Count > 0) return TargetWord(lacking[0]);
            return gm.Deck.Words[gm.Deck.Next(gm.Deck.Words.Count)];
        }

        public void RefreshVivid()
        {
            foreach (var s in Slots) if (s != null) s.Vivid = gm.IsVivid(s.Word);
        }
    }
}
