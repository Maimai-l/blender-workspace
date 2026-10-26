using UnityEngine;

namespace WordDefense
{
    /// <summary>Gentle scale-up on hover for buttons.</summary>
    public class HoverScale : MonoBehaviour, UnityEngine.EventSystems.IPointerEnterHandler, UnityEngine.EventSystems.IPointerExitHandler
    {
        public float amount = 1.04f;
        bool over;
        float s = 1f;
        public void OnPointerEnter(UnityEngine.EventSystems.PointerEventData e) { over = true; }
        public void OnPointerExit(UnityEngine.EventSystems.PointerEventData e) { over = false; }
        void Update()
        {
            s = UIKit.Smooth(s, over ? amount : 1f, 18f, UIKit.Dt);
            transform.localScale = Vector3.one * s;
        }
    }
}
