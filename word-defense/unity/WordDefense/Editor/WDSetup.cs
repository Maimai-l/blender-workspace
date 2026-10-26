using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.TextCore.LowLevel;

namespace WordDefense.EditorTools
{
    /// <summary>
    /// Rebuilds everything the game needs from the source files: TMP font assets, effect textures, palette materials,
    /// model import settings, project settings and the game scene. Menu: Word Defense / Setup.
    /// </summary>
    public static class WDSetup
    {
        public const string Root = "Assets/WordDefense";
        public const string ScenePath = Root + "/Scenes/WordDefense.unity";
        const string Mats = Root + "/Materials";
        const string Tex = Root + "/Textures";
        const string Fonts = Root + "/Fonts";

        // Same names and colours as wdlib.PALETTE in the Blender scripts: (hex, metallic, roughness, emission)
        static readonly Dictionary<string, (string hex, float metal, float rough, float emit)> Palette = new Dictionary<string, (string, float, float, float)>
        {
            { "M_Grass", ("#8CC27C", 0f, 0.9f, 0f) }, { "M_GrassDark", ("#7EB872", 0f, 0.9f, 0f) }, { "M_GrassLight", ("#9DCC88", 0f, 0.9f, 0f) },
            { "M_Dirt", ("#C9A27A", 0f, 0.95f, 0f) }, { "M_Road", ("#EED9B0", 0f, 0.9f, 0f) }, { "M_RoadEdge", ("#D3BE97", 0f, 0.9f, 0f) },
            { "M_Cliff", ("#E2C8A0", 0f, 0.95f, 0f) }, { "M_CliffB", ("#CDAE86", 0f, 0.95f, 0f) }, { "M_CliffC", ("#B39272", 0f, 0.95f, 0f) },
            { "M_CliffDark", ("#8C7462", 0f, 0.95f, 0f) }, { "M_Rock", ("#BDB3A6", 0f, 0.9f, 0f) }, { "M_RockDark", ("#968C82", 0f, 0.9f, 0f) },
            { "M_Water", ("#5CC6E6", 0f, 0.08f, 0f) }, { "M_Stone", ("#F3EEE4", 0f, 0.85f, 0f) }, { "M_StoneShade", ("#DCD3C4", 0f, 0.85f, 0f) },
            { "M_StoneDark", ("#B8AD9C", 0f, 0.85f, 0f) }, { "M_Roof", ("#4B63D1", 0f, 0.6f, 0f) }, { "M_RoofDark", ("#3A4DA8", 0f, 0.6f, 0f) },
            { "M_Gold", ("#F2B544", 0.6f, 0.35f, 0f) }, { "M_Flag", ("#FF6B5B", 0f, 0.85f, 0f) }, { "M_Wood", ("#9B6B47", 0f, 0.85f, 0f) },
            { "M_WoodDark", ("#6E4A33", 0f, 0.85f, 0f) }, { "M_Door", ("#3C3049", 0f, 0.8f, 0f) }, { "M_Window", ("#2E3A66", 0f, 0.4f, 0f) },
            { "M_WindowLit", ("#FFD27A", 0f, 0.5f, 1.6f) }, { "M_Steel", ("#3A4766", 0.5f, 0.45f, 0f) }, { "M_SteelLight", ("#6B7BA6", 0.5f, 0.4f, 0f) },
            { "M_Leaf", ("#6CC072", 0f, 0.85f, 0f) }, { "M_LeafDark", ("#47A06A", 0f, 0.85f, 0f) }, { "M_LeafAutumn", ("#F4A64A", 0f, 0.85f, 0f) },
            { "M_LeafPink", ("#F7A8C0", 0f, 0.85f, 0f) }, { "M_Trunk", ("#8A6447", 0f, 0.9f, 0f) }, { "M_Ink", ("#2A2A4C", 0f, 0.45f, 0f) },
            { "M_InkLight", ("#45407A", 0f, 0.45f, 0f) }, { "M_InkArmor", ("#5D5B86", 0.3f, 0.4f, 0f) }, { "M_InkGlow", ("#FF4FA0", 0f, 0.4f, 3.0f) },
            { "M_EyeWhite", ("#F6F3FF", 0f, 0.3f, 0f) }, { "M_Crystal", ("#B57CFF", 0f, 0.2f, 2.2f) }, { "M_PortalStone", ("#4A4462", 0f, 0.85f, 0f) },
            { "M_PortalCore", ("#2B1748", 0f, 0.5f, 1.5f) }, { "M_Parchment", ("#F5E9CF", 0f, 0.9f, 0f) }, { "M_ShellGold", ("#FFC24D", 0.7f, 0.3f, 0f) },
            { "M_ShellCore", ("#FFF1C2", 0f, 0.3f, 3.0f) }, { "M_Snow", ("#F4F8FF", 0f, 0.6f, 0f) }, { "M_Cloud", ("#FFFFFF", 0f, 1f, 0.12f) },
        };
        static readonly HashSet<string> InkMaterials = new HashSet<string> { "M_Ink", "M_InkLight", "M_InkArmor", "M_EyeWhite", "M_InkGlow", "M_ShellGold" };

