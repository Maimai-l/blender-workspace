using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Renders the real key model into a small RenderTexture for the HUD.</summary>
    public class KeyIcon : MonoBehaviour
    {
        public RenderTexture Texture { get; private set; }
        Transform model;
        Camera cam;
        public bool spinFast;

        public static KeyIcon Create(GameObject keyModelSource)
        {
            var stage = new GameObject("KeyIconStage");
            stage.transform.position = new Vector3(0f, -300f, 0f);
            var icon = stage.AddComponent<KeyIcon>();
            icon.Texture = new RenderTexture(256, 256, 16, RenderTextureFormat.ARGB32);
            icon.Texture.name = "KeyIconRT";
            var camGo = new GameObject("IconCam");
            camGo.transform.SetParent(stage.transform, false);
            camGo.transform.localPosition = new Vector3(0f, 0f, -1.05f);
            icon.cam = camGo.AddComponent<Camera>();
            icon.cam.clearFlags = CameraClearFlags.SolidColor;
            icon.cam.backgroundColor = new Color(0f, 0f, 0f, 0f);
            icon.cam.fieldOfView = 28f;
            icon.cam.nearClipPlane = 0.1f; icon.cam.farClipPlane = 3f;
            icon.cam.targetTexture = icon.Texture;
            icon.cam.depth = -10;
            var data = camGo.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            data.renderPostProcessing = false;
            data.renderShadows = false;
            var lgo = new GameObject("IconLight");
            lgo.transform.SetParent(stage.transform, false);
            lgo.transform.localPosition = new Vector3(-0.5f, 0.6f, -0.8f);
            var l = lgo.AddComponent<Light>();
            l.type = LightType.Point; l.range = 3f; l.intensity = 6f; l.color = new Color(1f, 0.95f, 0.85f); l.shadows = LightShadows.None;
            var l2go = new GameObject("IconRim");
            l2go.transform.SetParent(stage.transform, false);
            l2go.transform.localPosition = new Vector3(0.7f, -0.2f, 0.6f);
            var l2 = l2go.AddComponent<Light>();
            l2.type = LightType.Point; l2.range = 3f; l2.intensity = 4f; l2.color = new Color(1f, 0.7f, 0.4f); l2.shadows = LightShadows.None;
            if (keyModelSource != null)
            {
                var m = Instantiate(keyModelSource, stage.transform);
                m.name = "IconKey";
                m.transform.localPosition = Vector3.zero;
                m.transform.localRotation = Quaternion.Euler(0f, 0f, 35f);
                m.transform.localScale = Vector3.one * 1.1f;
                foreach (var c in m.GetComponentsInChildren<Collider>()) Destroy(c);
                foreach (var r in m.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                icon.model = m.transform;
            }
            return icon;
        }

        void LateUpdate()
        {
            if (model != null) model.Rotate(0f, (spinFast ? 160f : 40f) * Time.unscaledDeltaTime, 0f, Space.World);
        }

        void OnDestroy()
        {
            if (Texture != null) Texture.Release();
        }
    }
}
