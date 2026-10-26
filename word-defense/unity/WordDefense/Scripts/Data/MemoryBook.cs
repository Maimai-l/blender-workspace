using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace WordDefense.Data
{
    /// <summary>
    /// Per-word memory model (a small FSRS-style scheduler), saved between sessions.
    ///
    /// Every answer is graded by how fast the word was recalled: within 3 s = Easy, within 6.5 s = Good, slower = Hard,
    /// a wrong match or a word that reaches the castle = Again. Stability (in days) grows with each success and collapses
    /// on a lapse; retrievability decays over real time with the FSRS forgetting curve R = (1 + t / (9 S))^-1.
    ///
    /// A word is "记忆深刻" (vivid) when its stability is at least 3 days and it is still fresh (R ≥ 0.85). In practice
    /// that takes two fast, error-free recalls in a row (or three ordinary ones); any mistake revokes it, and after a
    /// couple of weeks without practice it fades. Review data already stored in vocabulary.db (stability / last_review)
    /// counts as well, so words the player knows from their own review app start out vivid.
    /// </summary>
    public sealed class MemoryBook
    {
        public const float VividStability = 3f;
        public const float VividRetrievability = 0.85f;
        public const float FastSeconds = 3f, GoodSeconds = 6.5f;

        public enum Grade { Again = 1, Hard = 2, Good = 3, Easy = 4 }

        [Serializable]
        public sealed class Record
        {
            public string word;
            public float stability;     // days
            public long lastTicks;      // UTC ticks of the last review
            public int reps, lapses, streak;
            public float bestSeconds = -1f;
        }

        [Serializable]
        sealed class SaveData
        {
            public int version = 1;
            public List<Record> records = new List<Record>();
            public string lastBoss = "";
            public int games, wins;
        }

        readonly Dictionary<string, Record> records = new Dictionary<string, Record>();
        readonly string path;
        public string LastBoss = "";
        public int Games, Wins;
        public Func<DateTime> Clock = () => DateTime.UtcNow;

        public MemoryBook(string filePath)
        {
            path = filePath;
            Load();
        }

        public static string DefaultPath(string profile)
        {
            return Path.Combine(Application.persistentDataPath, string.IsNullOrEmpty(profile) ? "memory.json" : "memory_" + profile + ".json");
        }

        public int Count { get { return records.Count; } }

        public Record Get(string word)
        {
            Record r;
            return records.TryGetValue(word, out r) ? r : null;
        }

        public static float Retrievability(float stabilityDays, double elapsedDays)
        {
            if (stabilityDays <= 0f) return 0f;
            return (float)(1.0 / (1.0 + Math.Max(0.0, elapsedDays) / (9.0 * stabilityDays)));
        }

        public float RetrievabilityNow(string word)
        {
            var r = Get(word);
            if (r == null || r.stability <= 0f) return 0f;
            return Retrievability(r.stability, (Clock() - new DateTime(r.lastTicks, DateTimeKind.Utc)).TotalDays);
        }

        /// <summary>记忆深刻: strong and fresh in-game memory, or strong review data from the database.</summary>
        public bool IsVivid(WordEntry e)
        {
            var r = Get(e.Word);
            if (r != null && r.stability >= VividStability && RetrievabilityNow(e.Word) >= VividRetrievability) return true;
            if (e.DbStability >= VividStability && !string.IsNullOrEmpty(e.DbLastReview))
            {
                DateTime last;
                if (DateTime.TryParse(e.DbLastReview, System.Globalization.CultureInfo.InvariantCulture,
                        System.Globalization.DateTimeStyles.AssumeUniversal | System.Globalization.DateTimeStyles.AdjustToUniversal, out last))
                    return Retrievability((float)e.DbStability, (Clock() - last).TotalDays) >= VividRetrievability;
            }
            return false;
        }

        /// <summary>0..1 bar for the results screen.</summary>
        public float Strength(string word)
        {
            var r = Get(word);
            if (r == null) return 0f;
            return Mathf.Clamp01(r.stability / (VividStability * 1.5f)) * RetrievabilityNow(word);
        }

        public static Grade GradeFor(float seconds)
        {
            if (seconds <= FastSeconds) return Grade.Easy;
            if (seconds <= GoodSeconds) return Grade.Good;
            return Grade.Hard;
        }

        public Record Review(string word, Grade g, float seconds = -1f)
        {
            Record r;
            if (!records.TryGetValue(word, out r))
            {
                r = new Record { word = word };
                records[word] = r;
            }
            if (g == Grade.Again)
            {
                r.stability = r.reps == 0 ? 0.2f : Mathf.Max(0.2f, r.stability * 0.25f);
                r.lapses++;
                r.streak = 0;
            }
            else
            {
                if (r.reps == 0 || r.stability <= 0f)
                    r.stability = g == Grade.Easy ? 2.4f : (g == Grade.Good ? 1.2f : 0.6f);
                else
                    r.stability *= 1f + (g == Grade.Easy ? 2.2f : (g == Grade.Good ? 1.4f : 0.6f));
                r.stability = Mathf.Min(r.stability, 365f);
                r.streak++;
                if (seconds > 0f && (r.bestSeconds < 0f || seconds < r.bestSeconds)) r.bestSeconds = seconds;
            }
            r.reps++;
            r.lastTicks = Clock().Ticks;
            return r;
        }

        /// <summary>Words that should come back soon: lapsed or fading.</summary>
        public bool IsDue(string word)
        {
            var r = Get(word);
            if (r == null) return false;
            return r.lapses > 0 && r.streak == 0 || RetrievabilityNow(word) < 0.8f;
        }

        public void Reset()
        {
            records.Clear();
            LastBoss = "";
            Games = Wins = 0;
        }

        // ------------------------------------------------------------ persistence
        void Load()
        {
            try
            {
                if (!File.Exists(path)) return;
                var data = JsonUtility.FromJson<SaveData>(File.ReadAllText(path, Encoding.UTF8));
                if (data == null) return;
                foreach (var r in data.records)
                    if (!string.IsNullOrEmpty(r.word)) records[r.word] = r;
                LastBoss = data.lastBoss ?? "";
                Games = data.games;
                Wins = data.wins;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[WD] memory file could not be read: " + e.Message);
            }
        }

        public void Save()
        {
            try
            {
                var data = new SaveData { lastBoss = LastBoss, games = Games, wins = Wins };
                data.records.AddRange(records.Values);
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                string tmp = path + ".tmp";
                File.WriteAllText(tmp, JsonUtility.ToJson(data), Encoding.UTF8);
                if (File.Exists(path)) File.Delete(path);
                File.Move(tmp, path);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[WD] memory file could not be saved: " + e.Message);
            }
        }
    }
}