        [MenuItem("Word Defense/Setup/All")]
        public static void All()
        {
            Folders();
            BuildFonts();
            BuildTextures();
            BuildMaterials();
            ConfigureModels();
            ConfigureProject();
            BuildScene();
            Debug.Log("[WD] setup complete");
        }

        static void Folders()
        {
            foreach (var f in new[] { Mats, Tex, Fonts, Root + "/Scenes", Root + "/Settings" })
                if (!AssetDatabase.IsValidFolder(f))
                    AssetDatabase.CreateFolder(Path.GetDirectoryName(f).Replace('\\', '/'), Path.GetFileName(f));
        }

        // ------------------------------------------------------------ fonts
        [MenuItem("Word Defense/Setup/1 Fonts")]
        public static void BuildFonts()
        {
            Folders();
            var inter = MakeFont(Fonts + "/Inter-SemiBold.ttf", Fonts + "/WD_Inter_SemiBold SDF.asset", 0, 90, 1024);
            var zh = MakeFont(Fonts + "/NotoSansSC-VF.ttf", Fonts + "/WD_NotoSC_Regular SDF.asset", 4 << 16, 64, 2048);
            var zhBold = MakeFont(Fonts + "/NotoSansSC-VF.ttf", Fonts + "/WD_NotoSC_Bold SDF.asset", 6 << 16, 64, 2048);
            var zhBlack = MakeFont(Fonts + "/NotoSansSC-VF.ttf", Fonts + "/WD_NotoSC_Black SDF.asset", 7 << 16, 64, 2048);
            // English text falls back to Chinese glyphs and the other way round
            SetFallback(inter, zhBold);
            SetFallback(zh, inter);
            SetFallback(zhBold, inter);
            SetFallback(zhBlack, inter);
            var settings = AssetDatabase.LoadAssetAtPath<TMP_Settings>("Assets/TextMesh Pro/Resources/TMP Settings.asset");
            if (settings != null)
            {
                var so = new SerializedObject(settings);
                var p = so.FindProperty("m_defaultFontAsset");
                if (p != null) p.objectReferenceValue = zhBold;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            AssetDatabase.SaveAssets();
        }

        static void SetFallback(TMP_FontAsset fa, TMP_FontAsset fb)
        {
            if (fa == null || fb == null) return;
            if (fa.fallbackFontAssetTable == null) fa.fallbackFontAssetTable = new List<TMP_FontAsset>();
            if (!fa.fallbackFontAssetTable.Contains(fb)) fa.fallbackFontAssetTable.Add(fb);
            EditorUtility.SetDirty(fa);
        }

        static TMP_FontAsset MakeFont(string fontPath, string assetPath, int faceIndex, int pointSize, int atlas)
        {
            var existing = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(assetPath);
            if (existing != null) return existing;
            var font = AssetDatabase.LoadAssetAtPath<Font>(fontPath);
            if (font == null) { Debug.LogError("[WD] missing font " + fontPath); return null; }
            var m = typeof(TMP_FontAsset).GetMethods(BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public)
                .FirstOrDefault(x => x.Name == "CreateFontAsset" && x.GetParameters().Length == 9 && x.GetParameters()[0].ParameterType == typeof(Font));
            TMP_FontAsset fa;
            if (m != null)
            {
                var ps = m.GetParameters();
                var args = new object[9];
                args[0] = font;
                for (int i = 1; i < 9; i++)
                {
                    string n = ps[i].Name.ToLowerInvariant();
                    if (n.Contains("face")) args[i] = faceIndex;
                    else if (n.Contains("sampling") || n.Contains("pointsize")) args[i] = pointSize;
                    else if (n.Contains("padding")) args[i] = 9;
                    else if (n.Contains("rendermode")) args[i] = GlyphRenderMode.SDFAA;
                    else if (n.Contains("width")) args[i] = atlas;
                    else if (n.Contains("height")) args[i] = atlas;
                    else if (n.Contains("population")) args[i] = AtlasPopulationMode.Dynamic;
                    else if (n.Contains("multi")) args[i] = true;
                    else args[i] = ps[i].ParameterType.IsValueType ? System.Activator.CreateInstance(ps[i].ParameterType) : null;
                }
                fa = (TMP_FontAsset)m.Invoke(null, args);
            }
            else
            {
                fa = TMP_FontAsset.CreateFontAsset(font, pointSize, 9, GlyphRenderMode.SDFAA, atlas, atlas, AtlasPopulationMode.Dynamic, true);
            }
            fa.name = Path.GetFileNameWithoutExtension(assetPath);
            AssetDatabase.CreateAsset(fa, assetPath);
            if (fa.atlasTextures != null)
                foreach (var t in fa.atlasTextures)
                    if (t != null && !AssetDatabase.Contains(t)) { t.name = fa.name + " Atlas"; AssetDatabase.AddObjectToAsset(t, fa); }
            if (fa.material != null && !AssetDatabase.Contains(fa.material)) { fa.material.name = fa.name + " Material"; AssetDatabase.AddObjectToAsset(fa.material, fa); }
            EditorUtility.SetDirty(fa);
            AssetDatabase.SaveAssets();
            Debug.Log("[WD] font asset " + assetPath + " face " + fa.faceInfo.styleName);
            return fa;
        }

        // ------------------------------------------------------------ textures
        [MenuItem("Word Defense/Setup/2 Textures")]
        public static void BuildTextures()
        {
            Folders();
            Png("fx_soft", 128, (u, v) => { float r = Mathf.Sqrt(u * u + v * v); return new Color(1, 1, 1, Mathf.Exp(-r * r * 5.5f) * Mathf.Clamp01((1f - r) * 4f)); });
            Png("fx_spark", 128, (u, v) =>
            {
                float r = Mathf.Sqrt(u * u + v * v);
                float star = Mathf.Max(Mathf.Exp(-Mathf.Abs(u) * 28f) * Mathf.Exp(-Mathf.Abs(v) * 2.6f), Mathf.Exp(-Mathf.Abs(v) * 28f) * Mathf.Exp(-Mathf.Abs(u) * 2.6f));
                return new Color(1, 1, 1, Mathf.Clamp01(star + Mathf.Exp(-r * r * 30f)) * Mathf.Clamp01((1f - r) * 3f));
            });
            Png("fx_ring", 256, (u, v) => { float r = Mathf.Sqrt(u * u + v * v); float d = Mathf.Abs(r - 0.82f); return new Color(1, 1, 1, Mathf.Exp(-d * d * 900f) + 0.06f * Mathf.Exp(-d * d * 120f) * (r < 0.82f ? 1f : 0f)); });
            Png("fx_flake", 128, (u, v) =>
            {
                Vector2 p = new Vector2(u, v);
                float d = 9f;
                for (int k = 0; k < 6; k++)
                {
                    float a = k * Mathf.PI / 3f;
                    Vector2 dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
                    d = Mathf.Min(d, Seg(p, Vector2.zero, dir * 0.85f));
                    Vector2 m = dir * 0.5f;
                    d = Mathf.Min(d, Seg(p, m, m + new Vector2(Mathf.Cos(a + 0.7f), Mathf.Sin(a + 0.7f)) * 0.25f));
                    d = Mathf.Min(d, Seg(p, m, m + new Vector2(Mathf.Cos(a - 0.7f), Mathf.Sin(a - 0.7f)) * 0.25f));
                }
                return new Color(1, 1, 1, Mathf.Clamp01((0.07f - d) * 40f) + 0.35f * Mathf.Exp(-(u * u + v * v) * 8f));
            });
            Png("portal_swirl", 256, (u, v) =>
            {
                float r = Mathf.Sqrt(u * u + v * v);
                float a = Mathf.Atan2(v, u);
                float arms = 0.5f + 0.5f * Mathf.Sin(a * 3f + r * 12f);
                float fade = Mathf.Clamp01((1f - r) * 3f);
                Color c = Color.Lerp(new Color(1f, 0.35f, 0.7f), new Color(0.55f, 0.35f, 1f), r);
                c.a = fade * (0.35f + 0.65f * arms * arms) * Mathf.Clamp01(0.3f + r);
                return c;
            });
            AppIcon();
            AssetDatabase.Refresh();
        }

        static float Seg(Vector2 p, Vector2 a, Vector2 b)
        {
            Vector2 pa = p - a, ba = b - a;
            float h = Mathf.Clamp01(Vector2.Dot(pa, ba) / Vector2.Dot(ba, ba));
            return (pa - ba * h).magnitude;
        }

        static void Png(string name, int size, System.Func<float, float, Color> f)
        {
            var t = new Texture2D(size, size, TextureFormat.RGBA32, false);
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                    t.SetPixel(x, y, f((x + 0.5f) / size * 2f - 1f, (y + 0.5f) / size * 2f - 1f));
            t.Apply();
            string path = Tex + "/" + name + ".png";
            File.WriteAllBytes(path, t.EncodeToPNG());
            Object.DestroyImmediate(t);
            AssetDatabase.ImportAsset(path);
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.alphaIsTransparency = true;
            ti.wrapMode = TextureWrapMode.Clamp;
            ti.mipmapEnabled = true;
            ti.sRGBTexture = true;
            ti.textureCompression = TextureImporterCompression.Uncompressed;
            ti.SaveAndReimport();
        }

        static void AppIcon()
        {
            int s = 256;
            var t = new Texture2D(s, s, TextureFormat.RGBA32, false);
            Color amber = new Color(1f, 0.76f, 0.3f), ink = new Color(0.106f, 0.122f, 0.231f);
            for (int y = 0; y < s; y++)
                for (int x = 0; x < s; x++)
                {
                    float u = (x + 0.5f) / s, v = (y + 0.5f) / s;
                    float qx = Mathf.Abs(u - 0.5f) - 0.32f, qy = Mathf.Abs(v - 0.5f) - 0.32f;
                    float box = new Vector2(Mathf.Max(qx, 0), Mathf.Max(qy, 0)).magnitude + Mathf.Min(Mathf.Max(qx, qy), 0) - 0.14f;
                    float a = Mathf.Clamp01(0.5f - box * s);
                    Color c = Color.Lerp(amber, new Color(1f, 0.62f, 0.25f), v);
                    // castle silhouette
                    bool castle = (u > 0.3f && u < 0.7f && v > 0.24f && v < 0.48f) || (u > 0.26f && u < 0.4f && v > 0.24f && v < 0.66f) || (u > 0.6f && u < 0.74f && v > 0.24f && v < 0.66f);
                    castle |= (v > 0.66f && v < 0.72f && ((u > 0.26f && u < 0.31f) || (u > 0.35f && u < 0.4f) || (u > 0.6f && u < 0.65f) || (u > 0.69f && u < 0.74f)));
                    bool gate = u > 0.45f && u < 0.55f && v > 0.24f && v < 0.38f;
                    if (castle && !gate) c = ink;
                    c.a = a;
                    t.SetPixel(x, y, c);
                }
            t.Apply();
            string path = Tex + "/app_icon.png";
            File.WriteAllBytes(path, t.EncodeToPNG());
            Object.DestroyImmediate(t);
            AssetDatabase.ImportAsset(path);
        }

        // ------------------------------------------------------------ materials
        [MenuItem("Word Defense/Setup/3 Materials")]
        public static void BuildMaterials()
        {
            Folders();
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            foreach (var kv in Palette)
            {
                string path = Mats + "/" + kv.Key + ".mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (m == null) { m = new Material(lit); AssetDatabase.CreateAsset(m, path); }
                m.shader = lit;
                Color c;
                ColorUtility.TryParseHtmlString(kv.Value.hex, out c);
                m.SetColor("_BaseColor", c);
                m.SetFloat("_Metallic", kv.Value.metal);
                m.SetFloat("_Smoothness", 1f - kv.Value.rough);
                m.SetFloat("_EnvironmentReflections", kv.Key == "M_Water" || kv.Value.metal > 0f ? 1f : 0f);
                m.SetFloat("_SpecularHighlights", kv.Value.rough < 0.6f ? 1f : 0f);
                if (kv.Value.emit > 0f || InkMaterials.Contains(kv.Key))
                {
                    m.EnableKeyword("_EMISSION");
                    m.SetColor("_EmissionColor", kv.Value.emit > 0f ? c * kv.Value.emit : Color.black);
                    m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
                }
                else
                {
                    m.DisableKeyword("_EMISSION");
                    m.SetColor("_EmissionColor", Color.black);
                }
                if (kv.Value.rough >= 0.6f) m.EnableKeyword("_SPECULARHIGHLIGHTS_OFF"); else m.DisableKeyword("_SPECULARHIGHLIGHTS_OFF");
                if (kv.Key == "M_Water" || kv.Value.metal > 0f) m.DisableKeyword("_ENVIRONMENTREFLECTIONS_OFF"); else m.EnableKeyword("_ENVIRONMENTREFLECTIONS_OFF");
                EditorUtility.SetDirty(m);
            }
            // effects
            FxMat("FX_Additive", "WordDefense/FxAdditive", "fx_soft");
            FxMat("FX_Alpha", "WordDefense/FxAlpha", "fx_soft");
            var swirl = FxMat("FX_PortalSwirl", "WordDefense/FxAdditive", "portal_swirl");
            swirl.SetColor("_Tint", new Color(1.4f, 1.2f, 1.6f, 1f));
            var sky = AssetDatabase.LoadAssetAtPath<Material>(Mats + "/WD_Sky.mat");
            if (sky == null) { sky = new Material(Shader.Find("WordDefense/SkyGradient")); AssetDatabase.CreateAsset(sky, Mats + "/WD_Sky.mat"); }
            sky.shader = Shader.Find("WordDefense/SkyGradient");
            sky.SetColor("_Top", new Color(0.47f, 0.71f, 0.93f));
            sky.SetColor("_Horizon", new Color(0.99f, 0.91f, 0.82f));
            sky.SetColor("_Mid", new Color(0.8f, 0.88f, 0.95f));
            sky.SetColor("_Bottom", new Color(0.62f, 0.77f, 0.91f));
            sky.SetVector("_SunDir", new Vector4(0.45f, 0.35f, 0.8f, 0f));
            EditorUtility.SetDirty(sky);
            AssetDatabase.SaveAssets();
        }

        static Material FxMat(string name, string shader, string tex)
        {
            string path = Mats + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            var sh = Shader.Find(shader);
            if (m == null) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
            m.shader = sh;
            m.mainTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(Tex + "/" + tex + ".png");
            m.renderQueue = 3000;
            EditorUtility.SetDirty(m);
            return m;
        }

        // ------------------------------------------------------------ models
        [MenuItem("Word Defense/Setup/4 Models")]
        public static void ConfigureModels()
        {
            foreach (var guid in AssetDatabase.FindAssets("t:Model", new[] { Root + "/Models" }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                var mi = AssetImporter.GetAtPath(path) as ModelImporter;
                if (mi == null) continue;
                mi.globalScale = 1f;
                mi.useFileScale = true;
                mi.importBlendShapes = false;
                mi.importVisibility = false;
                mi.importCameras = false;
                mi.importLights = false;
                mi.animationType = ModelImporterAnimationType.None;
                mi.importAnimation = false;
                mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
                mi.materialLocation = ModelImporterMaterialLocation.InPrefab;
                mi.importNormals = ModelImporterNormals.Import;
                mi.meshCompression = ModelImporterMeshCompression.Off;
                mi.isReadable = false;
                mi.addCollider = false;
                mi.SaveAndReimport();
                mi.SearchAndRemapMaterials(ModelImporterMaterialName.BasedOnMaterialName, ModelImporterMaterialSearch.Everywhere);
                mi.SaveAndReimport();
            }
        }

        // ------------------------------------------------------------ project
        [MenuItem("Word Defense/Setup/5 Project Settings")]
        public static void ConfigureProject()
        {
            var tm = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = tm.FindProperty("layers");
            if (layers != null && layers.arraySize > GameManager.EnemyLayer)
            {
                layers.GetArrayElementAtIndex(GameManager.EnemyLayer).stringValue = "Enemy";
                tm.ApplyModifiedPropertiesWithoutUndo();
            }
            PlayerSettings.productName = "Word Defense";
            PlayerSettings.companyName = "WordDefense";
            PlayerSettings.defaultScreenWidth = 1600;
            PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.SplashScreen.show = false;
            var icon = AssetDatabase.LoadAssetAtPath<Texture2D>(Tex + "/app_icon.png");
            if (icon != null) PlayerSettings.SetIcons(UnityEditor.Build.NamedBuildTarget.Unknown, new[] { icon }, IconKind.Any);
            var rp = GraphicsSettings.defaultRenderPipeline;
            if (rp != null)
            {
                var so = new SerializedObject(rp);
                Set(so, "m_ShadowDistance", 95f);
                Set(so, "m_ShadowCascadeCount", 2);
                Set(so, "m_MSAA", 4);
                Set(so, "m_MainLightShadowmapResolution", 4096);
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            // VSync on in every quality level: uncapped, the game renders 1000+ fps on a desktop GPU (heat, fan noise, tearing)
            var qs = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/QualitySettings.asset")[0]);
            var levels = qs.FindProperty("m_QualitySettings");
            for (int i = 0; levels != null && i < levels.arraySize; i++)
            {
                var v = levels.GetArrayElementAtIndex(i).FindPropertyRelative("vSyncCount");
                if (v != null) v.intValue = 1;
            }
            qs.ApplyModifiedPropertiesWithoutUndo();
            AssetDatabase.SaveAssets();
        }

        static void Set(SerializedObject so, string name, float v)
        {
            var p = so.FindProperty(name);
            if (p == null) return;
            if (p.propertyType == SerializedPropertyType.Float) p.floatValue = v;
            else p.intValue = (int)v;
        }

        // ------------------------------------------------------------ scene
        [MenuItem("Word Defense/Setup/6 Build Scene")]
        public static void BuildScene()
        {
            Folders();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var pathAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(Root + "/Data/path.json");
            var route = PathRoute.FromJson(pathAsset.text);

            // lighting and atmosphere
            RenderSettings.skybox = AssetDatabase.LoadAssetAtPath<Material>(Mats + "/WD_Sky.mat");
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.74f, 0.83f, 0.95f);
            RenderSettings.ambientEquatorColor = new Color(0.9f, 0.86f, 0.8f);
            RenderSettings.ambientGroundColor = new Color(0.62f, 0.58f, 0.52f);
            RenderSettings.ambientIntensity = 1f;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = new Color(0.82f, 0.88f, 0.94f);
            RenderSettings.fogStartDistance = 58f;
            RenderSettings.fogEndDistance = 170f;
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;

            var sun = new GameObject("Sun");
            var light = sun.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = new Color(1f, 0.96f, 0.9f);
            light.intensity = 1.35f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.82f;
            light.shadowBias = 0.04f;
            light.shadowNormalBias = 0.3f;
            sun.transform.rotation = Quaternion.Euler(50f, -32f, 0f);
            RenderSettings.sun = light;

            // camera
            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = 30f;
            cam.nearClipPlane = 0.5f;
            cam.farClipPlane = 400f;
            cam.clearFlags = CameraClearFlags.Skybox;
            Vector3 target = new Vector3(-1.4f, 0f, 3.6f);
            camGo.transform.position = new Vector3(-1.4f, 31.5f, -30.5f);
            camGo.transform.rotation = Quaternion.LookRotation(target - camGo.transform.position, Vector3.up);
            camGo.AddComponent<AudioListener>();
            var camData = camGo.AddComponent<UniversalAdditionalCameraData>();
            camData.renderPostProcessing = true;
            camData.antialiasing = AntialiasingMode.None;
            camData.renderShadows = true;
            camGo.AddComponent<CameraRig>();

            // post-processing
            var vol = new GameObject("Global Volume").AddComponent<Volume>();
            vol.isGlobal = true;
            vol.sharedProfile = Profile();

            // world
            var world = Place("WD_World", Vector3.zero, Quaternion.identity);
            foreach (var t in world.GetComponentsInChildren<Transform>(true))
            {
                if (t.name == "WindmillBlades") { var a = t.gameObject.AddComponent<Ambient>(); a.mode = Ambient.Mode.Spin; a.axis = Vector3.forward; a.speed = 40f; }
                else if (t.name == "Clouds") { var a = t.gameObject.AddComponent<Ambient>(); a.mode = Ambient.Mode.Drift; a.speed = 0.08f; a.amount = 1.6f; }
                else GameObjectUtility.SetStaticEditorFlags(t.gameObject, StaticEditorFlags.BatchingStatic | StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic);
            }
            foreach (var r in world.GetComponentsInChildren<MeshRenderer>(true))
                if (r.name == "Clouds") r.shadowCastingMode = ShadowCastingMode.Off;

            // castle + cannon
            var castleGo = Place("WD_Castle", route.Castle, Quaternion.identity);
            var castle = castleGo.AddComponent<Castle>();
            Transform mount = castleGo.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "CannonMount");
            Vector3 mountPos = mount != null ? mount.position : route.Castle + new Vector3(3.85f, 3.12f, 0f);
            Vector3 field = new Vector3(2f, 0f, 4f) - mountPos;
            field.y = 0f;
            var cannonGo = Place("WD_Cannon", mountPos, Quaternion.LookRotation(field.normalized, Vector3.up));
            cannonGo.transform.SetParent(castleGo.transform, true);
            var cannon = cannonGo.AddComponent<Cannon>();

            // portal at the start of the road, opening along the road
            Vector3 fwd;
            route.Sample(0f, out fwd);
            var portalGo = Place("WD_Portal", route.Portal, Quaternion.LookRotation(Vector3.Cross(Vector3.up, -fwd).normalized * -1f, Vector3.up));
            portalGo.transform.rotation = Quaternion.FromToRotation(Vector3.left, fwd);
            var swirl = AssetDatabase.LoadAssetAtPath<Material>(Mats + "/FX_PortalSwirl.mat");
            foreach (var t in portalGo.GetComponentsInChildren<Transform>(true))
            {
                if (t.name == "PortalCore")
                {
                    var mr = t.GetComponent<MeshRenderer>();
                    if (mr != null && swirl != null) mr.sharedMaterial = swirl;
                    if (mr != null) mr.shadowCastingMode = ShadowCastingMode.Off;
                    var a = t.gameObject.AddComponent<Ambient>(); a.mode = Ambient.Mode.Spin; a.axis = Vector3.right; a.speed = -70f;
                }
                else if (t.name.StartsWith("Crystal")) { var a = t.gameObject.AddComponent<Ambient>(); a.mode = Ambient.Mode.Bob; a.speed = 1.6f; a.amount = 0.18f; }
            }
            var portalLight = new GameObject("PortalGlow").AddComponent<Light>();
            portalLight.type = LightType.Point;
            portalLight.color = new Color(0.8f, 0.45f, 1f);
            portalLight.intensity = 6f;
            portalLight.range = 7f;
            portalLight.transform.position = route.Portal + Vector3.up * 2f;
            portalLight.transform.SetParent(portalGo.transform, true);

            // game manager
            var gmGo = new GameObject("Game");
            var gm = gmGo.AddComponent<GameManager>();
            gm.pathJson = pathAsset;
            gm.cam = cam;
            gm.castle = castle;
            gm.cannon = cannon;
            gm.portal = portalGo.transform;
            gm.scoutModel = Model("WD_Scout");
            gm.soldierModel = Model("WD_Soldier");
            gm.bruteModel = Model("WD_Brute");
            gm.bossModel = Model("WD_Boss");
            gm.shellModel = Model("WD_Shell");
            gm.fontEn = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(Fonts + "/WD_Inter_SemiBold SDF.asset");
            gm.fontZh = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(Fonts + "/WD_NotoSC_Regular SDF.asset");
            gm.fontZhBold = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(Fonts + "/WD_NotoSC_Bold SDF.asset");
            gm.fontZhBlack = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(Fonts + "/WD_NotoSC_Black SDF.asset");
            gm.fxAdditive = AssetDatabase.LoadAssetAtPath<Material>(Mats + "/FX_Additive.mat");
            gm.fxAlpha = AssetDatabase.LoadAssetAtPath<Material>(Mats + "/FX_Alpha.mat");
            gm.fxSoft = AssetDatabase.LoadAssetAtPath<Texture2D>(Tex + "/fx_soft.png");
            gm.fxSpark = AssetDatabase.LoadAssetAtPath<Texture2D>(Tex + "/fx_spark.png");
            gm.fxRing = AssetDatabase.LoadAssetAtPath<Texture2D>(Tex + "/fx_ring.png");
            gm.fxFlake = AssetDatabase.LoadAssetAtPath<Texture2D>(Tex + "/fx_flake.png");

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log("[WD] scene saved " + ScenePath);
        }

        static GameObject Model(string name) { return AssetDatabase.LoadAssetAtPath<GameObject>(Root + "/Models/" + name + ".fbx"); }

        static GameObject Place(string model, Vector3 pos, Quaternion rot)
        {
            var asset = Model(model);
            var go = (GameObject)PrefabUtility.InstantiatePrefab(asset);
            go.transform.SetPositionAndRotation(pos, rot);
            return go;
        }

        static VolumeProfile Profile()
        {
            string path = Root + "/Settings/WD_Volume.asset";
            var old = AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
            if (old != null) AssetDatabase.DeleteAsset(path);
            var p = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(p, path);
            var tone = p.Add<Tonemapping>(true);
            tone.mode.Override(TonemappingMode.Neutral);
            var bloom = p.Add<Bloom>(true);
            bloom.threshold.Override(0.95f);
            bloom.intensity.Override(0.55f);
            bloom.scatter.Override(0.68f);
            var ca = p.Add<ColorAdjustments>(true);
            ca.postExposure.Override(0.12f);
            ca.contrast.Override(10f);
            ca.saturation.Override(6f);
            var vig = p.Add<Vignette>(true);
            vig.intensity.Override(0.2f);
            vig.smoothness.Override(0.5f);
            var st = p.Add<SplitToning>(true);
            st.shadows.Override(new Color(0.42f, 0.5f, 0.72f));
            st.highlights.Override(new Color(1f, 0.93f, 0.84f));
            st.balance.Override(0f);
            foreach (var c in p.components) AssetDatabase.AddObjectToAsset(c, p);
            EditorUtility.SetDirty(p);
            AssetDatabase.SaveAssets();
            return p;
        }
    }
}
