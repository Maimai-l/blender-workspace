using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    public class KeyPickup : MonoBehaviour
    {
        public Transform visual;
        public Light glow;
        public ParticleSystem sparkle;
        bool taken;
        Vector3 basePos;

        float baseGlow = 1f;

        void Start() { if (visual != null) basePos = visual.localPosition; if (glow != null) baseGlow = glow.intensity; }

        void Update()
        {
            if (visual == null || taken) return;
            visual.localPosition = basePos + Vector3.up * Mathf.Sin(Time.time * 2f) * 0.08f;
            visual.Rotate(0f, 70f * Time.deltaTime, 0f, Space.World);
            if (glow != null) glow.intensity = baseGlow * (1f + Mathf.Sin(Time.time * 3f) * 0.2f);
        }

        void OnTriggerEnter(Collider other)
        {
            if (taken) return;
            var p = other.GetComponentInParent<PlayerController>();
            if (p == null || p.IsDead) return;
            taken = true;
            StartCoroutine(CollectRoutine(p));
        }

        IEnumerator CollectRoutine(PlayerController p)
        {
            AudioManager.Play2D(Sfx.Id.KeyPickup, 0.9f);
            Fx.Magic(visual != null ? visual.position : transform.position, new Color(1f, 0.8f, 0.3f), 40);
            var gm = GameManager.Instance;
            if (gm != null) gm.CollectKey();
            if (sparkle != null) sparkle.Stop();
            float t = 0f;
            Vector3 start = visual != null ? visual.position : transform.position;
            Vector3 startScale = visual != null ? visual.localScale : Vector3.one;
            while (t < 1f && visual != null)
            {
                t += Time.deltaTime / 0.7f;
                Vector3 tgt = p.transform.position + Vector3.up * 1.3f;
                visual.position = Vector3.Lerp(start, tgt, t * t) + Vector3.up * Mathf.Sin(t * Mathf.PI) * 0.8f;
                visual.localScale = startScale * Mathf.Lerp(1f, 0.2f, t);
                visual.Rotate(0f, 720f * Time.deltaTime, 0f, Space.World);
                if (glow != null) glow.intensity = Mathf.Lerp(baseGlow, 0f, t);
                yield return null;
            }
            if (visual != null) visual.gameObject.SetActive(false);
            if (glow != null) glow.enabled = false;
        }
    }
}
