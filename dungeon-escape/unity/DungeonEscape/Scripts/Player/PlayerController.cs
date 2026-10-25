using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace DungeonEscape
{
    /// <summary>Third-person knight: camera-relative movement, jump, dodge roll, 3-hit combo, interaction, damage reactions.</summary>
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour
    {
        [Header("References")]
        public Animator animator;
        public Health health;
        public SwordTrail swordTrail;
        public LayerMask enemyMask;
        public LayerMask groundMask;

        [Header("Movement")]
        public float runSpeed = 6.2f;
        public float acceleration = 42f;
        public float deceleration = 60f;
        public float airControl = 0.55f;
        public float turnSpeed = 900f;
        public float gravity = 25f;
        public float fallMultiplier = 1.4f;
        public float jumpHeight = 1.3f;
        public float coyoteTime = 0.13f;
        public float jumpBuffer = 0.16f;

        [Header("Dodge")]
        public float dodgeDistance = 4.8f;
        public float dodgeDuration = 0.55f;
        public float dodgeCooldown = 0.2f;
        public Vector2 iFrames = new Vector2(0.02f, 0.42f);

        struct AttackDef
        {
            public string state; public float duration, hitTime, damage, range, arc, lunge, lungeTime, comboOpen, cancelTime, knockback, shake; public bool heavy;
        }

        static readonly AttackDef[] Attacks =
        {
            new AttackDef { state = "Attack1", duration = 0.62f, hitTime = 0.21f, damage = 24f, range = 2.5f, arc = 140f, lunge = 0.9f, lungeTime = 0.18f, comboOpen = 0.1f, cancelTime = 0.36f, knockback = 2.5f, shake = 0.22f },
            new AttackDef { state = "Attack2", duration = 0.62f, hitTime = 0.21f, damage = 24f, range = 2.5f, arc = 140f, lunge = 0.9f, lungeTime = 0.18f, comboOpen = 0.1f, cancelTime = 0.36f, knockback = 2.5f, shake = 0.22f },
            new AttackDef { state = "Attack3", duration = 0.86f, hitTime = 0.36f, damage = 42f, range = 2.9f, arc = 160f, lunge = 1.2f, lungeTime = 0.3f, comboOpen = 0.2f, cancelTime = 0.64f, knockback = 5.5f, shake = 0.55f, heavy = true },
        };

        enum Act { None, Attack, Dodge, Interact, Hit, Land, Dead, Victory }

        CharacterController controller;
        Act act;
        float actTime;
        Vector3 hv;                 // planar velocity
        float vy;
        bool grounded, wasGrounded;
        float airTime, peakFall;
        float coyoteTimer, jumpBufferTimer, attackBufferTimer, dodgeBufferTimer;
        bool jumpedThisAir;
        int attackIndex;
        bool attackQueued, attackHitDone;
        float lastAttackEnd = -10f;
        AttackDef curAttack;
        Vector3 dodgeDir;
        float nextDodgeTime;
        Vector3 knockVel;
        float invulnUntil;
        Interactable interactTarget;
        bool interactDone;
        string curState;
        float stepAccum;
        Vector3 lastSafePos;
        float nextSafeSample;
        float inputBlockedUntil;
        readonly HashSet<EnemyAI> hitThisSwing = new HashSet<EnemyAI>();

        public Interactable CurrentInteractable { get; private set; }
        public bool IsDead { get { return act == Act.Dead; } }
        public bool IsDodging { get { return act == Act.Dodge; } }
        public bool IsAttacking { get { return act == Act.Attack; } }
        public bool IsGrounded { get { return grounded; } }
        public Vector3 PlanarVelocity { get { return hv; } }

        void Awake()
        {
            controller = GetComponent<CharacterController>();
            if (health == null) health = GetComponent<Health>();
            if (animator == null) animator = GetComponentInChildren<Animator>();
            lastSafePos = transform.position;
        }

        void OnEnable()
        {
            health.Damaged += OnDamaged;
            health.Died += OnDied;
            health.CanBeDamaged = CanBeDamaged;
        }

        void OnDisable()
        {
            health.Damaged -= OnDamaged;
            health.Died -= OnDied;
            health.CanBeDamaged = null;
        }

        void Start()
        {
            PlayState("Locomotion", 0f, true);
            inputBlockedUntil = Time.time + 0.25f;
        }

        public void Teleport(Vector3 pos, Quaternion rot)
        {
            controller.enabled = false;
            transform.SetPositionAndRotation(pos, rot);
            controller.enabled = true;
            hv = Vector3.zero; vy = 0f;
            lastSafePos = pos;
        }

        public void Celebrate()
        {
            act = Act.Victory; actTime = 0f;
            hv = Vector3.zero;
            if (swordTrail != null) swordTrail.Emit(false);
            PlayState("Victory", 0.2f, true);
        }

        public void BlockInput(float seconds)
        {
            inputBlockedUntil = Time.time + seconds;
        }

        bool CanBeDamaged(DamageInfo info)
        {
            var gm = GameManager.Instance;
            if (gm != null && gm.State != GameState.Playing) return false;
            if (act == Act.Dead || act == Act.Victory) return false;
            if (act == Act.Dodge && actTime >= iFrames.x && actTime <= iFrames.y) return false;
            return Time.time >= invulnUntil;
        }

        void OnDamaged(DamageInfo info)
        {
            var gm = GameManager.Instance;
            if (gm != null) gm.DamageTaken += info.amount;
            Vector3 away = transform.position - info.sourcePosition; away.y = 0f;
            if (away.sqrMagnitude < 0.001f) away = -transform.forward;
            away.Normalize();
            AudioManager.PlayAt(Sfx.Id.PlayerHurt, transform.position + Vector3.up, 0.9f, Random.Range(0.92f, 1.06f));
            Fx.HitSpark(transform.position + Vector3.up * 1.2f + away * 0.2f, new Color(1f, 0.25f, 0.15f), 14);
            if (gm != null && gm.Cam != null) gm.Cam.Shake(info.heavy ? 0.75f : 0.45f);
            invulnUntil = Time.time + 0.5f;
            if (health.IsDead) return;
            bool armored = act == Act.Attack && curAttack.heavy && actTime < curAttack.hitTime + 0.05f;
            if (!armored)
            {
                EndAttackFx();
                act = Act.Hit; actTime = 0f;
                knockVel = away * Mathf.Max(2.5f, info.knockback);
                PlayState("Hit", 0.04f, true);
            }
        }

        void OnDied()
        {
            EndAttackFx();
            act = Act.Dead; actTime = 0f;
            PlayState("Death", 0.08f, true);
            var gm = GameManager.Instance;
            if (gm != null) gm.OnPlayerDied();
        }

        void Update()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;
            var gm = GameManager.Instance;
            bool playing = gm == null || gm.State == GameState.Playing;
            PlayerInputState input = default(PlayerInputState);
            if (playing && Time.time >= inputBlockedUntil && act != Act.Dead && act != Act.Victory) input = InputHub.Read();

            Vector3 camF = Vector3.forward, camR = Vector3.right;
            Transform cam = (gm != null && gm.Cam != null) ? gm.Cam.transform : (Camera.main != null ? Camera.main.transform : null);
            if (cam != null)
            {
                camF = cam.forward; camF.y = 0f; camF.Normalize();
                camR = cam.right; camR.y = 0f; camR.Normalize();
            }
            Vector3 wish = camF * input.move.y + camR * input.move.x;
            float wishMag = Mathf.Clamp01(wish.magnitude);
            if (wishMag > 0.001f) wish /= wish.magnitude;

            if (input.jump) jumpBufferTimer = jumpBuffer; else jumpBufferTimer -= dt;
            if (input.attack) attackBufferTimer = 0.28f; else attackBufferTimer -= dt;
            if (input.dodge) dodgeBufferTimer = 0.2f; else dodgeBufferTimer -= dt;
            if (grounded) coyoteTimer = coyoteTime; else coyoteTimer -= dt;

            actTime += dt;
            Vector3 extra = Vector3.zero;

            // ---------------------------------------------------- action state machine
            switch (act)
            {
                case Act.None:
                case Act.Land:
                    if (act == Act.Land && actTime > 0.22f) { act = Act.None; }
                    {
                        float accelMul = grounded ? 1f : airControl;
                        float landSlow = act == Act.Land ? 0.35f : 1f;
                        Vector3 target = wish * (runSpeed * wishMag * landSlow);
                        float rate = (target.sqrMagnitude > hv.sqrMagnitude ? acceleration : deceleration) * accelMul;
                        hv = Vector3.MoveTowards(hv, target, rate * dt);
                        if (wishMag > 0.1f) Face(wish, turnSpeed * (grounded ? 1f : 0.6f), dt);
                    }
                    if (playing && dodgeBufferTimer > 0f && grounded && Time.time >= nextDodgeTime) { StartDodge(wishMag > 0.1f ? wish : transform.forward); break; }
                    if (playing && attackBufferTimer > 0f && grounded) { StartAttack(0, wishMag > 0.1f ? wish : Vector3.zero); break; }
                    if (playing && jumpBufferTimer > 0f && coyoteTimer > 0f) { DoJump(); }
                    if (playing && input.interact && CurrentInteractable != null) { StartInteract(CurrentInteractable); }
                    break;

                case Act.Attack:
                    hv = Vector3.MoveTowards(hv, Vector3.zero, deceleration * dt);
                    if (actTime < curAttack.lungeTime)
                    {
                        float k = 1f - (actTime / curAttack.lungeTime);
                        extra += transform.forward * (curAttack.lunge / curAttack.lungeTime) * 2f * k * dt;
                    }
                    if (actTime < curAttack.hitTime && wishMag > 0.1f) Face(wish, 300f, dt);
                    if (!attackHitDone && actTime >= curAttack.hitTime) { attackHitDone = true; DoAttackHit(); }
                    if (swordTrail != null && actTime > curAttack.hitTime + 0.12f) swordTrail.Emit(false);
                    if (attackBufferTimer > 0f && actTime >= curAttack.comboOpen && attackIndex < Attacks.Length - 1) { attackQueued = true; attackBufferTimer = 0f; }
                    if (attackQueued && actTime >= curAttack.cancelTime) { StartAttack(attackIndex + 1, wishMag > 0.1f ? wish : Vector3.zero); break; }
                    if (dodgeBufferTimer > 0f && actTime > curAttack.hitTime + 0.06f && Time.time >= nextDodgeTime) { EndAttackFx(); StartDodge(wishMag > 0.1f ? wish : transform.forward); break; }
                    if (actTime >= curAttack.duration) { act = Act.None; lastAttackEnd = Time.time; EndAttackFx(); }
                    break;

                case Act.Dodge:
                    {
                        float x = Mathf.Clamp01(actTime / dodgeDuration);
                        float peak = 1.5f * dodgeDistance / dodgeDuration;
                        hv = dodgeDir * (peak * (1f - x * x));
                        if (actTime >= dodgeDuration) { act = Act.None; nextDodgeTime = Time.time + dodgeCooldown; hv = dodgeDir * 1.5f; }
                    }
                    break;

                case Act.Interact:
                    hv = Vector3.MoveTowards(hv, Vector3.zero, deceleration * dt);
                    if (interactTarget != null)
                    {
                        Vector3 to = interactTarget.transform.position - transform.position; to.y = 0f;
                        if (to.sqrMagnitude > 0.01f) Face(to.normalized, 540f, dt);
                    }
                    if (!interactDone && actTime >= 0.35f)
                    {
                        interactDone = true;
                        if (interactTarget != null) interactTarget.Interact(this);
                    }
                    if (actTime >= 0.75f) act = Act.None;
                    break;

                case Act.Hit:
                    hv = knockVel;
                    knockVel = Vector3.MoveTowards(knockVel, Vector3.zero, 18f * dt);
                    if (actTime >= 0.38f) act = Act.None;
                    break;

                case Act.Dead:
                case Act.Victory:
                    hv = Vector3.MoveTowards(hv, Vector3.zero, deceleration * dt);
                    break;
            }

            // ---------------------------------------------------- gravity & move
            if (grounded && vy < 0f) vy = -2f;
            vy -= gravity * (vy < 0f ? fallMultiplier : 1f) * dt;
            vy = Mathf.Max(vy, -30f);
            Vector3 motion = (hv + Vector3.up * vy) * dt + extra;
            wasGrounded = grounded;
            CollisionFlags flags = controller.Move(motion);
            grounded = controller.isGrounded;
            if ((flags & CollisionFlags.Above) != 0 && vy > 0f) vy = 0f;

            if (!grounded)
            {
                airTime += dt;
                if (vy < 0f) peakFall = Mathf.Max(peakFall, -vy);
            }
            else if (!wasGrounded)
            {
                OnLanded();
            }
            if (grounded) { airTime = 0f; }

            UpdateInteractTarget();
            UpdateAnimation(dt);
            Footsteps(dt);
            SafetyNet();
        }

        void Face(Vector3 dir, float degPerSec, float dt)
        {
            dir.y = 0f;
            if (dir.sqrMagnitude < 0.0001f) return;
            Quaternion target = Quaternion.LookRotation(dir.normalized, Vector3.up);
            transform.rotation = Quaternion.RotateTowards(transform.rotation, target, degPerSec * dt);
        }

        void DoJump()
        {
            vy = Mathf.Sqrt(2f * gravity * jumpHeight);
            coyoteTimer = 0f; jumpBufferTimer = 0f;
            grounded = false;
            jumpedThisAir = true;
            airTime = 0.001f;
            peakFall = 0f;
            PlayState("JumpUp", 0.06f, true);
            AudioManager.PlayAt(Sfx.Id.Jump, transform.position, 0.5f, Random.Range(0.95f, 1.08f));
        }

        void OnLanded()
        {
            bool hard = peakFall > 9f;
            if (airTime > 0.12f)
            {
                AudioManager.PlayAt(Sfx.Id.Land, transform.position, hard ? 0.8f : 0.45f, hard ? 0.85f : 1.05f);
                if (hard) Fx.Dust(transform.position + Vector3.up * 0.05f, 10, 1.2f);
            }
            if (hard && act == Act.None)
            {
                act = Act.Land; actTime = 0f;
                PlayState("Land", 0.05f, true);
            }
            jumpedThisAir = false;
            peakFall = 0f;
        }

        void StartDodge(Vector3 dir)
        {
            dodgeBufferTimer = 0f; attackBufferTimer = 0f;
            act = Act.Dodge; actTime = 0f;
            dodgeDir = dir; dodgeDir.y = 0f; dodgeDir.Normalize();
            transform.rotation = Quaternion.LookRotation(dodgeDir, Vector3.up);
            PlayState("Dodge", 0.05f, true);
            AudioManager.PlayAt(Sfx.Id.Dodge, transform.position, 0.6f, Random.Range(0.95f, 1.05f));
            Fx.Dust(transform.position + Vector3.up * 0.05f, 6, 0.8f);
        }

        void StartAttack(int index, Vector3 wish)
        {
            attackBufferTimer = 0f;
            if (index == 0 && Time.time - lastAttackEnd > 0.6f) attackIndex = 0;
            attackIndex = index;
            curAttack = Attacks[attackIndex];
            act = Act.Attack; actTime = 0f;
            attackQueued = false; attackHitDone = false;
            hitThisSwing.Clear();
            Vector3 aim = AimAssist(wish.sqrMagnitude > 0.01f ? wish : transform.forward);
            if (aim.sqrMagnitude > 0.01f) transform.rotation = Quaternion.LookRotation(aim, Vector3.up);
            PlayState(curAttack.state, 0.05f, true);
            AudioManager.PlayAt(curAttack.heavy ? Sfx.Id.SwingHeavy : Sfx.Id.Swing, transform.position + Vector3.up, 0.7f, Random.Range(0.94f, 1.08f));
            if (swordTrail != null) swordTrail.Emit(true);
        }

        void EndAttackFx()
        {
            if (swordTrail != null) swordTrail.Emit(false);
        }

        Vector3 AimAssist(Vector3 want)
        {
            var gm = GameManager.Instance;
            if (gm == null) return want;
            EnemyAI best = null; float bestScore = float.MaxValue;
            foreach (var e in gm.Enemies)
            {
                if (e == null || e.IsDead || !e.isActiveAndEnabled) continue;
                Vector3 to = e.transform.position - transform.position; to.y = 0f;
                float d = to.magnitude;
                if (d > 4.6f) continue;
                float ang = Vector3.Angle(want, to);
                if (ang > 80f && d > 1.6f) continue;
                float score = d + ang * 0.03f;
                if (score < bestScore) { bestScore = score; best = e; }
            }
            if (best == null) return want;
            Vector3 dir = best.transform.position - transform.position; dir.y = 0f;
            return dir.sqrMagnitude > 0.001f ? dir.normalized : want;
        }

        void DoAttackHit()
        {
            Vector3 center = transform.position + transform.forward * (curAttack.range * 0.5f) + Vector3.up;
            var cols = Physics.OverlapSphere(center, curAttack.range * 0.7f, enemyMask, QueryTriggerInteraction.Ignore);
            int hits = 0;
            foreach (var c in cols)
            {
                var e = c.GetComponentInParent<EnemyAI>();
                if (e == null || e.IsDead || hitThisSwing.Contains(e)) continue;
                Vector3 to = e.transform.position - transform.position; to.y = 0f;
                float d = to.magnitude;
                if (d > curAttack.range + e.radius) continue;
                if (d > 1.0f && Vector3.Angle(transform.forward, to) > curAttack.arc * 0.5f) continue;
                hitThisSwing.Add(e);
                if (e.TakeHit(curAttack.damage, transform.position, curAttack.knockback, curAttack.heavy)) hits++;
            }
            var gm = GameManager.Instance;
            if (hits > 0)
            {
                if (gm != null && gm.Cam != null) gm.Cam.Shake(curAttack.shake);
                StartCoroutine(HitStop(curAttack.heavy ? 0.09f : 0.055f));
            }
            else if (curAttack.heavy)
            {
                Fx.Dust(transform.position + transform.forward * 1.6f, 12, 1.4f);
                AudioManager.PlayAt(Sfx.Id.Land, transform.position + transform.forward * 1.6f, 0.7f, 0.7f);
                if (gm != null && gm.Cam != null) gm.Cam.Shake(0.3f);
            }
        }

        IEnumerator HitStop(float seconds)
        {
            var gm = GameManager.Instance;
            if (gm != null && gm.State != GameState.Playing) yield break;
            Time.timeScale = 0.06f;
            yield return new WaitForSecondsRealtime(seconds);
            if (gm == null || gm.State == GameState.Playing) Time.timeScale = 1f;
        }

        void StartInteract(Interactable target)
        {
            interactTarget = target;
            interactDone = false;
            act = Act.Interact; actTime = 0f;
            PlayState("Interact", 0.1f, true);
        }

        void UpdateInteractTarget()
        {
            Interactable best = null;
            float bestD = float.MaxValue;
            if (act != Act.Dead && act != Act.Victory)
            {
                foreach (var it in Interactable.All)
                {
                    if (it == null || !it.isActiveAndEnabled || !it.Available) continue;
                    Vector3 to = it.transform.position - transform.position; to.y = 0f;
                    float d = to.magnitude;
                    if (d > it.radius) continue;
                    if (d < bestD) { bestD = d; best = it; }
                }
            }
            CurrentInteractable = best;
        }

        void UpdateAnimation(float dt)
        {
            if (animator == null) return;
            animator.SetFloat("Speed", new Vector3(hv.x, 0f, hv.z).magnitude, 0.06f, dt);
            if (act == Act.None)
            {
                if (!grounded && airTime > 0.12f)
                {
                    if (jumpedThisAir && vy > 1.5f) PlayState("JumpUp", 0.08f);
                    else PlayState("Fall", 0.18f);
                }
                else if (grounded)
                {
                    PlayState("Locomotion", curState == "Fall" || curState == "JumpUp" ? 0.08f : 0.16f);
                }
            }
            else if (act == Act.Land && actTime > 0.18f)
            {
                PlayState("Locomotion", 0.12f);
            }
        }

        void PlayState(string state, float fade, bool restart = false)
        {
            if (animator == null) return;
            if (!restart && curState == state) return;
            curState = state;
            animator.CrossFadeInFixedTime(state, fade, 0, 0f);
        }

        void Footsteps(float dt)
        {
            if (!grounded || act == Act.Dodge || act == Act.Dead) { stepAccum = 0.6f; return; }
            float sp = hv.magnitude;
            if (sp < 0.6f) return;
            stepAccum += sp * dt;
            float stride = Mathf.Lerp(0.8f, 1.7f, Mathf.InverseLerp(1.5f, runSpeed, sp));
            if (stepAccum >= stride)
            {
                stepAccum -= stride;
                AudioManager.PlayAt(Sfx.Id.Footstep, transform.position, 0.32f, Random.Range(0.88f, 1.12f));
            }
        }

        void SafetyNet()
        {
            if (grounded && act == Act.None && Time.time >= nextSafeSample)
            {
                nextSafeSample = Time.time + 0.3f;
                if (transform.position.y > -0.25f) lastSafePos = transform.position;
            }
            if (transform.position.y < -10f)
            {
                Teleport(lastSafePos + Vector3.up * 0.2f, transform.rotation);
                var gm = GameManager.Instance;
                if (gm != null) gm.ShowToast("", "You climb back to safety");
            }
        }
    }
}
