using System.Collections.Generic;
using UnityEngine;

namespace WordDefense
{
    /// <summary>All game audio is synthesized at startup (no imported sound files). Primitives adapted from the
    /// Dungeon Escape synth; the sound designs and the music loop are new.</summary>
    public static class Sfx
    {
        public enum Id
        {
            Select, Deny, Fire, Homing, Hit, Correct, Wrong, Spawn, WaveHorn, BossHorn, BossRoar, BossBreak,
            CastleHit, SkillReady, Frost, Victory, Defeat, Card, Vivid, MusicLoop
        }

        const int SR = 44100;
        static readonly Dictionary<Id, AudioClip> cache = new Dictionary<Id, AudioClip>();

        public static AudioClip Get(Id id)
        {
            AudioClip c;
            if (cache.TryGetValue(id, out c) && c != null) return c;
            c = Make(id);
            cache[id] = c;
            return c;
        }

        // ------------------------------------------------------------ primitives
        static float[] Buf(float sec) { return new float[Mathf.CeilToInt(sec * SR)]; }

        static float Env(float t, float attack, float tau)
        {
            if (t < 0f) return 0f;
            if (t < attack) return t / attack;
            return Mathf.Exp(-(t - attack) / tau);
        }

        static void Sine(float[] b, float f0, float f1, float amp, float start, float dur, float attack, float tau, float vib = 0f, float vibRate = 5f)
        {
            int s0 = (int)(start * SR), n = (int)(dur * SR);
            double ph = 0;
            for (int i = 0; i < n && s0 + i < b.Length; i++)
            {
                float t = (float)i / SR;
                float f = Mathf.Lerp(f0, f1, Mathf.Clamp01(t / dur)) * (1f + vib * Mathf.Sin(2f * Mathf.PI * vibRate * t));
                ph += 2.0 * System.Math.PI * f / SR;
                b[s0 + i] += amp * Env(t, attack, tau) * (float)System.Math.Sin(ph);
            }
        }

        static void Harm(float[] b, float f, float amp, float start, float dur, float attack, float release, int harmonics, float bright, float vib = 0.004f)
        {
            int s0 = (int)(start * SR), n = (int)(dur * SR);
            double ph = 0;
            for (int i = 0; i < n && s0 + i < b.Length; i++)
            {
                float t = (float)i / SR;
                float e = t < attack ? t / attack : (t > dur - release ? Mathf.Clamp01((dur - t) / release) : 1f);
                float ff = f * (1f + vib * Mathf.Sin(2f * Mathf.PI * 5.2f * t));
                ph += 2.0 * System.Math.PI * ff / SR;
                float v = 0f;
                for (int h = 1; h <= harmonics; h++) v += Mathf.Pow(bright, h - 1) / h * (float)System.Math.Sin(ph * h);
                b[s0 + i] += amp * e * v;
            }
        }

        static void Noise(float[] b, float amp, float start, float dur, float attack, float tau, float lp0, float lp1, float hp, int seed, float am = 0f, float amRate = 0f)
        {
            var rng = new System.Random(seed);
            int s0 = (int)(start * SR), n = (int)(dur * SR);
            float low = 0f, low2 = 0f;
            for (int i = 0; i < n && s0 + i < b.Length; i++)
            {
                float t = (float)i / SR;
                float fc = Mathf.Lerp(lp0, lp1, Mathf.Clamp01(t / dur));
                float a = 1f - Mathf.Exp(-2f * Mathf.PI * fc / SR);
                float ah = 1f - Mathf.Exp(-2f * Mathf.PI * hp / SR);
                float x = (float)(rng.NextDouble() * 2.0 - 1.0);
                low += a * (x - low);
                low2 += ah * (low - low2);
                float y = hp > 0f ? low - low2 : low;
                float mod = am > 0f ? (1f - am + am * (0.5f + 0.5f * Mathf.Sin(2f * Mathf.PI * amRate * t))) : 1f;
                b[s0 + i] += amp * Env(t, attack, tau) * y * mod;
            }
        }

        static void Click(float[] b, float start, float amp, float freq, int seed)
        {
            Noise(b, amp, start, 0.03f, 0.0005f, 0.004f, 9000f, 9000f, 1500f, seed);
            Sine(b, freq, freq * 0.9f, amp * 0.5f, start, 0.05f, 0.0005f, 0.012f);
        }

        static AudioClip Finish(string name, float[] b, float peak = 0.9f, bool fadeEdges = true)
        {
            float m = 0f;
            for (int i = 0; i < b.Length; i++) m = Mathf.Max(m, Mathf.Abs(b[i]));
            if (m > 0f) { float k = peak / m; for (int i = 0; i < b.Length; i++) b[i] *= k; }
            if (fadeEdges)
            {
                int f = Mathf.Min(220, b.Length / 4);
                for (int i = 0; i < f; i++) b[b.Length - 1 - i] *= (float)i / f;
            }
            var clip = AudioClip.Create(name, b.Length, 1, SR, false);
            clip.SetData(b, 0);
            return clip;
        }

