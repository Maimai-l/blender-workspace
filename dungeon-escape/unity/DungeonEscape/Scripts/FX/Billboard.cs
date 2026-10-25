using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Turns a quad toward the camera. Axis-locked mode keeps its tilt and only yaws (light shafts).</summary>
    public class Billboard : MonoBehaviour
    {
        public bool axisLocked = true;
        float pitch;
        bool init;

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            if (!init) { init = true; pitch = transform.eulerAngles.x; }
            if (axisLocked)
            {
                Vector3 to = transform.position - cam.transform.position; to.y = 0f;
                if (to.sqrMagnitude < 0.0001f) return;
                float yaw = Mathf.Atan2(to.x, to.z) * Mathf.Rad2Deg;
                transform.rotation = Quaternion.Euler(pitch, yaw, 0f);
            }
            else
            {
                transform.rotation = Quaternion.LookRotation(cam.transform.forward, Vector3.up);
            }
        }
    }
}
