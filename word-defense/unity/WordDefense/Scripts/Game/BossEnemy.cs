using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using WordDefense.Data;

namespace WordDefense
{
    /// <summary>The Boss: a long English sentence. Its keywords must be hit in order; each hit breaks a chest plate.</summary>
    public class BossEnemy : Enemy
    {
        public BossSentence Sentence;
        public List<SessionWord> Keywords = new List<SessionWord>();
        public int Current;
        public float LastHitTime = -10f;
        readonly List<Transform> plates = new List<Transform>();

        /// <summary>Correct shells already flying at the Boss; the player may aim at the next keyword meanwhile.</summary>
        public int Pending;
        readonly HashSet<int> landed = new HashSet<int>();

        public SessionWord CurrentWord { get { return Current < Keywords.Count ? Keywords[Current] : null; } }
        public int Effective { get { return Current + Pending; } }
        /// <summary>The keyword the next shell has to match.</summary>
        public SessionWord TargetWord { get { return Effective < Keywords.Count ? Keywords[Effective] : null; } }
        public bool Defeated { get { return Current >= Keywords.Count; } }
        public override bool Targetable { get { return Alive && !Defeated && Effective < Keywords.Count && Time.time - SpawnTime > 1.0f; } }

        public int ReserveHit()
        {
            int k = Effective;
            Pending++;
            Word = TargetWord ?? CurrentWord;
            return k;
        }

        /// <summary>A correct shell for keyword k landed. Keywords break strictly in order, so a fast later shell waits
        /// for the earlier one. Returns how many plates broke.</summary>
        public int LandHit(int k, Vector3 from)
        {
            Pending = Mathf.Max(0, Pending - 1);
            landed.Add(k);
            int broke = 0;
            while (landed.Contains(Current) && !Defeated)
            {
                landed.Remove(Current);
                BreakCurrent(from);
                broke++;
            }
            if (broke == 0) Flash(new Color(1f, 0.85f, 0.4f), 0.6f);
            Word = TargetWord ?? CurrentWord;
            return broke;
        }

        public void SetupBoss(BossSentence s, List<SessionWord> keywords)
        {
            Sentence = s;
            Keywords = keywords;
            Word = CurrentWord;
            for (int i = 0; i < 4; i++)
            {
                var p = PartT("Plate" + i);
                if (p == null) continue;
                if (i < keywords.Count) plates.Add(p);
                else p.gameObject.SetActive(false);
            }
        }

        public int KeywordIndexOf(SessionWord w)
        {
            for (int i = 0; i < Keywords.Count; i++)
                if (Keywords[i] == w || Keywords[i].Core == w.Core) return i;
            return -1;
        }

        public void BreakCurrent(Vector3 from)
        {
            if (Defeated) return;
            if (Current < plates.Count && plates[Current] != null) StartCoroutine(PlateFall(plates[Current]));
            Current++;
            Word = TargetWord ?? CurrentWord;
            LastHitTime = Time.time;
            Flash(new Color(1f, 0.85f, 0.4f), 1.3f);
            Dist = Mathf.Max(0f, Dist - 1.6f);
            Stagger(0.8f);
        }

        IEnumerator PlateFall(Transform p)
        {
            p.SetParent(null, true);
            Vector3 v = (transform.forward * 2.2f + Vector3.up * 3.5f + transform.right * Random.Range(-1.5f, 1.5f));
            Vector3 spin = new Vector3(Random.Range(-400f, 400f), Random.Range(-300f, 300f), Random.Range(-400f, 400f));
            float t = 0f;
            Fx.Sparks(p.position, new Color(1f, 0.8f, 0.35f), 26);
            while (t < 1.4f)
            {
                t += Time.deltaTime;
                v += Vector3.down * 12f * Time.deltaTime;
                p.position += v * Time.deltaTime;
                p.Rotate(spin * Time.deltaTime, Space.Self);
                if (p.position.y < 0.05f) { p.position = new Vector3(p.position.x, 0.05f, p.position.z); v = Vector3.Scale(v, new Vector3(0.4f, -0.3f, 0.4f)); spin *= 0.5f; }
                if (t > 1.0f) p.localScale = Vector3.one * Mathf.Lerp(1f, 0f, (t - 1.0f) / 0.4f);
                yield return null;
            }
            Destroy(p.gameObject);
        }

        /// <summary>Wrong or out-of-order shell: the Boss shrugs it off and lurches forward.</summary>
        public void Enrage()
        {
            Flash(new Color(1f, 0.2f, 0.35f), 1.2f);
            Dist = Mathf.Min(gm.Path.Length - 2f, Dist + 1.4f);
            LastWrongTime = Time.time;
        }

        protected override void Animate(float dt)
        {
            base.Animate(dt);
            float roar = Mathf.Clamp01(1f - (Time.time - LastWrongTime) / 0.6f);
            Pose("Head", Vector3.zero, Quaternion.Euler(-roar * 18f + Mathf.Sin(phase) * 3f, Mathf.Sin(phase * 0.5f) * 5f, 0f));
            Pose("Scroll", new Vector3(0f, Mathf.Sin(phase * 2f) * 0.05f, 0f), Quaternion.Euler(Mathf.Sin(phase) * 2f, 0f, Mathf.Sin(phase * 0.7f) * 2f));
        }

        protected override IEnumerator DieRoutine(Vector3 from)
        {
            Vector3 c = transform.position + Vector3.up * 2.4f;
            float t = 0f;
            while (t < 1.1f)
            {
                t += Time.deltaTime;
                transform.position += Random.insideUnitSphere * 0.04f;
                Flash(new Color(1f, 0.85f, 0.5f), 0.6f + t);
                if (Random.value < 0.25f) Fx.Sparks(c + Random.insideUnitSphere * 1.6f, new Color(1f, 0.4f, 0.75f), 8);
                yield return null;
            }
            Fx.BossExplosion(c);
            float k = 0f;
            Vector3 s0 = transform.localScale;
            while (k < 1f)
            {
                k += Time.deltaTime / 0.3f;
                transform.localScale = Vector3.Lerp(s0, s0 * 0.05f, k);
                yield return null;
            }
            Destroy(gameObject);
        }
    }
}
