using System.Collections.Generic;
using UnityEngine;

namespace DungeonEscape
{
    /// <summary>All game audio is synthesized here at runtime (no imported sound files).</summary>
    public static class Sfx
    {
        public enum Id
        {
            Footstep, Swing, SwingHeavy, HitBone, PlayerHurt, EnemyDie, Growl, Telegraph, KeyPickup, Unlock, Locked,
            DoorOpen, GateOpen, GateSlam, Jump, Land, Dodge, Heal, Orb, Victory, Defeat, UiClick, UiConfirm, Ignite, Rise, Boom,
            AmbientLoop, TorchLoop, CombatLoop, HeartbeatLoop
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

        // ------------------------------------------------------------ designs
        static AudioClip Make(Id id)
        {
            float[] b;
            switch (id)
            {
                case Id.Footstep:
                    b = Buf(0.18f);
                    Noise(b, 0.7f, 0f, 0.14f, 0.002f, 0.03f, 900f, 700f, 70f, 11);
                    Sine(b, 120f, 55f, 0.55f, 0f, 0.12f, 0.002f, 0.025f);
                    Noise(b, 0.12f, 0.005f, 0.05f, 0.001f, 0.008f, 7000f, 7000f, 2500f, 12);
                    Sine(b, 2600f, 2500f, 0.04f, 0.01f, 0.06f, 0.001f, 0.02f);
                    return Finish("sfx_footstep", b, 0.8f);
                case Id.Swing:
                    b = Buf(0.34f);
                    Noise(b, 0.9f, 0f, 0.32f, 0.07f, 0.07f, 1500f, 5500f, 500f, 21);
                    Noise(b, 0.25f, 0.02f, 0.25f, 0.05f, 0.05f, 7000f, 9000f, 3000f, 22);
                    return Finish("sfx_swing", b, 0.85f);
                case Id.SwingHeavy:
                    b = Buf(0.5f);
                    Noise(b, 1f, 0f, 0.48f, 0.12f, 0.1f, 800f, 3200f, 220f, 23);
                    Sine(b, 110f, 60f, 0.35f, 0.05f, 0.35f, 0.08f, 0.1f);
                    return Finish("sfx_swing_heavy", b, 0.9f);
                case Id.HitBone:
                    b = Buf(0.4f);
                    Noise(b, 0.9f, 0f, 0.08f, 0.0005f, 0.012f, 8000f, 6000f, 1400f, 31);
                    Sine(b, 1900f, 1700f, 0.3f, 0f, 0.15f, 0.0005f, 0.03f);
                    Sine(b, 2750f, 2600f, 0.22f, 0.003f, 0.12f, 0.0005f, 0.02f);
                    Sine(b, 1180f, 1100f, 0.2f, 0f, 0.2f, 0.0005f, 0.05f);
                    Sine(b, 160f, 70f, 0.6f, 0f, 0.25f, 0.001f, 0.06f);
                    Noise(b, 0.45f, 0f, 0.25f, 0.001f, 0.05f, 500f, 400f, 0f, 32);
                    return Finish("sfx_hit_bone", b);
                case Id.PlayerHurt:
                    b = Buf(0.55f);
                    Sine(b, 95f, 48f, 0.8f, 0f, 0.3f, 0.001f, 0.08f);
                    Noise(b, 0.5f, 0f, 0.3f, 0.001f, 0.07f, 800f, 500f, 0f, 41);
                    Sine(b, 523f, 520f, 0.18f, 0.005f, 0.5f, 0.001f, 0.25f);
                    Sine(b, 1307f, 1300f, 0.14f, 0.005f, 0.4f, 0.001f, 0.18f);
                    Sine(b, 2210f, 2200f, 0.1f, 0.005f, 0.3f, 0.001f, 0.12f);
                    Sine(b, 3470f, 3450f, 0.06f, 0.005f, 0.2f, 0.001f, 0.08f);
                    return Finish("sfx_player_hurt", b);
                case Id.EnemyDie:
                    {
                        b = Buf(1.1f);
                        var rng = new System.Random(51);
                        Sine(b, 140f, 60f, 0.6f, 0f, 0.3f, 0.002f, 0.08f);
                        Noise(b, 0.35f, 0.05f, 0.9f, 0.05f, 0.25f, 300f, 200f, 0f, 52);
                        for (int i = 0; i < 18; i++)
                        {
                            float t = (float)(rng.NextDouble() * rng.NextDouble()) * 0.75f;
                            Click(b, t, 0.5f * (1f - t), 1500f + (float)rng.NextDouble() * 2200f, 60 + i);
                        }
                        return Finish("sfx_enemy_die", b);
                    }
                case Id.Growl:
                    b = Buf(0.8f);
                    Noise(b, 0.9f, 0f, 0.75f, 0.1f, 0.28f, 1300f, 900f, 220f, 61, 0.75f, 23f);
                    Sine(b, 85f, 70f, 0.3f, 0f, 0.7f, 0.1f, 0.3f, 0.05f, 7f);
                    return Finish("sfx_growl", b, 0.8f);
                case Id.Telegraph:
                    b = Buf(0.5f);
                    Noise(b, 0.8f, 0f, 0.48f, 0.38f, 0.06f, 350f, 2600f, 200f, 71);
                    Sine(b, 3200f, 3400f, 0.05f, 0.1f, 0.35f, 0.2f, 0.1f, 0.01f, 30f);
                    return Finish("sfx_telegraph", b, 0.75f);
                case Id.KeyPickup:
                    {
                        b = Buf(1.8f);
                        float[] notes = { 1046.5f, 1318.5f, 1568f, 2093f };
                        float[] times = { 0f, 0.09f, 0.18f, 0.3f };
                        for (int i = 0; i < 4; i++)
                        {
                            Sine(b, notes[i], notes[i], 0.35f, times[i], 1.4f, 0.003f, 0.6f);
                            Sine(b, notes[i] * 2.76f, notes[i] * 2.76f, 0.12f, times[i], 0.6f, 0.002f, 0.22f);
                            Sine(b, notes[i] * 5.4f, notes[i] * 5.4f, 0.05f, times[i], 0.3f, 0.001f, 0.08f);
                        }
                        Sine(b, 4186f, 4186f, 0.04f, 0.2f, 1.4f, 0.25f, 0.5f, 0.02f, 9f);
                        Sine(b, 5274f, 5274f, 0.03f, 0.3f, 1.3f, 0.25f, 0.5f, 0.02f, 7f);
                        return Finish("sfx_key", b);
                    }
                case Id.Unlock:
                    b = Buf(0.7f);
                    Sine(b, 125f, 80f, 0.7f, 0f, 0.3f, 0.001f, 0.06f);
                    Noise(b, 0.5f, 0f, 0.1f, 0.0005f, 0.02f, 1600f, 1200f, 0f, 81);
                    Sine(b, 740f, 735f, 0.2f, 0f, 0.5f, 0.001f, 0.15f);
                    Sine(b, 1650f, 1640f, 0.15f, 0f, 0.4f, 0.001f, 0.1f);
                    Sine(b, 2900f, 2880f, 0.08f, 0f, 0.3f, 0.001f, 0.06f);
                    Click(b, 0.13f, 0.6f, 2400f, 82);
                    return Finish("sfx_unlock", b);
                case Id.Locked:
                    {
                        b = Buf(0.6f);
                        for (int i = 0; i < 5; i++) Click(b, i * 0.055f, 0.5f, 900f + i * 120f, 90 + i);
                        Sine(b, 110f, 70f, 0.5f, 0.02f, 0.3f, 0.002f, 0.07f);
                        return Finish("sfx_locked", b, 0.8f);
                    }
                case Id.DoorOpen:
                    {
                        b = Buf(2.8f);
                        int n = b.Length;
                        double ph = 0; float low = 0f;
                        for (int i = 0; i < n; i++)
                        {
                            float t = (float)i / SR;
                            float f = 92f + 26f * Mathf.Sin(2f * Mathf.PI * 3.1f * t) + 11f * Mathf.Sin(2f * Mathf.PI * 7.3f * t) - 20f * t / 2.8f;
                            ph += 2.0 * System.Math.PI * f / SR;
                            float saw = (float)(ph / (2 * System.Math.PI) % 1.0) * 2f - 1f;
                            low += 0.12f * (saw - low);
                            float env = Mathf.Clamp01(t / 0.3f) * Mathf.Clamp01((2.4f - t) / 0.6f) * (0.6f + 0.4f * Mathf.Sin(2f * Mathf.PI * 1.7f * t));
                            b[i] += 0.35f * env * low;
                        }
                        Noise(b, 0.55f, 0f, 2.7f, 0.25f, 1.1f, 180f, 140f, 0f, 101);
                        Sine(b, 70f, 45f, 0.7f, 2.3f, 0.5f, 0.005f, 0.15f);
                        Noise(b, 0.4f, 2.3f, 0.4f, 0.002f, 0.08f, 600f, 300f, 0f, 102);
                        return Finish("sfx_door_open", b);
                    }
                case Id.GateOpen:
                    {
                        b = Buf(2.8f);
                        var rng = new System.Random(111);
                        for (float t = 0.05f; t < 2.5f; t += 0.036f + (float)rng.NextDouble() * 0.02f)
                            Click(b, t, 0.18f + 0.1f * (float)rng.NextDouble(), 700f + (float)rng.NextDouble() * 1500f, (int)(t * 1000));
                        Noise(b, 0.6f, 0f, 2.7f, 0.2f, 1.2f, 220f, 160f, 0f, 112);
                        Noise(b, 0.25f, 0f, 2.6f, 0.3f, 1f, 900f, 700f, 300f, 113, 0.6f, 9f);
                        return Finish("sfx_gate_open", b);
                    }
                case Id.GateSlam:
                    b = Buf(1.4f);
                    Sine(b, 72f, 34f, 1f, 0f, 1.2f, 0.002f, 0.35f);
                    Noise(b, 0.7f, 0f, 0.6f, 0.001f, 0.15f, 450f, 250f, 0f, 121);
                    Sine(b, 320f, 318f, 0.25f, 0f, 1.2f, 0.002f, 0.5f);
                    Sine(b, 790f, 785f, 0.15f, 0f, 1f, 0.002f, 0.3f);
                    Sine(b, 1450f, 1440f, 0.1f, 0f, 0.8f, 0.002f, 0.2f);
                    return Finish("sfx_gate_slam", b);
                case Id.Jump:
                    b = Buf(0.22f);
                    Noise(b, 0.6f, 0f, 0.2f, 0.02f, 0.05f, 1800f, 3000f, 500f, 131);
                    Sine(b, 2500f, 2400f, 0.04f, 0f, 0.08f, 0.001f, 0.03f);
                    return Finish("sfx_jump", b, 0.6f);
                case Id.Land:
                    b = Buf(0.3f);
                    Sine(b, 105f, 52f, 0.8f, 0f, 0.25f, 0.002f, 0.05f);
                    Noise(b, 0.5f, 0f, 0.2f, 0.001f, 0.05f, 650f, 500f, 0f, 141);
                    Sine(b, 2900f, 2850f, 0.07f, 0.005f, 0.1f, 0.001f, 0.03f);
                    return Finish("sfx_land", b, 0.85f);
                case Id.Dodge:
                    b = Buf(0.5f);
                    Noise(b, 0.8f, 0f, 0.45f, 0.06f, 0.12f, 600f, 3200f, 250f, 151);
                    Noise(b, 0.15f, 0.02f, 0.35f, 0.05f, 0.1f, 9000f, 9000f, 3500f, 152, 0.8f, 31f);
                    return Finish("sfx_dodge", b, 0.75f);
                case Id.Heal:
                    b = Buf(1.3f);
                    Sine(b, 880f, 880f, 0.15f, 0f, 1.2f, 0.25f, 0.5f, 0.01f, 7f);
                    Sine(b, 1320f, 1320f, 0.12f, 0.05f, 1.15f, 0.25f, 0.45f, 0.01f, 6f);
                    Sine(b, 1760f, 1760f, 0.1f, 0.1f, 1.1f, 0.25f, 0.4f, 0.01f, 8f);
                    return Finish("sfx_heal", b, 0.6f);
                case Id.Orb:
                    b = Buf(0.5f);
                    Sine(b, 700f, 1650f, 0.4f, 0f, 0.4f, 0.004f, 0.12f);
                    Sine(b, 1400f, 3300f, 0.12f, 0f, 0.35f, 0.004f, 0.1f);
                    return Finish("sfx_orb", b, 0.7f);
                case Id.Victory:
                    {
                        b = Buf(4.2f);
                        float[][] chords = { new[] { 261.6f, 329.6f, 392f }, new[] { 349.2f, 440f, 523.3f }, new[] { 392f, 493.9f, 587.3f }, new[] { 523.3f, 659.3f, 784f, 1046.5f } };
                        float[] starts = { 0f, 0.42f, 0.84f, 1.3f };
                        float[] durs = { 0.45f, 0.45f, 0.5f, 2.8f };
                        for (int c = 0; c < 4; c++)
                        {
                            foreach (var f in chords[c]) Harm(b, f, 0.16f, starts[c], durs[c], 0.03f, c == 3 ? 1.8f : 0.1f, 6, 0.75f);
                            Sine(b, 98f, 62f, 0.5f, starts[c], 0.5f, 0.002f, 0.18f);
                            Noise(b, 0.15f, starts[c], 0.3f, 0.001f, 0.06f, 3000f, 2000f, 500f, 160 + c);
                        }
                        Harm(b, 130.8f, 0.12f, 1.3f, 2.8f, 0.05f, 1.8f, 4, 0.6f);
                        return Finish("sfx_victory", b);
                    }
                case Id.Defeat:
                    b = Buf(3.4f);
                    Sine(b, 60f, 30f, 0.8f, 0f, 1.5f, 0.002f, 0.5f);
                    Harm(b, 110f, 0.22f, 0.1f, 3.2f, 0.7f, 1.6f, 5, 0.55f);
                    Harm(b, 130.8f, 0.18f, 0.1f, 3.2f, 0.7f, 1.6f, 5, 0.55f);
                    Harm(b, 164.8f, 0.16f, 0.1f, 3.2f, 0.7f, 1.6f, 5, 0.55f);
                    Sine(b, 440f, 220f, 0.08f, 0.3f, 2.5f, 0.3f, 1.2f);
                    return Finish("sfx_defeat", b);
                case Id.UiClick:
                    b = Buf(0.08f);
                    Noise(b, 0.5f, 0f, 0.03f, 0.0005f, 0.004f, 9000f, 9000f, 2000f, 171);
                    Sine(b, 1800f, 1700f, 0.3f, 0f, 0.05f, 0.0005f, 0.012f);
                    return Finish("sfx_ui_click", b, 0.5f);
                case Id.UiConfirm:
                    b = Buf(0.5f);
                    Sine(b, 880f, 880f, 0.3f, 0f, 0.35f, 0.003f, 0.12f);
                    Sine(b, 1320f, 1320f, 0.3f, 0.09f, 0.4f, 0.003f, 0.15f);
                    Sine(b, 2640f, 2640f, 0.05f, 0.09f, 0.2f, 0.003f, 0.06f);
                    return Finish("sfx_ui_confirm", b, 0.6f);
                case Id.Ignite:
                    b = Buf(0.8f);
                    Noise(b, 0.9f, 0f, 0.75f, 0.05f, 0.22f, 300f, 2200f, 120f, 181);
                    for (int i = 0; i < 6; i++) Click(b, 0.05f + i * 0.09f, 0.2f, 3000f, 182 + i);
                    return Finish("sfx_ignite", b, 0.7f);
                case Id.Rise:
                    {
                        b = Buf(1.5f);
                        var rng = new System.Random(191);
                        Noise(b, 0.6f, 0f, 1.4f, 0.3f, 0.5f, 260f, 180f, 0f, 192);
                        for (int i = 0; i < 14; i++)
                        {
                            float t = 0.2f + (float)System.Math.Sqrt(rng.NextDouble()) * 1.0f;
                            Click(b, t, 0.3f, 1200f + (float)rng.NextDouble() * 2500f, 200 + i);
                        }
                        return Finish("sfx_rise", b, 0.8f);
                    }
                case Id.Boom:
                    b = Buf(2.4f);
                    Sine(b, 58f, 28f, 1f, 0f, 2.2f, 0.004f, 0.8f);
                    Noise(b, 0.6f, 0f, 1f, 0.002f, 0.35f, 320f, 160f, 0f, 211);
                    Noise(b, 0.3f, 0.05f, 2.3f, 0.1f, 1.1f, 130f, 90f, 0f, 212);
                    return Finish("sfx_boom", b);

                // ------------------------------------------------ loops (integer cycles so they loop seamlessly)
                case Id.AmbientLoop:
                    {
                        float L = 12f;
                        b = Buf(L);
                        for (int i = 0; i < b.Length; i++)
                        {
                            float t = (float)i / SR;
                            float lfo = 0.6f + 0.4f * Mathf.Sin(2f * Mathf.PI * t / 6f);
                            b[i] += 0.12f * lfo * Mathf.Sin(2f * Mathf.PI * 55f * t) + 0.06f * (1.4f - lfo) * Mathf.Sin(2f * Mathf.PI * 82.5f * t);
                        }
                        Noise(b, 0.6f, 0f, L, 0.001f, 1e6f, 380f, 380f, 40f, 221, 0.55f, 1f / 12f);
                        float[] drips = { 1.3f, 3.9f, 6.2f, 8.7f, 10.6f };
                        for (int d = 0; d < drips.Length; d++)
                        {
                            float f = 1500f + d * 140f;
                            Sine(b, f, f * 0.65f, 0.12f, drips[d], 0.12f, 0.001f, 0.035f);
                            Sine(b, f, f * 0.65f, 0.04f, drips[d] + 0.19f, 0.12f, 0.001f, 0.035f);
                        }
                        return Finish("loop_ambient", b, 0.7f, false);
                    }
                case Id.TorchLoop:
                    {
                        float L = 4f;
                        b = Buf(L);
                        Noise(b, 0.5f, 0f, L, 0.001f, 1e6f, 600f, 600f, 60f, 231, 0.35f, 0.75f);
                        var rng = new System.Random(232);
                        for (int i = 0; i < 46; i++)
                        {
                            float t = (float)rng.NextDouble() * (L - 0.05f);
                            Noise(b, 0.25f + 0.5f * (float)rng.NextDouble(), t, 0.03f, 0.0005f, 0.004f, 8000f, 8000f, 900f, 300 + i);
                        }
                        return Finish("loop_torch", b, 0.7f, false);
                    }
                case Id.CombatLoop:
                    {
                        float L = 4f, beat = 0.5f;
                        b = Buf(L);
                        float[] kicks = { 0f, 1f, 2f, 3f, 3.5f, 4f, 5f, 6f, 7f, 7.5f };
                        foreach (var k in kicks) Sine(b, 125f, 42f, 0.9f, k * beat, 0.35f, 0.002f, 0.12f);
                        float[] toms = { 5.25f, 5.5f, 5.75f, 6.5f, 6.75f };
                        foreach (var k in toms) Sine(b, 190f, 120f, 0.45f, k * beat, 0.25f, 0.002f, 0.09f);
                        foreach (var k in kicks) Noise(b, 0.12f, k * beat, 0.08f, 0.001f, 0.02f, 4000f, 3000f, 800f, (int)(k * 10) + 400);
                        for (int i = 0; i < b.Length; i++)
                        {
                            float t = (float)i / SR;
                            float pulse = 0.65f + 0.35f * Mathf.Cos(2f * Mathf.PI * t / beat);
                            float drone = 0f;
                            for (int h = 1; h <= 6; h++) drone += Mathf.Sin(2f * Mathf.PI * 73.5f * h * t) / (h * 1.4f);
                            b[i] += 0.11f * pulse * drone;
                            float trem = 0.5f + 0.5f * Mathf.Sin(2f * Mathf.PI * 12f * t);
                            b[i] += 0.035f * trem * (Mathf.Sin(2f * Mathf.PI * 293.75f * t) + Mathf.Sin(2f * Mathf.PI * 349.25f * t));
                        }
                        return Finish("loop_combat", b, 0.85f, false);
                    }
                case Id.HeartbeatLoop:
                    b = Buf(1f);
                    Sine(b, 62f, 40f, 0.9f, 0f, 0.25f, 0.004f, 0.07f);
                    Sine(b, 58f, 38f, 0.65f, 0.27f, 0.25f, 0.004f, 0.07f);
                    return Finish("loop_heartbeat", b, 0.9f, false);
            }
            return Finish("silence", Buf(0.05f));
        }
    }
}
