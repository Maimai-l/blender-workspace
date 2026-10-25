using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>Glowing orb dropped by enemies. Drifts to the player and heals.</summary>
    public class HealthOrb : MonoBehaviour
    {
        public float heal = 12f;
        float t;
        Vector3 vel;
        static Material s_mat;

        public static void Spawn(Vector3 pos, float amount)
        {
            if (amount <= 0f) return;
            var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = "HealthOrb";
            Destroy(go.GetComponent<Collider>());
            go.transform.position = pos;
            go.transform.localScale = Vector3.one * 0.22f;
            var r = go.GetComponent<Renderer>();
            if (s_mat == null)
            {
                s_mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
                s_mat.SetColor("_BaseColor", new Color(0.2f, 1f, 0.6f));
                s_mat.EnableKeyword("_EMISSION");
                s_mat.SetColor("_EmissionColor", new Color(0.25f, 1f, 0.6f) * 5f);
            }
            r.sharedMaterial = s_mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var l = go.AddComponent<Light>();
            l.type = LightType.Point; l.color = new Color(0.3f, 1f, 0.6f); l.range = 4.5f; l.intensity = 6f; l.shadows = LightShadows.None;
            var orb = go.AddComponent<HealthOrb>();
            orb.heal = amount;
            orb.vel = new Vector3(Random.Range(-1f, 1f), 3.5f, Random.Range(-1f, 1f));
        }

        void Update()
        {
            t += Time.deltaTime;
            var gm = GameManager.Instance;
            var p = gm != null ? gm.Player : null;
            Vector3 pos = transform.position;
            if (t < 0.7f)
            {
                vel += Vector3.down * 9f * Time.deltaTime;
                pos += vel * Time.deltaTime;
                if (pos.y < 0.6f) { pos.y = 0.6f; vel.y = Mathf.Abs(vel.y) * 0.3f; }
            }
            else if (p != null && !p.IsDead)
            {
                Vector3 tgt = p.transform.position + Vector3.up * 1.1f;
                float d = Vector3.Distance(pos, tgt);
                if (d < 7f)
                {
                    float sp = Mathf.Lerp(14f, 3f, d / 7f);
                    pos = Vector3.MoveTowards(pos, tgt, sp * Time.deltaTime);
                    if (d < 0.5f)
                    {
                        p.health.Heal(heal);
                        AudioManager.PlayAt(Sfx.Id.Orb, tgt, 0.7f, Random.Range(0.95f, 1.15f));
                        Fx.Magic(tgt, new Color(0.3f, 1f, 0.6f), 14);
                        Destroy(gameObject);
                        return;
                    }
                }
                else pos.y = 0.6f + Mathf.Sin(t * 3f) * 0.12f;
            }
            transform.position = pos;
            if (t > 40f) Destroy(gameObject);
        }
    }
}