        static float Note(int semitonesFromA4) { return 440f * Mathf.Pow(2f, semitonesFromA4 / 12f); }

        static void Pluck(float[] b, float f, float amp, float start, float tau)
        {
            Harm(b, f, amp, start, tau * 4f, 0.004f, tau * 3f, 5, 0.45f, 0f);
        }

        // ------------------------------------------------------------ designs
        static AudioClip Make(Id id)
        {
            float[] b;
            switch (id)
            {
                case Id.Select:
                    b = Buf(0.12f);
                    Sine(b, 880f, 1180f, 0.6f, 0f, 0.09f, 0.002f, 0.03f);
                    Noise(b, 0.15f, 0f, 0.02f, 0.0005f, 0.004f, 8000f, 8000f, 2000f, 3);
                    return Finish("sfx_select", b, 0.6f);
                case Id.Deny:
                    b = Buf(0.22f);
                    Sine(b, 230f, 210f, 0.6f, 0f, 0.07f, 0.003f, 0.03f);
                    Sine(b, 190f, 170f, 0.6f, 0.09f, 0.09f, 0.003f, 0.04f);
                    return Finish("sfx_deny", b, 0.5f);
                case Id.Card:
                    b = Buf(0.1f);
                    Sine(b, 520f, 760f, 0.5f, 0f, 0.07f, 0.002f, 0.02f);
                    Noise(b, 0.2f, 0f, 0.04f, 0.001f, 0.01f, 5000f, 3000f, 800f, 4);
                    return Finish("sfx_card", b, 0.5f);
                case Id.Fire:
                    b = Buf(0.6f);
                    Sine(b, 95f, 38f, 1f, 0f, 0.45f, 0.002f, 0.12f);
                    Noise(b, 0.9f, 0f, 0.35f, 0.001f, 0.07f, 2400f, 300f, 40f, 5);
                    Noise(b, 0.35f, 0f, 0.03f, 0.0005f, 0.006f, 9000f, 9000f, 3000f, 6);
                    Noise(b, 0.25f, 0.04f, 0.4f, 0.05f, 0.12f, 1200f, 4000f, 600f, 7);
                    return Finish("sfx_fire", b, 0.9f);
                case Id.Homing:
                    b = Buf(0.9f);
                    Sine(b, 520f, 1500f, 0.5f, 0f, 0.8f, 0.02f, 0.35f, 0.02f, 9f);
                    Sine(b, 1040f, 3000f, 0.18f, 0f, 0.8f, 0.02f, 0.3f, 0.02f, 9f);
                    Noise(b, 0.25f, 0f, 0.7f, 0.1f, 0.2f, 3000f, 9000f, 1500f, 8);
                    Sine(b, 95f, 40f, 0.6f, 0f, 0.3f, 0.002f, 0.08f);
                    return Finish("sfx_homing", b, 0.8f);
                case Id.Hit:
                    b = Buf(0.35f);
                    Noise(b, 0.9f, 0f, 0.1f, 0.0005f, 0.02f, 7000f, 2500f, 300f, 9);
                    Sine(b, 320f, 110f, 0.8f, 0f, 0.2f, 0.001f, 0.05f);
                    Noise(b, 0.3f, 0.02f, 0.3f, 0.01f, 0.08f, 1200f, 600f, 100f, 10);
                    return Finish("sfx_hit", b, 0.85f);
                case Id.Correct:
                    b = Buf(0.7f);
                    Harm(b, Note(19), 0.45f, 0f, 0.55f, 0.004f, 0.45f, 3, 0.3f, 0f);
                    Harm(b, Note(26), 0.35f, 0.06f, 0.55f, 0.004f, 0.45f, 3, 0.3f, 0f);
                    Sine(b, Note(31), Note(31), 0.12f, 0.06f, 0.4f, 0.003f, 0.12f);
                    return Finish("sfx_correct", b, 0.7f);
                case Id.Wrong:
                    b = Buf(0.55f);
                    Harm(b, 138f, 0.6f, 0f, 0.4f, 0.004f, 0.3f, 7, 0.75f, 0f);
                    Harm(b, 146f, 0.45f, 0f, 0.4f, 0.004f, 0.3f, 7, 0.7f, 0f);
                    Sine(b, 640f, 600f, 0.25f, 0f, 0.3f, 0.001f, 0.06f);
                    Noise(b, 0.5f, 0f, 0.06f, 0.0005f, 0.015f, 3000f, 1500f, 300f, 11);
                    return Finish("sfx_wrong", b, 0.8f);
                case Id.Spawn:
                    b = Buf(0.7f);
                    Noise(b, 0.8f, 0f, 0.65f, 0.15f, 0.2f, 300f, 1600f, 120f, 12);
                    Sine(b, 70f, 110f, 0.4f, 0f, 0.6f, 0.15f, 0.2f);
                    return Finish("sfx_spawn", b, 0.6f);
                case Id.WaveHorn:
                    b = Buf(1.5f);
                    Harm(b, 220f, 0.5f, 0f, 1.3f, 0.12f, 0.6f, 6, 0.6f, 0.006f);
                    Harm(b, 330f, 0.35f, 0.1f, 1.2f, 0.12f, 0.6f, 6, 0.55f, 0.006f);
                    Harm(b, 440f, 0.2f, 0.25f, 1.05f, 0.1f, 0.6f, 4, 0.5f, 0.006f);
                    return Finish("sfx_wave", b, 0.7f);
                case Id.BossHorn:
                    b = Buf(2.6f);
                    Harm(b, 98f, 0.6f, 0f, 2.4f, 0.3f, 1f, 8, 0.7f, 0.01f);
                    Harm(b, 147f, 0.45f, 0.15f, 2.2f, 0.3f, 1f, 8, 0.65f, 0.01f);
                    Harm(b, 104f, 0.3f, 0.5f, 1.9f, 0.3f, 1f, 6, 0.6f, 0.01f);
                    Noise(b, 0.15f, 0f, 2.4f, 0.4f, 1f, 300f, 200f, 40f, 13, 0.5f, 6f);
                    return Finish("sfx_bosshorn", b, 0.85f);
                case Id.BossRoar:
                    b = Buf(1.6f);
                    Noise(b, 1f, 0f, 1.5f, 0.12f, 0.5f, 500f, 250f, 60f, 14, 0.6f, 23f);
                    Sine(b, 75f, 48f, 0.8f, 0f, 1.4f, 0.1f, 0.5f, 0.05f, 7f);
                    Harm(b, 110f, 0.3f, 0.05f, 1.2f, 0.1f, 0.6f, 9, 0.8f, 0.03f);
                    return Finish("sfx_bossroar", b, 0.9f);
                case Id.BossBreak:
                    b = Buf(1.2f);
                    Noise(b, 1f, 0f, 0.3f, 0.0005f, 0.07f, 6000f, 800f, 120f, 15);
                    Sine(b, 160f, 55f, 1f, 0f, 0.5f, 0.001f, 0.15f);
                    Harm(b, Note(22), 0.35f, 0.05f, 1f, 0.004f, 0.8f, 3, 0.35f, 0f);
                    Harm(b, Note(29), 0.25f, 0.12f, 0.9f, 0.004f, 0.7f, 3, 0.35f, 0f);
                    return Finish("sfx_bossbreak", b, 0.9f);
                case Id.CastleHit:
                    b = Buf(1.0f);
                    Sine(b, 75f, 32f, 1f, 0f, 0.8f, 0.002f, 0.22f);
                    Noise(b, 0.8f, 0f, 0.7f, 0.002f, 0.18f, 900f, 200f, 30f, 16);
                    for (int i = 0; i < 9; i++) Noise(b, 0.25f, 0.08f + i * 0.06f, 0.05f, 0.001f, 0.012f, 4000f, 2500f, 600f, 40 + i);
                    return Finish("sfx_castlehit", b, 0.9f);
                case Id.SkillReady:
                    b = Buf(0.9f);
                    int[] up = { 15, 19, 22, 27 };
                    for (int i = 0; i < up.Length; i++) Harm(b, Note(up[i]), 0.35f, i * 0.07f, 0.6f, 0.003f, 0.5f, 3, 0.25f, 0f);
                    Noise(b, 0.08f, 0f, 0.8f, 0.2f, 0.3f, 9000f, 9000f, 5000f, 17);
                    return Finish("sfx_skillready", b, 0.7f);
                case Id.Frost:
                    b = Buf(2.0f);
                    Noise(b, 0.9f, 0f, 1.2f, 0.05f, 0.35f, 2500f, 9000f, 1200f, 18);
                    Sine(b, 95f, 40f, 0.6f, 0f, 0.4f, 0.002f, 0.1f);
                    int[] ice = { 24, 31, 28, 36, 33, 40 };
                    for (int i = 0; i < ice.Length; i++) Harm(b, Note(ice[i]), 0.22f, 0.35f + i * 0.09f, 1.2f, 0.002f, 1f, 2, 0.2f, 0f);
                    return Finish("sfx_frost", b, 0.8f);
                case Id.Vivid:
                    b = Buf(1.1f);
                    int[] viv = { 12, 16, 19, 24, 28 };
                    for (int i = 0; i < viv.Length; i++) Harm(b, Note(viv[i]), 0.3f, i * 0.06f, 0.9f, 0.003f, 0.7f, 3, 0.3f, 0f);
                    return Finish("sfx_vivid", b, 0.65f);
                case Id.Victory:
                    b = Buf(3.2f);
                    int[] arp = { 3, 7, 10, 15 };
                    for (int i = 0; i < arp.Length; i++) Harm(b, Note(arp[i]), 0.35f, i * 0.12f, 0.5f, 0.005f, 0.3f, 5, 0.5f, 0f);
                    foreach (int n in new[] { 3, 7, 10, 15, -9 }) Harm(b, Note(n), 0.3f, 0.6f, 2.5f, 0.02f, 1.6f, 6, 0.5f, 0.005f);
                    Noise(b, 0.08f, 0.6f, 2f, 0.3f, 0.8f, 9000f, 9000f, 4000f, 19);
                    return Finish("sfx_victory", b, 0.85f);
                case Id.Defeat:
                    b = Buf(3.0f);
                    int[] down = { 0, -4, -7, -12 };
                    for (int i = 0; i < down.Length; i++) Harm(b, Note(down[i]), 0.4f, i * 0.45f, 1.2f, 0.04f, 0.8f, 6, 0.55f, 0.008f);
                    Sine(b, 60f, 35f, 0.6f, 0f, 2.6f, 0.05f, 1.2f);
                    Noise(b, 0.3f, 0f, 2.5f, 0.05f, 1f, 600f, 150f, 30f, 20);
                    return Finish("sfx_defeat", b, 0.85f);
                case Id.MusicLoop:
                    return MakeMusic();
            }
            return Finish("silence", Buf(0.05f));
        }

