using UnityEngine;
using UnityEngine.EventSystems;

namespace WordDefense
{
    /// <summary>Lets the input router know which enemy's word tag is under the pointer.</summary>
    public class TagHover : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
    {
        public Enemy enemy;
        public void OnPointerEnter(PointerEventData e) { InputRouter.TagHover = enemy; }
        public void OnPointerExit(PointerEventData e) { if (InputRouter.TagHover == enemy) InputRouter.TagHover = null; }
        void OnDisable() { if (InputRouter.TagHover == enemy) InputRouter.TagHover = null; }
    }
}
