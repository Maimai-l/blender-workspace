using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Orbit camera with wall collision, shake, title/death/victory shots.</summary>
    [DefaultExecutionOrder(50)]
    public class ThirdPersonCamera : MonoBehaviour
    {
        public enum Mode { Title, Gameplay, Death, Victory }

        public Transform target;
        public Vector3 pivotOffset = new Vector3(0f, 1.6f, 0f);
        public float distance = 5.2f;
        public float minDistance = 2.4f;
        public float maxDistance = 7.5f;
        public float mouseSensitivity = 0.11f;
        public float stickSpeed = 170f;
        public float minPitch = -30f;
        public float maxPitch = 68f;
        public LayerMask collisionMask;
        public float collisionRadius = 0.22f;
        public float autoFollowSpeed = 40f;
        public Transform titlePoint;

        public float Yaw { get; private set; }
        public float Pitch { get; private set; }
        public Mode CurrentMode { get { return mode; } }

        Mode mode = Mode.Title;
        float curDist;
        Vector3 pivot, pivotVel;
        float trauma;
        float blend = 1f;
        Vector3 blendFromPos; Quaternion blendFromRot;
        float modeTime;
        Renderer[] targetRenderers;
        bool targetHidden;
        float titleT;
        float lastLookInput = -10f;

        void Start()
        {
            if (target != null)
            {
                Yaw = target.eulerAngles.y;
                pivot = target.position + pivotOffset;
                targetRenderers = target.GetComponentsInChildren<Renderer>();
            }
            Pitch = 16f;
            curDist = distance;
            if (titlePoint != null && mode == Mode.Title)
            {
                transform.SetPositionAndRotation(titlePoint.position, titlePoint.rotation);
            }
        }

        public void BeginGameplay(bool cinematic)
        {
            blendFromPos = transform.position;
            blendFromRot = transform.rotation;
            blend = cinematic ? 0f : 1f;
            mode = Mode.Gameplay;
            modeTime = 0f;
            if (target != null) { Yaw = target.eulerAngles.y; pivot = target.position + pivotOffset; }
        }

        public void SnapBehind(float yaw)
        {
            Yaw = yaw;
            Pitch = 16f;
            if (target != null) pivot = target.position + pivotOffset;
        }

        public void SetDeath() { mode = Mode.Death; modeTime = 0f; }
        public void SetVictory() { mode = Mode.Victory; modeTime = 0f; blendFromPos = transform.position; blendFromRot = transform.rotation; blend = 0f; }

        public void Shake(float amount)
        {
            trauma = Mathf.Clamp01(trauma + amount);
        }

        void LateUpdate()
        {
            float dt = Time.unscaledDeltaTime;
            var gm = GameManager.Instance;
            modeTime += dt;
            if (target == null) return;

            if (mode == Mode.Title)
            {
                titleT += dt;
                if (titlePoint != null)
                {
                    Vector3 drift = titlePoint.right * Mathf.Sin(titleT * 0.18f) * 0.6f + Vector3.up * Mathf.Sin(titleT * 0.27f) * 0.15f;
                    transform.position = titlePoint.position + drift;
                    transform.rotation = titlePoint.rotation * Quaternion.Euler(Mathf.Sin(titleT * 0.21f) * 1.2f, Mathf.Sin(titleT * 0.15f) * 3f, 0f);
                }
                return;
            }

            var player = gm != null ? gm.Player : null;
            if (mode == Mode.Gameplay && player != null && player.IsDead) SetDeath();

            bool acceptInput = gm == null || gm.State == GameState.Playing;
            if (mode == Mode.Gameplay && acceptInput)
            {
                var input = InputHub.Read();
                if (input.lookDelta.sqrMagnitude > 0.5f || input.lookStick.sqrMagnitude > 0.01f) lastLookInput = Time.unscaledTime;
                else if (player != null && Time.unscaledTime - lastLookInput > 1.4f)
                {
                    Vector3 v = player.PlanarVelocity;
                    if (v.magnitude > 2.5f)
                    {
                        float followYaw = Mathf.Atan2(v.x, v.z) * Mathf.Rad2Deg;
                        float diff = Mathf.DeltaAngle(Yaw, followYaw);
                        if (Mathf.Abs(diff) < 115f) Yaw = Mathf.MoveTowardsAngle(Yaw, followYaw, autoFollowSpeed * Mathf.Clamp01(Mathf.Abs(diff) / 45f) * dt);
                    }
                }
                Yaw += input.lookDelta.x * mouseSensitivity + input.lookStick.x * stickSpeed * dt;
                Pitch -= input.lookDelta.y * mouseSensitivity + input.lookStick.y * stickSpeed * 0.7f * dt;
                Pitch = Mathf.Clamp(Pitch, minPitch, maxPitch);
                if (Mathf.Abs(input.zoom) > 0.01f) distance = Mathf.Clamp(distance - input.zoom * 0.6f, minDistance, maxDistance);
            }
            else if (mode == Mode.Death)
            {
                Yaw += 10f * dt;
                Pitch = Mathf.Lerp(Pitch, 38f, dt * 0.8f);
                distance = Mathf.Lerp(distance, 4.2f, dt * 0.8f);
            }

            Vector3 targetPivot = target.position + pivotOffset;
            pivot = Vector3.SmoothDamp(pivot, targetPivot, ref pivotVel, 0.06f, Mathf.Infinity, dt);

            Quaternion rot = Quaternion.Euler(Pitch, Yaw, 0f);
            Vector3 dir = rot * Vector3.back;
            float want = distance;
            RaycastHit hit;
            if (Physics.SphereCast(pivot, collisionRadius, dir, out hit, distance, collisionMask, QueryTriggerInteraction.Ignore))
                want = Mathf.Max(0.5f, hit.distance - 0.08f);
            curDist = want < curDist ? want : Mathf.Lerp(curDist, want, 1f - Mathf.Exp(-4f * dt));
            float squeeze = Mathf.Clamp01(1f - curDist / Mathf.Max(0.01f, distance));
            Vector3 pos = pivot + dir * curDist + Vector3.up * (squeeze * 0.6f);
            Quaternion look = squeeze > 0.01f ? Quaternion.LookRotation(pivot + Vector3.up * 0.15f * squeeze - pos, Vector3.up) : rot;

            if (mode == Mode.Victory)
            {
                Vector3 fwd = target.forward;
                Vector3 vpos = target.position + fwd * 3.4f + Vector3.up * 1.5f + target.right * Mathf.Sin(modeTime * 0.3f) * 0.8f;
                Vector3 lookAt = target.position + Vector3.up * 1.25f;
                Vector3 to = lookAt - vpos;
                RaycastHit vh;
                if (Physics.SphereCast(lookAt, 0.25f, -to.normalized, out vh, to.magnitude, collisionMask, QueryTriggerInteraction.Ignore))
                    vpos = lookAt - to.normalized * Mathf.Max(1.2f, vh.distance - 0.1f);
                pos = vpos;
                look = Quaternion.LookRotation(lookAt - vpos, Vector3.up);
            }

            // shake
            trauma = Mathf.Max(0f, trauma - dt * 1.6f);
            float s = trauma * trauma;
            if (s > 0.0001f)
            {
                float t = Time.unscaledTime * 22f;
                Vector3 off = new Vector3(Mathf.PerlinNoise(t, 1.3f) - 0.5f, Mathf.PerlinNoise(2.1f, t) - 0.5f, 0f) * 0.5f * s;
                pos += look * off;
                look *= Quaternion.Euler((Mathf.PerlinNoise(t, 7.7f) - 0.5f) * 5f * s, (Mathf.PerlinNoise(5.5f, t) - 0.5f) * 5f * s, (Mathf.PerlinNoise(t, 3.3f) - 0.5f) * 4f * s);
            }

            if (blend < 1f)
            {
                blend = Mathf.Min(1f, blend + dt / 1.8f);
                float e = blend * blend * (3f - 2f * blend);
                pos = Vector3.Lerp(blendFromPos, pos, e);
                look = Quaternion.Slerp(blendFromRot, look, e);
            }
            transform.SetPositionAndRotation(pos, look);

            bool hide = mode == Mode.Gameplay && curDist < 0.7f;
            if (hide != targetHidden && targetRenderers != null)
            {
                targetHidden = hide;
                foreach (var r in targetRenderers)
                    if (r != null) r.shadowCastingMode = hide ? UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly : UnityEngine.Rendering.ShadowCastingMode.On;
            }
        }
    }
}
