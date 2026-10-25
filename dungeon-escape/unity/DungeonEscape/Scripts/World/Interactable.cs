using System.Collections.Generic;
using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Something the player can use with the interact button when close enough.</summary>
    public abstract class Interactable : MonoBehaviour
    {
        public static readonly List<Interactable> All = new List<Interactable>();
        public float radius = 2.6f;

        public abstract string Prompt { get; }
        public virtual bool Available { get { return true; } }
        public abstract void Interact(PlayerController player);

        protected virtual void OnEnable() { if (!All.Contains(this)) All.Add(this); }
        protected virtual void OnDisable() { All.Remove(this); }
    }
}
