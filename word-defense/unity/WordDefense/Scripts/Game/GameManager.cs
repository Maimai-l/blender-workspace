using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using WordDefense.Data;

namespace WordDefense
{
    public enum GameState { Loading, Title, Playing, Paused, Victory, Defeat }
    public enum GamePhase { None, Break, Waves, BossIntro, Boss, Ending }

    public enum FeedbackKind { Correct, Wrong, OrderWrong, Leak, Jammed, NeedShell, SkillReady, SkillUsed, VividNew, BossBreak, Armed, WaveStart, BossIncoming, Selected }

    public sealed class Feedback
    {
        public FeedbackKind Kind;
        public Enemy Enemy;
        public SessionWord Word;        // the enemy's word
        public SessionWord ShellWord;   // the word of the shell that was used
        public int Value;
        public float Seconds;
        public bool Homing;
        public Vector3 World;
    }

    [Serializable]
    public sealed class WaveDef
    {
        public int count;
        public float interval;
        public int maxAlive;
        public float scout, soldier, brute;
    }

    /// <summary>Game flow, spawning, matching and scoring. UI and the autopilot talk to the game only through this class.</summary>
    [DefaultExecutionOrder(-50)]
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }
        public const int EnemyLayer = 8;
        public const int WaveCount = 4;
        public const int SkillCost = 3;
        public const float SlowDuration = 6f;
        public const float SlowFactor = 0.35f;
        public const float JamSeconds = 0.9f;

        /// <summary>Set before reloading the scene to skip the title (restart from the result screens).</summary>
        public static bool AutoStart;
        /// <summary>Memory file profile; the autopilot uses its own so tests never touch the player's progress.</summary>
        public static string MemoryProfile = "";
        public static MemoryBook SharedMemory;

        [Header("Scene")]
        public TextAsset pathJson;
        public Camera cam;
        public Castle castle;
        public Cannon cannon;
        public Transform portal;
        [Header("Models")]
        public GameObject scoutModel, soldierModel, bruteModel, bossModel, shellModel;
        [Header("Look")]
        public TMP_FontAsset fontEn, fontZh, fontZhBold, fontZhBlack;
        public Material fxAdditive, fxAlpha;
        public Texture2D fxSoft, fxSpark, fxRing, fxFlake;

        public GameState State { get; private set; }
        public GamePhase Phase { get; private set; }
        public PathRoute Path;
        public MemoryBook Memory;
        public SessionDeck Deck;
        public ShellTray Tray;
        public readonly List<Enemy> Enemies = new List<Enemy>();
        public BossEnemy Boss;
        public int Wave;                    // 1..WaveCount, WaveCount+1 during the Boss
        public float PlayTime;
        public float SpeedMultiplier = 1f;
        public int Combo, BestCombo, SkillCharge;
        public float SlowTimer;
        public int Score, Hits, Wrongs, Leaks, VividHits;
        public float JamUntil;
        public int SelectedSlot = -1;
        public float PhaseTime;             // time spent in the current phase (scaled)
        public string LoadError = "";
        public event Action<Feedback> OnFeedback;
        public event Action<GameState> OnStateChanged;

        public readonly WaveDef[] Waves =
        {
            new WaveDef { count = 6, interval = 3.4f, maxAlive = 3, scout = 0.35f, soldier = 0.65f, brute = 0f },
            new WaveDef { count = 8, interval = 3.0f, maxAlive = 4, scout = 0.45f, soldier = 0.55f, brute = 0f },
            new WaveDef { count = 10, interval = 2.6f, maxAlive = 5, scout = 0.35f, soldier = 0.45f, brute = 0.2f },
            new WaveDef { count = 12, interval = 2.3f, maxAlive = 6, scout = 0.35f, soldier = 0.4f, brute = 0.25f },
        };
        int spawnedInWave;
        float nextSpawnAt;
        float nextEscortAt;
        bool skillAnnounced;
        float gameStartTime;

        /// <summary>Enemy speed multiplier: +10 % per wave and +0.35 % per second of play, capped at 2.2.</summary>
        public float SpeedAt(int wave, float playTime)
        {
            int wi = Mathf.Clamp(wave - 1, 0, WaveCount);
            return Mathf.Min(2.2f, 1f + 0.1f * wi + 0.0035f * playTime);
        }

        public bool Jammed { get { return Time.time < JamUntil; } }
        public bool SkillReady { get { return SkillCharge >= SkillCost; } }
        public float ElapsedPlay { get { return PlayTime; } }

        // ------------------------------------------------------------ lifecycle
        void Awake()
        {
            Instance = this;
            Time.timeScale = 1f;
            Path = PathRoute.FromJson(pathJson != null ? pathJson.text : "{\"points\":[[0,0,0],[1,0,0]]}");
            Tray = new ShellTray(this);
            if (cam == null) cam = Camera.main;
            Fx.Init(this);
            Audio.Init(gameObject);
            Vocabulary.BeginLoad(Application.streamingAssetsPath);
            State = GameState.Loading;
        }

        void Start()
        {
            if (castle != null) castle.Setup(Path.Sample(Path.Length, out _) + Vector3.up * 0.1f);
            if (cannon != null) cannon.Setup();
            UIRoot.Build(this);
            Audio.PlayMusic();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void SetState(GameState s)
        {
            if (State == s) return;
            State = s;
            OnStateChanged?.Invoke(s);
        }

        void Emit(Feedback f) { OnFeedback?.Invoke(f); }

        static bool vocabLogged;   // one line per run in Player.log, not one per restart

        void Update()
        {
            if (State == GameState.Loading)
            {
                if (Vocabulary.Ready)
                {
                    if (!vocabLogged)
                    {
                        vocabLogged = true;
                        var st = Vocabulary.Stats;
                        Debug.Log("[WD] vocabulary.db loaded from " + Vocabulary.SourcePath + ": " + st.TotalRows + " rows, medium band " + st.Band + " -> "
                                  + Vocabulary.Pool.Count + " words and " + Vocabulary.BossSentences.Count + " boss sentences (" + st.LoadMs + " ms)");
                    }
                    if (Memory == null) Memory = SharedMemory ?? (SharedMemory = new MemoryBook(MemoryBook.DefaultPath(MemoryProfile)));
                    if (AutoStart) { AutoStart = false; StartGame(); }
                    else SetState(GameState.Title);
                }
                else if (Vocabulary.Failed)
                {
                    if (!vocabLogged) { vocabLogged = true; Debug.LogError("[WD] vocabulary.db could not be read: " + Vocabulary.Error); }
                    LoadError = Vocabulary.Error;
                    SetState(GameState.Title);
                }
                return;
            }
            if (State != GameState.Playing) return;
            float dt = Time.deltaTime;
            PlayTime += dt;
            PhaseTime += dt;
            SlowTimer = Mathf.Max(0f, SlowTimer - dt);
            SpeedMultiplier = SpeedAt(Wave, PlayTime);
            Enemies.RemoveAll(e => e == null);
            TickPhase();
            TickArmed();   // before the tray tick, so a vivid shell that fires itself is replaced in the same frame
            if (Phase != GamePhase.Ending) Tray.Tick();
            if (SelectedSlot >= 0 && Tray.Slots[SelectedSlot] == null) SelectedSlot = -1;
        }

        // ------------------------------------------------------------ flow
        public void StartGame()
        {
            if (!Vocabulary.Ready) return;
            if (Memory == null) Memory = SharedMemory ?? (SharedMemory = new MemoryBook(MemoryBook.DefaultPath(MemoryProfile)));
            foreach (var e in Enemies) if (e) Destroy(e.gameObject);
            Enemies.Clear();
            Boss = null;
            Deck = SessionDeck.Build(Memory, Environment.TickCount);
            Tray.Clear();
            Wave = 1;
            PlayTime = 0f;
            Combo = BestCombo = SkillCharge = 0;
            Score = Hits = Wrongs = Leaks = VividHits = 0;
            SlowTimer = 0f;
            SelectedSlot = -1;
            skillAnnounced = false;
            if (castle) castle.ResetCastle();
            gameStartTime = Time.time;
            BeginBreak(2.2f);
            SetState(GameState.Playing);
            Time.timeScale = 1f;
            Emit(new Feedback { Kind = FeedbackKind.WaveStart, Value = Wave });
            Audio.Play(Sfx.Id.WaveHorn, 0.8f);
        }

        void BeginBreak(float seconds)
        {
            Phase = GamePhase.Break;
            PhaseTime = 0f;
            nextSpawnAt = PlayTime + seconds;
            spawnedInWave = 0;
        }

        void TickPhase()
        {
            switch (Phase)
            {
                case GamePhase.Break:
                    if (PlayTime >= nextSpawnAt) { Phase = GamePhase.Waves; PhaseTime = 0f; }
                    break;
                case GamePhase.Waves:
                {
                    var def = Waves[Wave - 1];
                    int alive = Enemies.Count(e => e.Alive);
                    if (spawnedInWave < def.count && alive < def.maxAlive && PlayTime >= nextSpawnAt)
                    {
                        Spawn(PickKind(def), false);
                        spawnedInWave++;
                        nextSpawnAt = PlayTime + def.interval * UnityEngine.Random.Range(0.85f, 1.15f) / Mathf.Lerp(1f, SpeedMultiplier, 0.5f);
                    }
                    if (spawnedInWave >= def.count && alive == 0 && Enemies.Count == 0)
                    {
                        if (Wave < WaveCount)
                        {
                            Wave++;
                            BeginBreak(3.4f);
                            Emit(new Feedback { Kind = FeedbackKind.WaveStart, Value = Wave });
                            Audio.Play(Sfx.Id.WaveHorn, 0.8f);
                        }
                        else
                        {
                            Wave = WaveCount + 1;
                            Phase = GamePhase.BossIntro;
                            PhaseTime = 0f;
                            Emit(new Feedback { Kind = FeedbackKind.BossIncoming });
                            Audio.Play(Sfx.Id.BossHorn, 1f);
                            CameraRig.Shake(0.35f);
                        }
                    }
                    break;
                }
                case GamePhase.BossIntro:
                    if (PhaseTime >= 3.6f)
                    {
                        SpawnBoss();
                        Phase = GamePhase.Boss;
                        PhaseTime = 0f;
                        nextEscortAt = PlayTime + 6f;
                    }
                    break;
                case GamePhase.Boss:
                    if (PlayTime >= nextEscortAt)
                    {
                        int escorts = Enemies.Count(e => e.Alive && !(e is BossEnemy));
                        if (escorts < 2) Spawn(UnityEngine.Random.value < 0.5f ? EnemyKind.Scout : EnemyKind.Soldier, true);
                        nextEscortAt = PlayTime + 7.5f / Mathf.Lerp(1f, SpeedMultiplier, 0.4f);
                    }
                    break;
            }
        }

        EnemyKind PickKind(WaveDef d)
        {
            float r = UnityEngine.Random.value * (d.scout + d.soldier + d.brute);
            if (r < d.scout) return EnemyKind.Scout;
            if (r < d.scout + d.soldier) return EnemyKind.Soldier;
            return EnemyKind.Brute;
        }

        int SpawnsLeftBeforeBoss()
        {
            if (Wave > WaveCount) return 0;
            int left = Waves[Wave - 1].count - spawnedInWave;
            for (int w = Wave; w < WaveCount; w++) left += Waves[w].count;
            return left;
        }

        Enemy Spawn(EnemyKind kind, bool escort)
        {
            var onField = new HashSet<SessionWord>(Enemies.Where(e => e && e.Alive).Select(e => e.Word));
            var word = Deck.NextSpawn(onField, SpawnsLeftBeforeBoss(), escort);
            GameObject model = kind == EnemyKind.Scout ? scoutModel : (kind == EnemyKind.Brute ? bruteModel : soldierModel);
            var go = model != null ? Instantiate(model) : GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = kind + "_" + word.Word;
            var e = go.AddComponent<Enemy>();
            e.Init(this, kind, word);
            Enemies.Add(e);
            Fx.PortalPuff(Path.Sample(0f, out _) + Vector3.up * 1.2f);
            Audio.Play(Sfx.Id.Spawn, 0.35f, UnityEngine.Random.Range(0.9f, 1.1f));
            return e;
        }

        void SpawnBoss()
        {
            var go = bossModel != null ? Instantiate(bossModel) : GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = "Boss";
            var b = go.AddComponent<BossEnemy>();
            b.Init(this, EnemyKind.Boss, Deck.BossWords.Count > 0 ? Deck.BossWords[0] : Deck.Words[0]);
            b.SetupBoss(Deck.Boss, Deck.BossWords);
            Boss = b;
            Enemies.Add(b);
            Fx.PortalPuff(Path.Sample(0f, out _) + Vector3.up * 2f, 2.5f);
            CameraRig.Shake(0.5f);
            Audio.Play(Sfx.Id.BossRoar, 1f);
        }

        // ------------------------------------------------------------ input entry points (UI, keyboard and autopilot)
        public bool IsVivid(SessionWord w) { return w != null && Memory != null && Memory.IsVivid(w.Entry); }

        /// <summary>Card click or key 1–4. Normal shells are selected (then click an enemy); vivid shells fire on their own.</summary>
        public void ActivateSlot(int i)
        {
            if (State != GameState.Playing || i < 0 || i >= ShellTray.Size) return;
            var s = Tray.Slots[i];
            if (s == null) return;
            if (s.Vivid)
            {
                var target = MatchingTargets(s).FirstOrDefault();
                if (target != null) { FireHoming(i, target); return; }
                s.Armed = !s.Armed;
                Emit(new Feedback { Kind = FeedbackKind.Armed, ShellWord = s.Word, Value = s.Armed ? 1 : 0 });
                Audio.Play(Sfx.Id.Select, 0.6f, s.Armed ? 1.2f : 0.9f);
                return;
            }
            SelectedSlot = SelectedSlot == i ? -1 : i;
            Audio.Play(Sfx.Id.Select, 0.7f, SelectedSlot >= 0 ? 1f + i * 0.06f : 0.85f);
            if (SelectedSlot >= 0) Emit(new Feedback { Kind = FeedbackKind.Selected, ShellWord = s.Word, Value = i });
        }

        public void Deselect() { SelectedSlot = -1; }

        IEnumerable<Enemy> MatchingTargets(Shell s)
        {
            return Enemies.Where(e => e != null && Tray.Matches(s, e)).OrderByDescending(e => e is BossEnemy ? 2f : e.Progress);
        }

        /// <summary>World or word-tag click on an enemy.</summary>
        public bool ClickEnemy(Enemy e)
        {
            if (State != GameState.Playing || e == null || !e.Alive) return false;
            if (SelectedSlot < 0 || Tray.Slots[SelectedSlot] == null)
            {
                Emit(new Feedback { Kind = FeedbackKind.NeedShell, Enemy = e });
                Audio.Play(Sfx.Id.Deny, 0.5f);
                return false;
            }
            return Fire(SelectedSlot, e);
        }

        public bool Fire(int slot, Enemy e)
        {
            var s = Tray.Slots[slot];
            if (s == null || e == null || !e.Targetable) return false;
            if (Jammed)
            {
                Emit(new Feedback { Kind = FeedbackKind.Jammed });
                Audio.Play(Sfx.Id.Deny, 0.5f, 0.8f);
                return false;
            }
            var boss = e as BossEnemy;
            var targetWord = boss != null ? boss.TargetWord : e.Word;
            if (targetWord == null) return false;
            bool correct = ShellTray.Matches(s.Word, targetWord);
            float rt = Time.time - Mathf.Max(e.SpawnTime + 0.5f, s.CreatedAt);
            SelectedSlot = -1;
            cannon?.AimAt(e.AimPoint, 0.8f);
            cannon?.Fire();
            Audio.Play(Sfx.Id.Fire, 0.8f, UnityEngine.Random.Range(0.95f, 1.05f));
            CameraRig.Shake(0.08f);
            Vector3 from = cannon ? cannon.MuzzlePos : Path.Castle + Vector3.up * 4f;
            if (correct)
            {
                Tray.Consume(slot);
                int kw = -1;
                if (boss == null) e.Doomed = true;
                else kw = boss.ReserveHit();
                var shellWord = s.Word;
                Projectile.Launch(shellModel, from, () => e ? e.AimPoint : from, false, new Color(1f, 0.78f, 0.3f),
                    () => ResolveCorrect(e, shellWord, rt, false, from, kw));
            }
            else
            {
                JamUntil = Time.time + JamSeconds;
                bool order = boss != null && boss.KeywordIndexOf(s.Word) > boss.Effective;
                var shellWord = s.Word;
                Projectile.Launch(shellModel, from, () => e ? e.AimPoint : from, false, new Color(1f, 0.55f, 0.55f),
                    () => ResolveWrong(e, shellWord, targetWord, order, from));
            }
            return true;
        }

        void FireHoming(int slot, Enemy e)
        {
            var s = Tray.Slots[slot];
            if (s == null || e == null) return;
            var boss = e as BossEnemy;
            int kw = -1;
            if (boss == null) e.Doomed = true;
            else kw = boss.ReserveHit();
            Tray.Consume(slot);
            if (SelectedSlot == slot) SelectedSlot = -1;
            float rt = Time.time - Mathf.Max(e.SpawnTime + 0.5f, s.CreatedAt);
            cannon?.AimAt(e.AimPoint, 1.0f);
            cannon?.Fire();
            Audio.Play(Sfx.Id.Homing, 0.9f);
            Vector3 from = cannon ? cannon.MuzzlePos : Path.Castle + Vector3.up * 4f;
            var shellWord = s.Word;
            Projectile.Launch(shellModel, from, () => e ? e.AimPoint : from, true, new Color(1f, 0.92f, 0.55f),
                () => ResolveCorrect(e, shellWord, rt, true, from, kw));
        }

        void TickArmed()
        {
            if (State != GameState.Playing) return;
            for (int i = 0; i < ShellTray.Size; i++)
            {
                var s = Tray.Slots[i];
                if (s == null || !s.Armed) continue;
                var t = MatchingTargets(s).FirstOrDefault();
                if (t != null) FireHoming(i, t);
            }
        }

        void ResolveCorrect(Enemy e, SessionWord shellWord, float rt, bool homing, Vector3 from, int kw)
        {
            if (e == null) return;
            var boss = e as BossEnemy;
            if (boss == null && !e.Alive) return;
            if (boss != null && (boss.Defeated || kw < 0 || kw >= boss.Keywords.Count)) return;
            var w = boss != null ? boss.Keywords[kw] : e.Word;
            Hits++;
            if (homing) VividHits++;
            Combo++;
            BestCombo = Mathf.Max(BestCombo, Combo);
            if (SkillCharge < SkillCost) SkillCharge++;
            if (SkillReady && !skillAnnounced)
            {
                skillAnnounced = true;
                Emit(new Feedback { Kind = FeedbackKind.SkillReady });
                Audio.Play(Sfx.Id.SkillReady, 0.8f);
            }
            bool wasVivid = IsVivid(w);
            if (Memory != null) Memory.Review(w.Word, MemoryBook.GradeFor(rt), rt);
            w.Correct++;
            if (w.BestSeconds < 0f || rt < w.BestSeconds) w.BestSeconds = rt;
            bool nowVivid = IsVivid(w);
            int pts = 100 + 15 * Mathf.Min(Combo, 10) + (rt < 2f ? 50 : 0) + (boss != null ? 200 : 0);
            Score += pts;
            Emit(new Feedback { Kind = FeedbackKind.Correct, Enemy = e, Word = w, ShellWord = shellWord, Value = pts, Seconds = rt, Homing = homing, World = e.TagWorld });
            if (!wasVivid && nowVivid)
            {
                w.BecameVivid = true;
                Tray.RefreshVivid();
                Emit(new Feedback { Kind = FeedbackKind.VividNew, Word = w, World = e.TagWorld });
            }
            Fx.HitBurst(e.AimPoint, homing);
            Audio.Play(Sfx.Id.Hit, 0.9f, 1f + Mathf.Min(Combo, 8) * 0.045f);
            Audio.Play(Sfx.Id.Correct, 0.55f, 1f + Mathf.Min(Combo, 8) * 0.06f);
            if (boss != null)
            {
                if (boss.LandHit(kw, from) > 0)
                {
                    CameraRig.Shake(0.45f);
                    Audio.Play(Sfx.Id.BossBreak, 1f);
                    Emit(new Feedback { Kind = FeedbackKind.BossBreak, Enemy = boss, Word = w, Value = boss.Current });
                }
                if (boss.Defeated) StartCoroutine(VictoryRoutine(boss, from));
            }
            else
            {
                e.Kill(from);
                CameraRig.Shake(0.12f);
            }
        }

        void ResolveWrong(Enemy e, SessionWord shellWord, SessionWord targetWord, bool order, Vector3 from)
        {
            if (e == null || !e.Alive) return;
            Wrongs++;
            Combo = 0;
            if (!SkillReady) SkillCharge = 0;
            if (Memory != null && targetWord != null) Memory.Review(targetWord.Word, MemoryBook.Grade.Again);
            if (targetWord != null) Deck.OnWrong(targetWord);
            Tray.RefreshVivid();
            var boss = e as BossEnemy;
            if (boss != null) boss.Enrage();
            else e.Deflect(from);
            if (targetWord != null) { e.RevealText = targetWord.Gloss; e.RevealUntil = Time.time + 2.6f; }
            Fx.Deflect(e.AimPoint, from);
            CameraRig.Shake(0.18f);
            Audio.Play(Sfx.Id.Wrong, 0.9f);
            Emit(new Feedback { Kind = order ? FeedbackKind.OrderWrong : FeedbackKind.Wrong, Enemy = e, Word = targetWord, ShellWord = shellWord, World = e.TagWorld });
        }

        public void UseSkill()
        {
            if (State != GameState.Playing || !SkillReady || Phase == GamePhase.Ending) return;
            SkillCharge = 0;
            skillAnnounced = false;
            SlowTimer = SlowDuration;
            Vector3 from = cannon ? cannon.MuzzlePos : Path.Castle + Vector3.up * 4f;
            cannon?.AimAt(from + Vector3.up * 10f + Vector3.right * 10f, 0.6f);
            cannon?.Fire();
            Fx.FrostVolley(from, Path);
            CameraRig.Shake(0.3f);
            Audio.Play(Sfx.Id.Frost, 1f);
            Emit(new Feedback { Kind = FeedbackKind.SkillUsed });
        }

        public float SlowFactorFor(Enemy e) { return SlowTimer > 0f ? SlowFactor : 1f; }

        public void OnEnemyReachedCastle(Enemy e)
        {
            if (!e.Alive) return;
            if (e.Doomed) { e.Kill(e.transform.position + e.transform.forward); return; }   // the correct shell is still in flight
            var boss = e as BossEnemy;
            e.Leap(castle ? castle.Gate : Path.Castle, () =>
            {
                if (castle) castle.Damage(e.Damage);
                CameraRig.Shake(boss != null ? 1f : 0.4f);
                Audio.Play(Sfx.Id.CastleHit, 1f);
            });
            Leaks++;
            Combo = 0;
            if (!SkillReady) SkillCharge = 0;
            var w = boss != null ? boss.TargetWord ?? boss.CurrentWord : e.Word;
            if (w != null)
            {
                if (Memory != null) Memory.Review(w.Word, MemoryBook.Grade.Again);
                Deck.OnMissed(w);
                Tray.RefreshVivid();
            }
            Emit(new Feedback { Kind = FeedbackKind.Leak, Enemy = e, Word = w, Value = e.Damage, World = e.TagWorld });
            StartCoroutine(CheckDefeatSoon());
        }

        IEnumerator CheckDefeatSoon()
        {
            yield return new WaitForSeconds(0.4f);
            if (castle != null && castle.Hp <= 0 && Phase != GamePhase.Ending) StartCoroutine(DefeatRoutine());
        }

        IEnumerator VictoryRoutine(BossEnemy boss, Vector3 from)
        {
            Phase = GamePhase.Ending;
            SelectedSlot = -1;
            boss.Kill(from);
            foreach (var e in Enemies) if (e && e.Alive && e != boss) e.Kill(boss.transform.position);
            Time.timeScale = 0.45f;
            yield return new WaitForSeconds(0.9f);
            Time.timeScale = 1f;
            Audio.Play(Sfx.Id.Victory, 1f);
            yield return new WaitForSeconds(1.6f);
            FinishSession(true);
            SetState(GameState.Victory);
        }

        IEnumerator DefeatRoutine()
        {
            Phase = GamePhase.Ending;
            SelectedSlot = -1;
            if (castle) castle.Collapse();
            CameraRig.Shake(1f);
            Audio.Play(Sfx.Id.Defeat, 1f);
            Time.timeScale = 0.6f;
            yield return new WaitForSeconds(1.2f);
            Time.timeScale = 1f;
            yield return new WaitForSeconds(1.2f);
            FinishSession(false);
            SetState(GameState.Defeat);
        }

        void FinishSession(bool won)
        {
            if (Memory == null) return;
            Memory.Games++;
            if (won) Memory.Wins++;
            if (Deck != null && Deck.Boss != null) Memory.LastBoss = Deck.Boss.English;
            Memory.Save();
        }

        public int Accuracy { get { int n = Hits + Wrongs; return n == 0 ? 0 : Mathf.RoundToInt(100f * Hits / n); } }
        public float SessionSeconds { get { return PlayTime; } }

        // ------------------------------------------------------------ pause / restart
        public void TogglePause()
        {
            if (State == GameState.Playing) Pause();
            else if (State == GameState.Paused) Resume();
        }

        public void Pause()
        {
            if (State != GameState.Playing || Phase == GamePhase.Ending) return;
            Time.timeScale = 0f;
            SetState(GameState.Paused);
            Audio.Play(Sfx.Id.Select, 0.6f, 0.8f);
        }

        public void Resume()
        {
            if (State != GameState.Paused) return;
            Time.timeScale = 1f;
            SetState(GameState.Playing);
            Audio.Play(Sfx.Id.Select, 0.6f, 1.1f);
        }

        /// <summary>Reloads the scene; with skipTitle the next game starts immediately.</summary>
        public void Restart(bool skipTitle)
        {
            if (State == GameState.Playing || State == GameState.Paused) FinishSession(false);
            AutoStart = skipTitle;
            Time.timeScale = 1f;
            var scene = SceneManager.GetActiveScene();
            if (scene.buildIndex >= 0) SceneManager.LoadScene(scene.buildIndex);
            else SceneManager.LoadScene(scene.path);
        }

        public void Quit()
        {
            Application.Quit();
        }
    }
}
