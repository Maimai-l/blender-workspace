using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    /// <summary>Generic one-shot trigger that reports story beats to the GameManager.</summary>
    public class StoryTrigger : MonoBehaviour
    {
        public enum Beat { EnteredCorridor, SawDoor, Checkpoint }
        public Beat beat;
        bool fired;

        void OnTriggerEnter(Collider other)
        {
            if (fired || other.GetComponentInParent<PlayerController>() == null) return;
            var gm = GameManager.Instance;
            if (gm == null) return;
            fired = true;
            switch (beat)
            {
                case Beat.EnteredCorridor: gm.OnEnteredCorridor(); break;
                case Beat.SawDoor: gm.OnSawDoor(); break;
            }
        }
    }
}
