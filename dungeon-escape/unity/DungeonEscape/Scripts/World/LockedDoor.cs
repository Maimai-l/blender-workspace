using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>The great sealed door. Needs the key; plays an unlock sequence and swings open.</summary>
    public class LockedDoor : Interactable
    {
        public Transform leafA, leafB, bar, padlock;
        public float leafAOpen = -100f, leafBOpen = 100f;
        public RuneGlow sigil;
        public RuneGlow lockGlow;
        public NavMeshObstacle obstacle;
        bool opened, opening;
        float lockedMsgTime = -10f;

        public bool IsOpen { get { return opened; } }

        public override string Prompt
        {
            get
            {
                var gm = GameManager.Instance;
                return gm != null && gm.HasKey ? "Unlock the great door" : "Sealed. A key is needed";
            }
        }

        public override bool Available { get { return !opened && !opening; } }

        void Start()
        {
            var gm = GameManager.Instance;
            if (gm != null) gm.KeyCollectedEvent += OnKey;
            if (!opened)
            {
                if (sigil != null) sigil.SetTarget(new Color(1f, 0.12f, 0.06f), 5f, 0.01f);
                if (lockGlow != null) lockGlow.SetTarget(new Color(1f, 0.12f, 0.06f), 4f, 0.01f);
            }
        }

        void OnDestroy()
        {
            var gm = GameManager.Instance;
            if (gm != null) gm.KeyCollectedEvent -= OnKey;
        }

        void OnKey()
        {
            if (opened) return;
            if (sigil != null) { sigil.SetTarget(new Color(1f, 0.72f, 0.2f), 7f, 1.5f); sigil.pulse = 0.35f; sigil.pulseSpeed = 4f; }
            if (lockGlow != null) lockGlow.SetTarget(new Color(1f, 0.72f, 0.2f), 6f, 1.5f);
        }

        public override void Interact(PlayerController player)
        {
            var gm = GameManager.Instance;
            if (opened || opening) return;
            if (gm == null || !gm.HasKey)
            {
                AudioManager.PlayAt(Sfx.Id.Locked, transform.position + Vector3.up * 1.8f, 0.9f, 1f);
                if (Time.time - lockedMsgTime > 2f) { lockedMsgTime = Time.time; if (gm != null) gm.ShowToast("LOCKED", "The great door is sealed. Find the key."); }
                if (gm != null) gm.OnSawDoor();
                return;
            }
            StartCoroutine(OpenSequence());
        }

        IEnumerator OpenSequence()
        {
            opening = true;
            AudioManager.PlayAt(Sfx.Id.Unlock, padlock != null ? padlock.position : transform.position, 1f, 1f);
            if (lockGlow != null) lockGlow.SetTarget(new Color(1f, 0.95f, 0.8f), 9f, 0.2f);
            yield return new WaitForSeconds(0.35f);
            // padlock drops
            if (padlock != null)
            {
                Vector3 p0 = padlock.localPosition; Quaternion r0 = padlock.localRotation;
                float t = 0f;
                while (t < 1f)
                {
                    t += Time.deltaTime / 0.45f;
                    padlock.localPosition = p0 + new Vector3(0f, -1.75f * t * t, 0.12f * t);
                    padlock.localRotation = r0 * Quaternion.Euler(60f * t, 0f, 25f * t);
                    yield return null;
                }
                AudioManager.PlayAt(Sfx.Id.Land, padlock.position, 0.7f, 1.6f);
            }
            // bar lifts away
            if (bar != null)
            {
                Vector3 b0 = bar.localPosition;
                float t = 0f;
                while (t < 1f)
                {
                    t += Time.deltaTime / 0.5f;
                    bar.localPosition = b0 + new Vector3(0f, 0.5f * t, 0.25f * t);
                    yield return null;
                }
                bar.gameObject.SetActive(false);
            }
            var gm = GameManager.Instance;
            if (gm != null) gm.ShowToast("THE SEAL IS BROKEN", "The great door groans open");
            AudioManager.PlayAt(Sfx.Id.DoorOpen, transform.position + Vector3.up * 2f, 1f, 1f);
            if (sigil != null) { sigil.SetTarget(new Color(0.6f, 0.85f, 1f), 3f, 2f); sigil.pulse = 0.08f; }
            if (obstacle != null) obstacle.enabled = false;
            if (gm != null && gm.Cam != null) gm.Cam.Shake(0.25f);
            Quaternion a0 = leafA != null ? leafA.localRotation : Quaternion.identity;
            Quaternion bq0 = leafB != null ? leafB.localRotation : Quaternion.identity;
            float tt = 0f;
            while (tt < 1f)
            {
                tt += Time.deltaTime / 2.0f;
                float e = 1f - Mathf.Pow(1f - Mathf.Clamp01(tt), 3f);
                if (leafA != null) leafA.localRotation = a0 * Quaternion.Euler(0f, leafAOpen * e, 0f);
                if (leafB != null) leafB.localRotation = bq0 * Quaternion.Euler(0f, leafBOpen * e, 0f);
                yield return null;
            }
            opened = true; opening = false;
            if (padlock != null) padlock.gameObject.SetActive(false);
            if (gm != null) gm.OnDoorOpened();
        }

        public void OpenInstant()
        {
            opened = true;
            if (leafA != null) leafA.localRotation = leafA.localRotation * Quaternion.Euler(0f, leafAOpen, 0f);
            if (leafB != null) leafB.localRotation = leafB.localRotation * Quaternion.Euler(0f, leafBOpen, 0f);
            if (bar != null) bar.gameObject.SetActive(false);
            if (padlock != null) padlock.gameObject.SetActive(false);
            if (obstacle != null) obstacle.enabled = false;
            if (sigil != null) { sigil.SetTarget(new Color(0.6f, 0.85f, 1f), 3f, 0.01f); sigil.pulse = 0.08f; }
        }
    }
}
