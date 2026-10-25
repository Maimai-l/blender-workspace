using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Scriptable input for edge-case tests driven from editor commands.</summary>
    public class ManualInput : IPlayerInputSource
    {
        public static ManualInput Instance;
        public Vector2 move;
        public bool jump, attack, dodge, interact, pause;

        public static ManualInput Enable()
        {
            Instance = new ManualInput();
            InputHub.Override = Instance;
            return Instance;
        }

        public static void Disable()
        {
            if (InputHub.Override == Instance) InputHub.Override = null;
            Instance = null;
        }

        public PlayerInputState Read()
        {
            var s = new PlayerInputState { move = move, jump = jump, attack = attack, dodge = dodge, interact = interact, pause = pause };
            jump = attack = dodge = interact = pause = false;
            return s;
        }
    }
}
