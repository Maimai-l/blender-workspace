using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DungeonEscape.EditorTools
{
    /// <summary>Editor-only helpers to look at models and animation poses.</summary>
    public static class DEPreview
    {
        public static AnimationClip Clip(string model, string clip)
        {
            foreach (var o in AssetDatabase.LoadAllAssetsAtPath("Assets/DungeonEscape/Models/Characters/" + model + ".fbx"))
            {
                var c = o as AnimationClip;
                if (c != null && c.name == clip) return c;
            }
            return null;
        }

        /// <summary>
        /// Opens a clean preview stage and lines up the model sampled at "clip@normalizedTime" entries.
        /// Returns the camera name to screenshot.
        /// </summary>
        public static string Lineup(string model, string spec, float yaw = 180f, float camDist = 4.5f, float camHeight = 1.3f, float spacing = 1.6f, float scale = 1f)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/DungeonEscape/Models/Characters/" + model + ".fbx");
            var entries = spec.Split(';');
            float total = (entries.Length - 1) * spacing;
            for (int i = 0; i < entries.Length; i++)
            {
                var parts = entries[i].Split('@');
                var go = (GameObject)Object.Instantiate(prefab);
                go.name = entries[i];
                go.transform.position = new Vector3(-total / 2 + i * spacing, 0, 0);
                go.transform.rotation = Quaternion.Euler(0, yaw, 0);
                go.transform.localScale = Vector3.one * scale;
                var clip = Clip(model, parts[0]);
                if (clip != null)
                {
                    float t = parts.Length > 1 ? float.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture) : 0f;
                    clip.SampleAnimation(go, t * clip.length);
                }
            }
            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.transform.localScale = new Vector3(4, 1, 2);
            var fm = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            fm.SetColor("_BaseColor", new Color(0.25f, 0.25f, 0.27f));
            floor.GetComponent<Renderer>().sharedMaterial = fm;
            var key = new GameObject("Key").AddComponent<Light>();
            key.type = LightType.Directional; key.intensity = 1.6f; key.color = new Color(1f, 0.93f, 0.85f);
            key.transform.rotation = Quaternion.Euler(35, 150, 0); key.shadows = LightShadows.Soft;
            var fill = new GameObject("Fill").AddComponent<Light>();
            fill.type = LightType.Directional; fill.intensity = 0.5f; fill.color = new Color(0.6f, 0.7f, 1f);
            fill.transform.rotation = Quaternion.Euler(20, -60, 0);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.25f, 0.25f, 0.28f);
            var camGo = new GameObject("PreviewCam");
            var cam = camGo.AddComponent<Camera>();
            camGo.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.1f, 0.1f, 0.12f);
            cam.fieldOfView = 40;
            float dist = Mathf.Max(camDist, total * 1.35f);
            camGo.transform.position = new Vector3(0, camHeight, -dist);
            camGo.transform.LookAt(new Vector3(0, 0.9f * scale, 0));
            return "PreviewCam";
        }
    }
}
