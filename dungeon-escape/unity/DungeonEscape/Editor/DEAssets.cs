using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace DungeonEscape.EditorTools
{
    /// <summary>Procedural textures, URP materials and model import configuration for Dungeon Escape.</summary>
    public static class DEAssets
    {
        public const string Root = "Assets/DungeonEscape";
        public const string TexDir = Root + "/Textures";
        public const string MatDir = Root + "/Materials";
        public const string ModelDir = Root + "/Models";

        // ---------------------------------------------------------------- noise
        static float Hash(int x, int y, int s)
        {
            unchecked
            {
                int h = x * 374761393 + y * 668265263 + s * 1442695041;
                h = (h ^ (h >> 13)) * 1274126177;
                h ^= h >> 16;
                return (h & 0x7fffffff) / (float)0x7fffffff;
            }
        }

        static float Grad(int ix, int iy, int px, int py, int s, float dx, float dy)
        {
            ix = ((ix % px) + px) % px; iy = ((iy % py) + py) % py;
            float a = Hash(ix, iy, s) * 6.2831853f;
            return Mathf.Cos(a) * dx + Mathf.Sin(a) * dy;
        }

        static float Perlin(float x, float y, int px, int py, int s)
        {
            int x0 = Mathf.FloorToInt(x), y0 = Mathf.FloorToInt(y);
            float fx = x - x0, fy = y - y0;
            float u = fx * fx * fx * (fx * (fx * 6 - 15) + 10), v = fy * fy * fy * (fy * (fy * 6 - 15) + 10);
            float n00 = Grad(x0, y0, px, py, s, fx, fy), n10 = Grad(x0 + 1, y0, px, py, s, fx - 1, fy);
            float n01 = Grad(x0, y0 + 1, px, py, s, fx, fy - 1), n11 = Grad(x0 + 1, y0 + 1, px, py, s, fx - 1, fy - 1);
            return Mathf.Lerp(Mathf.Lerp(n00, n10, u), Mathf.Lerp(n01, n11, u), v) * 1.4142f;
        }

        static float Fbm(float u, float v, int basePeriod, int oct, int s, float gain = 0.5f)
        {
            float sum = 0, amp = 1, norm = 0; int p = basePeriod;
            for (int i = 0; i < oct; i++)
            {
                sum += amp * Perlin(u * p, v * p, p, p, s + i * 31);
                norm += amp; amp *= gain; p *= 2;
            }
            return sum / norm;
        }

        // ---------------------------------------------------------------- textures
        delegate Color PixelFn(float u, float v, int x, int y);

        static void WriteTex(string name, int w, int h, PixelFn fn, bool normal = false, bool linear = false, bool alpha = false, TextureWrapMode wrap = TextureWrapMode.Repeat)
        {
            Directory.CreateDirectory(TexDir);
            var tex = new Texture2D(w, h, alpha ? TextureFormat.RGBA32 : TextureFormat.RGB24, false, linear || normal);
            var px = new Color[w * h];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    px[y * w + x] = fn((float)x / w, (float)y / h, x, y);
            tex.SetPixels(px);
            tex.Apply();
            string path = TexDir + "/" + name + ".png";
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            ti.sRGBTexture = !(linear || normal);
            ti.alphaSource = alpha ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
            ti.alphaIsTransparency = alpha;
            ti.wrapMode = wrap;
            ti.mipmapEnabled = true;
            ti.anisoLevel = normal || !alpha ? 4 : 1;
            ti.textureCompression = TextureImporterCompression.CompressedHQ;
            ti.SaveAndReimport();
        }

        static float Height(float u, float v)
        {
            float h = 0.55f * Fbm(u, v, 6, 5, 3) + 0.30f * Fbm(u, v, 24, 3, 9) + 0.05f * Fbm(u, v, 64, 2, 17);
            return h;
        }

        [MenuItem("Dungeon Escape/Setup/1 Generate Textures")]
        public static void GenerateTextures()
        {
            const int S = 512;
            WriteTex("T_StoneGrain", S, S, (u, v, x, y) =>
            {
                float n1 = Fbm(u, v, 4, 6, 1), n2 = Fbm(u, v, 32, 3, 7), n3 = Fbm(u, v, 3, 3, 13);
                float val = 0.88f + 0.17f * n1 + 0.07f * n2;
                float sp = Hash(x, y, 99);
                if (sp > 0.992f) val *= 0.72f; else if (sp > 0.985f) val *= 0.86f; else if (sp < 0.004f) val *= 1.12f;
                return new Color(val * (1 + 0.035f * n3), val, val * (1 - 0.03f * n3));
            });
            float[,] hm = new float[S, S];
            for (int y = 0; y < S; y++) for (int x = 0; x < S; x++) hm[x, y] = Height((float)x / S, (float)y / S) - (Hash(x, y, 99) > 0.992f ? 0.06f : 0f);
            WriteTex("T_StoneNormal", S, S, (u, v, x, y) =>
            {
                float l = hm[(x + S - 1) % S, y], r = hm[(x + 1) % S, y], d = hm[x, (y + S - 1) % S], t = hm[x, (y + 1) % S];
                const float k = 3.6f;
                var n = new Vector3(-(r - l) * k, -(t - d) * k, 1f).normalized;
                return new Color(n.x * 0.5f + 0.5f, n.y * 0.5f + 0.5f, n.z * 0.5f + 0.5f);
            }, normal: true);
            WriteTex("T_WoodGrainV", S, S, (u, v, x, y) =>
            {
                float warp = Fbm(u, v, 3, 4, 5);
                float f = Mathf.Sin((u * 22f + warp * 1.6f) * 6.2831853f);
                float fine = Fbm(u, v, 64, 2, 21);
                float knot = Mathf.Clamp01(1f - Fbm(u, v, 2, 3, 77) * 3f);
                float val = 0.80f + 0.11f * f + 0.08f * fine - 0.08f * (1 - knot);
                return new Color(val * 1.02f, val, val * 0.96f);
            });
            WriteTex("T_WoodGrainU", S, S, (u, v, x, y) =>
            {
                float warp = Fbm(v, u, 3, 4, 5);
                float f = Mathf.Sin((v * 22f + warp * 1.6f) * 6.2831853f);
                float fine = Fbm(v, u, 64, 2, 21);
                float val = 0.80f + 0.11f * f + 0.08f * fine;
                return new Color(val * 1.02f, val, val * 0.96f);
            });
            WriteTex("T_MetalGrain", 256, 256, (u, v, x, y) =>
            {
                float n = Fbm(u, v, 8, 4, 41), s = Fbm(u * 0.1f, v, 64, 2, 43);
                float val = 0.9f + 0.1f * n + 0.04f * s;
                return new Color(val, val, val);
            });
            WriteTex("T_Cloth", 256, 256, (u, v, x, y) =>
            {
                float weave = Mathf.Sin(u * 128f * Mathf.PI) * Mathf.Sin(v * 128f * Mathf.PI);
                float val = 0.86f + 0.06f * weave + 0.08f * Fbm(u, v, 8, 3, 61);
                return new Color(val, val, val);
            });
            // effects
            WriteTex("T_Glow", 128, 128, (u, v, x, y) =>
            {
                float r = Vector2.Distance(new Vector2(u, v), new Vector2(0.5f, 0.5f)) * 2f;
                float a = Mathf.Clamp01(1f - r); a = a * a * (3 - 2 * a);
                return new Color(1, 1, 1, a * a);
            }, alpha: true, wrap: TextureWrapMode.Clamp);
            WriteTex("T_Smoke", 128, 128, (u, v, x, y) =>
            {
                float r = Vector2.Distance(new Vector2(u, v), new Vector2(0.5f, 0.5f)) * 2f;
                float a = Mathf.Clamp01(1f - r);
                a = a * a * (0.55f + 0.45f * (Fbm(u, v, 4, 4, 81) * 0.5f + 0.5f));
                return new Color(1, 1, 1, a);
            }, alpha: true, wrap: TextureWrapMode.Clamp);
            WriteTex("T_Flame", 64, 128, (u, v, x, y) =>
            {
                float cx = (u - 0.5f) * 2f;
                float w = Mathf.Lerp(0.85f, 0.05f, Mathf.Pow(v, 0.8f)) * Mathf.Clamp01(v * 6f);
                float d = Mathf.Abs(cx) / Mathf.Max(0.001f, w);
                float a = Mathf.Clamp01(1f - d) * Mathf.Clamp01((1f - v) * 1.5f);
                a = Mathf.SmoothStep(0, 1, a);
                return new Color(1, 1, 1, a);
            }, alpha: true, wrap: TextureWrapMode.Clamp);
            WriteTex("T_Vignette", 256, 256, (u, v, x, y) =>
            {
                float r = Vector2.Distance(new Vector2(u, v), new Vector2(0.5f, 0.5f)) * 1.41421f;
                float a = Mathf.SmoothStep(0.35f, 1.0f, r);
                return new Color(1, 1, 1, a);
            }, alpha: true, wrap: TextureWrapMode.Clamp);
            WriteTex("T_LightBeam", 64, 256, (u, v, x, y) =>
            {
                float side = Mathf.Sin(u * Mathf.PI); side *= side;
                float fall = Mathf.Pow(v, 0.7f);
                float streak = 0.75f + 0.25f * (Fbm(u, 0.5f, 6, 3, 91) * 0.5f + 0.5f);
                return new Color(1, 1, 1, Mathf.Clamp01(side * fall * streak));
            }, alpha: true, wrap: TextureWrapMode.Clamp);
            AssetDatabase.Refresh();
            Debug.Log("[DE] Textures generated");
        }

        // ---------------------------------------------------------------- materials
        public class MatDef
        {
            public string name; public Color color; public float metal; public float smooth;
            public string tex; public float tiling = 0.5f; public string normal; public float normalScale = 1f;
            public Color emission = Color.black; public float emissionIntensity;
        }

        static MatDef D(string n, float r, float g, float b, float metal, float smooth, string tex = null, string normal = null, float ns = 1f, float tiling = 0.5f)
        {
            return new MatDef { name = n, color = new Color(r, g, b), metal = metal, smooth = smooth, tex = tex, normal = normal, normalScale = ns, tiling = tiling };
        }

        static MatDef E(string n, float r, float g, float b, float intensity, float smooth = 0.5f)
        {
            return new MatDef { name = n, color = new Color(r * 0.3f, g * 0.3f, b * 0.3f), metal = 0, smooth = smooth, emission = new Color(r, g, b), emissionIntensity = intensity };
        }

        public static List<MatDef> Defs()
        {
            const string SG = "T_StoneGrain", SN = "T_StoneNormal";
            return new List<MatDef>
            {
                D("M_StoneA", 0.50f, 0.49f, 0.48f, 0, 0.16f, SG, SN, 1.0f),
                D("M_StoneB", 0.57f, 0.54f, 0.50f, 0, 0.18f, SG, SN, 1.0f),
                D("M_StoneC", 0.42f, 0.43f, 0.46f, 0, 0.16f, SG, SN, 1.0f),
                D("M_StoneDark", 0.27f, 0.27f, 0.29f, 0, 0.14f, SG, SN, 1.0f),
                D("M_Mortar", 0.21f, 0.20f, 0.18f, 0, 0.04f, SG, SN, 0.6f),
                D("M_FloorA", 0.47f, 0.44f, 0.40f, 0, 0.28f, SG, SN, 0.8f),
                D("M_FloorB", 0.37f, 0.35f, 0.33f, 0, 0.30f, SG, SN, 0.8f),
                D("M_FloorC", 0.54f, 0.49f, 0.43f, 0, 0.26f, SG, SN, 0.8f),
                D("M_Grout", 0.12f, 0.11f, 0.10f, 0, 0.04f, SG),
                D("M_Wood", 0.47f, 0.31f, 0.19f, 0, 0.22f, "T_WoodGrainV", null, 1f, 1f),
                D("M_WoodDark", 0.30f, 0.19f, 0.12f, 0, 0.2f, "T_WoodGrainU", null, 1f, 1f),
                D("M_Iron", 0.26f, 0.26f, 0.28f, 0.6f, 0.42f, "T_MetalGrain"),
                D("M_RustIron", 0.36f, 0.22f, 0.14f, 0.45f, 0.22f, "T_MetalGrain"),
                D("M_Steel", 0.80f, 0.82f, 0.86f, 0.62f, 0.62f, "T_MetalGrain"),
                D("M_SteelDark", 0.45f, 0.46f, 0.5f, 0.6f, 0.5f, "T_MetalGrain"),
                D("M_Gold", 1.0f, 0.77f, 0.38f, 0.8f, 0.7f, "T_MetalGrain"),
                D("M_Leather", 0.40f, 0.25f, 0.14f, 0, 0.32f, "T_Cloth"),
                D("M_ClothBlue", 0.18f, 0.32f, 0.68f, 0, 0.1f, "T_Cloth", null, 1f, 2f),
                D("M_ClothRed", 0.58f, 0.10f, 0.08f, 0, 0.08f, "T_Cloth", null, 1f, 2f),
                D("M_ClothDark", 0.18f, 0.16f, 0.15f, 0, 0.05f, "T_Cloth", null, 1f, 2f),
                D("M_Bone", 0.86f, 0.81f, 0.69f, 0, 0.32f, SG, SN, 0.4f, 1f),
                D("M_BoneDark", 0.46f, 0.40f, 0.33f, 0, 0.22f, SG),
                D("M_Socket", 0.02f, 0.02f, 0.02f, 0, 0.0f),
                E("M_EyeGlow", 1.0f, 0.30f, 0.08f, 6f),
                E("M_Flame", 1.0f, 0.55f, 0.18f, 5f),
                E("M_Ember", 1.0f, 0.32f, 0.06f, 3f),
                E("M_Rune", 1.0f, 0.16f, 0.08f, 4f),
                E("M_RuneLock", 1.0f, 0.16f, 0.08f, 4f),
                E("M_HealWater", 0.15f, 0.95f, 0.75f, 2.2f, 0.95f),
                D("M_Wax", 0.90f, 0.86f, 0.72f, 0, 0.35f),
                D("M_Clay", 0.56f, 0.34f, 0.21f, 0, 0.2f, SG),
                D("M_Velvet", 0.50f, 0.06f, 0.10f, 0, 0.12f, "T_Cloth", null, 1f, 3f),
                D("M_Statue", 0.56f, 0.56f, 0.55f, 0, 0.15f, SG, SN, 0.8f, 1f),
            };
        }

        static Texture2D Tex(string n)
        {
            if (string.IsNullOrEmpty(n)) return null;
            return AssetDatabase.LoadAssetAtPath<Texture2D>(TexDir + "/" + n + ".png");
        }

        public static Shader LitShader { get { return Shader.Find("Universal Render Pipeline/Lit"); } }

        [MenuItem("Dungeon Escape/Setup/2 Create Materials")]
        public static void CreateMaterials()
        {
            Directory.CreateDirectory(MatDir);
            foreach (var d in Defs())
            {
                string path = MatDir + "/" + d.name + ".mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                bool isNew = m == null;
                if (isNew) m = new Material(LitShader);
                m.shader = LitShader;
                m.SetColor("_BaseColor", d.color);
                m.SetFloat("_Metallic", d.metal);
                m.SetFloat("_Smoothness", d.smooth);
                var t = Tex(d.tex);
                m.SetTexture("_BaseMap", t);
                m.SetTextureScale("_BaseMap", new Vector2(d.tiling, d.tiling));
                var n = Tex(d.normal);
                if (n != null)
                {
                    m.SetTexture("_BumpMap", n);
                    m.SetFloat("_BumpScale", d.normalScale);
                    m.EnableKeyword("_NORMALMAP");
                }
                else
                {
                    m.SetTexture("_BumpMap", null);
                    m.DisableKeyword("_NORMALMAP");
                }
                if (d.emissionIntensity > 0)
                {
                    m.SetColor("_EmissionColor", d.emission * d.emissionIntensity);
                    m.EnableKeyword("_EMISSION");
                    m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
                }
                else
                {
                    m.SetColor("_EmissionColor", Color.black);
                    m.DisableKeyword("_EMISSION");
                    m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.EmissiveIsBlack;
                }
                m.enableInstancing = true;
                if (isNew) AssetDatabase.CreateAsset(m, path);
                else EditorUtility.SetDirty(m);
            }
            CreateFxMaterials();
            AssetDatabase.SaveAssets();
            Debug.Log("[DE] Materials created");
        }

        public static Material FxMaterial(string name, string tex, bool additive, Color tint)
        {
            string path = MatDir + "/FX/" + name + ".mat";
            Directory.CreateDirectory(MatDir + "/FX");
            var sh = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            bool isNew = m == null;
            if (isNew) m = new Material(sh);
            m.shader = sh;
            m.SetTexture("_BaseMap", Tex(tex));
            m.SetColor("_BaseColor", tint);
            m.SetFloat("_Surface", 1f);
            m.SetFloat("_Blend", additive ? 2f : 0f);
            m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            m.SetFloat("_DstBlend", additive ? (float)BlendMode.One : (float)BlendMode.OneMinusSrcAlpha);
            m.SetFloat("_SrcBlendAlpha", additive ? (float)BlendMode.One : (float)BlendMode.One);
            m.SetFloat("_DstBlendAlpha", additive ? (float)BlendMode.One : (float)BlendMode.OneMinusSrcAlpha);
            m.SetFloat("_ZWrite", 0f);
            m.SetFloat("_Cull", 0f);
            m.SetOverrideTag("RenderType", "Transparent");
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.renderQueue = (int)RenderQueue.Transparent;
            if (isNew) AssetDatabase.CreateAsset(m, path);
            else EditorUtility.SetDirty(m);
            return m;
        }

        static void CreateFxMaterials()
        {
            FxMaterial("FX_Flame", "T_Flame", true, new Color(3.2f, 2.0f, 0.9f, 1f)); // HDR so flames bloom against lit walls
            FxMaterial("FX_Glow", "T_Glow", true, Color.white);
            FxMaterial("FX_Ember", "T_Glow", true, new Color(1f, 0.45f, 0.1f, 1f));
            FxMaterial("FX_Smoke", "T_Smoke", false, new Color(0.15f, 0.14f, 0.13f, 0.5f));
            FxMaterial("FX_Dust", "T_Smoke", false, new Color(0.45f, 0.42f, 0.38f, 0.6f));
            FxMaterial("FX_Beam", "T_LightBeam", true, new Color(0.8f, 0.9f, 1f, 0.35f));
            FxMaterial("FX_Spark", "T_Glow", true, new Color(1f, 0.85f, 0.5f, 1f));
            FxMaterial("FX_Magic", "T_Glow", true, new Color(0.4f, 0.9f, 1f, 1f));
        }

        // ---------------------------------------------------------------- models
        [MenuItem("Dungeon Escape/Setup/3 Configure Models")]
        public static void ConfigureModels()
        {
            foreach (var guid in AssetDatabase.FindAssets("t:Model", new[] { ModelDir }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                if (!path.ToLower().EndsWith(".fbx")) continue;
                ConfigureModel(path);
            }
            AssetDatabase.SaveAssets();
            Debug.Log("[DE] Models configured");
        }

        public static void ConfigureModel(string path)
        {
            var mi = AssetImporter.GetAtPath(path) as ModelImporter;
            if (mi == null) return;
            bool isChar = path.Contains("/Characters/");
            mi.globalScale = 1f;
            mi.useFileScale = true;
            mi.bakeAxisConversion = false;
            mi.importNormals = ModelImporterNormals.Import;
            mi.importTangents = ModelImporterTangents.CalculateMikk;
            mi.meshCompression = ModelImporterMeshCompression.Off;
            mi.isReadable = true;
            mi.importCameras = false;
            mi.importLights = false;
            mi.importBlendShapes = false;
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            mi.materialLocation = ModelImporterMaterialLocation.InPrefab;
            if (isChar)
            {
                mi.animationType = ModelImporterAnimationType.Generic;
                mi.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
                mi.importAnimation = true;
                mi.generateSecondaryUV = false;
            }
            else
            {
                mi.animationType = ModelImporterAnimationType.None;
                mi.importAnimation = false;
                mi.generateSecondaryUV = true;
                mi.secondaryUVHardAngle = 70f;
                mi.secondaryUVPackMargin = 8f;
            }
            mi.SaveAndReimport();
            mi.SearchAndRemapMaterials(ModelImporterMaterialName.BasedOnMaterialName, ModelImporterMaterialSearch.Everywhere);
            if (isChar) ConfigureClips(mi);
            mi.SaveAndReimport();
        }

        static readonly string[] LoopClips = { "Idle", "Walk", "Run", "Fall" };

        static void ConfigureClips(ModelImporter mi)
        {
            mi.animationCompression = ModelImporterAnimationCompression.Off;
            mi.resampleCurves = true;
            var clips = mi.defaultClipAnimations;
            for (int i = 0; i < clips.Length; i++)
            {
                var c = clips[i];
                string n = c.takeName;
                int bar = n.LastIndexOf('|');
                if (bar >= 0) n = n.Substring(bar + 1);
                c.name = n;
                c.loopTime = System.Array.IndexOf(LoopClips, n) >= 0;
                c.loopPose = false;
                c.lockRootRotation = false;
                c.lockRootHeightY = false;
                c.lockRootPositionXZ = false;
                clips[i] = c;
            }
            mi.clipAnimations = clips;
        }

        [MenuItem("Dungeon Escape/Setup/All (textures, materials, models)")]
        public static void SetupAll()
        {
            GenerateTextures();
            CreateMaterials();
            ConfigureModels();
        }
    }
}
