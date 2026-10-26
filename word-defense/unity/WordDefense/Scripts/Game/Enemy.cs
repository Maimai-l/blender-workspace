using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using WordDefense.Data;

namespace WordDefense
{
    public enum EnemyKind { Scout, Soldier, Brute, Boss }

    /// <summary>An ink creature walking the road with an English word above its head. Animation is procedural:
    /// the Blender model's limbs are separate parts with their pivots at the joints.</summary>
    public class Enemy : MonoBehaviour
    {
        static int nextId;
        public int Id;
        public EnemyKind Kind;
        public SessionWord Word;
        public float Dist;
        public float BaseSpeed = 1.4f;
        public int Damage = 10;
        public float SpawnTime;
        public float TagHeight = 1.6f;
        public float Scale = 1f;
        public bool Alive = true;
        public bool Doomed;
        public float LastWrongTime = -10f;
        public string RevealText;          // shown under the word after a wrong match
        public float RevealUntil;

        protected GameManager gm;
        protected float lane, laneTarget, laneTimer;
        protected float phase, stride = 0.7f, bobAmp = 0.05f, swing = 28f;
        protected float stagger;            // seconds of reduced speed after a hit
        protected Vector3 knock;            // sideways shove from a deflected shell

        class Part
        {
            public Transform t;
            public Vector3 pos;
            public Quaternion rot;
        }
        readonly Dictionary<string, Part> parts = new Dictionary<string, Part>();
        protected readonly List<Material> mats = new List<Material>();
        readonly List<Color> baseCols = new List<Color>();
        readonly List<Color> emitCols = new List<Color>();
        protected float flash;
        protected Color flashColor = Color.white;
        float frost;
        Collider col;

        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        static readonly Color Ice = new Color(0.55f, 0.82f, 1f);

        public Vector3 TagWorld { get { return transform.position + Vector3.up * (TagHeight * Scale); } }
        public Vector3 AimPoint { get { return transform.position + Vector3.up * (TagHeight * Scale * 0.5f); } }
        public float Progress { get { return gm != null && gm.Path != null ? Dist / gm.Path.Length : 0f; } }
        public float Emerge { get { return Mathf.Clamp01((Time.time - SpawnTime) / 0.55f); } }
        public virtual bool Targetable { get { return Alive && !Doomed && Time.time - SpawnTime > 0.3f; } }
        public bool IsFrozen { get { return frost > 0.05f; } }

        public virtual void Init(GameManager g, EnemyKind kind, SessionWord word)
        {
            gm = g;
            Id = ++nextId;
            Kind = kind;
            Word = word;
            SpawnTime = Time.time;
            switch (kind)
            {
                case EnemyKind.Scout: BaseSpeed = 1.85f; Damage = 8; TagHeight = 1.05f; Scale = 1.55f; stride = 0.42f; bobAmp = 0.07f; swing = 34f; break;
                case EnemyKind.Soldier: BaseSpeed = 1.4f; Damage = 10; TagHeight = 1.55f; Scale = 1.45f; stride = 0.62f; bobAmp = 0.04f; swing = 30f; break;
                case EnemyKind.Brute: BaseSpeed = 1.05f; Damage = 18; TagHeight = 1.95f; Scale = 1.38f; stride = 0.85f; bobAmp = 0.05f; swing = 24f; break;
                case EnemyKind.Boss: BaseSpeed = 0.5f; Damage = 100; TagHeight = 5.25f; Scale = 1.15f; stride = 1.6f; bobAmp = 0.06f; swing = 18f; break;
            }
            lane = laneTarget = Random.Range(-0.55f, 0.55f) * (kind == EnemyKind.Boss ? 0f : 1f);
            foreach (Transform t in GetComponentsInChildren<Transform>(true))
                if (t != transform && !parts.ContainsKey(t.name))
                    parts[t.name] = new Part { t = t, pos = t.localPosition, rot = t.localRotation };
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                foreach (var m in r.materials)
                {
                    mats.Add(m);
                    baseCols.Add(m.HasProperty(BaseColorId) ? m.GetColor(BaseColorId) : Color.white);
                    emitCols.Add(m.HasProperty(EmissionId) ? m.GetColor(EmissionId) : Color.black);
                    m.EnableKeyword("_EMISSION");
                }
            }
            var cap = gameObject.AddComponent<CapsuleCollider>();
            cap.center = new Vector3(0f, TagHeight * 0.5f, 0f);
            cap.height = TagHeight * 1.05f;
            cap.radius = kind == EnemyKind.Boss ? 1.6f : (kind == EnemyKind.Brute ? 0.85f : 0.62f);
            col = cap;
            gameObject.layer = GameManager.EnemyLayer;
            transform.localScale = Vector3.one * 0.01f;
            Place(0f);
        }

