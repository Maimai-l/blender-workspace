using System;
using System.Collections.Generic;
using UnityEngine;

namespace WordDefense
{
    /// <summary>The road from the portal to the castle gate, baked in Blender (Data/path.json) together with the road mesh.</summary>
    public sealed class PathRoute
    {
        [Serializable]
        sealed class PathData
        {
            public float[][] points;
        }

        readonly List<Vector3> pts = new List<Vector3>();
        readonly List<float> cum = new List<float>();
        public float Length { get; private set; }
        public Vector3 Castle, Portal;

        public static PathRoute FromJson(string json)
        {
            var r = new PathRoute();
            // JsonUtility cannot read nested arrays, so parse the few fields by hand
            r.ParsePoints(json);
            r.Castle = ReadVec(json, "\"castle\"");
            r.Portal = ReadVec(json, "\"portal\"");
            return r;
        }

        void ParsePoints(string json)
        {
            int i = json.IndexOf("\"points\"", StringComparison.Ordinal);
            int start = json.IndexOf('[', i) + 1;
            int depth = 1, p = start;
            var nums = new List<float>();
            var sb = new System.Text.StringBuilder();
            while (p < json.Length && depth > 0)
            {
                char c = json[p];
                if (c == '[') depth++;
                else if (c == ']') { depth--; Flush(sb, nums); }
                else if (c == ',') Flush(sb, nums);
                else if (!char.IsWhiteSpace(c)) sb.Append(c);
                p++;
            }
            for (int k = 0; k + 2 < nums.Count; k += 3) pts.Add(new Vector3(nums[k], nums[k + 1], nums[k + 2]));
            cum.Add(0f);
            for (int k = 1; k < pts.Count; k++) cum.Add(cum[k - 1] + Vector3.Distance(pts[k - 1], pts[k]));
            Length = cum[cum.Count - 1];
        }

        static void Flush(System.Text.StringBuilder sb, List<float> nums)
        {
            if (sb.Length == 0) return;
            nums.Add(float.Parse(sb.ToString(), System.Globalization.CultureInfo.InvariantCulture));
            sb.Length = 0;
        }

        static Vector3 ReadVec(string json, string key)
        {
            int i = json.IndexOf(key, StringComparison.Ordinal);
            if (i < 0) return Vector3.zero;
            int a = json.IndexOf('[', i), b = json.IndexOf(']', a);
            var parts = json.Substring(a + 1, b - a - 1).Split(',');
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            return new Vector3(float.Parse(parts[0], inv), float.Parse(parts[1], inv), float.Parse(parts[2], inv));
        }

        public int Count { get { return pts.Count; } }
        public Vector3 this[int i] { get { return pts[i]; } }

        /// <summary>Position and direction at distance d along the road.</summary>
        public Vector3 Sample(float d, out Vector3 forward)
        {
            if (pts.Count < 2) { forward = Vector3.forward; return Vector3.zero; }
            d = Mathf.Clamp(d, 0f, Length);
            int lo = 0, hi = cum.Count - 1;
            while (hi - lo > 1)
            {
                int mid = (lo + hi) / 2;
                if (cum[mid] <= d) lo = mid; else hi = mid;
            }
            float seg = cum[hi] - cum[lo];
            float t = seg > 1e-5f ? (d - cum[lo]) / seg : 0f;
            // smooth the direction over a short window so units turn gracefully
            Vector3 a = SampleRaw(d - 0.8f), b = SampleRaw(d + 0.8f);
            forward = b - a;
            forward.y = 0f;
            forward = forward.sqrMagnitude > 1e-6f ? forward.normalized : Vector3.forward;
            return Vector3.Lerp(pts[lo], pts[hi], t);
        }

        Vector3 SampleRaw(float d)
        {
            d = Mathf.Clamp(d, 0f, Length);
            int lo = 0, hi = cum.Count - 1;
            while (hi - lo > 1)
            {
                int mid = (lo + hi) / 2;
                if (cum[mid] <= d) lo = mid; else hi = mid;
            }
            float seg = cum[hi] - cum[lo];
            return Vector3.Lerp(pts[lo], pts[hi], seg > 1e-5f ? (d - cum[lo]) / seg : 0f);
        }

        /// <summary>Distance along the road of the point closest to p (coarse).</summary>
        public float Project(Vector3 p)
        {
            float best = float.MaxValue, bestD = 0f;
            for (int i = 0; i < pts.Count; i++)
            {
                float dd = (pts[i] - p).sqrMagnitude;
                if (dd < best) { best = dd; bestD = cum[i]; }
            }
            return bestD;
        }
    }
}
