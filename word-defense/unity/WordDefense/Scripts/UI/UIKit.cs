using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace WordDefense
{
    /// <summary>Design tokens, procedurally drawn sprites and factory helpers for the runtime-built UI.</summary>
    public static class UIKit
    {
        // ------------------------------------------------------------ tokens
        // UI blends in linear space (linear colour space project), where a dark panel over the bright scene looks far
        // more transparent than its alpha suggests; these alphas give the intended dark-glass look on screen.
        public static readonly Color Glass = Hex("#11152A", 0.94f);
        public static readonly Color GlassLight = Hex("#1D2340", 0.95f);
        public static readonly Color Stroke = new Color(1f, 1f, 1f, 0.10f);
        public static readonly Color TextHi = Color.white;
        public static readonly Color TextMid = Hex("#BAC3DE");
        public static readonly Color TextLow = Hex("#7F89AA");
        public static readonly Color Mint = Hex("#3EE0A1");
        public static readonly Color Coral = Hex("#FF5C6C");
        public static readonly Color Amber = Hex("#FFC34D");
        public static readonly Color Ice = Hex("#7FD8FF");
        public static readonly Color Violet = Hex("#A78BFA");
        public static readonly Color Ink = Hex("#1B1F3B");
        public static readonly Color Paper = Hex("#FFFFFF", 0.96f);

        public static TMP_FontAsset FontEn, FontZh, FontZhBold, FontZhBlack;

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

        /// <summary>Soft drop shadow for a rounded panel (9-sliced; place it slightly larger than the panel).</summary>
        public static Sprite Shadow(int radius, int blur)
        {
            int pad = blur * 2;
            int size = (radius + pad) * 2 + 4;
            return Make("sh" + radius + "_" + blur, size, size, (x, y) =>
            {
                float d = RoundBox(x, y, size, size, radius + pad) + pad;
                return Mathf.Exp(-Mathf.Max(0f, d + blur * 0.5f) * Mathf.Max(0f, d + blur * 0.5f) / (blur * blur * 0.9f)) * (d < -blur ? 1f : 1f);
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

        public static Sprite RadialGlow(int size = 128)
        {
            return Make("glow" + size, size, size, (x, y) =>
            {
                float r = new Vector2(x - size / 2f, y - size / 2f).magnitude / (size / 2f);
                return Mathf.Pow(Mathf.Clamp01(1f - r), 2.2f);
            }, Vector4.zero);
        }

        public static Sprite VGradient() { return Make("vgrad", 4, 256, (x, y) => y / 256f, Vector4.zero); }
        public static Sprite HGradient() { return Make("hgrad", 256, 4, (x, y) => x / 256f, Vector4.zero); }
        /// <summary>Horizontal ramp that stays dense for longer (alpha = x^power), for shades behind text.</summary>
        public static Sprite HRamp(float power) { return Make("hramp" + power, 256, 4, (x, y) => Mathf.Pow(x / 256f, power), Vector4.zero); }
        public static Sprite Vignette()
        {
            return Make("vignette", 256, 256, (x, y) =>
            {
                float u = (x / 256f - 0.5f) * 2f, v = (y / 256f - 0.5f) * 2f;
                float r = Mathf.Sqrt(u * u * 0.8f + v * v);
                float t = Mathf.Clamp01((r - 0.55f) / 0.8f);   // GLSL-style smoothstep (Mathf.SmoothStep interpolates values instead)
                return t * t * (3f - 2f * t);
            }, Vector4.zero);
        }
        /// <summary>A glow that hugs the four screen edges and leaves the middle clear (damage flash).</summary>
        public static Sprite EdgeGlow()
        {
            return Make("edgeglow", 256, 256, (x, y) =>
            {
                float u = Mathf.Abs(x / 256f - 0.5f) * 2f, v = Mathf.Abs(y / 256f - 0.5f) * 2f;
                float ex = (1f - u) * 1.6f, ey = 1f - v;          // distance to the side / top-bottom edges (16:9 screen)
                const float k = 0.08f;
                float e = -k * Mathf.Log(Mathf.Exp(-ex / k) + Mathf.Exp(-ey / k));   // smooth minimum rounds the corners
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

        /// <summary>Icons drawn from signed distance functions in a unit square (0..1, y up).</summary>
        public static Sprite Icon(string name, int size = 96)
        {
            Func<Vector2, float> sdf;
            switch (name)
            {
                case "castle":
                    sdf = p =>
                    {
                        float d = Box(p, new Vector2(0.5f, 0.36f), new Vector2(0.3f, 0.2f));
                        d = Mathf.Min(d, Box(p, new Vector2(0.24f, 0.52f), new Vector2(0.1f, 0.3f)));
                        d = Mathf.Min(d, Box(p, new Vector2(0.76f, 0.52f), new Vector2(0.1f, 0.3f)));
                        for (int i = 0; i < 2; i++)
                        {
                            float cx = i == 0 ? 0.24f : 0.76f;
                            d = Mathf.Min(d, Box(p, new Vector2(cx - 0.065f, 0.86f), new Vector2(0.035f, 0.05f)));
                            d = Mathf.Min(d, Box(p, new Vector2(cx + 0.065f, 0.86f), new Vector2(0.035f, 0.05f)));
                        }
                        d = Mathf.Min(d, Box(p, new Vector2(0.5f, 0.6f), new Vector2(0.035f, 0.05f)));
                        d = Mathf.Max(d, -Box(p, new Vector2(0.5f, 0.24f), new Vector2(0.075f, 0.09f)));
                        d = Mathf.Max(d, -(new Vector2(p.x - 0.5f, p.y - 0.33f).magnitude - 0.075f));
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
                            Vector2 tip = c + dir * 0.4f;
                            d = Mathf.Min(d, Seg(p, c, tip) - 0.035f);
                            Vector2 m = c + dir * 0.26f;
                            Vector2 n1 = new Vector2(Mathf.Cos(a + 0.7f), Mathf.Sin(a + 0.7f)), n2 = new Vector2(Mathf.Cos(a - 0.7f), Mathf.Sin(a - 0.7f));
                            d = Mathf.Min(d, Seg(p, m, m + n1 * 0.12f) - 0.03f);
                            d = Mathf.Min(d, Seg(p, m, m + n2 * 0.12f) - 0.03f);
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
                        Vector2 A = new Vector2(0.44f, 0f), B = new Vector2(0.18f * Mathf.Cos(seg / 2f), 0.18f * Mathf.Sin(seg / 2f));
                        Vector2 e = B - A, w = v - A;
                        float cross = e.x * w.y - e.y * w.x;
                        float dist = Seg(v, A, B);
                        return cross > 0f ? -dist : dist;
                    };
                    break;
                case "check":
                    sdf = p => Mathf.Min(Seg(p, new Vector2(0.2f, 0.52f), new Vector2(0.42f, 0.3f)), Seg(p, new Vector2(0.42f, 0.3f), new Vector2(0.8f, 0.72f))) - 0.07f;
                    break;
                case "cross":
                    sdf = p => Mathf.Min(Seg(p, new Vector2(0.25f, 0.25f), new Vector2(0.75f, 0.75f)), Seg(p, new Vector2(0.25f, 0.75f), new Vector2(0.75f, 0.25f))) - 0.07f;
                    break;
                case "pause":
                    sdf = p => Mathf.Min(Box(p, new Vector2(0.37f, 0.5f), new Vector2(0.06f, 0.24f)), Box(p, new Vector2(0.63f, 0.5f), new Vector2(0.06f, 0.24f))) - 0.02f;
                    break;
                case "speed":
                    sdf = p =>
                    {
                        float d1 = Mathf.Min(Seg(p, new Vector2(0.22f, 0.25f), new Vector2(0.47f, 0.5f)), Seg(p, new Vector2(0.47f, 0.5f), new Vector2(0.22f, 0.75f)));
                        float d2 = Mathf.Min(Seg(p, new Vector2(0.52f, 0.25f), new Vector2(0.77f, 0.5f)), Seg(p, new Vector2(0.77f, 0.5f), new Vector2(0.52f, 0.75f)));
                        return Mathf.Min(d1, d2) - 0.065f;
                    };
                    break;
                case "shell":
                    sdf = p =>
                    {
                        float d = new Vector2(p.x - 0.5f, (p.y - 0.5f) * 0.92f).magnitude - 0.36f;
                        float band = Mathf.Abs(p.y - 0.5f) - 0.045f;
                        return Mathf.Max(d, -Mathf.Max(band, d + 0.08f) * 1f) ;
                    };
                    break;
                case "pointer":
                    sdf = p =>
                    {
                        // downward triangle
                        Vector2 q = new Vector2(Mathf.Abs(p.x - 0.5f), p.y);
                        return Mathf.Max(q.y - 0.95f, (q.x * 0.9f + (0.95f - q.y) * 0.45f) - 0.45f) ;
                    };
                    break;
                case "crown":
                    sdf = p =>
                    {
                        float d = Box(p, new Vector2(0.5f, 0.3f), new Vector2(0.32f, 0.08f));
                        d = Mathf.Min(d, Seg(p, new Vector2(0.2f, 0.34f), new Vector2(0.24f, 0.72f)) - 0.05f);
                        d = Mathf.Min(d, Seg(p, new Vector2(0.5f, 0.34f), new Vector2(0.5f, 0.78f)) - 0.05f);
                        d = Mathf.Min(d, Seg(p, new Vector2(0.8f, 0.34f), new Vector2(0.76f, 0.72f)) - 0.05f);
                        d = Mathf.Min(d, Seg(p, new Vector2(0.22f, 0.38f), new Vector2(0.5f, 0.55f)) - 0.04f);
                        d = Mathf.Min(d, Seg(p, new Vector2(0.78f, 0.38f), new Vector2(0.5f, 0.55f)) - 0.04f);
                        return d;
                    };
                    break;
                default:
                    sdf = p => (p - new Vector2(0.5f, 0.5f)).magnitude - 0.4f;
                    break;
            }
            return Make("icon_" + name + size, size, size, (x, y) => 0.5f - sdf(new Vector2(x / size, y / size)) * size, Vector4.zero);
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

        /// <summary>Glass panel with soft shadow and hairline border. Returns the panel's RectTransform.</summary>
        public static RectTransform Panel(Transform parent, string name, Vector2 anchor, Vector2 pos, Vector2 size, int radius = 22, Color? color = null, bool shadow = true, Vector2? pivot = null)
        {
            var rt = Rect(parent, name, anchor, pos, size, pivot);
            if (shadow)
            {
                var sh = Img(rt, "Shadow", Shadow(radius, 14), new Color(0.02f, 0.03f, 0.08f, 0.45f), new Vector2(0.5f, 0.5f), new Vector2(0f, -6f), size + new Vector2(56f, 56f), true);
                sh.rectTransform.anchorMin = Vector2.zero; sh.rectTransform.anchorMax = Vector2.one;
                sh.rectTransform.offsetMin = new Vector2(-28f, -34f); sh.rectTransform.offsetMax = new Vector2(28f, 22f);
            }
            Fill(rt, "Bg", Rounded(radius), color ?? Glass);
            Fill(rt, "Stroke", Rounded(radius, 1.5f), Stroke);
            return rt;
        }

        public static TextMeshProUGUI Text(Transform parent, string name, string text, float size, Color color, TextAlignmentOptions align,
                                           Vector2 anchor, Vector2 pos, Vector2 box, TMP_FontAsset font = null, FontStyles style = FontStyles.Normal, float spacing = 0f)
        {
            var rt = Rect(parent, name, anchor, pos, box);
            var t = rt.gameObject.AddComponent<TextMeshProUGUI>();
            t.font = font ?? FontZhBold;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.fontStyle = style;
            t.characterSpacing = spacing;
            t.raycastTarget = false;
            t.textWrappingMode = TextWrappingModes.NoWrap;
            t.overflowMode = TextOverflowModes.Overflow;
            t.richText = true;
            return t;
        }

        public static Button Button(Transform parent, string name, string label, Vector2 anchor, Vector2 pos, Vector2 size, Color bg, Color fg, UnityAction onClick, float fontSize = 30f)
        {
            var rt = Rect(parent, name, anchor, pos, size);
            var sh = Img(rt, "Shadow", Shadow((int)(size.y / 2f), 12), new Color(0f, 0f, 0f, 0.35f), new Vector2(0.5f, 0.5f), new Vector2(0f, -5f), size + new Vector2(40f, 40f), true);
            var img = Fill(rt, "Bg", Rounded((int)Mathf.Min(48f, size.y / 2f)), bg);
            img.raycastTarget = true;
            Fill(rt, "Stroke", Rounded((int)Mathf.Min(48f, size.y / 2f), 1.5f), new Color(1f, 1f, 1f, 0.18f));
            var label2 = Text(rt, "Label", label, fontSize, fg, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), Vector2.zero, size);
            var b = rt.gameObject.AddComponent<Button>();
            b.targetGraphic = img;
            var cb = b.colors;
            cb.normalColor = Color.white;
            cb.highlightedColor = new Color(1.08f, 1.08f, 1.08f, 1f);
            cb.selectedColor = Color.white;
            cb.pressedColor = new Color(0.82f, 0.82f, 0.82f, 1f);
            cb.colorMultiplier = 1.1f;
            cb.fadeDuration = 0.08f;
            b.colors = cb;
            b.navigation = new Navigation { mode = Navigation.Mode.None };
            rt.gameObject.AddComponent<HoverScale>();
            if (onClick != null) b.onClick.AddListener(onClick);
            b.onClick.AddListener(() => Audio.Play(Sfx.Id.Select, 0.6f));
            return b;
        }

        public static float Smooth(float current, float target, float speed, float dt)
        {
            return Mathf.Lerp(current, target, 1f - Mathf.Exp(-speed * dt));
        }

        public static float Dt { get { return Time.unscaledDeltaTime > 0f ? Mathf.Min(Time.unscaledDeltaTime, 0.1f) : 0.02f; } }
    }

}
