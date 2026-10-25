using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DungeonEscape
{
    public enum GameState { Title, Playing, Paused, Dead, Victory }

    /// <summary>Owns the game flow: title, objectives, key/door/encounter progress, pause, defeat, victory, restart and checkpoint.</summary>
    [DefaultExecutionOrder(-100)]
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        // Survive scene reloads (restart / checkpoint retry).
        static bool s_skipTitle;
        static bool s_checkpointUnlocked;
        static bool s_spawnAtCheckpoint;
        public static int SessionRestarts { get; private set; }
        public static bool SkipTitleOnLoad { get { return s_skipTitle; } set { s_skipTitle = value; } }
        public static bool CheckpointUnlocked { get { return s_checkpointUnlocked; } }

        [Header("Scene references (assigned by the level builder)")]
        public Transform checkpointPoint;
        public KeyPickup keyPickup;
        public LockedDoor greatDoor;
        public ArenaEncounter encounter;
        public Transform titleCameraPoint;
        public Light titleLight;
        public List<EnemyAI> keyRoomGuards = new List<EnemyAI>();
        public List<Torch> pathTorches = new List<Torch>();

        [Header("Combat pacing")]
        public int maxSimultaneousAttackers = 2;

        public GameState State { get; private set; }
        public bool HasKey { get; private set; }
        public bool DoorOpened { get; private set; }
        public bool EncounterStarted { get; private set; }
        public bool EncounterCleared { get; private set; }
        public int EncounterTotal { get; private set; }
        public int EncounterRemaining { get; private set; }
        public int EncounterWave { get; private set; }
        public int EncounterWaves { get; private set; }
        public int Kills { get; private set; }
        public float DamageTaken { get; set; }
        public float PlayTime { get; private set; }
        public string Objective { get; private set; }
        public bool StartedFromCheckpoint { get; private set; }
        public EnemyAI ActiveBoss { get; set; }

        public PlayerController Player { get; private set; }
        public ThirdPersonCamera Cam { get; private set; }
        public readonly List<EnemyAI> Enemies = new List<EnemyAI>();
        readonly HashSet<EnemyAI> attackers = new HashSet<EnemyAI>();

        public event Action<GameState> StateChanged;
        public event Action<string> ObjectiveChanged;
        public event Action<string, string> Toast;
        public event Action KeyCollectedEvent;
        public event Action DoorOpenedEvent;
        public event Action EncounterStartedEvent;
        public event Action EncounterProgressEvent;
        public event Action EncounterClearedEvent;

        void Awake()
        {
            Instance = this;
            Time.timeScale = 1f;
            State = GameState.Title;
            Player = FindAnyObjectByType<PlayerController>();
            Cam = FindAnyObjectByType<ThirdPersonCamera>();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void Start()
        {
            SetObjective("Escape the dungeon");
            if (s_spawnAtCheckpoint && s_checkpointUnlocked)
            {
                ApplyCheckpoint();
            }
            s_spawnAtCheckpoint = false;
            if (s_skipTitle)
            {
                s_skipTitle = false;
                StartGame();
            }
            else
            {
                SetState(GameState.Title);
            }
        }

        void ApplyCheckpoint()
        {
            StartedFromCheckpoint = true;
            HasKey = true;
            DoorOpened = true;
            if (keyPickup != null) keyPickup.gameObject.SetActive(false);
            foreach (var g in keyRoomGuards) if (g != null) g.gameObject.SetActive(false);
            foreach (var t in pathTorches) if (t != null) t.Ignite(0f, true);
            if (greatDoor != null) greatDoor.OpenInstant();
            if (Player != null && checkpointPoint != null) Player.Teleport(checkpointPoint.position, checkpointPoint.rotation);
            if (Cam != null && checkpointPoint != null) Cam.SnapBehind(checkpointPoint.rotation.eulerAngles.y);
        }

        void Update()
        {
            if (State == GameState.Playing) PlayTime += Time.unscaledDeltaTime;
            var input = InputHub.Read();
            if (input.pause)
            {
                Debug.Log("[GM] pause input frame=" + Time.frameCount + " state=" + State + " src=" + InputHub.LastPauseSource);
                if (State == GameState.Playing) Pause();
                else if (State == GameState.Paused) Resume();
            }
            if (State == GameState.Title && input.confirm) StartGame();
        }

        void SetState(GameState s)
        {
            State = s;
            bool lockCursor = s == GameState.Playing;
            Cursor.lockState = lockCursor ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !lockCursor;
            if (StateChanged != null) StateChanged(s);
        }

        public void SetObjective(string text)
        {
            Objective = text;
            if (ObjectiveChanged != null) ObjectiveChanged(text);
        }

        public void ShowToast(string title, string subtitle)
        {
            if (Toast != null) Toast(title, subtitle);
        }

        // ------------------------------------------------------------ flow
        public void StartGame()
        {
            if (State != GameState.Title) return;
            Time.timeScale = 1f;
            SetState(GameState.Playing);
            if (titleLight != null) StartCoroutine(FadeOutLight(titleLight, 1.6f));
            if (Cam != null) Cam.BeginGameplay(!StartedFromCheckpoint);
            if (StartedFromCheckpoint)
            {
                SetObjective("Enter the crypt and defeat its guardians");
                ShowToast("CHECKPOINT", "The sealed door stands open");
            }
            else
            {
                SetObjective("Find a way out of the cells");
                StartCoroutine(OpeningHints());
            }
            AudioManager.Play2D(Sfx.Id.UiConfirm, 0.6f);
        }

        IEnumerator FadeOutLight(Light l, float seconds)
        {
            float start = l.intensity, t = 0f;
            while (t < 1f && l != null) { t += Time.unscaledDeltaTime / seconds; l.intensity = Mathf.Lerp(start, 0f, t); yield return null; }
            if (l != null) l.enabled = false;
        }

        IEnumerator OpeningHints()
        {
            yield return new WaitForSeconds(1.2f);
            ShowToast("THE DUNGEON", "Your cell door has been left ajar...");
        }

        public void Pause()
        {
            if (State != GameState.Playing) return;
            Time.timeScale = 0f;
            SetState(GameState.Paused);
            AudioManager.SetPaused(true);
        }

        public void Resume()
        {
            if (State != GameState.Paused) return;
            Time.timeScale = 1f;
            SetState(GameState.Playing);
            AudioManager.SetPaused(false);
        }

        public void Restart(bool fromCheckpoint)
        {
            SessionRestarts++;
            s_skipTitle = true;
            s_spawnAtCheckpoint = fromCheckpoint && s_checkpointUnlocked;
            if (!fromCheckpoint) s_checkpointUnlocked = false;
            Time.timeScale = 1f;
            AudioManager.SetPaused(false);
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
        }

        public void QuitGame()
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }

        // ------------------------------------------------------------ progress
        public void OnEnteredCorridor()
        {
            if (!HasKey && Objective == "Find a way out of the cells") SetObjective("Follow the torches deeper into the dungeon");
        }

        public void OnSawDoor()
        {
            if (!HasKey && !DoorOpened) SetObjective("The great door is sealed. Find its key");
        }

        public void CollectKey()
        {
            if (HasKey) return;
            HasKey = true;
            SetObjective("Return to the great door and unlock it");
            ShowToast("IRON KEY OBTAINED", "The sealed door in the great hall can now be opened");
            for (int i = 0; i < pathTorches.Count; i++) if (pathTorches[i] != null) pathTorches[i].Ignite(0.6f + i * 0.35f, false);
            if (KeyCollectedEvent != null) KeyCollectedEvent();
        }

        public void OnDoorOpened()
        {
            if (DoorOpened) return;
            DoorOpened = true;
            s_checkpointUnlocked = true;
            SetObjective("Enter the crypt beyond the door");
            if (DoorOpenedEvent != null) DoorOpenedEvent();
        }

        public void OnEncounterStarted(int total, int waves)
        {
            EncounterStarted = true;
            EncounterTotal = total;
            EncounterRemaining = total;
            EncounterWaves = waves;
            EncounterWave = 1;
            SetObjective("Defeat the crypt guardians");
            if (EncounterStartedEvent != null) EncounterStartedEvent();
            if (EncounterProgressEvent != null) EncounterProgressEvent();
        }

        public void OnEncounterWave(int wave)
        {
            EncounterWave = wave;
            if (EncounterProgressEvent != null) EncounterProgressEvent();
        }

        public void OnEncounterKill()
        {
            EncounterRemaining = Mathf.Max(0, EncounterRemaining - 1);
            if (EncounterProgressEvent != null) EncounterProgressEvent();
        }

        public void OnEncounterCleared()
        {
            if (EncounterCleared) return;
            EncounterCleared = true;
            EncounterRemaining = 0;
            SetObjective("Escape through the north gate");
            ShowToast("THE WAY IS OPEN", "The guardians have fallen. Escape!");
            if (EncounterProgressEvent != null) EncounterProgressEvent();
            if (EncounterClearedEvent != null) EncounterClearedEvent();
        }

        public void RegisterEnemy(EnemyAI e) { if (!Enemies.Contains(e)) Enemies.Add(e); }

        public void UnregisterEnemy(EnemyAI e)
        {
            Enemies.Remove(e);
            attackers.Remove(e);
        }

        public void OnEnemyKilled(EnemyAI e)
        {
            Kills++;
            attackers.Remove(e);
        }

        public bool RequestAttackToken(EnemyAI e)
        {
            attackers.RemoveWhere(x => x == null || x.IsDead || !x.isActiveAndEnabled);
            if (attackers.Contains(e)) return true;
            if (attackers.Count < maxSimultaneousAttackers) { attackers.Add(e); return true; }
            return false;
        }

        public void ReleaseAttackToken(EnemyAI e) { attackers.Remove(e); }

        public void OnPlayerDied()
        {
            if (State != GameState.Playing) return;
            StartCoroutine(DefeatRoutine());
        }

        IEnumerator DefeatRoutine()
        {
            SetObjective("You have fallen");
            AudioManager.StopMusic(1.5f);
            AudioManager.Play2D(Sfx.Id.Defeat, 0.9f);
            yield return new WaitForSeconds(2.4f);
            SetState(GameState.Dead);
        }

        public void OnReachedExit()
        {
            if (State != GameState.Playing || !EncounterCleared) return;
            StartCoroutine(VictoryRoutine());
        }

        IEnumerator VictoryRoutine()
        {
            if (Player != null) Player.Celebrate();
            if (Cam != null) Cam.SetVictory();
            AudioManager.StopMusic(1f);
            AudioManager.Play2D(Sfx.Id.Victory, 0.9f);
            SetObjective("You escaped!");
            yield return new WaitForSeconds(2.6f);
            SetState(GameState.Victory);
        }
    }
}
