using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace DungeonEscape
{
    /// <summary>Procedural sprites and small factory helpers for the runtime-built UI.</summary>
    public static class UIKit
    {
        static readonly Dictionary<string, Sprite> sprites = new Dictionary<string, Sprite>();

        public static readonly Color Gold = new Color(1f, 0.8f, 0.42f);
        public static readonly Color Parchment = new Color(0.93f, 0.89f, 0.8f);
        public static readonly Color Ink = new Color(0.04f, 0.035f, 0.035f, 0.82f);
        public static readonly Color Blood = new Color(0.86f, 0.12f, 0.1f);

        static Sprite Make(string key, int w, int h, System.Func<float, float, Color> fn, Vector4 border)
        {
            Sprite s;
            if (sprites.TryGetValue(key, out s) && s != null) return s;
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            tex.wrapMode = TextureWrapMode.Clamp;
            tex.filterMode = FilterMode.Bilinear;
            var px = new Color[w * h];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    px[y * w + x] = fn(x + 0.5f, y + 0.5f);
            tex.SetPixels(px);
            tex.Apply();
            s = Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(0.5f, 0.5f), 100f, 0, SpriteMeshType.FullRect, border);
            s.name = key;
            sprites[key] = s;
            return s;
        }

        static float RoundBox(float x, float y, float w, float h, float r)
        {
            float qx = Mathf.Abs(x - w / 2f) - (w / 2f - r);
            float qy = Mathf.Abs(y - h / 2f) - (h / 2f - r);
            float outside = new Vector2(Mathf.Max(qx, 0f), Mathf.Max(qy, 0f)).magnitude;
            float inside = Mathf.Min(Mathf.Max(qx, qy), 0f);
            return outside + inside - r;
        }

        /// <summary>9-sliced rounded rectangle; border>0 draws only an outline ring of that width.</summary>
        public static Sprite Rounded(int radius, int border = 0)
        {
            int size = radius * 2 + 8;
            return Make("round" + radius + "_" + border, size, size, (x, y) =>
            {
                float d = RoundBox(x, y, size, size, radius);
                float a = Mathf.Clamp01(0.5f - d);
                if (border > 0) a *= Mathf.Clamp01(d + border + 0.5f);
                return new Color(1f, 1f, 1f, a);
            }, new Vector4(radius + 2, radius + 2, radius + 2, radius + 2));
        }

        public static Sprite Circle(int size = 64)
        {
            return Make("circle" + size, size, size, (x, y) =>
            {
                float d = new Vector2(x - size / 2f, y - size / 2f).magnitude - (size / 2f - 1f);
                return new Color(1f, 1f, 1f, Mathf.Clamp01(0.5f - d));
            }, Vector4.zero);
        }

        public static Sprite Diamond(int size = 48, bool hollow = false)
        {
            return Make("diamond" + size + hollow, size, size, (x, y) =>
            {
                float d = (Mathf.Abs(x - size / 2f) + Mathf.Abs(y - size / 2f)) - (size / 2f - 2f);
                float a = Mathf.Clamp01(0.5f - d * 0.8f);
                if (hollow) a *= Mathf.Clamp01(d + 6f);
                return new Color(1f, 1f, 1f, a);
            }, Vector4.zero);
        }

        public static Sprite VGradient()
        {
            return Make("vgrad", 4, 128, (x, y) => new Color(1f, 1f, 1f, y / 128f), Vector4.zero);
        }

        public static Sprite HGradientCenter()
        {
            return Make("hgradc", 256, 4, (x, y) =>
            {
                float t = Mathf.Abs(x / 256f - 0.5f) * 2f;
                return new Color(1f, 1f, 1f, Mathf.Clamp01(1f - t * t));
            }, Vector4.zero);
        }

        public static Sprite Radial()
        {
            return Make("radial", 256, 256, (x, y) =>
            {
                float r = new Vector2(x / 256f - 0.5f, y / 256f - 0.5f).magnitude * 1.4142f;
                return new Color(1f, 1f, 1f, Mathf.SmoothStep(0.25f, 1f, r));
            }, Vector4.zero);
        }

        public static Sprite White()
        {
            return Make("white", 4, 4, (x, y) => Color.white, Vector4.zero);
        }

        // ------------------------------------------------------------ factories
        public static RectTransform Rect(Transform parent, string name, Vector2 anchorMin, Vector2 anchorMax, Vector2 pivot, Vector2 pos, Vector2 size)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = anchorMin; rt.anchorMax = anchorMax; rt.pivot = pivot;
            rt.anchoredPosition = pos; rt.sizeDelta = size;
            return rt;
        }

        public static RectTransform Stretch(Transform parent, string name)
        {
            var rt = Rect(parent, name, Vector2.zero, Vector2.one, new Vector2(0.5f, 0.5f), Vector2.zero, Vector2.zero);
            return rt;
        }

        public static Image Img(RectTransform rt, Sprite sprite, Color color, bool sliced = false)
        {
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.color = color;
            img.raycastTarget = false;
            if (sliced) img.type = Image.Type.Sliced;
            return img;
        }

        public static TextMeshProUGUI Text(Transform parent, string name, string text, float size, Color color, TextAlignmentOptions align,
                                           Vector2 anchor, Vector2 pos, Vector2 boxSize, bool bold = false, float spacing = 0f)
        {
            var rt = Rect(parent, name, anchor, anchor, anchor, pos, boxSize);
            var t = rt.gameObject.AddComponent<TextMeshProUGUI>();
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.fontStyle = bold ? FontStyles.Bold : FontStyles.Normal;
            t.characterSpacing = spacing;
            t.raycastTarget = false;
            t.textWrappingMode = TextWrappingModes.Normal;
            t.overflowMode = TextOverflowModes.Overflow;
            return t;
        }

        public static void Shadow(TextMeshProUGUI t, float softness = 0.5f, float offset = 1.2f, float alpha = 0.85f)
        {
            var m = t.fontMaterial;
            m.EnableKeyword("UNDERLAY_ON");
            m.SetColor("_UnderlayColor", new Color(0f, 0f, 0f, alpha));
            m.SetFloat("_UnderlayOffsetX", offset);
            m.SetFloat("_UnderlayOffsetY", -offset);
            m.SetFloat("_UnderlaySoftness", softness);
            t.fontMaterial = m;
        }

        public static Button Button(Transform parent, string label, Vector2 pos, Vector2 size, UnityAction onClick)
        {
            var rt = Rect(parent, "Btn_" + label, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), pos, size);
            var bg = Img(rt, Rounded(14), new Color(0.09f, 0.075f, 0.07f, 0.92f), true);
            bg.raycastTarget = true;
            var border = Img(Stretch(rt, "Border"), Rounded(14, 2), new Color(Gold.r, Gold.g, Gold.b, 0.55f), true);
            border.raycastTarget = false;
            var txt = Text(rt, "Label", label, 26f, Parchment, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), Vector2.zero, size, true, 6f);
            var b = rt.gameObject.AddComponent<Button>();
            b.targetGraphic = bg;
            var cb = b.colors;
            cb.normalColor = new Color(0.09f, 0.075f, 0.07f, 0.92f);
            cb.highlightedColor = new Color(0.35f, 0.24f, 0.1f, 0.96f);
            cb.selectedColor = new Color(0.35f, 0.24f, 0.1f, 0.96f);
            cb.pressedColor = new Color(0.55f, 0.38f, 0.14f, 1f);
            cb.colorMultiplier = 1f;
            cb.fadeDuration = 0.08f;
            b.colors = cb;
            b.transition = Selectable.Transition.ColorTint;
            if (onClick != null) b.onClick.AddListener(onClick);
            b.onClick.AddListener(() => AudioManager.Play2D(Sfx.Id.UiClick, 0.7f));
            return b;
        }
    }
}
