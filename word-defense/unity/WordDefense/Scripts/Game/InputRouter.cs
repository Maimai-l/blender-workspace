using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;

namespace WordDefense
{
    /// <summary>
    /// Mouse and keyboard. UI (cards, word tags, buttons) is clicked through the EventSystem; clicks that miss the UI are
    /// ray-cast against enemies. Keys: 1–4 shells, Space skill, Esc pause / cancel, right click cancels.
    /// The autopilot uses <see cref="ClickScreen"/> and <see cref="PressKey"/>, which follow the same paths.
    /// </summary>
    public class InputRouter : MonoBehaviour
    {
        public static InputRouter Instance;
        public Enemy Hover { get; private set; }
        public Vector2 PointerPos { get; private set; }
        public bool PointerOverUI { get; private set; }
        public static Enemy TagHover;        // set by word tags under the pointer
        readonly List<RaycastResult> hits = new List<RaycastResult>();

        public enum Key2 { Slot1, Slot2, Slot3, Slot4, Skill, Pause, Cancel }

        void Awake() { Instance = this; }

        void Update()
        {
            var gm = GameManager.Instance;
            if (gm == null) return;
            var mouse = Mouse.current;
            var kb = Keyboard.current;
            if (mouse != null)
            {
                PointerPos = mouse.position.ReadValue();
                PointerOverUI = EventSystem.current != null && EventSystem.current.IsPointerOverGameObject();
                Hover = TagHover != null ? TagHover : (PointerOverUI ? null : RayEnemy(PointerPos));
                if (mouse.leftButton.wasPressedThisFrame && !PointerOverUI) WorldClick(PointerPos);
                if (mouse.rightButton.wasPressedThisFrame) PressKey(Key2.Cancel);
            }
            if (kb != null)
            {
                if (kb.digit1Key.wasPressedThisFrame || kb.numpad1Key.wasPressedThisFrame) PressKey(Key2.Slot1);
                if (kb.digit2Key.wasPressedThisFrame || kb.numpad2Key.wasPressedThisFrame) PressKey(Key2.Slot2);
                if (kb.digit3Key.wasPressedThisFrame || kb.numpad3Key.wasPressedThisFrame) PressKey(Key2.Slot3);
                if (kb.digit4Key.wasPressedThisFrame || kb.numpad4Key.wasPressedThisFrame) PressKey(Key2.Slot4);
                if (kb.spaceKey.wasPressedThisFrame) PressKey(Key2.Skill);
                if (kb.escapeKey.wasPressedThisFrame || kb.pKey.wasPressedThisFrame) PressKey(Key2.Pause);
            }
            if (gm.State == GameState.Playing && gm.SelectedSlot >= 0 && Hover != null && gm.cannon != null)
                gm.cannon.AimAt(Hover.AimPoint, 0.2f);
        }

        public static void PressKey(Key2 k)
        {
            var gm = GameManager.Instance;
            if (gm == null) return;
            switch (k)
            {
                case Key2.Slot1: gm.ActivateSlot(0); break;
                case Key2.Slot2: gm.ActivateSlot(1); break;
                case Key2.Slot3: gm.ActivateSlot(2); break;
                case Key2.Slot4: gm.ActivateSlot(3); break;
                case Key2.Skill: gm.UseSkill(); break;
                case Key2.Pause:
                    if (gm.State == GameState.Playing && gm.SelectedSlot >= 0) gm.Deselect();
                    else gm.TogglePause();
                    break;
                case Key2.Cancel: gm.Deselect(); break;
            }
        }

        public Enemy RayEnemy(Vector2 screen)
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.cam == null) return null;
            var ray = gm.cam.ScreenPointToRay(screen);
            // generous picking: a thick ray so small, fast enemies are easy to click
            var hitsAll = Physics.SphereCastAll(ray, 0.45f, 200f, 1 << GameManager.EnemyLayer, QueryTriggerInteraction.Collide);
            Enemy best = null;
            float bestD = float.MaxValue;
            foreach (var h in hitsAll)
            {
                var e = h.collider.GetComponentInParent<Enemy>();
                if (e == null || !e.Alive) continue;
                if (h.distance < bestD) { bestD = h.distance; best = e; }
            }
            return best;
        }

        public void WorldClick(Vector2 screen)
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.State != GameState.Playing) return;
            var e = RayEnemy(screen);
            if (e != null) gm.ClickEnemy(e);
        }

        /// <summary>Synthetic click (autopilot): UI first, exactly as the EventSystem would route it, otherwise the world.</summary>
        public bool ClickScreen(Vector2 screen)
        {
            var es = EventSystem.current;
            if (es != null)
            {
                var data = new PointerEventData(es) { position = screen, button = PointerEventData.InputButton.Left };
                hits.Clear();
                es.RaycastAll(data, hits);
                foreach (var h in hits)
                {
                    var handler = ExecuteEvents.GetEventHandler<IPointerClickHandler>(h.gameObject);
                    if (handler == null) continue;
                    data.pointerCurrentRaycast = h;
                    data.pointerPress = handler;
                    data.rawPointerPress = h.gameObject;
                    ExecuteEvents.Execute(handler, data, ExecuteEvents.pointerClickHandler);
                    return true;
                }
            }
            WorldClick(screen);
            return false;
        }
    }
}