        /// <summary>A calm 16-second loop: four soft pad chords with a pentatonic pluck pattern.</summary>
        static AudioClip MakeMusic()
        {
            float len = 16f;
            var b = Buf(len);
            int[][] chords = { new[] { -9, -5, -2, 2 }, new[] { -12, -9, -5, -2 }, new[] { -16, -12, -9, -5 }, new[] { -14, -10, -7, -2 } };
            for (int c = 0; c < 4; c++)
                foreach (int n in chords[c])
                    Harm(b, Note(n), 0.16f, c * 4f, 4.2f, 0.8f, 1.2f, 4, 0.35f, 0.003f);
            int[] scale = { 3, 5, 7, 10, 12, 15, 17, 19 };
            var rng = new System.Random(5);
            for (int k = 0; k < 32; k++)
            {
                if (k % 8 == 7) continue;
                int n = scale[(k * 3 + rng.Next(3)) % scale.Length];
                Pluck(b, Note(n), k % 4 == 0 ? 0.12f : 0.08f, k * 0.5f, 0.18f);
            }
            // fold the tail into the head so the loop is seamless
            int tail = (int)(1.2f * SR);
            var clip = AudioClip.Create("music_loop", b.Length, 1, SR, false);
            float m = 0f;
            for (int i = 0; i < b.Length; i++) m = Mathf.Max(m, Mathf.Abs(b[i]));
            if (m > 0f) for (int i = 0; i < b.Length; i++) b[i] *= 0.55f / m;
            for (int i = 0; i < tail && i < b.Length; i++) b[i] = b[i] * Mathf.Clamp01(i / (float)tail * 1.5f) + 0f;
            clip.SetData(b, 0);
            return clip;
        }
    }