        protected Transform PartT(string name)
        {
            Part p;
            return parts.TryGetValue(name, out p) ? p.t : null;
        }

        protected void Place(float dt)
        {
            Vector3 fwd;
            Vector3 p = gm.Path.Sample(Dist, out fwd);
            Vector3 side = Vector3.Cross(Vector3.up, fwd).normalized;
            laneTimer -= dt;
            if (laneTimer <= 0f && Kind != EnemyKind.Boss)
            {
                laneTimer = Random.Range(2.5f, 5f);
                laneTarget = Mathf.Clamp(lane + Random.Range(-0.4f, 0.4f), -0.6f, 0.6f);
            }
            lane = Mathf.MoveTowards(lane, laneTarget, dt * 0.25f);
            knock = Vector3.MoveTowards(knock, Vector3.zero, dt * 2.5f);
            transform.position = p + side * lane + knock;
            if (fwd.sqrMagnitude > 0.001f)
            {
                var target = Quaternion.LookRotation(fwd, Vector3.up);
                transform.rotation = dt <= 0f ? target : Quaternion.Slerp(transform.rotation, target, 1f - Mathf.Exp(-dt * 8f));
            }
        }

        public float CurrentSpeed
        {
            get
            {
                float s = BaseSpeed * gm.SpeedMultiplier * gm.SlowFactorFor(this);
                if (stagger > 0f) s *= 0.25f;
                return s;
            }
        }

        protected virtual void Update()
        {
            if (gm == null) return;
            float dt = Time.deltaTime;
            float e = Emerge;
            float s = Scale * (e < 1f ? Ease.OutBack(e) : 1f);
            if (Alive) transform.localScale = Vector3.one * Mathf.Max(0.01f, s);
            if (!Alive) return;
            bool playing = gm.State == GameState.Playing;
            if (playing && e >= 0.6f)
            {
                stagger = Mathf.Max(0f, stagger - dt);
                float v = CurrentSpeed;
                Dist += v * dt;
                phase += v * dt / stride * Mathf.PI;
                if (Dist >= gm.Path.Length - 0.3f)
                {
                    if (Doomed) Dist = gm.Path.Length - 0.3f;   // the correct shell is still in flight: wait for it
                    else { gm.OnEnemyReachedCastle(this); return; }
                }
            }
            Place(playing ? dt : 0f);
            Animate(dt);
            Tint(dt);
        }

        protected virtual void Animate(float dt)
        {
            float sn = Mathf.Sin(phase), cs = Mathf.Cos(phase);
            Pose("Body", new Vector3(0f, Mathf.Abs(sn) * bobAmp, 0f), Quaternion.Euler(0f, 0f, sn * 4f));
            Pose("FootL", new Vector3(0f, Mathf.Max(0f, sn) * 0.07f, 0f), Quaternion.Euler(sn * swing, 0f, 0f));
            Pose("FootR", new Vector3(0f, Mathf.Max(0f, -sn) * 0.07f, 0f), Quaternion.Euler(-sn * swing, 0f, 0f));
            Pose("LegL", Vector3.zero, Quaternion.Euler(sn * swing, 0f, 0f));
            Pose("LegR", Vector3.zero, Quaternion.Euler(-sn * swing, 0f, 0f));
            Pose("ArmL", Vector3.zero, Quaternion.Euler(-sn * swing * 0.6f, 0f, 0f));
            Pose("ArmR", Vector3.zero, Quaternion.Euler(sn * swing * 0.6f, 0f, cs * 3f));
            Pose("Head", Vector3.zero, Quaternion.Euler(0f, sn * 4f, 0f));
        }

        protected void Pose(string name, Vector3 offset, Quaternion rot)
        {
            Part p;
            if (!parts.TryGetValue(name, out p) || p.t == null) return;
            p.t.localPosition = p.pos + offset;
            p.t.localRotation = p.rot * rot;
        }

