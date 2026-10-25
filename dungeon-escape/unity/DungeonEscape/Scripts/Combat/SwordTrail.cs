using System.Collections.Generic;
using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Ribbon trail between the blade base and tip, smoothed with Catmull-Rom, drawn in world space.</summary>
    public class SwordTrail : MonoBehaviour
    {
        public Transform basePoint;
        public Transform tipPoint;
        public Material material;
        public Color color = new Color(1f, 0.92f, 0.75f, 0.5f);
        public float lifetime = 0.12f;

        struct Sample { public Vector3 a, b; public float t; }
        readonly List<Sample> samples = new List<Sample>();
        readonly List<Vector3> verts = new List<Vector3>();
        readonly List<Color> cols = new List<Color>();
        readonly List<Vector2> uvs = new List<Vector2>();
        readonly List<int> tris = new List<int>();
        Mesh mesh;
        bool emitting;

        void Awake()
        {
            mesh = new Mesh();
            mesh.MarkDynamic();
        }

        public void Emit(bool on)
        {
            emitting = on;
        }

        void LateUpdate()
        {
            if (basePoint == null || tipPoint == null || material == null) return;
            float now = Time.time;
            if (emitting) samples.Add(new Sample { a = basePoint.position, b = tipPoint.position, t = now });
            samples.RemoveAll(s => now - s.t > lifetime);
            while (samples.Count > 40) samples.RemoveAt(0);
            Build(now);
            if (verts.Count > 0) Graphics.DrawMesh(mesh, Matrix4x4.identity, material, 0);
        }

        static Vector3 CR(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t)
        {
            float t2 = t * t, t3 = t2 * t;
            return 0.5f * ((2f * p1) + (-p0 + p2) * t + (2f * p0 - 5f * p1 + 4f * p2 - p3) * t2 + (-p0 + 3f * p1 - 3f * p2 + p3) * t3);
        }

        void Build(float now)
        {
            verts.Clear(); cols.Clear(); uvs.Clear(); tris.Clear();
            int n = samples.Count;
            if (n < 2) { mesh.Clear(); return; }
            const int sub = 4;
            int total = (n - 1) * sub + 1;
            for (int k = 0; k < total; k++)
            {
                float f = (float)k / sub;
                int i = Mathf.Min(Mathf.FloorToInt(f), n - 2);
                float t = f - i;
                var s0 = samples[Mathf.Max(0, i - 1)]; var s1 = samples[i]; var s2 = samples[i + 1]; var s3 = samples[Mathf.Min(n - 1, i + 2)];
                Vector3 a = CR(s0.a, s1.a, s2.a, s3.a, t);
                Vector3 b = CR(s0.b, s1.b, s2.b, s3.b, t);
                float age = Mathf.Lerp(now - s1.t, now - s2.t, t) / lifetime;
                float alpha = Mathf.Clamp01(1f - age) * Mathf.Clamp01((float)k / total * 3f);
                Vector3 a2 = Vector3.Lerp(b, a, 0.55f);
                verts.Add(a2); verts.Add(b);
                cols.Add(new Color(color.r, color.g, color.b, 0f));
                cols.Add(new Color(color.r, color.g, color.b, color.a * alpha));
                float u = (float)k / (total - 1);
                uvs.Add(new Vector2(u, 0f)); uvs.Add(new Vector2(u, 1f));
                if (k > 0)
                {
                    int v = k * 2;
                    tris.Add(v - 2); tris.Add(v - 1); tris.Add(v);
                    tris.Add(v - 1); tris.Add(v + 1); tris.Add(v);
                }
            }
            mesh.Clear();
            mesh.SetVertices(verts);
            mesh.SetColors(cols);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateBounds();
        }
    }
}
