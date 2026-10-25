using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace DungeonEscape.EditorTools
{
    public static class DEAnimators
    {
        public const string Dir = "Assets/DungeonEscape/Animation";

        [MenuItem("Dungeon Escape/Setup/4 Animator Controllers")]
        public static void CreateAll()
        {
            Directory.CreateDirectory(Dir);
            Build("Knight", new[] { "Idle", "Walk", "Run" }, new[] { 0f, 2.2f, 6.2f },
                new[] { "JumpUp", "Fall", "Land", "Attack1", "Attack2", "Attack3", "Dodge", "Hit", "Death", "Victory", "Interact" });
            Build("Skeleton", new[] { "Idle", "Walk", "Run" }, new[] { 0f, 1.6f, 3.6f }, new[] { "Attack", "Hit", "Death", "Rise" });
            Build("Warden", new[] { "Idle", "Walk", "Run" }, new[] { 0f, 1.6f, 3.6f }, new[] { "Attack", "Hit", "Death", "Rise" });
            AssetDatabase.SaveAssets();
        }

        public static AnimatorController Get(string model)
        {
            return AssetDatabase.LoadAssetAtPath<AnimatorController>(Dir + "/AC_" + model + ".controller");
        }

        static void Build(string model, string[] loco, float[] thresholds, string[] states)
        {
            string path = Dir + "/AC_" + model + ".controller";
            AssetDatabase.DeleteAsset(path);
            var ac = AnimatorController.CreateAnimatorControllerAtPath(path);
            ac.AddParameter("Speed", AnimatorControllerParameterType.Float);
            BlendTree tree;
            var locoState = ac.CreateBlendTreeInController("Locomotion", out tree, 0);
            tree.blendType = BlendTreeType.Simple1D;
            tree.blendParameter = "Speed";
            tree.useAutomaticThresholds = false;
            for (int i = 0; i < loco.Length; i++) tree.AddChild(DEPreview.Clip(model, loco[i]), thresholds[i]);
            var sm = ac.layers[0].stateMachine;
            sm.defaultState = locoState;
            int k = 0;
            foreach (var s in states)
            {
                var st = sm.AddState(s, new Vector3(300 + (k % 3) * 220, k / 3 * 70, 0));
                st.motion = DEPreview.Clip(model, s);
                k++;
            }
        }
    }

    public static class DEBuilder
    {
        public const string ScenePath = "Assets/DungeonEscape/Scenes/Dungeon.unity";
        const string Models = "Assets/DungeonEscape/Models/";

        class Region
        {
            public string name; public int x0, z0, x1, z1, rows; public float floorY; public bool floor = true, ceiling = true;
        }

        static List<Region> regions;
        static Dictionary<Vector2Int, int> cellRegion;
        static HashSet<string> connections;
        static Dictionary<string, Portal> portals;
        class Portal { public Vector2 center; public bool alongX; public float baseY; public string a, b; }

        static GameObject envKit, props, statues, doorFbx;
        static Transform envRoot, propRoot, lightRoot, colRoot, gameRoot, fxRoot;
        static int L_Env, L_Player, L_Enemy, L_Interact;
        static System.Random rng;
        static FxLibrary fx;
        static readonly List<Vector3> archPiers = new List<Vector3>();

        // ================================================================== entry
        [MenuItem("Dungeon Escape/Build Level")]
        public static void Build()
        {
            EnsureLayers();
            DEAnimators.CreateAll();
            envKit = AssetDatabase.LoadAssetAtPath<GameObject>(Models + "Env/EnvKit.fbx");
            props = AssetDatabase.LoadAssetAtPath<GameObject>(Models + "Props/Props.fbx");
            statues = AssetDatabase.LoadAssetAtPath<GameObject>(Models + "Props/Statues.fbx");
            doorFbx = AssetDatabase.LoadAssetAtPath<GameObject>(Models + "Props/Door_Great.fbx");
            rng = new System.Random(1234);
            archPiers.Clear();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            envRoot = new GameObject("Environment").transform;
            propRoot = new GameObject("Props").transform;
            lightRoot = new GameObject("Lights").transform;
            colRoot = new GameObject("Colliders").transform;
            gameRoot = new GameObject("Gameplay").transform;
            fxRoot = new GameObject("FX").transform;

            var gmGo = new GameObject("GameManager");
            var gm = gmGo.AddComponent<GameManager>();
            gmGo.AddComponent<AudioManager>();
            fx = gmGo.AddComponent<FxLibrary>();
            AssignFx(fx);

            DefineLayout();
            BuildFloorsCeilings();
            BuildWalls();
            BuildPortals(gm);
            BuildSpecial();
            BuildPillars();
            DressStart(gm);
            DressCorridorA(gm);
            DressHub(gm);
            DressCorridorB(gm);
            DressKeyRoom(gm);
            DressArena(gm);
            DressExit(gm);
            SetupPlayerAndCamera(gm);
            SetupHUD(gm);
            ConfigurePipelineShadows();
            SetupRendering();
            BuildRoute();
            BakeNavMesh();

            foreach (var r in envRoot.GetComponentsInChildren<Transform>()) GameObjectUtility.SetStaticEditorFlags(r.gameObject, StaticEditorFlags.BatchingStatic);
            EditorSceneManager.SaveScene(scene, ScenePath);
            var list = new List<EditorBuildSettingsScene> { new EditorBuildSettingsScene(ScenePath, true) };
            EditorBuildSettings.scenes = list.ToArray();
            AssetDatabase.SaveAssets();
            Debug.Log("[DE] Level built: " + ScenePath);
        }

        // ================================================================== layers / assets
        static void EnsureLayers()
        {
            var tm = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = tm.FindProperty("layers");
            string[] want = { "Environment", "Player", "Enemy", "Interactable" };
            for (int i = 0; i < want.Length; i++)
            {
                if (LayerMask.NameToLayer(want[i]) >= 0) continue;
                for (int j = 8; j < 32; j++)
                {
                    var el = layers.GetArrayElementAtIndex(j);
                    if (string.IsNullOrEmpty(el.stringValue)) { el.stringValue = want[i]; break; }
                }
            }
            tm.ApplyModifiedProperties();
            L_Env = LayerMask.NameToLayer("Environment");
            L_Player = LayerMask.NameToLayer("Player");
            L_Enemy = LayerMask.NameToLayer("Enemy");
            L_Interact = LayerMask.NameToLayer("Interactable");
        }

        static Material Mat(string n) { return AssetDatabase.LoadAssetAtPath<Material>("Assets/DungeonEscape/Materials/" + n + ".mat"); }
        static Material FxMat(string n) { return AssetDatabase.LoadAssetAtPath<Material>("Assets/DungeonEscape/Materials/FX/" + n + ".mat"); }

        static void AssignFx(FxLibrary f)
        {
            f.glow = FxMat("FX_Glow"); f.smoke = FxMat("FX_Smoke"); f.dust = FxMat("FX_Dust"); f.flame = FxMat("FX_Flame");
            f.ember = FxMat("FX_Ember"); f.spark = FxMat("FX_Spark"); f.magic = FxMat("FX_Magic"); f.beam = FxMat("FX_Beam");
            f.bone = DEAssets.FxMaterial("FX_Bone", "T_Smoke", false, new Color(0.9f, 0.85f, 0.75f, 1f));
            f.trail = DEAssets.FxMaterial("FX_Trail", null, true, Color.white);
            var orb = Mat("M_HealOrb");
            if (orb == null)
            {
                orb = new Material(DEAssets.LitShader);
                orb.SetColor("_BaseColor", new Color(0.2f, 1f, 0.6f));
                orb.EnableKeyword("_EMISSION");
                orb.SetColor("_EmissionColor", new Color(0.25f, 1f, 0.6f) * 5f);
                AssetDatabase.CreateAsset(orb, "Assets/DungeonEscape/Materials/M_HealOrb.mat");
            }
            f.orb = orb;
        }

        static GameObject Part(GameObject fbx, string name)
        {
            var t = fbx.transform.Find(name);
            if (t == null) { Debug.LogError("[DE] missing part " + name); return new GameObject(name); }
            return t.gameObject;
        }

        static GameObject Place(GameObject fbx, string name, Vector3 pos, float yaw, Transform parent, int layer = -1)
        {
            var go = (GameObject)Object.Instantiate(Part(fbx, name), parent);
            go.name = name;
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            go.layer = layer >= 0 ? layer : L_Env;
            return go;
        }

        static BoxCollider Box(string name, Vector3 center, Vector3 size, Quaternion rot, int layer = -1, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent != null ? parent : colRoot, false);
            go.transform.SetPositionAndRotation(center, rot);
            go.layer = layer >= 0 ? layer : L_Env;
            var bc = go.AddComponent<BoxCollider>();
            bc.size = size;
            return bc;
        }

        static string V(int seed) { return new[] { "A", "B", "C" }[((seed % 3) + 3) % 3]; }

        // ================================================================== layout
        static void R(string n, int x0, int z0, int x1, int z1, int rows, float floorY = 0f, bool floor = true, bool ceiling = true)
        {
            regions.Add(new Region { name = n, x0 = x0, z0 = z0, x1 = x1, z1 = z1, rows = rows, floorY = floorY, floor = floor, ceiling = ceiling });
        }

        static void Connect(string a, string b) { connections.Add(a + "|" + b); connections.Add(b + "|" + a); }

        static void Gate(string a, string b, float cx, float cz, bool alongX, float baseY = 0f)
        {
            var p = new Portal { center = new Vector2(cx, cz), alongX = alongX, baseY = baseY, a = a, b = b };
            portals[a + "|" + b] = p; portals[b + "|" + a] = p;
        }

        static void DefineLayout()
        {
            regions = new List<Region>();
            connections = new HashSet<string>();
            portals = new Dictionary<string, Portal>();
            R("Start", -6, 4, 6, 12, 2);
            R("CellE", 2, 0, 6, 4, 2);
            R("CellW", -6, 0, -2, 4, 2);
            R("CorrA1", -2, 12, 2, 22, 2);
            R("Pit", -2, 22, 2, 24, 2, 0f, false, true);
            R("CorrA2", -2, 24, 2, 36, 2);
            R("Hub", -8, 36, 8, 52, 2);
            R("Font", -12, 42, -8, 46, 2);
            R("CorrB1", 8, 42, 20, 46, 2);
            R("CorrB2", 16, 46, 20, 58, 2);
            R("KeyRoom", 12, 58, 26, 70, 2);
            R("Passage", -2, 52, 2, 56, 2);
            R("Arena", -10, 56, 10, 76, 3);
            R("ExitCorr", -2, 76, 2, 82, 2);
            R("Stairs", -2, 82, 2, 92, 3, 0f, false, false);
            R("Landing", -2, 92, 2, 96, 3, 2.5f, true, false);
            R("Outside", -2, 96, 2, 100, 3, 2.5f, true, false);
            Connect("Start", "CellE"); Connect("Start", "CellW"); Connect("CorrA1", "Pit"); Connect("Pit", "CorrA2");
            Connect("CorrB1", "CorrB2"); Connect("ExitCorr", "Stairs"); Connect("Stairs", "Landing");
            Gate("Start", "CorrA1", 0, 12, true);
            Gate("CorrA2", "Hub", 0, 36, true);
            Gate("Hub", "Font", -8, 44, false);
            Gate("Hub", "CorrB1", 8, 44, false);
            Gate("CorrB2", "KeyRoom", 18, 58, true);
            Gate("Hub", "Passage", 0, 52, true);
            Gate("Passage", "Arena", 0, 56, true);
            Gate("Arena", "ExitCorr", 0, 76, true);
            Gate("Landing", "Outside", 0, 96, true, 2.5f);
            cellRegion = new Dictionary<Vector2Int, int>();
            for (int i = 0; i < regions.Count; i++)
            {
                var r = regions[i];
                for (int x = r.x0 / 2; x < r.x1 / 2; x++)
                    for (int z = r.z0 / 2; z < r.z1 / 2; z++)
                        cellRegion[new Vector2Int(x, z)] = i;
            }
        }

        static Region RegionAt(Vector2Int c)
        {
            int i;
            return cellRegion.TryGetValue(c, out i) ? regions[i] : null;
        }

        // ================================================================== floors, ceilings
        static void BuildFloorsCeilings()
        {
            var floorParent = new GameObject("Floors").transform; floorParent.SetParent(envRoot, false);
            var ceilParent = new GameObject("Ceilings").transform; ceilParent.SetParent(envRoot, false);
            foreach (var kv in cellRegion)
            {
                var r = regions[kv.Value];
                Vector3 c = new Vector3(kv.Key.x * 2 + 1, 0f, kv.Key.y * 2 + 1);
                int h = kv.Key.x * 73856093 ^ kv.Key.y * 19349663;
                if (r.floor) Place(envKit, "Floor_" + V(h), c + Vector3.up * r.floorY, 90f * (rng.Next(4)), floorParent);
                if (r.ceiling) Place(envKit, "Ceil_" + V(h >> 3), c + Vector3.up * (r.rows * 2.5f), 90f * rng.Next(4), ceilParent);
            }
            foreach (var r in regions)
            {
                if (r.floor)
                {
                    float top = r.floorY;
                    float bottom = r.floorY > 0.1f ? 0f : -1f;
                    Box("Floor_" + r.name, new Vector3((r.x0 + r.x1) / 2f, (top + bottom) / 2f, (r.z0 + r.z1) / 2f), new Vector3(r.x1 - r.x0, top - bottom, r.z1 - r.z0), Quaternion.identity);
                }
                if (r.ceiling)
                {
                    float y = r.rows * 2.5f;
                    Box("Ceil_" + r.name, new Vector3((r.x0 + r.x1) / 2f, y + 0.25f, (r.z0 + r.z1) / 2f), new Vector3(r.x1 - r.x0, 0.5f, r.z1 - r.z0), Quaternion.identity);
                }
            }
        }

        // ================================================================== walls
        static readonly Vector2Int[] Dirs = { new Vector2Int(1, 0), new Vector2Int(-1, 0), new Vector2Int(0, 1), new Vector2Int(0, -1) };
        static readonly List<KeyValuePair<Vector2, bool>> wallEdges = new List<KeyValuePair<Vector2, bool>>();
        static readonly Dictionary<Vector2Int, int> vertexRows = new Dictionary<Vector2Int, int>();
        static readonly HashSet<Vector2Int> vertexH = new HashSet<Vector2Int>(), vertexV = new HashSet<Vector2Int>();

        static string WallName(int row, int rows, int seed)
        {
            string kind = row == 0 ? "WallBase_" : (row == rows - 1 ? "WallTop_" : "WallMid_");
            return kind + V(seed + row);
        }

        static void WallStack(Vector3 edgeCenter, Vector3 facing, int rowFrom, int rows, Transform parent, int seed, float colBottom)
        {
            float yaw = Quaternion.LookRotation(facing).eulerAngles.y;
            for (int row = rowFrom; row < rows; row++)
                Place(envKit, WallName(row, rows, seed), edgeCenter + Vector3.up * (row * 2.5f), yaw, parent);
            float top = rows * 2.5f, bottom = rowFrom == 0 ? colBottom : rowFrom * 2.5f;
            Box("Wall", edgeCenter - facing * 0.2f + Vector3.up * ((top + bottom) / 2f), new Vector3(2.02f, top - bottom, 0.6f), Quaternion.LookRotation(facing));
        }

        static void BuildWalls()
        {
            wallEdges.Clear(); vertexRows.Clear(); vertexH.Clear(); vertexV.Clear();
            var parent = new GameObject("Walls").transform; parent.SetParent(envRoot, false);
            foreach (var kv in cellRegion)
            {
                var r = regions[kv.Value];
                foreach (var d in Dirs)
                {
                    var n = kv.Key + d;
                    var rn = RegionAt(n);
                    Vector3 cc = new Vector3(kv.Key.x * 2 + 1, 0f, kv.Key.y * 2 + 1);
                    Vector3 dir = new Vector3(d.x, 0f, d.y);
                    Vector3 edge = cc + dir;
                    int seed = Mathf.Abs((int)(edge.x * 7 + edge.z * 13));
                    int rowFrom = 0;
                    if (rn == r) continue;
                    if (rn != null)
                    {
                        string key = r.name + "|" + rn.name;
                        bool portal = portals.ContainsKey(key);
                        bool open = connections.Contains(key);
                        if (portal || open)
                        {
                            int otherTop = rn.ceiling ? rn.rows : 0;
                            if (portal) otherTop = Mathf.Max(otherTop, 2);
                            if (r.rows > otherTop && rn.ceiling || (portal && r.rows > 2))
                            {
                                rowFrom = portal ? 2 : rn.rows;
                                if (rowFrom >= r.rows) continue;
                            }
                            else continue;
                        }
                    }
                    WallStack(edge, -dir, rowFrom, r.rows, parent, seed, r.name == "Pit" ? -2.2f : -0.5f);
                    if (rowFrom == 0)
                    {
                        // record vertices for corner pillars
                        Vector3 side = new Vector3(Mathf.Abs(d.y), 0f, Mathf.Abs(d.x));
                        Vector3 v0 = edge - side, v1 = edge + side;
                        foreach (var v in new[] { v0, v1 })
                        {
                            var vi = new Vector2Int(Mathf.RoundToInt(v.x), Mathf.RoundToInt(v.z));
                            int cur; vertexRows.TryGetValue(vi, out cur);
                            vertexRows[vi] = Mathf.Max(cur, r.rows);
                            if (d.x != 0) vertexV.Add(vi); else vertexH.Add(vi);
                        }
                    }
                }
            }
        }

        static void BuildPillars()
        {
            var parent = new GameObject("Pillars").transform; parent.SetParent(envRoot, false);
            foreach (var kv in vertexRows)
            {
                if (!vertexH.Contains(kv.Key) || !vertexV.Contains(kv.Key)) continue;
                Vector3 p = new Vector3(kv.Key.x, 0f, kv.Key.y);
                if (archPiers.Any(a => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(p.x, p.z)) < 1.0f)) continue;
                int rows = kv.Value;
                for (int row = 0; row < rows; row++)
                {
                    string n = row == 0 ? "Pillar_Base" : (row == rows - 1 ? "Pillar_Top" : "Pillar_Mid");
                    Place(envKit, n, p + Vector3.up * (row * 2.5f), 90f * ((kv.Key.x + kv.Key.y) & 3), parent);
                }
                Box("Pillar", p + Vector3.up * (rows * 1.25f), new Vector3(0.62f, rows * 2.5f, 0.62f), Quaternion.identity);
            }
        }

        // ================================================================== portals (arches, door, gates)
        static void BuildPortals(GameManager gm)
        {
            var parent = new GameObject("Arches").transform; parent.SetParent(envRoot, false);
            var done = new HashSet<Portal>();
            foreach (var p in portals.Values)
            {
                if (!done.Add(p)) continue;
                Vector3 c = new Vector3(p.center.x, p.baseY, p.center.y);
                float yaw = p.alongX ? 0f : 90f;
                Place(envKit, "Arch_4", c, yaw, parent);
                Vector3 along = p.alongX ? Vector3.right : Vector3.forward;
                Vector3 across = p.alongX ? Vector3.forward : Vector3.right;
                foreach (float s in new[] { -1f, 1f })
                {
                    Vector3 pc = c + along * (s * 2.05f);
                    archPiers.Add(pc);
                    Box("ArchPier", pc + Vector3.up * 1.62f, new Vector3(0.72f, 3.24f, 0.82f), Quaternion.LookRotation(across));
                }
                Box("ArchTop", c + Vector3.up * 4.62f, new Vector3(4.8f, 0.76f, 0.82f), Quaternion.LookRotation(across));
            }
        }

        // ================================================================== special geometry (pit, stairs, platform)
        static void BuildSpecial()
        {
            var parent = new GameObject("Special").transform; parent.SetParent(envRoot, false);
            Place(envKit, "Pit_4x2", new Vector3(0f, 0f, 23f), 0f, parent);
            float th = Mathf.Atan2(1.35f, 2f);
            Vector3 mid = new Vector3(0f, -0.725f, 23f);
            Quaternion rot = Quaternion.Euler(-th * Mathf.Rad2Deg, 0f, 0f);
            Box("PitSlope", mid - rot * Vector3.up * 0.2f, new Vector3(4f, 0.4f, 2.45f), rot);
            Box("PitBottom", new Vector3(0f, -2.0f, 23f), new Vector3(4f, 1f, 2f), Quaternion.identity);

            Place(envKit, "Stairs_12", new Vector3(0f, 0f, 82f), 0f, parent);
            float sth = Mathf.Atan2(2.5f, 10f);
            Quaternion srot = Quaternion.Euler(-sth * Mathf.Rad2Deg, 0f, 0f);
            Vector3 smid = new Vector3(0f, 1.25f, 86.6f);
            Box("StairRamp", smid - srot * Vector3.up * 0.2f, new Vector3(4f, 0.4f, 10.5f), srot);
            Box("Platform", new Vector3(0f, 1.25f, 95.8f), new Vector3(4f, 2.5f, 8.4f), Quaternion.identity);
        }

        // ================================================================== dressing helpers
        const float LightScale = 3f;

        static Light PointLight(string name, Vector3 pos, Color color, float intensity, float range, bool shadows, Transform parent = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent != null ? parent : lightRoot, false);
            go.transform.position = pos;
            var l = go.AddComponent<Light>();
            l.type = LightType.Point; l.color = color; l.intensity = intensity * LightScale; l.range = range * 1.3f;
            l.shadows = shadows ? LightShadows.Soft : LightShadows.None;
            l.shadowNearPlane = 0.2f;
            l.shadowStrength = 0.9f;
            var ad = go.AddComponent<UniversalAdditionalLightData>();
            ad.usePipelineSettings = true;
            if (shadows)
            {
                // Torches and braziers use the medium shadow tier (256 px faces); feature lights keep the high tier.
                bool minor = name == "TorchLight" || name == "BrazierLight";
                var so = new SerializedObject(ad);
                var tier = so.FindProperty("m_AdditionalLightsShadowResolutionTier");
                if (tier != null) { tier.intValue = minor ? 1 : 2; so.ApplyModifiedPropertiesWithoutUndo(); }
            }
            return l;
        }

        static Torch WallTorch(Vector3 wallPoint, Vector3 facing, bool lit, bool shadows, float intensity = 4.5f)
        {
            float yaw = Quaternion.LookRotation(facing).eulerAngles.y;
            var t = Place(props, "TorchSconce", wallPoint, yaw, propRoot);
            var flamePt = new Vector3(0f, 0.37f, 0.28f);
            var ps = Fx.MakeFlame(t.transform, flamePt, 1.0f, fx.flame, fx.ember, fx.smoke);
            var l = PointLight("TorchLight", t.transform.TransformPoint(flamePt + new Vector3(0f, 0.2f, 0.75f)), new Color(1f, 0.6f, 0.28f), intensity, 10f, shadows, t.transform);
            var torch = t.AddComponent<Torch>();
            torch.lightSource = l; torch.flame = ps; torch.baseIntensity = intensity * LightScale; torch.startLit = lit;
            return torch;
        }

        static Torch Brazier(Vector3 pos, bool lit, bool shadows, float intensity = 6f)
        {
            var b = Place(props, "Brazier", pos, rng.Next(360), propRoot);
            var ps = Fx.MakeFlame(b.transform, new Vector3(0f, 1.0f, 0f), 1.5f, fx.flame, fx.ember, fx.smoke);
            var l = PointLight("BrazierLight", pos + Vector3.up * 1.6f, new Color(1f, 0.58f, 0.25f), intensity, 12f, shadows, b.transform);
            var torch = b.AddComponent<Torch>();
            torch.lightSource = l; torch.flame = ps; torch.baseIntensity = intensity * LightScale; torch.startLit = lit;
            var cap = b.AddComponent<CapsuleCollider>(); cap.center = new Vector3(0f, 0.6f, 0f); cap.radius = 0.45f; cap.height = 1.2f;
            return torch;
        }

        static GameObject Prop(string name, Vector3 pos, float yaw, Vector3? box = null, float boxY = -1f)
        {
            var g = Place(props, name, pos, yaw, propRoot);
            if (box.HasValue)
            {
                var bc = g.AddComponent<BoxCollider>();
                bc.size = box.Value;
                bc.center = new Vector3(0f, boxY >= 0 ? boxY : box.Value.y / 2f, 0f);
            }
            return g;
        }

        static Transform Marker(string name, Vector3 pos, float yaw, Transform parent)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            return go.transform;
        }

        static GameObject Trigger(string name, Vector3 center, Vector3 size)
        {
            var go = new GameObject(name);
            go.transform.SetParent(gameRoot, false);
            go.transform.position = center;
            go.layer = 2;
            var bc = go.AddComponent<BoxCollider>();
            bc.isTrigger = true; bc.size = size;
            return go;
        }

        static void Probe(string name, Vector3 center, Vector3 size)
        {
            var go = new GameObject(name);
            go.transform.SetParent(lightRoot, false);
            go.transform.position = center;
            var rp = go.AddComponent<ReflectionProbe>();
            rp.mode = ReflectionProbeMode.Realtime;
            rp.refreshMode = ReflectionProbeRefreshMode.OnAwake;
            rp.timeSlicingMode = ReflectionProbeTimeSlicingMode.NoTimeSlicing;
            rp.resolution = 128;
            rp.size = size;
            rp.boxProjection = true;
            rp.clearFlags = ReflectionProbeClearFlags.SolidColor;
            rp.backgroundColor = new Color(0.02f, 0.02f, 0.025f);
            rp.intensity = 1f;
            rp.shadowDistance = 30f;
        }

        // ================================================================== areas
        static void DressStart(GameManager gm)
        {
            // cell bars and the open cell gate
            foreach (float x in new[] { -5f, -3f, 3f })
            {
                var b = Prop("CellBars_2", new Vector3(x, 0f, 4f), 0f);
                Box("Bars", new Vector3(x, 1.3f, 4f), new Vector3(2f, 2.6f, 0.14f), Quaternion.identity);
            }
            var gate = Prop("CellGate", new Vector3(5.95f, 0f, 4f), 180f + 105f);
            Prop("CellBars_2", new Vector3(5f, 0f, 4f), 0f).transform.localScale = new Vector3(1f, 1f, 1f);
            Object.DestroyImmediate(propRoot.GetChild(propRoot.childCount - 1).gameObject);
            var topBar = Prop("CellBars_2", new Vector3(5f, 2.62f, 4f), 0f);
            topBar.transform.localScale = new Vector3(1f, 0.05f, 1f);
            Box("GateLeaf", new Vector3(5.95f, 1.25f, 4.95f), new Vector3(0.12f, 2.4f, 1.9f), Quaternion.Euler(0f, 15f, 0f));

            // west cell: remains and chains
            var rem = Place(statues, "Skeleton_Remains", new Vector3(-4.3f, 0.25f, 0.75f), 10f, propRoot);
            Prop("Chain_Hanging", new Vector3(-5.2f, 2.6f, 0.15f), 0f);
            Prop("Chain_Hanging", new Vector3(-3.2f, 2.6f, 0.15f), 0f);
            Prop("BonePile", new Vector3(-2.8f, 0f, 2.6f), 40f);
            // player cell
            Prop("Pebbles", new Vector3(4.6f, 0f, 1.0f), 0f);
            Prop("Chain_Hanging", new Vector3(5.6f, 2.4f, 0.15f), 0f);
            Prop("Skull", new Vector3(2.6f, 0f, 0.6f), 120f);
            // guard room
            Prop("Table", new Vector3(-2.4f, 0f, 8.6f), 90f, new Vector3(1.7f, 0.85f, 0.85f));
            var cand = Prop("Candles", new Vector3(-2.4f, 0.81f, 8.9f), 0f);
            PointLight("CandleLight", new Vector3(-2.4f, 1.3f, 8.9f), new Color(1f, 0.7f, 0.4f), 1.6f, 4.5f, false);
            Prop("Barrel", new Vector3(-5.2f, 0f, 11.2f), 10f, new Vector3(0.66f, 0.9f, 0.66f));
            Prop("Barrel", new Vector3(-4.4f, 0f, 11.3f), 70f, new Vector3(0.66f, 0.9f, 0.66f));
            Prop("Crate", new Vector3(5.1f, 0f, 11.1f), 12f, new Vector3(0.8f, 0.8f, 0.8f));
            Prop("Crate_Small", new Vector3(5.2f, 0.8f, 11.1f), 40f);
            Prop("Crate_Small", new Vector3(4.3f, 0f, 11.3f), -15f, new Vector3(0.55f, 0.55f, 0.55f));
            Prop("Urn", new Vector3(5.4f, 0f, 6.2f), 0f);
            Prop("Rubble_B", new Vector3(-5.2f, 0f, 5.2f), 30f);
            Prop("Banner_Red", new Vector3(-5.86f, 4.6f, 8f), 90f);
            WallTorch(new Vector3(-3.2f, 2.4f, 11.86f), Vector3.back, true, true);
            WallTorch(new Vector3(3.2f, 2.4f, 11.86f), Vector3.back, true, true);
            WallTorch(new Vector3(5.86f, 2.2f, 1.7f), Vector3.left, true, true, 3.2f);
            WallTorch(new Vector3(5.86f, 2.4f, 8f), Vector3.left, true, false, 3.5f);
            Probe("Probe_Start", new Vector3(0f, 2.5f, 7f), new Vector3(12f, 5f, 14f));
            // title camera
            gm.titleCameraPoint = Marker("TitleCam", new Vector3(1.1f, 2.0f, 6.9f), 0f, gameRoot);
            gm.titleCameraPoint.LookAt(new Vector3(4.0f, 1.05f, 2.4f));
            var spawn = Marker("PlayerSpawn", new Vector3(4f, 0.02f, 2.2f), 0f, gameRoot);
            gm.titleLight = PointLight("TitleKeyLight", new Vector3(2.7f, 2.3f, 4.7f), new Color(1f, 0.82f, 0.62f), 2.2f, 4.2f, false);
        }

        static void DressCorridorA(GameManager gm)
        {
            WallTorch(new Vector3(1.86f, 2.4f, 16f), Vector3.left, true, true);
            WallTorch(new Vector3(-1.86f, 2.4f, 20.2f), Vector3.right, true, false);
            WallTorch(new Vector3(1.86f, 2.4f, 27f), Vector3.left, true, true);
            WallTorch(new Vector3(-1.86f, 2.4f, 32f), Vector3.right, true, false);
            Prop("Rubble_A", new Vector3(1.4f, 0f, 20.6f), 20f);
            Prop("Rubble_B", new Vector3(-1.3f, 0f, 25.4f), 200f);
            Prop("Pebbles", new Vector3(0.4f, 0f, 21.2f), 0f);
            Prop("Pebbles", new Vector3(-0.6f, 0f, 24.8f), 90f);
            Prop("BonePile", new Vector3(1.1f, 0f, 14f), 110f);
            Prop("Banner_Blue", new Vector3(-1.86f, 4.6f, 28f), 90f);
            Prop("Chain_Hanging", new Vector3(0.8f, 5f, 30f), 0f);
            var st = Trigger("Story_Corridor", new Vector3(0f, 1.5f, 14f), new Vector3(4f, 3f, 2f)).AddComponent<StoryTrigger>();
            st.beat = StoryTrigger.Beat.EnteredCorridor;
            Probe("Probe_CorrA", new Vector3(0f, 2.5f, 24f), new Vector3(4f, 5f, 24f));
        }

        static void DressHub(GameManager gm)
        {
            foreach (var p in new[] { new Vector3(-4f, 0f, 40f), new Vector3(4f, 0f, 40f), new Vector3(-4f, 0f, 48f), new Vector3(4f, 0f, 48f) })
            {
                Place(envKit, "Column_5", p, 0f, envRoot);
                Box("Column", p + Vector3.up * 2.5f, new Vector3(0.9f, 5f, 0.9f), Quaternion.identity);
            }
            foreach (float z in new[] { 40f, 44f, 48f })
                for (int x = -7; x <= 7; x += 2) Place(envKit, "Beam_2", new Vector3(x, 5f, z), 0f, envRoot);
            // the great door
            var door = (GameObject)Object.Instantiate(doorFbx, gameRoot);
            door.name = "GreatDoor";
            door.transform.SetPositionAndRotation(new Vector3(0f, 0f, 52f), Quaternion.Euler(0f, 180f, 0f));
            foreach (var t in door.GetComponentsInChildren<Transform>()) t.gameObject.layer = L_Interact;
            var ld = door.AddComponent<LockedDoor>();
            ld.radius = 3.2f;
            ld.leafA = door.transform.Find("Door_LeafA"); ld.leafB = door.transform.Find("Door_LeafB");
            ld.bar = door.transform.Find("Door_Bar"); ld.padlock = door.transform.Find("Door_Lock");
            AddLeafCollider(ld.leafA, -1f); AddLeafCollider(ld.leafB, 1f);
            var obs = door.AddComponent<NavMeshObstacle>();
            obs.shape = NavMeshObstacleShape.Box; obs.size = new Vector3(3.4f, 4f, 0.6f); obs.center = new Vector3(0f, 2f, 0f); obs.carving = true;
            ld.obstacle = obs;
            var sigil = door.transform.Find("Door_Sigil").gameObject.AddComponent<RuneGlow>();
            sigil.renderers = new[] { sigil.GetComponent<Renderer>() }; sigil.materialPrefix = "M_RuneLock";
            sigil.linkedLight = PointLight("SigilLight", new Vector3(0f, 4.4f, 51.2f), new Color(1f, 0.15f, 0.08f), 2f, 6f, false, door.transform);
            sigil.lightIntensityPerUnit = 1.05f;
            ld.sigil = sigil;
            var lockGlow = ld.padlock.gameObject.AddComponent<RuneGlow>();
            lockGlow.renderers = new[] { lockGlow.GetComponent<Renderer>() }; lockGlow.materialPrefix = "M_RuneLock";
            ld.lockGlow = lockGlow;
            gm.greatDoor = ld;
            // flanking braziers start cold: they ignite as the path back lights up
            var bl = Brazier(new Vector3(-3.3f, 0f, 50.4f), false, true);
            var br = Brazier(new Vector3(3.3f, 0f, 50.4f), false, true);
            Place(statues, "Statue_Knight", new Vector3(-5.7f, 0f, 50.85f), 180f, propRoot).AddComponent<BoxCollider>().size = new Vector3(1.5f, 2.2f, 1.5f);
            Place(statues, "Statue_Knight", new Vector3(5.7f, 0f, 50.85f), 180f, propRoot).AddComponent<BoxCollider>().size = new Vector3(1.5f, 2.2f, 1.5f);
            foreach (var bc in propRoot.GetComponentsInChildren<BoxCollider>()) if (bc.name == "Statue_Knight") bc.center = new Vector3(0f, 1.1f, 0f);
            Prop("Banner_Red", new Vector3(-5.7f, 4.6f, 51.86f), 180f);
            Prop("Banner_Red", new Vector3(5.7f, 4.6f, 51.86f), 180f);
            Prop("Banner_Blue", new Vector3(-7.86f, 4.6f, 39f), 90f);
            Prop("Banner_Blue", new Vector3(7.86f, 4.6f, 39f), -90f);
            // chandelier
            Prop("Chandelier", new Vector3(0f, 5f, 44f), 0f);
            PointLight("ChandelierLight", new Vector3(0f, 3.3f, 44f), new Color(1f, 0.68f, 0.38f), 6f, 13f, true);
            WallTorch(new Vector3(-7.86f, 2.4f, 48.5f), Vector3.right, true, false);
            WallTorch(new Vector3(7.86f, 2.4f, 39.5f), Vector3.left, true, false);
            WallTorch(new Vector3(-2.9f, 2.4f, 36.14f), Vector3.forward, true, false, 3.5f);
            WallTorch(new Vector3(2.9f, 2.4f, 36.14f), Vector3.forward, true, false, 3.5f);
            Prop("Barrel", new Vector3(7.1f, 0f, 37f), 0f, new Vector3(0.66f, 0.9f, 0.66f));
            Prop("Crate", new Vector3(-7f, 0f, 37.1f), 8f, new Vector3(0.8f, 0.8f, 0.8f));
            Prop("Crate_Small", new Vector3(-6.2f, 0f, 37.2f), -20f, new Vector3(0.55f, 0.55f, 0.55f));
            Prop("Urn", new Vector3(7.3f, 0f, 50.9f), 0f);
            Prop("Urn", new Vector3(-7.3f, 0f, 50.9f), 0f);
            Prop("Rubble_A", new Vector3(-6.8f, 0f, 41f), 60f);
            Prop("Pebbles", new Vector3(2.5f, 0f, 43f), 0f);
            // healing font alcove
            var font = Prop("HealingFont", new Vector3(-10.3f, 0f, 44f), 0f);
            var fc = font.AddComponent<CapsuleCollider>(); fc.radius = 0.85f; fc.height = 1f; fc.center = new Vector3(0f, 0.5f, 0f);
            var hf = font.AddComponent<HealingFont>();
            hf.glow = PointLight("FontLight", new Vector3(-10.3f, 1.6f, 44f), new Color(0.3f, 1f, 0.8f), 2.6f, 7f, false, font.transform);
            hf.motes = Fx.MakeMotes(font.transform, new Vector3(0f, 1.5f, 0f), new Vector3(1.6f, 1.2f, 1.6f), new Color(0.4f, 1f, 0.8f, 0.8f), 6f, fx.magic, 0.06f);
            Prop("Candles", new Vector3(-11.4f, 0f, 42.6f), 0f);
            Prop("Candles", new Vector3(-11.4f, 0f, 45.4f), 50f);
            var sd = Trigger("Story_Door", new Vector3(0f, 1.5f, 48.5f), new Vector3(9f, 3f, 5f)).AddComponent<StoryTrigger>();
            sd.beat = StoryTrigger.Beat.SawDoor;
            Probe("Probe_Hub", new Vector3(0f, 2.5f, 44f), new Vector3(16f, 5f, 16f));
            gm.pathTorches.Add(bl); gm.pathTorches.Add(br);
            gm.checkpointPoint = Marker("Checkpoint", new Vector3(0f, 0.02f, 53.6f), 0f, gameRoot);
        }

        static void AddLeafCollider(Transform leaf, float side)
        {
            var go = new GameObject("LeafCollider");
            go.transform.SetParent(leaf, false);
            go.layer = L_Interact;
            var bc = go.AddComponent<BoxCollider>();
            bc.center = new Vector3(side * 0.85f, 1.8f, 0f);
            bc.size = new Vector3(1.7f, 3.6f, 0.2f);
        }

        static void DressCorridorB(GameManager gm)
        {
            WallTorch(new Vector3(11f, 2.4f, 45.86f), Vector3.back, true, false);
            WallTorch(new Vector3(16.14f, 2.4f, 53f), Vector3.right, true, true);
            var p1 = WallTorch(new Vector3(19.86f, 2.4f, 49f), Vector3.left, false, false);
            var p2 = WallTorch(new Vector3(14f, 2.4f, 42.14f), Vector3.forward, false, false);
            gm.pathTorches.Insert(0, p2); gm.pathTorches.Insert(0, p1);
            Prop("Urn", new Vector3(19.3f, 0f, 42.8f), 0f);
            Prop("Urn", new Vector3(18.6f, 0f, 42.6f), 40f);
            Prop("BonePile", new Vector3(17f, 0f, 56.2f), 200f);
            Prop("Rubble_A", new Vector3(9.3f, 0f, 42.7f), 0f);
            Prop("Chain_Hanging", new Vector3(18f, 5f, 47f), 0f);
            Probe("Probe_CorrB", new Vector3(16f, 2.5f, 48f), new Vector3(12f, 5f, 16f));
        }

        static void DressKeyRoom(GameManager gm)
        {
            var ped = Prop("Pedestal", new Vector3(19f, 0f, 65.5f), 0f, new Vector3(1.1f, 1.1f, 1.1f));
            var keyRoot = new GameObject("KeyPickup");
            keyRoot.transform.SetParent(gameRoot, false);
            keyRoot.transform.position = new Vector3(19f, 1.5f, 65.5f);
            keyRoot.layer = 2;
            var visual = Place(props, "Key_Gold", keyRoot.transform.position, 0f, keyRoot.transform, 0);
            visual.transform.localScale = Vector3.one * 1.6f;
            var trig = keyRoot.AddComponent<SphereCollider>(); trig.isTrigger = true; trig.radius = 1.35f;
            var kp = keyRoot.AddComponent<KeyPickup>();
            kp.visual = visual.transform;
            kp.glow = PointLight("KeyLight", new Vector3(19f, 2.2f, 65.5f), new Color(1f, 0.78f, 0.35f), 3.2f, 6.5f, true, keyRoot.transform);
            kp.sparkle = Fx.MakeMotes(keyRoot.transform, Vector3.zero, new Vector3(0.6f, 0.8f, 0.6f), new Color(1f, 0.85f, 0.4f, 1f), 10f, fx.magic, 0.05f);
            gm.keyPickup = kp;
            var beamGo = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Object.DestroyImmediate(beamGo.GetComponent<Collider>());
            beamGo.name = "KeyBeam";
            beamGo.transform.SetParent(keyRoot.transform, false);
            beamGo.transform.position = new Vector3(19f, 2.9f, 65.5f);
            beamGo.transform.localScale = new Vector3(1.4f, 4.2f, 1f);
            beamGo.GetComponent<Renderer>().sharedMaterial = DEAssets.FxMaterial("FX_BeamGold", "T_LightBeam", true, new Color(1f, 0.78f, 0.38f, 0.32f));
            beamGo.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
            beamGo.AddComponent<Billboard>();
            Prop("Sarcophagus", new Vector3(14.6f, 0f, 65f), 0f, new Vector3(1.1f, 1.05f, 2.3f));
            Prop("Sarcophagus", new Vector3(23.4f, 0f, 65f), 0f, new Vector3(1.1f, 1.05f, 2.3f));
            Prop("Banner_Red", new Vector3(16f, 4.6f, 69.86f), 180f);
            Prop("Banner_Red", new Vector3(22f, 4.6f, 69.86f), 180f);
            Prop("Candles", new Vector3(13.2f, 0f, 69.2f), 0f);
            Prop("Candles", new Vector3(24.8f, 0f, 69.2f), 30f);
            Prop("Urn", new Vector3(12.8f, 0f, 58.8f), 0f);
            Prop("Urn", new Vector3(25.2f, 0f, 58.7f), 0f);
            Prop("BonePile", new Vector3(24.4f, 0f, 61f), 70f);
            Prop("Skull", new Vector3(13.6f, 0f, 61.2f), 200f);
            Prop("Rubble_B", new Vector3(25f, 0f, 68.6f), 10f);
            WallTorch(new Vector3(14.2f, 2.4f, 58.14f), Vector3.forward, true, true);
            WallTorch(new Vector3(21.8f, 2.4f, 58.14f), Vector3.forward, true, false);
            WallTorch(new Vector3(12.14f, 2.4f, 66f), Vector3.right, true, false, 3.5f);
            WallTorch(new Vector3(25.86f, 2.4f, 66f), Vector3.left, true, false, 3.5f);
            foreach (float z in new[] { 62f, 66f })
                for (int x = 13; x <= 25; x += 2) Place(envKit, "Beam_2", new Vector3(x, 5f, z), 0f, envRoot);
            gm.keyRoomGuards.Add(SpawnEnemy("Skeleton", new Vector3(17f, 0f, 62.6f), 180f, gameRoot));
            gm.keyRoomGuards.Add(SpawnEnemy("Skeleton", new Vector3(21.4f, 0f, 63.6f), 200f, gameRoot));
            Probe("Probe_Key", new Vector3(19f, 2.5f, 64f), new Vector3(14f, 5f, 12f));
        }

        static void DressArena(GameManager gm)
        {
            var circle = Prop("RuneCircle", new Vector3(0f, 0f, 66f), 0f);
            var runes = circle.AddComponent<RuneGlow>();
            runes.renderers = new[] { circle.GetComponent<Renderer>() }; runes.materialPrefix = "M_Rune";
            runes.linkedLight = PointLight("RuneLight", new Vector3(0f, 1.2f, 66f), new Color(1f, 0.15f, 0.08f), 2f, 16f, true);
            runes.lightIntensityPerUnit = 2.7f;
            foreach (var p in new[] { new Vector3(-6f, 0f, 60f), new Vector3(6f, 0f, 60f), new Vector3(-6f, 0f, 72f), new Vector3(6f, 0f, 72f) })
            {
                Place(envKit, "Column_75", p, 0f, envRoot);
                Box("Column", p + Vector3.up * 3.75f, new Vector3(0.9f, 7.5f, 0.9f), Quaternion.identity);
            }
            foreach (float z in new[] { 60f, 64f, 68f, 72f })
                for (int x = -9; x <= 9; x += 2) Place(envKit, "Beam_2", new Vector3(x, 7.5f, z), 0f, envRoot);
            var braziers = new List<Torch>();
            foreach (var p in new[] { new Vector3(-8.6f, 0f, 60.5f), new Vector3(8.6f, 0f, 60.5f), new Vector3(-8.6f, 0f, 71.5f), new Vector3(8.6f, 0f, 71.5f) })
                braziers.Add(Brazier(p, false, false, 5f));
            WallTorch(new Vector3(-9.86f, 2.6f, 66f), Vector3.right, true, false, 4f);
            WallTorch(new Vector3(9.86f, 2.6f, 66f), Vector3.left, true, false, 4f);
            WallTorch(new Vector3(-3.4f, 2.4f, 56.14f), Vector3.forward, true, true, 4f);
            WallTorch(new Vector3(3.4f, 2.4f, 56.14f), Vector3.forward, true, false, 4f);
            WallTorch(new Vector3(-3.4f, 2.4f, 75.86f), Vector3.back, true, false, 4f);
            WallTorch(new Vector3(3.4f, 2.4f, 75.86f), Vector3.back, true, false, 4f);
            foreach (var p in new[] { new Vector3(-3f, 7.5f, 61f), new Vector3(3f, 7.5f, 61f), new Vector3(-3f, 7.5f, 71f), new Vector3(3f, 7.5f, 71f) })
                Prop("Chain_Hanging", p, rng.Next(90));
            Prop("Banner_Red", new Vector3(-6f, 6.9f, 75.86f), 180f);
            Prop("Banner_Red", new Vector3(6f, 6.9f, 75.86f), 180f);
            Prop("Banner_Blue", new Vector3(-9.86f, 6.9f, 62f), 90f);
            Prop("Banner_Blue", new Vector3(9.86f, 6.9f, 70f), -90f);
            Prop("BonePile", new Vector3(-8.8f, 0f, 74.6f), 30f);
            Prop("BonePile", new Vector3(8.7f, 0f, 57.4f), 150f);
            Prop("Skull", new Vector3(-9.2f, 0f, 57.3f), 60f);
            Prop("Skull", new Vector3(9.1f, 0f, 74.8f), 250f);
            Prop("Rubble_A", new Vector3(-9f, 0f, 68.5f), 0f);
            Prop("Pebbles", new Vector3(7.5f, 0f, 64f), 0f);
            Prop("Sarcophagus", new Vector3(-8.7f, 0f, 66f), 0f, new Vector3(1.1f, 1.05f, 2.3f));
            Prop("Sarcophagus", new Vector3(8.7f, 0f, 66f), 0f, new Vector3(1.1f, 1.05f, 2.3f));

            var entrance = MakeGate("EntranceGate", new Vector3(0f, 0f, 56f), true);
            var exit = MakeGate("ExitGate", new Vector3(0f, 0f, 76f), false);
            var encGo = Trigger("ArenaEncounter", new Vector3(0f, 2f, 67.5f), new Vector3(18f, 4f, 15f));
            var enc = encGo.AddComponent<ArenaEncounter>();
            enc.entranceGate = entrance; enc.exitGate = exit; enc.runes = runes;
            enc.braziers = braziers.ToArray();
            var sps = new List<Transform>();
            var spRoot = new GameObject("SpawnPoints").transform; spRoot.SetParent(encGo.transform, false);
            for (int i = 0; i < 8; i++)
            {
                float a = i * 45f * Mathf.Deg2Rad;
                float r = i % 2 == 0 ? 5.2f : 6.2f;
                sps.Add(Marker("Spawn" + i, new Vector3(Mathf.Sin(a) * r, 0f, 66f + Mathf.Cos(a) * r), 0f, spRoot));
            }
            enc.spawnPoints = sps.ToArray();
            enc.skeletonPrefab = EnemyPrefab("Skeleton");
            enc.wardenPrefab = EnemyPrefab("Warden");
            gm.encounter = enc;
            Probe("Probe_Arena", new Vector3(0f, 3.75f, 66f), new Vector3(20f, 7.5f, 20f));
        }

        static Gate MakeGate(string name, Vector3 pos, bool startOpen)
        {
            var root = new GameObject(name);
            root.transform.SetParent(gameRoot, false);
            root.transform.position = pos;
            root.layer = L_Interact;
            var bars = Place(props, "Gate_Portcullis", pos, 0f, root.transform, L_Interact);
            var bc = bars.AddComponent<BoxCollider>(); bc.center = new Vector3(0f, 2.3f, 0f); bc.size = new Vector3(3.4f, 4.6f, 0.2f);
            var g = root.AddComponent<Gate>();
            g.bars = bars.transform; g.startOpen = startOpen; g.openHeight = 3.9f;
            var obs = root.AddComponent<NavMeshObstacle>();
            obs.shape = NavMeshObstacleShape.Box; obs.size = new Vector3(3.4f, 3f, 0.5f); obs.center = new Vector3(0f, 1.5f, 0f); obs.carving = true;
            obs.enabled = !startOpen;
            g.obstacle = obs;
            return g;
        }

        static void DressExit(GameManager gm)
        {
            WallTorch(new Vector3(-1.86f, 2.4f, 79f), Vector3.right, true, false, 3.5f);
            WallTorch(new Vector3(1.86f, 2.4f, 80.5f), Vector3.left, true, false, 3.5f);
            // sky opening above the open stairwell
            var sky = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Object.DestroyImmediate(sky.GetComponent<Collider>());
            sky.name = "SkyOpening";
            sky.transform.SetParent(envRoot, false);
            sky.transform.SetPositionAndRotation(new Vector3(0f, 9.5f, 91f), Quaternion.Euler(-90f, 0f, 0f));
            sky.transform.localScale = new Vector3(8f, 22f, 1f);
            var skyMat = Mat("M_Sky");
            if (skyMat == null)
            {
                skyMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
                skyMat.SetColor("_BaseColor", new Color(0.62f, 0.78f, 1f) * 2.2f);
                AssetDatabase.CreateAsset(skyMat, "Assets/DungeonEscape/Materials/M_Sky.mat");
            }
            sky.GetComponent<Renderer>().sharedMaterial = skyMat;
            sky.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
            var exitWall = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Object.DestroyImmediate(exitWall.GetComponent<Collider>());
            exitWall.name = "DaylightPortal";
            exitWall.transform.SetParent(envRoot, false);
            exitWall.transform.SetPositionAndRotation(new Vector3(0f, 5f, 99.7f), Quaternion.Euler(0f, 0f, 0f));
            exitWall.transform.localScale = new Vector3(4.2f, 5.2f, 1f);
            var dayMat = Mat("M_Daylight");
            if (dayMat == null)
            {
                dayMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
                dayMat.SetColor("_BaseColor", new Color(1f, 0.96f, 0.86f) * 4.5f);
                AssetDatabase.CreateAsset(dayMat, "Assets/DungeonEscape/Materials/M_Daylight.mat");
            }
            exitWall.GetComponent<Renderer>().sharedMaterial = dayMat;
            exitWall.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
            var spot = new GameObject("DaylightSpot");
            spot.transform.SetParent(lightRoot, false);
            spot.transform.position = new Vector3(0f, 12f, 104f);
            spot.transform.LookAt(new Vector3(0f, 0f, 86f));
            var sl = spot.AddComponent<Light>();
            sl.type = LightType.Spot; sl.color = new Color(1f, 0.93f, 0.82f); sl.intensity = 210f; sl.range = 40f; sl.spotAngle = 60f; sl.innerSpotAngle = 30f;
            sl.shadows = LightShadows.Soft;
            spot.AddComponent<UniversalAdditionalLightData>();
            PointLight("SkyFill", new Vector3(0f, 7f, 87f), new Color(0.6f, 0.75f, 1f), 6f, 14f, false);
            PointLight("PortalGlow", new Vector3(0f, 4f, 98.5f), new Color(1f, 0.95f, 0.85f), 3f, 10f, false);
            for (int i = 0; i < 3; i++)
            {
                var beam = GameObject.CreatePrimitive(PrimitiveType.Quad);
                Object.DestroyImmediate(beam.GetComponent<Collider>());
                beam.name = "GodRay" + i;
                beam.transform.SetParent(fxRoot, false);
                beam.transform.SetPositionAndRotation(new Vector3(-1f + i, 5.5f, 86.5f + i * 2.5f), Quaternion.Euler(28f, 0f, 0f));
                beam.transform.localScale = new Vector3(1.6f, 9f, 1f);
                beam.GetComponent<Renderer>().sharedMaterial = FxMat("FX_Beam");
                beam.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
                beam.AddComponent<Billboard>().axisLocked = true;
            }
            Fx.MakeMotes(fxRoot, new Vector3(0f, 4f, 89f), new Vector3(3.5f, 6f, 12f), new Color(1f, 0.95f, 0.8f, 0.6f), 25f, fx.glow, 0.045f).name = "SunDust";
            Prop("Rubble_B", new Vector3(1.4f, 2.5f, 94.5f), 0f);
            Trigger("ExitZone", new Vector3(0f, 4f, 97.2f), new Vector3(3.6f, 3f, 1.6f)).AddComponent<ExitZone>();
            Probe("Probe_Exit", new Vector3(0f, 3.75f, 88f), new Vector3(4f, 7.5f, 24f));
        }

        // ================================================================== characters
        static readonly Dictionary<string, GameObject> enemyPrefabs = new Dictionary<string, GameObject>();

        static void SetLayerRecursive(GameObject g, int layer) { foreach (var t in g.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = layer; }

        static GameObject EnemyPrefab(string kind)
        {
            GameObject cached;
            if (enemyPrefabs.TryGetValue(kind, out cached) && cached != null) return cached;
            Directory.CreateDirectory("Assets/DungeonEscape/Prefabs");
            string path = "Assets/DungeonEscape/Prefabs/" + kind + ".prefab";
            bool warden = kind == "Warden";
            float scale = warden ? 1.35f : 1f;
            var root = new GameObject(kind);
            var model = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Models + "Characters/" + kind + ".fbx"));
            model.transform.SetParent(root.transform, false);
            model.transform.localScale = Vector3.one * scale;
            var anim = model.GetComponent<Animator>();
            if (anim == null) anim = model.AddComponent<Animator>();
            anim.runtimeAnimatorController = DEAnimators.Get(kind);
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.CullUpdateTransforms;
            SetLayerRecursive(root, L_Enemy);
            var agent = root.AddComponent<NavMeshAgent>();
            agent.radius = warden ? 0.55f : 0.4f; agent.height = 1.9f * scale; agent.speed = warden ? 3.0f : 3.6f;
            agent.angularSpeed = 720f; agent.acceleration = 16f; agent.stoppingDistance = 0.1f; agent.autoBraking = true;
            agent.obstacleAvoidanceType = ObstacleAvoidanceType.HighQualityObstacleAvoidance;
            agent.avoidancePriority = warden ? 30 : 50;
            var cap = root.AddComponent<CapsuleCollider>();
            cap.center = new Vector3(0f, 0.95f * scale, 0f); cap.height = 1.9f * scale; cap.radius = 0.38f * scale;
            var rb = root.AddComponent<Rigidbody>(); rb.isKinematic = true; rb.useGravity = false;
            var h = root.AddComponent<Health>(); h.max = h.current = warden ? 280f : 60f;
            var ai = root.AddComponent<EnemyAI>();
            ai.animator = anim; ai.health = h; ai.bodyRenderer = model.GetComponentInChildren<SkinnedMeshRenderer>();
            ai.sightMask = 1 << L_Env;
            ai.kind = warden ? EnemyAI.Kind.Warden : EnemyAI.Kind.Skeleton;
            ai.displayName = warden ? "The Warden" : "Skeleton";
            ai.isBoss = warden;
            ai.radius = warden ? 0.6f : 0.45f;
            ai.animScale = scale;
            ai.chaseSpeed = warden ? 3.0f : 3.6f;
            ai.attackRange = warden ? 2.5f : 1.8f;
            ai.attackReach = warden ? 3.3f : 2.5f;
            ai.attackArc = warden ? 120f : 100f;
            ai.damage = warden ? 24f : 10f;
            ai.attackHitTime = 0.5f;
            ai.attackDuration = 1.15f;
            ai.attackAnimSpeed = warden ? 0.78f : 1f;
            ai.attackCooldown = warden ? 1.4f : 1.1f;
            ai.attackKnockback = warden ? 6f : 3f;
            ai.heavyAttack = warden;
            ai.hitStun = warden ? 0.5f : 0.42f;
            ai.poise = warden ? 3 : 1;
            ai.orbHeal = warden ? 35f : 14f;
            ai.aggroRange = 13f;
            ai.holdDistance = warden ? 4.5f : 3.8f;
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, path);
            Object.DestroyImmediate(root);
            enemyPrefabs[kind] = prefab;
            return prefab;
        }

        static EnemyAI SpawnEnemy(string kind, Vector3 pos, float yaw, Transform parent)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(EnemyPrefab(kind), parent);
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            // Saved with the agent off: in a player build the NavMeshSurface registers its data in OnEnable,
            // after scene agents would try to attach. EnemyAI.Start switches it on.
            go.GetComponent<NavMeshAgent>().enabled = false;
            return go.GetComponent<EnemyAI>();
        }

        static void SetupPlayerAndCamera(GameManager gm)
        {
            var spawn = gameRoot.Find("PlayerSpawn");
            var player = new GameObject("Player");
            player.transform.SetPositionAndRotation(spawn.position, spawn.rotation);
            var model = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Models + "Characters/Knight.fbx"));
            model.transform.SetParent(player.transform, false);
            var anim = model.GetComponent<Animator>();
            if (anim == null) anim = model.AddComponent<Animator>();
            anim.runtimeAnimatorController = DEAnimators.Get("Knight");
            anim.applyRootMotion = false;
            anim.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            SetLayerRecursive(player, L_Player);
            var cc = player.AddComponent<CharacterController>();
            cc.center = new Vector3(0f, 0.93f, 0f); cc.height = 1.8f; cc.radius = 0.36f; cc.stepOffset = 0.4f; cc.slopeLimit = 50f; cc.skinWidth = 0.04f;
            var h = player.AddComponent<Health>(); h.max = h.current = 100f;
            var pc = player.AddComponent<PlayerController>();
            pc.animator = anim; pc.health = h;
            pc.enemyMask = 1 << L_Enemy;
            pc.groundMask = 1 << L_Env;
            // sword trail anchors (bind pose: blade base and tip from the Blender model)
            var hand = model.GetComponentsInChildren<Transform>().FirstOrDefault(t => t.name == "hand.R");
            if (hand != null)
            {
                var basePt = new GameObject("SwordBase").transform; basePt.SetParent(hand, false);
                basePt.position = model.transform.TransformPoint(new Vector3(0.29f, 0.835f, 0.25f));
                var tipPt = new GameObject("SwordTip").transform; tipPt.SetParent(hand, false);
                tipPt.position = model.transform.TransformPoint(new Vector3(0.29f, 0.835f, 0.99f));
                var trail = player.AddComponent<SwordTrail>();
                trail.basePoint = basePt; trail.tipPoint = tipPt; trail.material = fx.trail;
                pc.swordTrail = trail;
            }
            PointLight("PlayerLantern", player.transform.position + new Vector3(0f, 2.4f, -0.4f), new Color(1f, 0.8f, 0.6f), 0.6f, 5f, false, player.transform);

            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = 58f; cam.nearClipPlane = 0.08f; cam.farClipPlane = 220f;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.012f, 0.012f, 0.018f);
            camGo.AddComponent<AudioListener>();
            var cd = camGo.AddComponent<UniversalAdditionalCameraData>();
            cd.renderPostProcessing = true;
            cd.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            cd.antialiasingQuality = AntialiasingQuality.High;
            var tpc = camGo.AddComponent<ThirdPersonCamera>();
            tpc.target = player.transform;
            tpc.collisionMask = (1 << L_Env) | (1 << L_Interact);
            tpc.titlePoint = gm.titleCameraPoint;
            camGo.transform.SetPositionAndRotation(gm.titleCameraPoint.position, gm.titleCameraPoint.rotation);
        }

        static void SetupHUD(GameManager gm)
        {
            var hudGo = new GameObject("HUD");
            var hud = hudGo.AddComponent<HUD>();
            hud.keyModel = Part(props, "Key_Gold");
            var es = new GameObject("EventSystem", typeof(EventSystem));
            var mod = es.AddComponent<InputSystemUIInputModule>();
            mod.AssignDefaultActions();
        }

        // ================================================================== rendering
        /// <summary>Many torches cast point-light shadows (6 faces each). A bigger atlas with 512px faces
        /// keeps every visible shadowed light at full resolution instead of URP shrinking them each frame.</summary>
        static void ConfigurePipelineShadows()
        {
            var rp = UnityEngine.Rendering.GraphicsSettings.defaultRenderPipeline;
            var assets = new List<UnityEngine.Object>();
            if (rp != null) assets.Add(rp);
            for (int q = 0; q < QualitySettings.names.Length; q++)
            {
                var a = QualitySettings.GetRenderPipelineAssetAt(q);
                if (a != null && !assets.Contains(a)) assets.Add(a);
            }
            foreach (var a in assets)
            {
                var so = new SerializedObject(a);
                var res = so.FindProperty("m_AdditionalLightsShadowmapResolution");
                if (res != null) res.intValue = 4096;
                var hi = so.FindProperty("m_AdditionalLightsShadowResolutionTierHigh");
                if (hi != null) hi.intValue = 512;
                var me = so.FindProperty("m_AdditionalLightsShadowResolutionTierMedium");
                if (me != null) me.intValue = 256;
                var lo = so.FindProperty("m_AdditionalLightsShadowResolutionTierLow");
                if (lo != null) lo.intValue = 128;
                so.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(a);
            }
        }

        static void SetupRendering()
        {
            RenderSettings.skybox = null;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.2f, 0.21f, 0.26f);
            RenderSettings.ambientEquatorColor = new Color(0.14f, 0.125f, 0.11f);
            RenderSettings.ambientGroundColor = new Color(0.07f, 0.06f, 0.055f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogDensity = 0.024f;
            RenderSettings.fogColor = new Color(0.03f, 0.03f, 0.04f);
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
            RenderSettings.reflectionIntensity = 1f;
            var ls = new LightingSettings();
            ls.bakedGI = false; ls.realtimeGI = false;
            Lightmapping.lightingSettings = ls;
            if (!File.Exists("Assets/DungeonEscape/Settings/DE_Lighting.lighting"))
            {
                Directory.CreateDirectory("Assets/DungeonEscape/Settings");
                AssetDatabase.CreateAsset(ls, "Assets/DungeonEscape/Settings/DE_Lighting.lighting");
            }
            else
            {
                var existing = AssetDatabase.LoadAssetAtPath<LightingSettings>("Assets/DungeonEscape/Settings/DE_Lighting.lighting");
                if (existing != null) Lightmapping.lightingSettings = existing;
            }

            string profPath = "Assets/DungeonEscape/Settings/DE_Volume.asset";
            AssetDatabase.DeleteAsset(profPath);
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(profile, profPath);
            T Add<T>() where T : VolumeComponent
            {
                var c = profile.Add<T>(true);
                c.name = typeof(T).Name;
                AssetDatabase.AddObjectToAsset(c, profile);
                return c;
            }
            Add<Tonemapping>().mode.Override(TonemappingMode.ACES);
            var bloom = Add<Bloom>(); bloom.threshold.Override(0.95f); bloom.intensity.Override(0.85f); bloom.scatter.Override(0.68f); bloom.tint.Override(new Color(1f, 0.9f, 0.82f));
            var vig = Add<Vignette>(); vig.intensity.Override(0.33f); vig.smoothness.Override(0.45f);
            var ca = Add<ColorAdjustments>(); ca.postExposure.Override(0.45f); ca.contrast.Override(14f); ca.saturation.Override(-4f);
            var lgg = Add<LiftGammaGain>(); lgg.lift.Override(new Vector4(0.97f, 1f, 1.06f, -0.015f)); lgg.gain.Override(new Vector4(1.03f, 1f, 0.96f, 0f));
            var fg = Add<FilmGrain>(); fg.type.Override(FilmGrainLookup.Thin1); fg.intensity.Override(0.16f); fg.response.Override(0.8f);
            var wb = Add<WhiteBalance>(); wb.temperature.Override(5f);
            var chr = Add<ChromaticAberration>(); chr.intensity.Override(0.06f);
            EditorUtility.SetDirty(profile);
            AssetDatabase.SaveAssets();
            var vgo = new GameObject("PostProcessVolume");
            var vol = vgo.AddComponent<Volume>();
            vol.isGlobal = true; vol.priority = 1f; vol.sharedProfile = profile;
        }

        // ================================================================== autopilot route & navmesh
        static void BuildRoute()
        {
            var root = new GameObject("AutoPilotRoute").transform;
            root.SetParent(gameRoot, false);
            var pts = new List<KeyValuePair<string, Vector3>>
            {
                new KeyValuePair<string, Vector3>("Move", new Vector3(5f, 0f, 5.6f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(0f, 0f, 9.5f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(0f, 0f, 18.5f)),
                new KeyValuePair<string, Vector3>("Jump", new Vector3(0f, 0f, 21.3f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(0f, 0f, 26f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(0f, 0f, 38f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(5.5f, 0f, 44f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(18f, 0f, 44f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(18f, 0f, 57f)),
                new KeyValuePair<string, Vector3>("Key", new Vector3(19f, 0f, 64.4f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(18f, 0f, 56f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(18f, 0f, 44f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(5f, 0f, 44f)),
                new KeyValuePair<string, Vector3>("Door", new Vector3(0f, 0f, 49.6f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(0f, 0f, 54f)),
                new KeyValuePair<string, Vector3>("Arena", new Vector3(0f, 0f, 63f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(0f, 0f, 79f)),
                new KeyValuePair<string, Vector3>("Move", new Vector3(0f, 2.5f, 93.5f)),
                new KeyValuePair<string, Vector3>("Exit", new Vector3(0f, 2.5f, 98.6f)),
            };
            for (int i = 0; i < pts.Count; i++) Marker("AP_" + i.ToString("00") + "_" + pts[i].Key, pts[i].Value, 0f, root);
        }

        static void BakeNavMesh()
        {
            var go = new GameObject("NavMesh");
            var surf = go.AddComponent<NavMeshSurface>();
            surf.collectObjects = CollectObjects.All;
            surf.useGeometry = NavMeshCollectGeometry.PhysicsColliders;
            surf.layerMask = 1 << L_Env;
            surf.agentTypeID = 0;
            surf.BuildNavMesh();
            string path = "Assets/DungeonEscape/Scenes/Dungeon_NavMesh.asset";
            AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(surf.navMeshData, path);
        }
    }
}
