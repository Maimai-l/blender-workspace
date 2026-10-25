using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>The crypt arena: locks the player in, spawns two waves, then opens the exit.</summary>
    public class ArenaEncounter : MonoBehaviour
    {
        public Gate entranceGate;
        public Gate exitGate;
        public RuneGlow runes;
        public Transform[] spawnPoints;
        public GameObject skeletonPrefab;
        public GameObject wardenPrefab;
        public Torch[] braziers;

        bool started;
        readonly List<EnemyAI> live = new List<EnemyAI>();
        float stuckCheck;

        public bool Started { get { return started; } }

        void Start()
        {
            if (runes != null) runes.SetTarget(new Color(0.35f, 0.05f, 0.04f), 0.6f, 0.01f);
        }

        void OnTriggerEnter(Collider other)
        {
            if (started) return;
            var p = other.GetComponentInParent<PlayerController>();
            var gm = GameManager.Instance;
            if (p == null || p.IsDead || gm == null || !gm.DoorOpened) return;
            started = true;
            StartCoroutine(Run());
        }

        IEnumerator Run()
        {
            var gm = GameManager.Instance;
            gm.OnEncounterStarted(6, 2);
            if (entranceGate != null) entranceGate.Slam();
            AudioManager.Play2D(Sfx.Id.Boom, 1f);
            if (runes != null) { runes.SetTarget(new Color(1f, 0.12f, 0.05f), 2.6f, 1.2f); runes.pulse = 0.25f; runes.pulseSpeed = 3f; }
            if (braziers != null) foreach (var b in braziers) if (b != null) b.Ignite(0.3f, false);
            gm.ShowToast("THE CRYPT AWAKENS", "Defeat the guardians to open the way");
            AudioManager.PlayMusic(Sfx.Id.CombatLoop, 0.5f, 2f);
            yield return new WaitForSeconds(1.6f);
            yield return SpawnWave(new[] { skeletonPrefab, skeletonPrefab, skeletonPrefab });
            yield return WaitForWave();
            yield return new WaitForSeconds(1.6f);
            gm.OnEncounterWave(2);
            gm.ShowToast("THE WARDEN RISES", "The master of the crypt joins the fight");
            AudioManager.Play2D(Sfx.Id.Boom, 0.9f);
            if (gm.Cam != null) gm.Cam.Shake(0.5f);
            yield return new WaitForSeconds(0.8f);
            yield return SpawnWave(new[] { wardenPrefab, skeletonPrefab, skeletonPrefab });
            yield return WaitForWave();
            yield return new WaitForSeconds(1.2f);
            if (runes != null) { runes.SetTarget(new Color(0.3f, 0.85f, 1f), 2.2f, 2.5f); runes.pulse = 0.1f; runes.pulseSpeed = 1.5f; }
            if (exitGate != null) exitGate.Open(2.4f);
            if (entranceGate != null) entranceGate.Open(2.4f);
            AudioManager.StopMusic(2.5f);
            gm.OnEncounterCleared();
        }

        IEnumerator WaitForWave()
        {
            while (live.Count > 0)
            {
                stuckCheck += Time.deltaTime;
                if (stuckCheck > 1f)
                {
                    stuckCheck = 0f;
                    // Failsafe: enemies that lost the navmesh can never be reached, so they are removed.
                    for (int i = live.Count - 1; i >= 0; i--)
                    {
                        var e = live[i];
                        if (e == null) { live.RemoveAt(i); GameManager.Instance.OnEncounterKill(); continue; }
                        var ag = e.GetComponent<NavMeshAgent>();
                        if (!e.IsDead && ag != null && ag.enabled && !ag.isOnNavMesh && e.transform.position.y < -3f)
                            e.TakeHit(9999f, e.transform.position + Vector3.forward, 0f, true);
                    }
                }
                yield return null;
            }
        }

        IEnumerator SpawnWave(GameObject[] prefabs)
        {
            var gm = GameManager.Instance;
            var used = new List<int>();
            foreach (var prefab in prefabs)
            {
                if (prefab == null) continue;
                int idx = PickSpawn(used);
                used.Add(idx);
                Transform sp = spawnPoints[idx];
                Vector3 pos = sp.position;
                NavMeshHit nh;
                if (NavMesh.SamplePosition(pos, out nh, 2f, NavMesh.AllAreas)) pos = nh.position;
                Vector3 look = gm.Player != null ? gm.Player.transform.position - pos : sp.forward;
                look.y = 0f;
                var go = Instantiate(prefab, pos, Quaternion.LookRotation(look.sqrMagnitude > 0.01f ? look : Vector3.forward));
                var e = go.GetComponent<EnemyAI>();
                e.Died += OnEnemyDied;
                live.Add(e);
                if (e.isBoss) gm.ActiveBoss = e;
                e.SpawnRise();
                yield return new WaitForSeconds(0.4f);
            }
        }

        int PickSpawn(List<int> used)
        {
            var gm = GameManager.Instance;
            Vector3 pp = gm != null && gm.Player != null ? gm.Player.transform.position : transform.position;
            int best = 0; float bestScore = float.MinValue;
            for (int i = 0; i < spawnPoints.Length; i++)
            {
                if (used.Contains(i)) continue;
                float d = Vector3.Distance(spawnPoints[i].position, pp);
                float score = (d >= 4.5f ? 10f : 0f) - Mathf.Abs(d - 7f) + Random.value * 3f;
                if (score > bestScore) { bestScore = score; best = i; }
            }
            return best;
        }

        void OnEnemyDied(EnemyAI e)
        {
            live.Remove(e);
            var gm = GameManager.Instance;
            if (gm == null) return;
            if (gm.ActiveBoss == e) gm.ActiveBoss = null;
            gm.OnEncounterKill();
        }
    }
}
