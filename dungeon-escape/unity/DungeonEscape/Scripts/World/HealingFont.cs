using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>Restores health while the player stands in its glow.</summary>
    public class HealingFont : MonoBehaviour
    {
        public float radius = 2.4f;
        public float healPerSecond = 35f;
        public Light glow;
        public ParticleSystem motes;
        float baseIntensity = 2.5f;
        float active;
        bool announced;
        float sfxTimer;

        void Start() { if (glow != null) baseIntensity = glow.intensity; }

        void Update()
        {
            var gm = GameManager.Instance;
            var p = gm != null ? gm.Player : null;
            bool healing = false;
            if (p != null && !p.IsDead && gm.State == GameState.Playing)
            {
                Vector3 d = p.transform.position - transform.position; d.y = 0f;
                if (d.magnitude < radius && p.health.current < p.health.max)
                {
                    healing = true;
                    p.health.Heal(healPerSecond * Time.deltaTime);
                    sfxTimer -= Time.deltaTime;
                    if (sfxTimer <= 0f) { sfxTimer = 0.9f; AudioManager.PlayAt(Sfx.Id.Heal, transform.position + Vector3.up, 0.5f, 1f); }
                    if (!announced) { announced = true; gm.ShowToast("HEALING SPRING", "Its waters restore your strength"); }
                }
            }
            active = Mathf.MoveTowards(active, healing ? 1f : 0f, Time.deltaTime * 3f);
            if (glow != null) glow.intensity = baseIntensity * (1f + active * 0.8f + Mathf.Sin(Time.time * 2.2f) * 0.1f);
        }
    }
}
