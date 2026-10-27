using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace WordDefense
{
    /// <summary>
    /// Design tokens, procedurally drawn sprites and factory helpers for the runtime-built UI.
    /// The interface is typeset like a bilingual learner's dictionary laid over the battlefield:
    /// things you click are paper, things you read are ink type, red pen marks mistakes, gold marks words you know well.
    /// </summary>
    public static class UIKit
    {
        // ------------------------------------------------------------ colour
        public static readonly Color Ink = Hex("#22233F");       // type, hairlines, selected sense
        public static readonly Color Paper = Hex("#FFFEFA");     // slips, headword labels, buttons
        public static readonly Color Mist = Hex("#EEF2F8");      // inactive paper, overlays
        public static readonly Color RedPen = Hex("#D3263A");    // wrong answers, damage, missed words
        public static readonly Color Gold = Hex("#F2B544");      // 记忆深刻 fills
        public static readonly Color GoldInk = Hex("#A86F00");   // 记忆深刻 type on paper
        public static readonly Color Frost = Hex("#2E8FD0");     // the slow skill

        public static Color InkA(float a) { return A(Ink, a); }

        // ------------------------------------------------------------ type
        // Source Serif 4 for English, 思源宋体 (Noto Serif SC) for Chinese: the two halves of a bilingual dictionary.
        public static TMP_FontAsset Latin, LatinItalic, LatinBoldItalic, Song, SongBold, SongBlack;
        static readonly Dictionary<TMP_FontAsset, Material> halos = new Dictionary<TMP_FontAsset, Material>();

        public static void RegisterHalo(TMP_FontAsset font, Material halo)
        {
            if (font == null || halo == null) return;
            halos[font] = halo;
            // a tag's material="…" is looked up by the case-insensitive hash of its name, as TMP parses tag values
            int hash = TMP_TextUtilities.GetHashCode(halo.name);
            Material known;
            if (!MaterialReferenceManager.TryGetMaterial(hash, out known)) MaterialReferenceManager.AddFontMaterial(hash, halo);   // registered once per run; a restart builds the UI again
        }

        /// <summary>Soft paper halo around ink type, the way map labels stay legible over any terrain.</summary>
        public static TextMeshProUGUI Halo(TextMeshProUGUI t)
        {
            Material m;
            if (t != null && t.font != null && halos.TryGetValue(t.font, out m) && m != null) t.fontSharedMaterial = m;
            return t;
        }

        public static string Tag(TMP_FontAsset f, string s) { return f != null ? "<font=\"" + f.name + "\">" + s + "</font>" : s; }

        /// <summary>Like Tag, for text that has a halo: the font switch keeps the halo material.</summary>
        public static string TagHalo(TMP_FontAsset f, string s)
        {
            return f != null && halos.ContainsKey(f) ? "<font=\"" + f.name + "\" material=\"" + halos[f].name + "\">" + s + "</font>" : Tag(f, s);
        }

        public static Color Hex(string h, float a = 1f)
        {
            Color c;
            ColorUtility.TryParseHtmlString(h, out c);
            c.a = a;
            return c;
        }

        public static Color A(Color c, float a) { c.a = a; return c; }

        public static string Css(Color c) { return "#" + ColorUtility.ToHtmlStringRGBA(c); }

        // ------------------------------------------------------------ sprites
        static readonly Dictionary<string, Sprite> cache = new Dictionary<string, Sprite>();

        static Sprite Make(string key, int w, int h, Func<float, float, float> alpha, Vector4 border)
        {
            Sprite s;
            if (cache.TryGetValue(key, out s) && s != null) return s;
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            tex.wrapMode = TextureWrapMode.Clamp;
            tex.filterMode = FilterMode.Bilinear;
            var px = new Color32[w * h];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    float a = Mathf.Clamp01(alpha(x + 0.5f, y + 0.5f));
                    px[y * w + x] = new Color32(255, 255, 255, (byte)(a * 255f + 0.5f));
                }
            tex.SetPixels32(px);
            tex.Apply(false, true);
            s = Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(0.5f, 0.5f), 100f, 0, SpriteMeshType.FullRect, border);
            s.name = key;
            cache[key] = s;
            return s;
        }

        static float RoundBox(float x, float y, float w, float h, float r)
        {
            float qx = Mathf.Abs(x - w / 2f) - (w / 2f - r);
            float qy = Mathf.Abs(y - h / 2f) - (h / 2f - r);
            return new Vector2(Mathf.Max(qx, 0f), Mathf.Max(qy, 0f)).magnitude + Mathf.Min(Mathf.Max(qx, qy), 0f) - r;
        }

        /// <summary>9-sliced rounded rectangle; ring &gt; 0 draws only an outline of that width.</summary>
        public static Sprite Rounded(int radius, float ring = 0f)
        {
            int size = radius * 2 + 4;
            return Make("rr" + radius + "_" + ring, size, size, (x, y) =>
            {
                float d = RoundBox(x, y, size, size, radius);
                float a = Mathf.Clamp01(0.5f - d);
                if (ring > 0f) a *= Mathf.Clamp01(d + ring + 0.5f);
                return a;
            }, new Vector4(radius + 2, radius + 2, radius + 2, radius + 2));
        }

        /// <summary>Soft contact shadow for paper (9-sliced; place it slightly larger than the paper).</summary>
        public static Sprite Shadow(int radius, int blur)
        {
            int pad = blur * 2;
            int size = (radius + pad) * 2 + 4;
            return Make("sh" + radius + "_" + blur, size, size, (x, y) =>
            {
                float d = RoundBox(x, y, size, size, radius + pad) + pad;
                float t = Mathf.Max(0f, d + blur * 0.5f);
                return Mathf.Exp(-t * t / (blur * blur * 0.9f));
            }, new Vector4(radius + pad + 2, radius + pad + 2, radius + pad + 2, radius + pad + 2));
        }

        public static Sprite Circle(int size = 128) { return Make("circle" + size, size, size, (x, y) => 0.5f - (new Vector2(x - size / 2f, y - size / 2f).magnitude - (size / 2f - 1.5f)), Vector4.zero); }

        public static Sprite Ring(int size, float width)
        {
            return Make("ring" + size + "_" + width, size, size, (x, y) =>
            {
                float r = new Vector2(x - size / 2f, y - size / 2f).magnitude;
                float outer = size / 2f - 1.5f;
                return Mathf.Clamp01(0.5f - (r - outer)) * Mathf.Clamp01(0.5f - (outer - width - r));
            }, Vector4.zero);
        }

        /// <summary>A segment of a ring, clockwise from the top, with round ends.</summary>
        public static Sprite Arc(int size, float width, float fromDeg, float toDeg)
        {
            return Make("arc" + size + "_" + width + "_" + fromDeg + "_" + toDeg, size, size, (x, y) =>
            {
                Vector2 p = new Vector2(x - size / 2f, y - size / 2f);
                float mid = size / 2f - 1.5f - width / 2f;
                float a0 = fromDeg * Mathf.Deg2Rad, a1 = toDeg * Mathf.Deg2Rad;
                float ang = Mathf.Atan2(p.x, p.y);
                if (ang < 0f) ang += Mathf.PI * 2f;
                float d;
                if (ang >= a0 && ang <= a1) d = Mathf.Abs(p.magnitude - mid) - width / 2f;
                else
                {
                    Vector2 e0 = new Vector2(Mathf.Sin(a0), Mathf.Cos(a0)) * mid, e1 = new Vector2(Mathf.Sin(a1), Mathf.Cos(a1)) * mid;
                    d = Mathf.Min((p - e0).magnitude, (p - e1).magnitude) - width / 2f;
                }
                return 0.5f - d;
            }, Vector4.zero);
        }

        public static Sprite RadialGlow(int size = 128)
        {
            return Make("glow" + size, size, size, (x, y) =>
            {
                float r = new Vector2(x - size / 2f, y - size / 2f).magnitude / (size / 2f);
                return Mathf.Pow(Mathf.Clamp01(1f - r), 1.6f);
            }, Vector4.zero);
        }

        public static Sprite VGradient() { return Make("vgrad", 4, 256, (x, y) => y / 256f, Vector4.zero); }

        /// <summary>Horizontal ramp, opaque on the left, eased out to the right (alpha = (1 - x)^power).</summary>
        public static Sprite PageRamp(float power)
        {
            return Make("pageramp" + power, 256, 4, (x, y) => Mathf.Pow(1f - x / 256f, power), Vector4.zero);
        }

        public static Sprite Vignette()
        {
            return Make("vignette", 256, 256, (x, y) =>
            {
                float u = (x / 256f - 0.5f) * 2f, v = (y / 256f - 0.5f) * 2f;
                float r = Mathf.Sqrt(u * u * 0.8f + v * v);
                float t = Mathf.Clamp01((r - 0.55f) / 0.8f);
                return t * t * (3f - 2f * t);
            }, Vector4.zero);
        }

        /// <summary>A glow that hugs the four screen edges and leaves the middle clear (damage flash).</summary>
        public static Sprite EdgeGlow()
        {
            return Make("edgeglow", 256, 256, (x, y) =>
            {
                float u = Mathf.Abs(x / 256f - 0.5f) * 2f, v = Mathf.Abs(y / 256f - 0.5f) * 2f;
                float ex = (1f - u) * 1.6f, ey = 1f - v;
                const float k = 0.08f;
                float e = -k * Mathf.Log(Mathf.Exp(-ex / k) + Mathf.Exp(-ey / k));
                float t = Mathf.Clamp01(1f - e / 0.38f);
                float s = t * t * (3f - 2f * t);
                return s * s;
            }, Vector4.zero);
        }

        public static Sprite White() { return Make("white", 4, 4, (x, y) => 1f, Vector4.zero); }

        static float Seg(Vector2 p, Vector2 a, Vector2 b)
        {
            Vector2 pa = p - a, ba = b - a;
            float h = Mathf.Clamp01(Vector2.Dot(pa, ba) / Vector2.Dot(ba, ba));
            return (pa - ba * h).magnitude;
        }

        static float Box(Vector2 p, Vector2 c, Vector2 half)
        {
            Vector2 d = new Vector2(Mathf.Abs(p.x - c.x) - half.x, Mathf.Abs(p.y - c.y) - half.y);
            return new Vector2(Mathf.Max(d.x, 0f), Mathf.Max(d.y, 0f)).magnitude + Mathf.Min(Mathf.Max(d.x, d.y), 0f);
        }

        /// <summary>The same icon grown and feathered: a paper halo placed behind an ink icon.</summary>
        public static Sprite IconHalo(string name, int size = 96) { return Icon(name, size, 0.07f, 9f); }

        /// <summary>Icons drawn from signed distance functions in a unit square (0..1, y up).</summary>
        public static Sprite Icon(string name, int size = 96, float grow = 0f, float feather = 1f)
        {
            Func<Vector2, float> sdf;
            switch (name)
            {
                case "castle":
                    sdf = p =>
                    {
                        float d = Box(p, new Vector2(0.5f, 0.32f), new Vector2(0.34f, 0.2f));
                        d = Mathf.Min(d, Box(p, new Vector2(0.24f, 0.5f), new Vector2(0.1f, 0.34f)));
                        d = Mathf.Min(d, Box(p, new Vector2(0.76f, 0.5f), new Vector2(0.1f, 0.34f)));
                        d = Mathf.Max(d, -Box(p, new Vector2(0.24f, 0.86f), new Vector2(0.03f, 0.04f)));
                        d = Mathf.Max(d, -Box(p, new Vector2(0.76f, 0.86f), new Vector2(0.03f, 0.04f)));
                        d = Mathf.Min(d, Box(p, new Vector2(0.5f, 0.56f), new Vector2(0.05f, 0.06f)));
                        d = Mathf.Max(d, -Box(p, new Vector2(0.5f, 0.2f), new Vector2(0.08f, 0.09f)));
                        d = Mathf.Max(d, -(new Vector2(p.x - 0.5f, p.y - 0.29f).magnitude - 0.08f));
                        return d;
                    };
                    break;
                case "flake":
                    sdf = p =>
                    {
                        Vector2 c = new Vector2(0.5f, 0.5f);
                        float d = 9f;
                        for (int k = 0; k < 6; k++)
                        {
                            float a = k * Mathf.PI / 3f + Mathf.PI / 2f;
                            Vector2 dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
                            d = Mathf.Min(d, Seg(p, c, c + dir * 0.42f) - 0.032f);
                            Vector2 m = c + dir * 0.27f;
                            Vector2 n1 = new Vector2(Mathf.Cos(a + 0.75f), Mathf.Sin(a + 0.75f)), n2 = new Vector2(Mathf.Cos(a - 0.75f), Mathf.Sin(a - 0.75f));
                            d = Mathf.Min(d, Seg(p, m, m + n1 * 0.12f) - 0.028f);
                            d = Mathf.Min(d, Seg(p, m, m + n2 * 0.12f) - 0.028f);
                        }
                        return d;
                    };
                    break;
                case "star":
                    sdf = p =>
                    {
                        Vector2 q = p - new Vector2(0.5f, 0.47f);
                        float a = Mathf.Atan2(q.y, q.x) - Mathf.PI / 2f;
                        float seg = Mathf.PI * 2f / 5f;
                        a = Mathf.Repeat(a + seg / 2f, seg) - seg / 2f;
                        float r = q.magnitude;
                        Vector2 v = new Vector2(Mathf.Cos(a), Mathf.Abs(Mathf.Sin(a))) * r;
                        Vector2 A0 = new Vector2(0.46f, 0f), B0 = new Vector2(0.19f * Mathf.Cos(seg / 2f), 0.19f * Mathf.Sin(seg / 2f));
                        Vector2 e = B0 - A0, w = v - A0;
                        float cross = e.x * w.y - e.y * w.x;
                        float dist = Seg(v, A0, B0);
                        return cross > 0f ? -dist : dist;
                    };
                    break;
                case "cross":   // a red-pen mark: two strokes, the second slightly longer
                    sdf = p => Mathf.Min(Seg(p, new Vector2(0.24f, 0.24f), new Vector2(0.76f, 0.76f)), Seg(p, new Vector2(0.22f, 0.78f), new Vector2(0.8f, 0.2f))) - 0.075f;
                    break;
                case "check":
                    sdf = p => Mathf.Min(Seg(p, new Vector2(0.18f, 0.5f), new Vector2(0.4f, 0.27f)), Seg(p, new Vector2(0.4f, 0.27f), new Vector2(0.82f, 0.76f))) - 0.075f;
                    break;
                case "pause":
                    sdf = p => Mathf.Min(Box(p, new Vector2(0.36f, 0.5f), new Vector2(0.07f, 0.26f)), Box(p, new Vector2(0.64f, 0.5f), new Vector2(0.07f, 0.26f))) - 0.02f;
                    break;
                case "pointer":
                    sdf = p =>
                    {
                        Vector2 q = new Vector2(Mathf.Abs(p.x - 0.5f), p.y);
                        return Mathf.Max(q.y - 0.95f, (q.x * 0.9f + (0.95f - q.y) * 0.45f) - 0.45f);
                    };
                    break;
                case "crown":
                    sdf = p =>
                    {
                        float d = Box(p, new Vector2(0.5f, 0.28f), new Vector2(0.32f, 0.07f));
                        Vector2 a = new Vector2(0.18f, 0.35f), b = new Vector2(0.82f, 0.35f);
                        // three points of a crown as a filled zig-zag above the band
                        float zig = 9f;
                        Vector2[] pts = { a, new Vector2(0.2f, 0.74f), new Vector2(0.36f, 0.5f), new Vector2(0.5f, 0.8f), new Vector2(0.64f, 0.5f), new Vector2(0.8f, 0.74f), b };
                        bool inside = false;
                        for (int i = 0, j = pts.Length - 1; i < pts.Length; j = i++)
                        {
                            if ((pts[i].y > p.y) != (pts[j].y > p.y) && p.x < (pts[j].x - pts[i].x) * (p.y - pts[i].y) / (pts[j].y - pts[i].y) + pts[i].x) inside = !inside;
                            zig = Mathf.Min(zig, Seg(p, pts[i], pts[j]));
                        }
                        zig = inside ? -zig : zig;
                        return Mathf.Min(d, zig);
                    };
                    break;
                default:
                    sdf = p => (p - new Vector2(0.5f, 0.5f)).magnitude - 0.4f;
                    break;
            }
            return Make("icon_" + name + size + "_" + grow + "_" + feather, size, size, (x, y) => 0.5f - (sdf(new Vector2(x / size, y / size)) - grow) * size / feather, Vector4.zero);
        }

        // ------------------------------------------------------------ factories
        public static RectTransform Rect(Transform parent, string name, Vector2 anchor, Vector2 pos, Vector2 size, Vector2? pivot = null)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.layer = 5;
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = rt.anchorMax = anchor;
            rt.pivot = pivot ?? new Vector2(0.5f, 0.5f);
            rt.anchoredPosition = pos;
            rt.sizeDelta = size;
            return rt;
        }

        public static RectTransform Stretch(Transform parent, string name, float inset = 0f)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.layer = 5;
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(inset, inset);
            rt.offsetMax = new Vector2(-inset, -inset);
            return rt;
        }

        public static Image Img(Transform parent, string name, Sprite sprite, Color color, Vector2 anchor, Vector2 pos, Vector2 size, bool sliced = false)
        {
            var rt = Rect(parent, name, anchor, pos, size);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.color = color;
            img.raycastTarget = false;
            if (sliced) img.type = Image.Type.Sliced;
            return img;
        }

        public static Image Fill(Transform parent, string name, Sprite sprite, Color color, bool sliced = true, float inset = 0f)
        {
            var rt = Stretch(parent, name, inset);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.color = color;
            img.raycastTarget = false;
            if (sliced && sprite != null) img.type = Image.Type.Sliced;
            return img;
        }

        /// <summary>A soft contact shadow under a piece of paper of the given radius (stretches with its parent).</summary>
        public static Image PaperShadow(Transform paper, int radius, float strength = 1f)
        {
            var sh = Fill(paper, "Shadow", Shadow(radius, 10), InkA(0.2f * strength));
            sh.rectTransform.offsetMin = new Vector2(-24f, -30f);
            sh.rectTransform.offsetMax = new Vector2(24f, 16f);
            return sh;
        }

        public static TextMeshProUGUI Text(Transform parent, string name, string text, float size, Color color, TextAlignmentOptions align,
                                           Vector2 anchor, Vector2 pos, Vector2 box, TMP_FontAsset font = null, Vector2? pivot = null)
        {
            var rt = Rect(parent, name, anchor, pos, box, pivot);
            var t = rt.gameObject.AddComponent<TextMeshProUGUI>();
            t.font = font ?? SongBold;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.raycastTarget = false;
            t.textWrappingMode = TextWrappingModes.NoWrap;
            t.overflowMode = TextOverflowModes.Overflow;
            t.richText = true;
            return t;
        }

        public enum ButtonStyle { Primary, Secondary }

        /// <summary>Primary: ink with paper type. Secondary: paper with an ink rule. Both are flat paper, no gloss.</summary>
        public static Button Button(Transform parent, string name, string label, Vector2 anchor, Vector2 pos, Vector2 size, ButtonStyle style, UnityAction onClick, float fontSize = 30f, Vector2? pivot = null)
        {
            var rt = Rect(parent, name, anchor, pos, size, pivot);
            bool primary = style == ButtonStyle.Primary;
            var img = Fill(rt, "Bg", Rounded(6), primary ? Ink : Paper);
            img.raycastTarget = true;
            if (!primary) Fill(rt, "Rule", Rounded(6, 2f), Ink);
            var text = Text(rt, "Label", label, fontSize, primary ? Paper : Ink, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0f, 1f), size, SongBold);
            var b = rt.gameObject.AddComponent<Button>();
            b.targetGraphic = img;
            var cb = b.colors;
            cb.normalColor = Color.white;
            cb.highlightedColor = primary ? new Color(1.35f, 1.35f, 1.4f, 1f) : new Color(0.93f, 0.95f, 0.99f, 1f);
            cb.selectedColor = Color.white;
            cb.pressedColor = primary ? new Color(0.8f, 0.8f, 0.85f, 1f) : new Color(0.86f, 0.89f, 0.95f, 1f);
            cb.disabledColor = new Color(1f, 1f, 1f, 0.45f);
            cb.colorMultiplier = 1f;
            cb.fadeDuration = 0.08f;
            b.colors = cb;
            b.navigation = new Navigation { mode = Navigation.Mode.None };
            if (onClick != null) b.onClick.AddListener(onClick);
            b.onClick.AddListener(() => Audio.Play(Sfx.Id.Select, 0.6f));
            return b;
        }

        /// <summary>A key cap: a small paper key with an ink rule, for 空格 / Esc / 1–4.</summary>
        public static RectTransform Keycap(Transform parent, string name, string key, Vector2 anchor, Vector2 pos, float height = 34f, Vector2? pivot = null)
        {
            var probe = Text(parent, name + "Probe", key, height * 0.56f, Ink, TextAlignmentOptions.Center, anchor, pos, new Vector2(200f, height), SongBold);
            float w = Mathf.Max(height, probe.GetPreferredValues(key).x + height * 0.6f);
            UnityEngine.Object.Destroy(probe.gameObject);
            var rt = Rect(parent, name, anchor, pos, new Vector2(w, height), pivot);
            Fill(rt, "Bg", Rounded(5), Paper);
            Fill(rt, "Rule", Rounded(5, 1.5f), InkA(0.55f));
            var under = Img(rt, "Under", White(), InkA(0.55f), new Vector2(0.5f, 0f), new Vector2(0f, 1.5f), new Vector2(w - 8f, 3f));
            under.rectTransform.pivot = new Vector2(0.5f, 0.5f);
            Text(rt, "Key", key, height * 0.56f, Ink, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0f, 1.5f), new Vector2(w, height), SongBold);
            return rt;
        }

        public static float Smooth(float current, float target, float speed, float dt)
        {
            return Mathf.Lerp(current, target, 1f - Mathf.Exp(-speed * dt));
        }

        public static float Dt { get { return Time.unscaledDeltaTime > 0f ? Mathf.Min(Time.unscaledDeltaTime, 0.1f) : 0.02f; } }
    }
}
