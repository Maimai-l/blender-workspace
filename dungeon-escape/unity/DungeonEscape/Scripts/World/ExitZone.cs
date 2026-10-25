using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    public class ExitZone : MonoBehaviour
    {
        void OnTriggerEnter(Collider other)
        {
            if (other.GetComponentInParent<PlayerController>() == null) return;
            var gm = GameManager.Instance;
            if (gm != null) gm.OnReachedExit();
        }
    }
}