    /// <summary>Pooled 2D one-shots and the music loop.</summary>
    public static class Audio
    {
        static AudioSource[] pool;
        static AudioSource music;
        static int next;
        public static float SfxVolume = 0.9f, MusicVolume = 0.32f;

        public static void Init(GameObject host)
        {
            pool = new AudioSource[24];
            for (int i = 0; i < pool.Length; i++)
            {
                var s = host.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.spatialBlend = 0f;
                pool[i] = s;
            }
            music = host.AddComponent<AudioSource>();
            music.playOnAwake = false;
            music.loop = true;
            music.spatialBlend = 0f;
            foreach (Sfx.Id id in System.Enum.GetValues(typeof(Sfx.Id))) Sfx.Get(id);
        }

        public static void Play(Sfx.Id id, float vol = 1f, float pitch = 1f)
        {
            if (pool == null) return;
            var s = pool[next];
            next = (next + 1) % pool.Length;
            if (s == null) return;
            s.pitch = pitch;
            s.PlayOneShot(Sfx.Get(id), vol * SfxVolume);
        }

        public static void PlayMusic()
        {
            if (music == null) return;
            music.clip = Sfx.Get(Sfx.Id.MusicLoop);
            music.volume = MusicVolume;
            if (!music.isPlaying) music.Play();
        }
    }
}
