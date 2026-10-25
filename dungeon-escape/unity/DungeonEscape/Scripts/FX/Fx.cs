using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Code-built particle effects. One-shots self-destruct; Make* builders are used by the level builder.</summary>
    public static class Fx
    {
        static Material Mat(System.Func<FxLibrary, Material> pick)
        {
            var lib = FxLibrary.Instance;
            if (lib == null) lib = Object.FindAnyObjectByType<FxLibrary>();
            return lib != null ? pick(lib) : null;
        }

        static ParticleSystem NewSystem(string name, Vector3 pos, Material mat, bool oneShot)
        {
            var go = new GameObject(name);
            go.transform.position = pos;
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.playOnAwake = false;
            main.loop = !oneShot;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.scalingMode = ParticleSystemScalingMode.Hierarchy;
            if (oneShot) main.stopAction = ParticleSystemStopAction.Destroy;
            var em = ps.emission; em.rateOverTime = 0f;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            return ps;
        }

        static void Burst(ParticleSystem ps, int count)
        {
            var em = ps.emission;
            em.SetBursts(new[] { new ParticleSystem.Burst(0f, (short)count) });
            ps.Play();
        }

        static Gradient Fade(Color a, Color b)
        {
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(a, 0f), new GradientColorKey(b, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.8f, 0.4f), new GradientAlphaKey(0f, 1f) });
            return g;
        }

        public static void HitSpark(Vector3 pos, Color color, int count)
        {
            var ps = NewSystem("FX_HitSpark", pos, Mat(l => l.spark), true);
            var main = ps.main;
            main.duration = 0.4f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.15f, 0.35f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(3.5f, 9f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.09f);
            main.startColor = color;
            main.gravityModifier = 1.2f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Sphere; sh.radius = 0.08f;
            var col = ps.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, color);
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Stretch; r.velocityScale = 0.04f; r.lengthScale = 1.5f;
            Burst(ps, count);
            var flashGo = new GameObject("FX_HitFlash");
            flashGo.transform.position = pos;
            var l = flashGo.AddComponent<Light>();
            l.type = LightType.Point; l.color = color; l.range = 4.5f; l.intensity = 10f; l.shadows = LightShadows.None;
            Object.Destroy(flashGo, 0.07f);
        }

        public static void BoneChips(Vector3 pos, int count)
        {
            var ps = NewSystem("FX_BoneChips", pos, Mat(l => l.bone), true);
            var main = ps.main;
            main.duration = 1f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 0.9f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(2f, 5f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.09f);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, 6.28f);
            main.startColor = new Color(0.85f, 0.8f, 0.68f);
            main.gravityModifier = 2.4f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Sphere; sh.radius = 0.15f;
            var rot = ps.rotationOverLifetime; rot.enabled = true; rot.z = new ParticleSystem.MinMaxCurve(-8f, 8f);
            var col = ps.colorOverLifetime; col.enabled = true; col.color = Fade(new Color(0.9f, 0.85f, 0.75f), new Color(0.6f, 0.55f, 0.5f));
            Burst(ps, count);
        }

        public static void Dust(Vector3 pos, int count, float radius)
        {
            var ps = NewSystem("FX_Dust", pos, Mat(l => l.dust), true);
            var main = ps.main;
            main.duration = 2f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(1.0f, 1.8f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.3f, 1.3f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.5f * radius, 1.1f * radius);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, 6.28f);
            main.startColor = new Color(0.55f, 0.5f, 0.45f, 0.5f);
            main.gravityModifier = -0.05f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Circle; sh.radius = radius * 0.6f; sh.rotation = new Vector3(90f, 0f, 0f);
            var sz = ps.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0.6f, 1f, 1.5f));
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.55f, 0.15f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            var lim = ps.limitVelocityOverLifetime; lim.enabled = true; lim.dampen = 0.15f; lim.limit = 0.4f;
            Burst(ps, count);
        }

        public static void Magic(Vector3 pos, Color color, int count)
        {
            var ps = NewSystem("FX_Magic", pos, Mat(l => l.magic), true);
            var main = ps.main;
            main.duration = 1.5f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.6f, 1.3f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.8f, 3.2f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.06f, 0.18f);
            main.startColor = color;
            main.gravityModifier = -0.25f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Sphere; sh.radius = 0.25f;
            var col = ps.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, color);
            var lim = ps.limitVelocityOverLifetime; lim.enabled = true; lim.dampen = 0.2f; lim.limit = 0.6f;
            Burst(ps, count);
            var lgo = new GameObject("FX_MagicLight");
            lgo.transform.position = pos;
            var l = lgo.AddComponent<Light>();
            l.type = LightType.Point; l.color = color; l.range = 5f; l.intensity = 8f; l.shadows = LightShadows.None;
            Object.Destroy(lgo, 0.25f);
        }

        public static void Embers(Vector3 pos, int count)
        {
            var ps = NewSystem("FX_Embers", pos, Mat(l => l.ember), true);
            var main = ps.main;
            main.duration = 1.5f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.6f, 1.4f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 2.2f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.07f);
            main.startColor = new Color(1f, 0.55f, 0.15f);
            main.gravityModifier = -0.3f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Sphere; sh.radius = 0.12f;
            Burst(ps, count);
        }

        // ------------------------------------------------------------------ persistent builders (edit-time or runtime)
        static void Child(Transform parent, ParticleSystem ps, Vector3 localPos)
        {
            ps.transform.SetParent(parent, false);
            ps.transform.localPosition = localPos;
            ps.transform.localRotation = Quaternion.identity;
        }

        public static ParticleSystem MakeFlame(Transform parent, Vector3 localPos, float scale, Material flameMat, Material emberMat, Material smokeMat)
        {
            var ps = NewSystem("Flame", Vector3.zero, flameMat, false);
            Child(parent, ps, localPos);
            var main = ps.main;
            main.playOnAwake = true;
            main.duration = 1f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.35f, 0.6f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.3f * scale, 0.8f * scale);
            // Taller than wide so the teardrop texture keeps its shape.
            main.startSize3D = true;
            main.startSizeX = new ParticleSystem.MinMaxCurve(0.26f * scale, 0.40f * scale);
            main.startSizeY = new ParticleSystem.MinMaxCurve(0.42f * scale, 0.66f * scale);
            main.startSizeZ = 1f;
            main.startRotation = new ParticleSystem.MinMaxCurve(-0.25f, 0.25f);
            main.startColor = Color.white;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 80;
            var em = ps.emission; em.rateOverTime = 36f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Cone; sh.angle = 6f; sh.radius = 0.04f * scale; sh.rotation = new Vector3(-90f, 0f, 0f);
            var sz = ps.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0.15f));
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(new Color(1f, 0.9f, 0.6f), 0f), new GradientColorKey(new Color(1f, 0.62f, 0.22f), 0.35f), new GradientColorKey(new Color(0.95f, 0.35f, 0.08f), 0.7f), new GradientColorKey(new Color(0.6f, 0.12f, 0.04f), 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.12f), new GradientAlphaKey(0.7f, 0.6f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            var noise = ps.noise; noise.enabled = true; noise.strength = 0.25f * scale; noise.frequency = 1.5f; noise.scrollSpeed = 1.2f;
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.sortingFudge = -1f;

            // Bright inner core at the base of the flame.
            var cp = NewSystem("FlameCore", Vector3.zero, flameMat, false);
            Child(ps.transform, cp, new Vector3(0f, 0.02f * scale, 0f));
            var mc = cp.main;
            mc.playOnAwake = true;
            mc.duration = 1f;
            mc.startLifetime = new ParticleSystem.MinMaxCurve(0.22f, 0.36f);
            mc.startSpeed = new ParticleSystem.MinMaxCurve(0.15f * scale, 0.35f * scale);
            mc.startSize3D = true;
            mc.startSizeX = new ParticleSystem.MinMaxCurve(0.13f * scale, 0.19f * scale);
            mc.startSizeY = new ParticleSystem.MinMaxCurve(0.22f * scale, 0.32f * scale);
            mc.startSizeZ = 1f;
            mc.startRotation = new ParticleSystem.MinMaxCurve(-0.15f, 0.15f);
            mc.startColor = new Color(1f, 0.92f, 0.7f, 1f);
            mc.maxParticles = 40;
            var ec = cp.emission; ec.rateOverTime = 22f;
            var shc = cp.shape; shc.shapeType = ParticleSystemShapeType.Cone; shc.angle = 3f; shc.radius = 0.02f * scale; shc.rotation = new Vector3(-90f, 0f, 0f);
            var szc = cp.sizeOverLifetime; szc.enabled = true; szc.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0.3f));
            var cc = cp.colorOverLifetime; cc.enabled = true;
            var gc = new Gradient();
            gc.SetKeys(new[] { new GradientColorKey(new Color(1f, 0.97f, 0.85f), 0f), new GradientColorKey(new Color(1f, 0.75f, 0.35f), 1f) },
                       new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.15f), new GradientAlphaKey(0.8f, 0.6f), new GradientAlphaKey(0f, 1f) });
            cc.color = gc;
            var rc = cp.GetComponent<ParticleSystemRenderer>();
            rc.renderMode = ParticleSystemRenderMode.Billboard;
            rc.sortingFudge = -2f;

            if (emberMat != null)
            {
                var ep = NewSystem("Embers", Vector3.zero, emberMat, false);
                Child(ps.transform, ep, Vector3.zero);
                var m2 = ep.main;
                m2.playOnAwake = true;
                m2.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.6f);
                m2.startSpeed = new ParticleSystem.MinMaxCurve(0.4f * scale, 1.2f * scale);
                m2.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.045f);
                m2.startColor = new Color(1f, 0.6f, 0.2f);
                m2.maxParticles = 30;
                var e2 = ep.emission; e2.rateOverTime = 4f * scale;
                var s2 = ep.shape; s2.shapeType = ParticleSystemShapeType.Cone; s2.angle = 15f; s2.radius = 0.05f * scale; s2.rotation = new Vector3(-90f, 0f, 0f);
                var n2 = ep.noise; n2.enabled = true; n2.strength = 0.6f; n2.frequency = 1.2f;
                var c2 = ep.colorOverLifetime; c2.enabled = true; c2.color = Fade(new Color(1f, 0.8f, 0.4f), new Color(1f, 0.3f, 0.05f));
            }
            if (smokeMat != null)
            {
                var sp = NewSystem("Smoke", Vector3.zero, smokeMat, false);
                Child(ps.transform, sp, new Vector3(0f, 0.25f * scale, 0f));
                var m3 = sp.main;
                m3.playOnAwake = true;
                m3.startLifetime = new ParticleSystem.MinMaxCurve(1.5f, 2.5f);
                m3.startSpeed = new ParticleSystem.MinMaxCurve(0.3f, 0.6f);
                m3.startSize = new ParticleSystem.MinMaxCurve(0.25f * scale, 0.5f * scale);
                m3.startRotation = new ParticleSystem.MinMaxCurve(0f, 6.28f);
                m3.startColor = new Color(0.1f, 0.09f, 0.08f, 0.25f);
                m3.maxParticles = 30;
                var e3 = sp.emission; e3.rateOverTime = 5f;
                var s3 = sp.shape; s3.shapeType = ParticleSystemShapeType.Cone; s3.angle = 8f; s3.radius = 0.05f; s3.rotation = new Vector3(-90f, 0f, 0f);
                var z3 = sp.sizeOverLifetime; z3.enabled = true; z3.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0.6f, 1f, 2.2f));
                var c3 = sp.colorOverLifetime; c3.enabled = true;
                var g3 = new Gradient();
                g3.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                           new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.5f, 0.2f), new GradientAlphaKey(0f, 1f) });
                c3.color = g3;
            }
            return ps;
        }

        public static ParticleSystem MakeMotes(Transform parent, Vector3 localPos, Vector3 boxSize, Color color, float rate, Material mat, float size = 0.05f)
        {
            var ps = NewSystem("Motes", Vector3.zero, mat, false);
            Child(parent, ps, localPos);
            var main = ps.main;
            main.playOnAwake = true;
            main.prewarm = true;
            main.startLifetime = new ParticleSystem.MinMaxCurve(3f, 6f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.02f, 0.15f);
            main.startSize = new ParticleSystem.MinMaxCurve(size * 0.5f, size * 1.4f);
            main.startColor = color;
            main.maxParticles = 300;
            var em = ps.emission; em.rateOverTime = rate;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = boxSize;
            var noise = ps.noise; noise.enabled = true; noise.strength = 0.08f; noise.frequency = 0.4f; noise.scrollSpeed = 0.1f;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.3f), new GradientAlphaKey(1f, 0.7f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            return ps;
        }
    }
}
