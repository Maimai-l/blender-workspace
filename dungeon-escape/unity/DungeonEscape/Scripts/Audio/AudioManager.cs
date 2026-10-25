using System.Collections;
using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Pooled one-shots, ambience, combat music and the low-health heartbeat.</summary>
    public class AudioManager : MonoBehaviour
    {
        static AudioManager inst;
        AudioSource[] pool;
        int next;
        AudioSource music, ambient, heartbeat;
        Coroutine musicFade;

        public static AudioManager Ensure()
        {
            if (inst != null) return inst;
            inst = FindAnyObjectByType<AudioManager>();
            if (inst == null) inst = new GameObject("AudioManager").AddComponent<AudioManager>();
            inst.Init();
            return inst;
        }

        bool inited;

        void Awake()
        {
            if (inst != null && inst != this) { Destroy(gameObject); return; }
            inst = this;
            Init();
        }

        void OnDestroy() { if (inst == this) inst = null; }

        void Init()
        {
            if (inited) return;
            inited = true;
            pool = new AudioSource[28];
            for (int i = 0; i < pool.Length; i++)
            {
                var go = new GameObject("sfx" + i);
                go.transform.SetParent(transform, false);
                var s = go.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.rolloffMode = AudioRolloffMode.Linear;
                s.minDistance = 2f; s.maxDistance = 30f;
                s.dopplerLevel = 0f;
                pool[i] = s;
            }
            foreach (Sfx.Id id in System.Enum.GetValues(typeof(Sfx.Id))) Sfx.Get(id);
            music = MakeLoop("music", 0f);
            ambient = MakeLoop("ambient", 0.32f);
            ambient.clip = Sfx.Get(Sfx.Id.AmbientLoop);
            ambient.Play();
            heartbeat = MakeLoop("heartbeat", 0f);
            heartbeat.clip = Sfx.Get(Sfx.Id.HeartbeatLoop);
            heartbeat.Play();
            var rz = gameObject.AddComponent<AudioReverbZone>();
            rz.reverbPreset = AudioReverbPreset.StoneCorridor;
            rz.minDistance = 400f; rz.maxDistance = 500f;
        }

        AudioSource MakeLoop(string name, float vol)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var s = go.AddComponent<AudioSource>();
            s.loop = true; s.playOnAwake = false; s.spatialBlend = 0f; s.volume = vol;
            return s;
        }

        void Update()
        {
            var gm = GameManager.Instance;
            float target = 0f;
            if (gm != null && gm.Player != null && !gm.Player.IsDead && gm.State == GameState.Playing)
            {
                float f = gm.Player.health.Fraction;
                if (f < 0.35f) target = Mathf.Lerp(0.55f, 0.15f, f / 0.35f);
            }
            heartbeat.volume = Mathf.MoveTowards(heartbeat.volume, target, Time.unscaledDeltaTime);
            heartbeat.pitch = target > 0.4f ? 1.25f : 1f;
        }

        AudioSource Next()
        {
            for (int k = 0; k < pool.Length; k++)
            {
                var s = pool[(next + k) % pool.Length];
                if (!s.isPlaying) { next = (next + k + 1) % pool.Length; return s; }
            }
            var r = pool[next]; next = (next + 1) % pool.Length; return r;
        }

        public static void Play2D(Sfx.Id id, float volume, float pitch = 1f)
        {
            var m = Ensure();
            var s = m.Next();
            s.transform.localPosition = Vector3.zero;
            s.spatialBlend = 0f;
            s.clip = Sfx.Get(id); s.volume = volume; s.pitch = pitch;
            s.ignoreListenerPause = true;
            s.Play();
        }

        public static void PlayAt(Sfx.Id id, Vector3 pos, float volume, float pitch = 1f)
        {
            var m = Ensure();
            var s = m.Next();
            s.transform.position = pos;
            s.spatialBlend = 0.85f;
            s.clip = Sfx.Get(id); s.volume = volume; s.pitch = pitch;
            s.ignoreListenerPause = false;
            s.Play();
        }

        public static AudioSource AttachLoop(Sfx.Id id, Transform parent, float volume, float maxDistance)
        {
            var go = new GameObject("loop_" + id);
            go.transform.SetParent(parent, false);
            var s = go.AddComponent<AudioSource>();
            s.clip = Sfx.Get(id);
            s.loop = true; s.spatialBlend = 1f; s.volume = volume;
            s.rolloffMode = AudioRolloffMode.Linear; s.minDistance = 1f; s.maxDistance = maxDistance;
            s.dopplerLevel = 0f;
            s.time = Random.Range(0f, s.clip.length * 0.9f);
            s.Play();
            return s;
        }

        public static void PlayMusic(Sfx.Id id, float volume, float fade)
        {
            var m = Ensure();
            m.music.clip = Sfx.Get(id);
            m.music.volume = 0f;
            m.music.Play();
            if (m.musicFade != null) m.StopCoroutine(m.musicFade);
            m.musicFade = m.StartCoroutine(m.Fade(m.music, volume, fade, false));
        }

        public static void StopMusic(float fade)
        {
            var m = Ensure();
            if (!m.music.isPlaying) return;
            if (m.musicFade != null) m.StopCoroutine(m.musicFade);
            m.musicFade = m.StartCoroutine(m.Fade(m.music, 0f, fade, true));
        }

        IEnumerator Fade(AudioSource s, float to, float seconds, bool stopAtEnd)
        {
            float from = s.volume, t = 0f;
            while (t < 1f)
            {
                t += Time.unscaledDeltaTime / Mathf.Max(0.01f, seconds);
                s.volume = Mathf.Lerp(from, to, t);
                yield return null;
            }
            if (stopAtEnd) s.Stop();
        }

        public static void SetPaused(bool paused)
        {
            AudioListener.pause = paused;
        }
    }
}
