using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Scene-referenced effect materials (keeps shader variants in builds).</summary>
    public class FxLibrary : MonoBehaviour
    {
        public static FxLibrary Instance { get; private set; }
        public Material glow;
        public Material smoke;
        public Material dust;
        public Material flame;
        public Material ember;
        public Material spark;
        public Material magic;
        public Material beam;
        public Material trail;
        public Material orb;
        public Material bone;

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }
    }
}
