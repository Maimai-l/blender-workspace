using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>Animated emissive color on specific material slots (runes, sigils, water).</summary>
    public class RuneGlow : MonoBehaviour
    {
        public Renderer[] renderers;
        public string materialPrefix = "M_Rune";
        public Color color = new Color(1f, 0.16f, 0.08f);
        public float intensity = 4f;
        public float pulse = 0.15f;
        public float pulseSpeed = 2f;
        public Light linkedLight;
        public float lightIntensityPerUnit = 0.6f;

        Color curColor, fromColor, toColor;
        float curInt, fromInt, toInt;
        float t = 1f, dur = 1f;
        MaterialPropertyBlock mpb;

        void Awake()
        {
            mpb = new MaterialPropertyBlock();
            curColor = toColor = fromColor = color;
            curInt = toInt = fromInt = intensity;
        }

        public void SetTarget(Color c, float inten, float seconds)
        {
            fromColor = curColor; fromInt = curInt;
            toColor = c; toInt = inten;
            dur = Mathf.Max(0.01f, seconds); t = 0f;
        }

        void Update()
        {
            if (t < 1f)
            {
                t = Mathf.Min(1f, t + Time.deltaTime / dur);
                float e = t * t * (3f - 2f * t);
                curColor = Color.Lerp(fromColor, toColor, e);
                curInt = Mathf.Lerp(fromInt, toInt, e);
            }
            float p = 1f + Mathf.Sin(Time.time * pulseSpeed) * pulse;
            Color emis = curColor * (curInt * p);
            if (renderers != null)
            {
                foreach (var r in renderers)
                {
                    if (r == null) continue;
                    var mats = r.sharedMaterials;
                    for (int i = 0; i < mats.Length; i++)
                    {
                        if (mats[i] == null || !mats[i].name.StartsWith(materialPrefix)) continue;
                        r.GetPropertyBlock(mpb, i);
                        mpb.SetColor("_EmissionColor", emis);
                        r.SetPropertyBlock(mpb, i);
                    }
                }
            }
            if (linkedLight != null)
            {
                linkedLight.color = curColor;
                linkedLight.intensity = curInt * lightIntensityPerUnit * p;
            }
        }
    }
}
