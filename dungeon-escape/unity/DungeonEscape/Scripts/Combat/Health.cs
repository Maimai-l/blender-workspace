using System;
using UnityEngine;

namespace DungeonEscape
{
    public struct DamageInfo
    {
        public float amount;
        public Vector3 sourcePosition;
        public float knockback;
        public bool heavy;
    }

    public class Health : MonoBehaviour
    {
        public float max = 100f;
        public float current = 100f;
        public bool invulnerable;
        public Func<DamageInfo, bool> CanBeDamaged;

        public event Action<DamageInfo> Damaged;
        public event Action<float> Healed;
        public event Action Died;

        public bool IsDead { get { return current <= 0f; } }
        public float Fraction { get { return max > 0 ? Mathf.Clamp01(current / max) : 0f; } }

        public bool TakeDamage(DamageInfo info)
        {
            if (IsDead || invulnerable || info.amount <= 0f) return false;
            if (CanBeDamaged != null && !CanBeDamaged(info)) return false;
            current = Mathf.Max(0f, current - info.amount);
            if (Damaged != null) Damaged(info);
            if (current <= 0f && Died != null) Died();
            return true;
        }

        public void Heal(float amount)
        {
            if (IsDead || amount <= 0f || current >= max) return;
            float before = current;
            current = Mathf.Min(max, current + amount);
            if (Healed != null) Healed(current - before);
        }

        public void ResetFull()
        {
            current = max;
        }
    }
}