        void Tint(float dt)
        {
            float targetFrost = gm.SlowTimer > 0f ? 1f : 0f;
            frost = Mathf.MoveTowards(frost, targetFrost, dt * 3f);
            flash = Mathf.MoveTowards(flash, 0f, dt * 5f);
            for (int i = 0; i < mats.Count; i++)
            {
                var m = mats[i];
                if (m == null) continue;
                m.SetColor(BaseColorId, Color.Lerp(baseCols[i], Ice, frost * 0.55f));
                m.SetColor(EmissionId, emitCols[i] + Ice * (frost * 0.18f) + flashColor * (flash * 1.6f));
            }
        }

        public void Flash(Color c, float amount = 1f)
        {
            flashColor = c;
            flash = Mathf.Max(flash, amount);
        }

        // ------------------------------------------------------------ outcomes
        /// <summary>A wrong shell bounced off the ink shield.</summary>
        public virtual void Deflect(Vector3 from)
        {
            Flash(new Color(1f, 0.25f, 0.3f), 1f);
            stagger = 0.25f;
            Vector3 away = transform.position - from;
            away.y = 0f;
            knock += away.normalized * 0.35f;
            LastWrongTime = Time.time;
        }

        /// <summary>Knocked down by a correct shell.</summary>
        public virtual void Kill(Vector3 from)
        {
            if (!Alive) return;
            Alive = false;
            if (col) col.enabled = false;
            StartCoroutine(DieRoutine(from));
        }

        protected virtual IEnumerator DieRoutine(Vector3 from)
        {
            Flash(Color.white, 1.4f);
            Vector3 away = transform.position - from;
            away.y = 0f;
            away = away.sqrMagnitude > 0.01f ? away.normalized : -transform.forward;
            Vector3 start = transform.position;
            Quaternion r0 = transform.rotation;
            Vector3 axis = Vector3.Cross(Vector3.up, away).normalized;
            float t = 0f, dur = 0.55f;
            while (t < dur)
            {
                t += Time.deltaTime;
                float k = Mathf.Clamp01(t / dur);
                transform.position = start + away * (1.3f * k) + Vector3.up * (Mathf.Sin(k * Mathf.PI) * 0.9f);
                transform.rotation = Quaternion.AngleAxis(110f * k, axis) * r0;
                transform.localScale = Vector3.one * Scale * Mathf.Lerp(1f, 0.15f, k * k);
                flash = Mathf.Max(flash, 1f - k);
                Tint(0f);
                yield return null;
            }
            Fx.InkBurst(transform.position + Vector3.up * 0.3f, Kind == EnemyKind.Brute ? 1.4f : 1f);
            Destroy(gameObject);
        }

        /// <summary>Reached the gate: leaps at the castle and bursts.</summary>
        public virtual void Leap(Vector3 gate, System.Action onHit)
        {
            if (!Alive) return;
            Alive = false;
            if (col) col.enabled = false;
            StartCoroutine(LeapRoutine(gate, onHit));
        }

        IEnumerator LeapRoutine(Vector3 gate, System.Action onHit)
        {
            Vector3 a = transform.position;
            float t = 0f, dur = 0.35f;
            while (t < dur)
            {
                t += Time.deltaTime;
                float k = Mathf.Clamp01(t / dur);
                transform.position = Vector3.Lerp(a, gate, k) + Vector3.up * Mathf.Sin(k * Mathf.PI) * 1.2f;
                yield return null;
            }
            onHit?.Invoke();
            Fx.InkBurst(gate + Vector3.up * 0.8f, 1.2f);
            Destroy(gameObject);
        }

        public void Stagger(float seconds) { stagger = Mathf.Max(stagger, seconds); }
    }

    public static class Ease
    {
        public static float OutBack(float t)
        {
            const float c1 = 1.70158f, c3 = c1 + 1f;
            float u = t - 1f;
            return 1f + c3 * u * u * u + c1 * u * u;
        }
        public static float OutCubic(float t) { float u = 1f - t; return 1f - u * u * u; }
        public static float InOutCubic(float t) { return t < 0.5f ? 4f * t * t * t : 1f - Mathf.Pow(-2f * t + 2f, 3f) / 2f; }
        public static float OutElastic(float t)
        {
            if (t <= 0f) return 0f;
            if (t >= 1f) return 1f;
            const float c4 = (2f * Mathf.PI) / 3f;
            return Mathf.Pow(2f, -10f * t) * Mathf.Sin((t * 10f - 0.75f) * c4) + 1f;
        }
    }
}
