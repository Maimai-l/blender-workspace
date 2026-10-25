using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>Flickering torch / brazier. Path torches start unlit and ignite after the key is taken.</summary>
    public class Torch : MonoBehaviour
    {
        public Light lightSource;
        public ParticleSystem flame;
        public float baseIntensity = 4f;
        public bool startLit = true;
        public AudioSource crackle;
        float seed;
        float lit;
        float igniteAt = -1f;

        void Awake()
        {
            seed = Random.value * 100f;
            lit = startLit ? 1f : 0f;
            Apply();
            if (!startLit && flame != null) flame.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }

        public void Ignite(float delay, bool instant)
        {
            if (instant) { lit = 1f; if (flame != null) flame.Play(); Apply(); igniteAt = -1f; return; }
            igniteAt = Time.time + delay;
        }

        void Update()
        {
            if (igniteAt > 0f && Time.time >= igniteAt)
            {
                igniteAt = -1f;
                if (flame != null) flame.Play();
                Fx.Embers(transform.position + Vector3.up * 0.1f, 12);
                AudioManager.PlayAt(Sfx.Id.Ignite, transform.position, 0.6f, Random.Range(0.9f, 1.1f));
                StartCoroutine(FadeIn());
            }
            Apply();
        }

        IEnumerator FadeIn()
        {
            float t = 0f;
            while (t < 1f) { t += Time.deltaTime * 2.5f; lit = Mathf.Max(lit, t); yield return null; }
            lit = 1f;
        }

        void Apply()
        {
            if (lightSource == null) return;
            float n = Mathf.PerlinNoise(seed, Time.time * 7f) * 0.6f + Mathf.PerlinNoise(seed + 9f, Time.time * 17f) * 0.4f;
            lightSource.intensity = baseIntensity * lit * (0.78f + 0.32f * n);
            lightSource.enabled = lit > 0.01f;
            if (crackle != null) crackle.volume = 0.35f * lit;
        }
    }
}
