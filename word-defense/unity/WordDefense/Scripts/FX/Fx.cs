using System.Collections;
using UnityEngine;

namespace WordDefense
{
    /// <summary>All particle effects, built in code from a few generated textures (Textures/fx_*.png) and two
    /// tiny URP shaders (WordDefense/FxAdditive, WordDefense/FxAlpha).</summary>
    public static class Fx
    {
        static Material addSoft, addSpark, addRing, addFlake, alphaSoft, alphaChunk, alphaFlake, trailMat;
        static GameManager gm;

        public static void Init(GameManager g)
        {
            gm = g;
            if (g.fxAdditive == null || g.fxAlpha == null) return;
            addSoft = Make(g.fxAdditive, g.fxSoft);
            addSpark = Make(g.fxAdditive, g.fxSpark);
            addRing = Make(g.fxAdditive, g.fxRing);
            addFlake = Make(g.fxAdditive, g.fxFlake);
            alphaSoft = Make(g.fxAlpha, g.fxSoft);
            alphaChunk = Make(g.fxAlpha, null);
            alphaFlake = Make(g.fxAlpha, g.fxFlake);
            trailMat = Make(g.fxAdditive, g.fxSoft);
        }

        static Material Make(Material baseMat, Texture2D tex)
        {
            var m = new Material(baseMat);
            if (tex != null) m.mainTexture = tex;
            return m;
        }

        // ------------------------------------------------------------ generic burst
        struct B
        {
            public int count;
            public float life0, life1, speed0, speed1, size0, size1, gravity, drag, radius, sizeEnd;
            public Color c0, c1;
            public Material mat;
            public bool hemisphere, stretch, spin;
            public float rate, duration;
        }

