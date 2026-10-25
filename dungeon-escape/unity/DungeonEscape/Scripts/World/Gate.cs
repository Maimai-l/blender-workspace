using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>Portcullis gate that raises/lowers and carves the navmesh while closed.</summary>
    public class Gate : MonoBehaviour
    {
        public Transform bars;
        public float openHeight = 3.9f;
        public bool startOpen;
        public NavMeshObstacle obstacle;
        float cur, target;
        float speed = 1.8f;

        public bool IsOpen { get { return target > 0.5f; } }

        void Awake()
        {
            cur = target = startOpen ? 1f : 0f;
            Apply();
        }

        public void Open(float seconds = 2.2f)
        {
            if (target > 0.5f) return;
            target = 1f; speed = 1f / Mathf.Max(0.05f, seconds);
            AudioManager.PlayAt(Sfx.Id.GateOpen, transform.position + Vector3.up * 2f, 1f, 1f);
            if (obstacle != null) obstacle.enabled = false;
        }

        public void Slam()
        {
            target = 0f; speed = 1f / 0.3f;
            StartCoroutine(SlamFx());
            if (obstacle != null) obstacle.enabled = true;
        }

        IEnumerator SlamFx()
        {
            yield return new WaitForSeconds(0.3f);
            AudioManager.PlayAt(Sfx.Id.GateSlam, transform.position + Vector3.up, 1f, 1f);
            Fx.Dust(transform.position + Vector3.up * 0.1f, 24, 2.2f);
            var gm = GameManager.Instance;
            if (gm != null && gm.Cam != null) gm.Cam.Shake(0.6f);
        }

        void Update()
        {
            if (Mathf.Approximately(cur, target)) return;
            cur = Mathf.MoveTowards(cur, target, speed * Time.deltaTime);
            Apply();
        }

        void Apply()
        {
            if (bars != null)
            {
                float e = cur * cur * (3f - 2f * cur);
                bars.localPosition = new Vector3(0f, e * openHeight, 0f);
            }
            if (obstacle != null && Mathf.Approximately(cur, target)) obstacle.enabled = target < 0.5f;
        }
    }
}
