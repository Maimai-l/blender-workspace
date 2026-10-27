using UnityEngine;
using UnityEngine.EventSystems;

namespace WordDefense
{
    /// <summary>Reports pointer enter / exit to a callback (hover lift on paper).</summary>
    public class PointerHover : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
    {
        public System.Action<bool> changed;
        public void OnPointerEnter(PointerEventData e) { if (changed != null) changed(true); }
        public void OnPointerExit(PointerEventData e) { if (changed != null) changed(false); }
        void OnDisable() { if (changed != null) changed(false); }
    }
}