        static ParticleSystem Burst(Vector3 pos, B b, Transform parent = null)
        {
            if (b.mat == null) return null;
            var go = new GameObject("fx");
            go.transform.position = pos;
            if (parent) go.transform.SetParent(parent, true);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.duration = b.duration > 0f ? b.duration : 0.2f;
            main.loop = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(b.life0, b.life1);
            main.startSpeed = new ParticleSystem.MinMaxCurve(b.speed0, b.speed1);
            main.startSize = new ParticleSystem.MinMaxCurve(b.size0, b.size1);
            main.startColor = new ParticleSystem.MinMaxGradient(b.c0, b.c1);
            main.gravityModifier = b.gravity;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = Mathf.Max(64, b.count * 2 + (int)(b.rate * Mathf.Max(1f, b.duration)) + 8);
            main.stopAction = ParticleSystemStopAction.Destroy;
            main.scalingMode = ParticleSystemScalingMode.Hierarchy;
            if (b.spin) main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            var em = ps.emission;
            em.rateOverTime = b.rate;
            if (b.count > 0) em.SetBursts(new[] { new ParticleSystem.Burst(0f, (short)b.count) });
            var sh = ps.shape;
            sh.shapeType = b.hemisphere ? ParticleSystemShapeType.Hemisphere : ParticleSystemShapeType.Sphere;
            sh.radius = Mathf.Max(0.01f, b.radius);
            if (b.drag > 0f)
            {
                var lim = ps.limitVelocityOverLifetime;
                lim.enabled = true;
                lim.drag = b.drag;
                lim.multiplyDragByParticleSize = false;
            }
            var sz = ps.sizeOverLifetime;
            sz.enabled = true;
            sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, b.sizeEnd));
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.9f, 0.55f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            if (b.spin)
            {
                var rot = ps.rotationOverLifetime;
                rot.enabled = true;
                rot.z = new ParticleSystem.MinMaxCurve(-4f, 4f);
            }
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = b.mat;
            r.renderMode = b.stretch ? ParticleSystemRenderMode.Stretch : ParticleSystemRenderMode.Billboard;
            if (b.stretch) { r.velocityScale = 0.06f; r.lengthScale = 1.2f; }
            r.sortingFudge = -2f;
            ps.Play(true);
            return ps;
        }

        // ------------------------------------------------------------ effects
        static Color A(Color c, float a) { c.a = a; return c; }

        public static void InkBurst(Vector3 p, float s = 1f)
        {
            Burst(p, new B { count = (int)(22 * s), life0 = 0.35f, life1 = 0.8f, speed0 = 2.5f * s, speed1 = 6f * s, size0 = 0.18f, size1 = 0.42f * s,
                gravity = 1.6f, drag = 2f, radius = 0.25f, sizeEnd = 0.2f, c0 = new Color(0.16f, 0.15f, 0.3f), c1 = new Color(0.3f, 0.25f, 0.55f), mat = alphaSoft });
            Burst(p, new B { count = (int)(16 * s), life0 = 0.25f, life1 = 0.6f, speed0 = 3f, speed1 = 8f, size0 = 0.06f, size1 = 0.16f,
                gravity = 0.6f, drag = 3f, radius = 0.2f, sizeEnd = 0f, c0 = new Color(1f, 0.35f, 0.7f), c1 = new Color(0.75f, 0.5f, 1f), mat = addSpark, stretch = true });
        }

        public static void HitBurst(Vector3 p, bool homing)
        {
            Color a = homing ? new Color(1f, 0.95f, 0.65f) : new Color(1f, 0.8f, 0.35f);
            Burst(p, new B { count = 1, life0 = 0.3f, life1 = 0.3f, size0 = homing ? 5.5f : 4f, size1 = homing ? 5.5f : 4f, sizeEnd = 0.1f, c0 = a, c1 = a, mat = addSoft, radius = 0.01f });
            Burst(p, new B { count = 1, life0 = 0.45f, life1 = 0.45f, size0 = 0.6f, size1 = 0.6f, sizeEnd = 9f, c0 = a, c1 = a, mat = addRing, radius = 0.01f });
            Burst(p, new B { count = homing ? 40 : 26, life0 = 0.3f, life1 = 0.7f, speed0 = 4f, speed1 = 11f, size0 = 0.08f, size1 = 0.2f,
                gravity = 0.8f, drag = 3f, radius = 0.2f, sizeEnd = 0f, c0 = a, c1 = Color.white, mat = addSpark, stretch = true });
            Burst(p, new B { count = 14, life0 = 0.7f, life1 = 1.3f, speed0 = 2f, speed1 = 5f, size0 = 0.12f, size1 = 0.22f, gravity = 0.9f, drag = 1.5f,
                radius = 0.2f, sizeEnd = 0.6f, c0 = new Color(1f, 0.85f, 0.45f), c1 = new Color(0.5f, 0.95f, 0.75f), mat = alphaChunk, spin = true });
        }

        public static void Deflect(Vector3 p, Vector3 from)
        {
            Color red = new Color(1f, 0.28f, 0.35f);
            Burst(p, new B { count = 1, life0 = 0.35f, life1 = 0.35f, size0 = 1.2f, size1 = 1.2f, sizeEnd = 4.5f, c0 = red, c1 = red, mat = addRing, radius = 0.01f });
            Burst(p, new B { count = 1, life0 = 0.25f, life1 = 0.25f, size0 = 3f, size1 = 3f, sizeEnd = 0.2f, c0 = red, c1 = red, mat = addSoft, radius = 0.01f });
            Burst(p, new B { count = 18, life0 = 0.25f, life1 = 0.55f, speed0 = 3f, speed1 = 7f, size0 = 0.06f, size1 = 0.14f, gravity = 1f, drag = 2f,
                radius = 0.3f, sizeEnd = 0f, c0 = red, c1 = new Color(1f, 0.6f, 0.4f), mat = addSpark, stretch = true });
        }

        public static void Rubble(Vector3 p, int amount)
        {
            float s = Mathf.Clamp(amount / 12f, 0.6f, 2.2f);
            Burst(p, new B { count = (int)(14 * s), life0 = 0.6f, life1 = 1.2f, speed0 = 2f, speed1 = 6f * s, size0 = 0.1f, size1 = 0.26f, gravity = 2.2f, drag = 0.5f,
                radius = 0.6f, sizeEnd = 0.8f, c0 = new Color(0.93f, 0.9f, 0.84f), c1 = new Color(0.75f, 0.7f, 0.62f), mat = alphaChunk, spin = true, hemisphere = true });
            Dust(p, 0.8f * s);
        }

        public static void Dust(Vector3 p, float s)
        {
            Burst(p, new B { count = (int)(12 * s) + 4, life0 = 0.9f, life1 = 1.8f, speed0 = 0.8f, speed1 = 2.5f * s, size0 = 0.9f * s, size1 = 1.8f * s, gravity = -0.05f, drag = 1.2f,
                radius = 0.8f * s, sizeEnd = 1.6f, c0 = new Color(0.9f, 0.86f, 0.78f, 0.75f), c1 = new Color(0.8f, 0.76f, 0.7f, 0.6f), mat = alphaSoft, hemisphere = true, spin = true });
        }

        public static ParticleSystem SmokeColumn(Vector3 p, Transform parent)
        {
            return Burst(p, new B { count = 0, rate = 7f, duration = 9999f, life0 = 2f, life1 = 3.2f, speed0 = 0.8f, speed1 = 1.6f, size0 = 0.8f, size1 = 1.4f,
                gravity = -0.08f, drag = 0.4f, radius = 0.4f, sizeEnd = 2.4f, c0 = new Color(0.32f, 0.3f, 0.33f, 0.55f), c1 = new Color(0.45f, 0.42f, 0.45f, 0.45f), mat = alphaSoft, hemisphere = true, spin = true }, parent);
        }

        public static void MuzzleFlash(Vector3 p, Vector3 dir)
        {
            Burst(p, new B { count = 1, life0 = 0.12f, life1 = 0.12f, size0 = 2.2f, size1 = 2.2f, sizeEnd = 0.2f, c0 = new Color(1f, 0.85f, 0.5f), c1 = Color.white, mat = addSoft, radius = 0.01f });
            Burst(p + dir * 0.3f, new B { count = 8, life0 = 0.5f, life1 = 0.9f, speed0 = 0.5f, speed1 = 1.8f, size0 = 0.4f, size1 = 0.7f, gravity = -0.1f, drag = 2f,
                radius = 0.2f, sizeEnd = 2f, c0 = new Color(0.95f, 0.93f, 0.9f, 0.7f), c1 = new Color(0.85f, 0.83f, 0.8f, 0.5f), mat = alphaSoft, spin = true });
        }

        public static void PortalPuff(Vector3 p, float s = 1f)
        {
            Burst(p, new B { count = (int)(18 * s), life0 = 0.4f, life1 = 0.9f, speed0 = 1.5f, speed1 = 4f * s, size0 = 0.3f, size1 = 0.7f * s, drag = 2.5f,
                radius = 0.6f * s, sizeEnd = 0.1f, c0 = new Color(0.75f, 0.45f, 1f), c1 = new Color(1f, 0.35f, 0.7f), mat = addSoft });
            Burst(p, new B { count = 1, life0 = 0.5f, life1 = 0.5f, size0 = 0.8f, size1 = 0.8f, sizeEnd = 5f * s, c0 = new Color(0.8f, 0.5f, 1f), c1 = new Color(0.8f, 0.5f, 1f), mat = addRing, radius = 0.01f });
        }

        public static void Sparks(Vector3 p, Color c, int n)
        {
            Burst(p, new B { count = n, life0 = 0.3f, life1 = 0.7f, speed0 = 3f, speed1 = 9f, size0 = 0.07f, size1 = 0.18f, gravity = 1f, drag = 2f,
                radius = 0.3f, sizeEnd = 0f, c0 = c, c1 = Color.white, mat = addSpark, stretch = true });
        }

        public static void BossExplosion(Vector3 p)
        {
            Burst(p, new B { count = 1, life0 = 0.6f, life1 = 0.6f, size0 = 14f, size1 = 14f, sizeEnd = 0.1f, c0 = new Color(1f, 0.8f, 0.6f), c1 = Color.white, mat = addSoft, radius = 0.01f });
            Burst(p, new B { count = 2, life0 = 0.8f, life1 = 1.0f, size0 = 1f, size1 = 1f, sizeEnd = 30f, c0 = new Color(1f, 0.55f, 0.8f), c1 = new Color(1f, 0.85f, 0.4f), mat = addRing, radius = 0.01f });
            InkBurst(p, 3f);
            Sparks(p, new Color(1f, 0.8f, 0.4f), 60);
            // paper confetti: the sentence falls apart into pages
            Burst(p + Vector3.up, new B { count = 90, life0 = 1.8f, life1 = 3.2f, speed0 = 5f, speed1 = 14f, size0 = 0.18f, size1 = 0.4f, gravity = 0.7f, drag = 1.6f,
                radius = 1f, sizeEnd = 0.8f, c0 = new Color(0.98f, 0.94f, 0.85f), c1 = new Color(1f, 0.78f, 0.35f), mat = alphaChunk, spin = true, hemisphere = true });
            Dust(p - Vector3.up * 2f, 3f);
        }

        public static void FrostVolley(Vector3 from, PathRoute path)
        {
            if (gm != null) gm.StartCoroutine(FrostRoutine(from, path));
        }

        static IEnumerator FrostRoutine(Vector3 from, PathRoute path)
        {
            Color ice = new Color(0.6f, 0.9f, 1f);
            Vector3 top = from + Vector3.up * 9f + Vector3.right * 6f;
            float t = 0f;
            var head = Burst(from, new B { count = 0, rate = 120f, duration = 0.5f, life0 = 0.25f, life1 = 0.4f, size0 = 0.5f, size1 = 0.9f, sizeEnd = 0.1f, c0 = ice, c1 = Color.white, mat = addSoft, radius = 0.1f });
            while (t < 0.45f)
            {
                t += Time.deltaTime;
                if (head) head.transform.position = Vector3.Lerp(from, top, Ease.OutCubic(Mathf.Clamp01(t / 0.45f)));
                yield return null;
            }
            Burst(top, new B { count = 1, life0 = 0.4f, life1 = 0.4f, size0 = 5f, size1 = 5f, sizeEnd = 0.1f, c0 = A(ice, 0.7f), c1 = A(Color.white, 0.7f), mat = addSoft, radius = 0.01f });
            Burst(top, new B { count = 60, life0 = 0.6f, life1 = 1.2f, speed0 = 6f, speed1 = 16f, size0 = 0.2f, size1 = 0.45f, drag = 2f, sizeEnd = 0.2f, c0 = ice, c1 = Color.white, mat = addFlake, spin = true, radius = 0.3f });
            // frost ring sweeping the island and snow over the road for the duration of the slow
            Vector3 mid = path != null && path.Count > 0 ? path.Sample(path.Length * 0.5f, out _) : from;
            Burst(mid + Vector3.up * 0.3f, new B { count = 1, life0 = 0.9f, life1 = 0.9f, size0 = 2f, size1 = 2f, sizeEnd = 18f, c0 = A(ice, 0.55f), c1 = A(ice, 0.55f), mat = addRing, radius = 0.01f });
            if (path != null)
            {
                for (int i = 0; i < 7; i++)
                {
                    Vector3 p = path.Sample(path.Length * (i + 0.5f) / 7f, out _);
                    Burst(p + Vector3.up * 6f, new B { count = 0, rate = 9f, duration = GameManager.SlowDuration - 1f, life0 = 2.2f, life1 = 3f, speed0 = 0.2f, speed1 = 0.6f,
                        size0 = 0.18f, size1 = 0.32f, gravity = 0.12f, radius = 3.5f, sizeEnd = 0.6f, c0 = new Color(0.85f, 0.95f, 1f), c1 = Color.white, mat = alphaFlake, spin = true });
                    Burst(p + Vector3.up * 0.2f, new B { count = 10, life0 = 0.8f, life1 = 1.4f, speed0 = 0.5f, speed1 = 2f, size0 = 0.3f, size1 = 0.6f, drag = 1f,
                        radius = 1.5f, sizeEnd = 1.4f, c0 = new Color(0.7f, 0.92f, 1f, 0.8f), c1 = new Color(0.9f, 0.97f, 1f, 0.6f), mat = alphaSoft, hemisphere = true });
                }
            }
        }

        public static void AttachTrail(GameObject go, Color c, bool homing)
        {
            if (trailMat == null) return;
            var tr = go.AddComponent<TrailRenderer>();
            tr.sharedMaterial = trailMat;
            tr.time = homing ? 0.45f : 0.22f;
            tr.minVertexDistance = 0.08f;
            tr.widthCurve = new AnimationCurve(new Keyframe(0f, homing ? 0.55f : 0.38f), new Keyframe(1f, 0f));
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(c, 0.3f), new GradientColorKey(c, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.7f, 0.4f), new GradientAlphaKey(0f, 1f) });
            tr.colorGradient = g;
            tr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            if (homing)
            {
                var ps = Burst(go.transform.position, new B { count = 0, rate = 60f, duration = 3f, life0 = 0.3f, life1 = 0.6f, speed0 = 0.2f, speed1 = 0.8f, size0 = 0.12f, size1 = 0.25f,
                    sizeEnd = 0f, c0 = c, c1 = Color.white, mat = addSpark, radius = 0.15f }, go.transform);
                if (ps) { var m = ps.main; m.stopAction = ParticleSystemStopAction.None; }
            }
        }
    }
}
