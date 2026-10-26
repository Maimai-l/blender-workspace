using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace WordDefense
{
    /// <summary>The castle: hit points, damage feedback, waving flags and the collapse on defeat.</summary>
    public class Castle : MonoBehaviour
    {
        public int MaxHp = 100;
        public int Hp = 100;
        public Vector3 Gate;
        public float LastHitTime = -10f;
        readonly List<Transform> towers = new List<Transform>();
        readonly List<KeyValuePair<Transform, Quaternion>> flags = new List<KeyValuePair<Transform, Quaternion>>();
        Transform keep;
        Vector3 rootPos;
        float shake;
        readonly List<ParticleSystem> smokes = new List<ParticleSystem>();
        bool collapsed;

        public void Setup(Vector3 gate)
        {
            Gate = gate;
            rootPos = transform.position;
            foreach (Transform t in GetComponentsInChildren<Transform>(true))
            {
                if (t.name.StartsWith("Tower_") && !t.name.EndsWith("_Flag")) towers.Add(t);
                else if (t.name == "Keep") keep = t;
                if (t.name.EndsWith("_Flag") || t.name.StartsWith("Banner_")) flags.Add(new KeyValuePair<Transform, Quaternion>(t, t.localRotation));
            }
            Hp = MaxHp;
        }

        public void ResetCastle()
        {
            Hp = MaxHp;
            collapsed = false;
            foreach (var s in smokes) if (s) Destroy(s.gameObject);
            smokes.Clear();
        }

        void Update()
        {
            float t = Time.time;
            for (int i = 0; i < flags.Count; i++)
            {
                var f = flags[i];
                if (f.Key == null) continue;
                float w = Mathf.Sin(t * 2.3f + i * 1.7f) * 7f + Mathf.Sin(t * 5.1f + i) * 2.5f;
                f.Key.localRotation = f.Value * Quaternion.Euler(0f, 0f, w);
            }
            if (!collapsed)
            {
                shake = Mathf.MoveTowards(shake, 0f, Time.deltaTime * 1.6f);
                transform.position = rootPos + (shake > 0f ? UnityEngine.Random.insideUnitSphere * shake * 0.12f : Vector3.zero);
            }
        }

        public void Damage(int amount)
        {
            if (collapsed) return;
            Hp = Mathf.Max(0, Hp - amount);
            LastHitTime = Time.time;
            shake = Mathf.Min(1f, shake + 0.5f + amount / 40f);
            Fx.Rubble(Gate + Vector3.up * 0.8f, amount);
            int want = Hp <= 25 ? 2 : (Hp <= 55 ? 1 : 0);
            while (smokes.Count < want && smokes.Count < towers.Count)
            {
                var tw = towers[smokes.Count == 0 ? 0 : 3 % towers.Count];
                smokes.Add(Fx.SmokeColumn(tw.position + Vector3.up * 5.2f, transform));
            }
        }

        public void Collapse()
        {
            if (collapsed) return;
            collapsed = true;
            StartCoroutine(CollapseRoutine());
        }

        IEnumerator CollapseRoutine()
        {
            var parts = new List<Transform>(towers);
            if (keep) parts.Add(keep);
            var start = new List<Vector3>();
            var rot = new List<Quaternion>();
            var axis = new List<Vector3>();
            foreach (var p in parts)
            {
                start.Add(p.position);
                rot.Add(p.rotation);
                Vector3 outward = p.position - transform.position;
                outward.y = 0f;
                axis.Add(Vector3.Cross(Vector3.up, outward.sqrMagnitude > 0.01f ? outward.normalized : Vector3.right));
                Fx.Dust(p.position + Vector3.up * 0.5f, 2.2f);
            }
            float t = 0f;
            while (t < 2.2f)
            {
                t += Time.deltaTime;
                for (int i = 0; i < parts.Count; i++)
                {
                    float k = Mathf.Clamp01((t - i * 0.18f) / 1.4f);
                    k = k * k;
                    parts[i].position = start[i] + Vector3.down * (k * 4.5f);
                    parts[i].rotation = Quaternion.AngleAxis(k * 28f, axis[i]) * rot[i];
                }
                transform.position = rootPos + UnityEngine.Random.insideUnitSphere * 0.08f * (1f - t / 2.2f);
                yield return null;
            }
        }
    }
}
