using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace WordDefense
{
    /// <summary>A shell flying from the cannon to a (moving) target on an arc; vivid shells swoop in on a homing curve.</summary>
    public class Projectile : MonoBehaviour
    {
        Vector3 start, side;
        Func<Vector3> target;
        float dur, t, arc;
        bool homing;
        Action onImpact;
        Vector3 last;

        public static Projectile Launch(GameObject model, Vector3 from, Func<Vector3> target, bool homing, Color trail, Action onImpact)
        {
            var go = model != null ? Instantiate(model) : GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = homing ? "HomingShell" : "Shell";
            foreach (var c in go.GetComponentsInChildren<Collider>()) Destroy(c);
            go.transform.position = from;
            go.transform.localScale = Vector3.one * (homing ? 1.5f : 1.3f);
            var p = go.AddComponent<Projectile>();
            p.start = from;
            p.target = target;
            p.homing = homing;
            p.onImpact = onImpact;
            Vector3 to = target();
            float d = Vector3.Distance(from, to);
            p.dur = homing ? 0.75f + d * 0.008f : 0.32f + d * 0.0065f;
            p.arc = homing ? 4f + d * 0.12f : 1.2f + d * 0.16f;
            Vector3 flat = to - from; flat.y = 0f;
            p.side = Vector3.Cross(Vector3.up, flat.normalized) * (UnityEngine.Random.value < 0.5f ? -1f : 1f) * (homing ? d * 0.28f : 0f);
            p.last = from;
            Fx.AttachTrail(go, trail, homing);
            return p;
        }

        void Update()
        {
            t += Time.deltaTime / dur;
            Vector3 to = target != null ? target() : last;
            float k = Mathf.Clamp01(t);
            Vector3 mid = (start + to) * 0.5f + Vector3.up * arc + side;
            Vector3 a = Vector3.Lerp(start, mid, k), b = Vector3.Lerp(mid, to, k);
            Vector3 pos = Vector3.Lerp(a, b, k);
            if (homing) pos += Vector3.Cross((to - start).normalized, Vector3.up) * Mathf.Sin(k * Mathf.PI * 3f) * 0.4f * (1f - k);
            Vector3 vel = pos - last;
            if (vel.sqrMagnitude > 1e-6f) transform.rotation = Quaternion.LookRotation(vel.normalized);
            transform.position = pos;
            transform.Rotate(0f, 0f, Time.deltaTime * 720f, Space.Self);
            last = pos;
            if (t >= 1f)
            {
                var cb = onImpact;
                onImpact = null;
                cb?.Invoke();
                Destroy(gameObject);
            }
        }
    }
}
