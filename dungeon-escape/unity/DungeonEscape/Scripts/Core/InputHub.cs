using UnityEngine;
using UnityEngine.InputSystem;

namespace DungeonEscape
{
    public struct PlayerInputState
    {
        public Vector2 move;        // -1..1
        public Vector2 lookDelta;   // mouse pixels this frame
        public Vector2 lookStick;   // gamepad stick -1..1
        public float zoom;
        public bool jump, attack, dodge, interact, pause, confirm;
    }

    public interface IPlayerInputSource
    {
        PlayerInputState Read();
    }

    /// <summary>Single place the game reads input from. The smoke-test autopilot can override it.</summary>
    public static class InputHub
    {
        public static IPlayerInputSource Override;
        static readonly HumanInput human = new HumanInput();
        static int cachedFrame = -1;
        static PlayerInputState cached;

        public static bool UsingGamepad { get { return human.UsingGamepad; } }
        public static string LastPauseSource = "";

        public static PlayerInputState Read()
        {
            if (cachedFrame == Time.frameCount) return cached;
            cachedFrame = Time.frameCount;
            cached = Override != null ? Override.Read() : human.Read();
            LastPauseSource = cached.pause ? "primary" : "";
            if (Override != null)
            {
                // Pause/menu keys still work for a human watching an autopilot run.
                var h = human.Read();
                if (h.pause) LastPauseSource += "+human";
                cached.pause |= h.pause;
            }
            return cached;
        }
    }

    public class HumanInput : IPlayerInputSource
    {
        public bool UsingGamepad;

        public PlayerInputState Read()
        {
            var s = new PlayerInputState();
            var kb = Keyboard.current;
            var mouse = Mouse.current;
            var gp = Gamepad.current;
            if (kb != null)
            {
                Vector2 m = Vector2.zero;
                if (kb.wKey.isPressed || kb.upArrowKey.isPressed) m.y += 1;
                if (kb.sKey.isPressed || kb.downArrowKey.isPressed) m.y -= 1;
                if (kb.dKey.isPressed || kb.rightArrowKey.isPressed) m.x += 1;
                if (kb.aKey.isPressed || kb.leftArrowKey.isPressed) m.x -= 1;
                if (m.sqrMagnitude > 0.01f) { s.move = m.normalized; UsingGamepad = false; }
                s.jump = kb.spaceKey.wasPressedThisFrame;
                s.dodge = kb.leftShiftKey.wasPressedThisFrame || kb.rightShiftKey.wasPressedThisFrame || kb.leftCtrlKey.wasPressedThisFrame;
                s.interact = kb.eKey.wasPressedThisFrame || kb.fKey.wasPressedThisFrame;
                s.pause = kb.escapeKey.wasPressedThisFrame || kb.pKey.wasPressedThisFrame;
                s.confirm = kb.enterKey.wasPressedThisFrame || kb.numpadEnterKey.wasPressedThisFrame || kb.spaceKey.wasPressedThisFrame;
                if (kb.jKey.wasPressedThisFrame) s.attack = true;
            }
            if (mouse != null)
            {
                s.lookDelta = mouse.delta.ReadValue();
                if (mouse.leftButton.wasPressedThisFrame) { s.attack = true; UsingGamepad = false; }
                if (mouse.rightButton.wasPressedThisFrame) s.dodge = true;
                s.zoom = Mathf.Clamp(mouse.scroll.ReadValue().y, -1f, 1f);
            }
            if (gp != null)
            {
                Vector2 ls = gp.leftStick.ReadValue();
                if (ls.magnitude > 0.18f) { s.move = Vector2.ClampMagnitude(ls, 1f); UsingGamepad = true; }
                Vector2 rs = gp.rightStick.ReadValue();
                if (rs.magnitude > 0.15f) { s.lookStick = rs; UsingGamepad = true; }
                if (gp.buttonSouth.wasPressedThisFrame) { s.jump = true; s.confirm = true; UsingGamepad = true; }
                if (gp.buttonWest.wasPressedThisFrame || gp.rightShoulder.wasPressedThisFrame) { s.attack = true; UsingGamepad = true; }
                if (gp.buttonEast.wasPressedThisFrame || gp.leftShoulder.wasPressedThisFrame) { s.dodge = true; UsingGamepad = true; }
                if (gp.buttonNorth.wasPressedThisFrame) { s.interact = true; UsingGamepad = true; }
                if (gp.startButton.wasPressedThisFrame) { s.pause = true; UsingGamepad = true; }
                if (gp.dpad.up.isPressed) s.zoom += 0.05f;
                if (gp.dpad.down.isPressed) s.zoom -= 0.05f;
            }
            return s;
        }
    }
}
