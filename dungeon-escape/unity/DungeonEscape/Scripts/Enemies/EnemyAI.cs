using System;
using UnityEngine;
using UnityEngine.AI;

namespace DungeonEscape
{
    [RequireComponent(typeof(NavMeshAgent))]
    public class EnemyAI : MonoBehaviour
    {
        public enum Kind { Skeleton, Warden }

        [Header("Identity")]
        public Kind kind = Kind.Skeleton;
        public string displayName = "Skeleton";
        public bool isBoss;

        [Header("References")]
        public Animator animator;
        public Health health;
        public Renderer bodyRenderer;
        public LayerMask sightMask;

        [Header("Tuning")]
        public float radius = 0.45f;
        public float animScale = 1f;
        public float aggroRange = 12f;
        public float chaseSpeed = 3.6f;
        public float holdDistance = 3.8f;
        public float attackRange = 2.0f;
        public float attackReach = 2.6f;
        public float attackArc = 100f;
        public float damage = 10f;
        public float attackHitTime = 0.5f;
        public float attackDuration = 1.15f;
        public float attackCooldown = 1.0f;
        public float attackKnockback = 3f;
        public bool heavyAttack;
        public float attackAnimSpeed = 1f;
        public float hitStun = 0.42f;
        public int poise = 1;
        public float orbHeal = 12f;
        public bool dormant;

        public bool IsDead { get; private set; }
        public bool IsWindingUp { get { return state == State.Attack && stateTime < attackHitTime; } }
        public bool IsAggro { get { return state == State.Chase || state == State.Hold || state == State.Attack || state == State.Stagger; } }
        public event Action<EnemyAI> Died;

        enum State { Idle, Rise, Chase, Hold, Attack, Stagger, Dead }

        State state = State.Idle;
        float stateTime;
        NavMeshAgent agent;
        float repathTimer, tokenTimer, nextAttackTime;
        bool attackHitDone;
        int hitsTaken;
        Vector3 staggerVel;
        string curAnim;
        float strafeSign = 1f;
        float flash;
        float eyeBoost = 1f;
        MaterialPropertyBlock mpb;
        Color[] baseColors;
        int eyeIndex = -1;
        Color eyeEmission;
        Vector3 homePos;
        bool hasToken;

        void Awake()
        {
            agent = GetComponent<NavMeshAgent>();
            if (health == null) health = GetComponent<Health>();
            if (animator == null) animator = GetComponentInChildren<Animator>();
            if (bodyRenderer == null) bodyRenderer = GetComponentInChildren<SkinnedMeshRenderer>();
            mpb = new MaterialPropertyBlock();
            if (bodyRenderer != null)
            {
                var mats = bodyRenderer.sharedMaterials;
                baseColors = new Color[mats.Length];
                for (int i = 0; i < mats.Length; i++)
                {
                    baseColors[i] = mats[i] != null && mats[i].HasProperty("_BaseColor") ? mats[i].GetColor("_BaseColor") : Color.white;
                    if (mats[i] != null && mats[i].name.StartsWith("M_EyeGlow"))
                    {
                        eyeIndex = i;
                        eyeEmission = mats[i].GetColor("_EmissionColor");
                    }
                }
            }
            agent.updateRotation = false;
            agent.autoBraking = true;
            homePos = transform.position;
            strafeSign = UnityEngine.Random.value < 0.5f ? -1f : 1f;
        }

        void OnEnable()
        {
            var gm = GameManager.Instance;
            if (gm != null) gm.RegisterEnemy(this);
        }

        void OnDisable()
        {
            var gm = GameManager.Instance;
            if (gm != null) gm.UnregisterEnemy(this);
        }

        void Start()
        {
            var gm = GameManager.Instance;
            if (gm != null) gm.RegisterEnemy(this);
            Play("Locomotion", 0f);
            agent.speed = chaseSpeed;
            // Scene-placed enemies are saved with the agent off (see DEBuilder.SpawnEnemy); by Start the NavMesh is registered.
            if (!IsDead && !agent.enabled) agent.enabled = true;
            if (agent.enabled && !agent.isOnNavMesh) agent.Warp(transform.position);
        }

        /// <summary>Spawned by the encounter: climb out of the ground, then hunt.</summary>
        public void SpawnRise()
        {
            dormant = false;
            state = State.Rise; stateTime = 0f;
            if (agent.isOnNavMesh) agent.isStopped = true;
            Play("Rise", 0f);
            Fx.Dust(transform.position + Vector3.up * 0.1f, 18, 1.6f);
            AudioManager.PlayAt(Sfx.Id.Rise, transform.position + Vector3.up, 0.8f, UnityEngine.Random.Range(0.9f, 1.1f));
        }

        public void Aggro()
        {
            if (IsDead || state == State.Rise) return;
            if (state == State.Idle) { dormant = false; SetState(State.Chase); AudioManager.PlayAt(Sfx.Id.Growl, transform.position + Vector3.up * 1.5f, 0.7f, kind == Kind.Warden ? 0.7f : UnityEngine.Random.Range(0.95f, 1.15f)); }
        }

        void SetState(State s)
        {
            if (s != State.Attack && s != State.Chase) ReleaseToken();
            state = s; stateTime = 0f;
            if (animator != null) animator.speed = 1f;
        }

        void ReleaseToken()
        {
            if (!hasToken) return;
            hasToken = false;
            var gm = GameManager.Instance;
            if (gm != null) gm.ReleaseAttackToken(this);
        }

        void Update()
        {
            float dt = Time.deltaTime;
            stateTime += dt;
            UpdateLook(dt);
            if (IsDead) { DeadUpdate(); return; }
            var gm = GameManager.Instance;
            var player = gm != null ? gm.Player : null;
            bool playing = gm == null || gm.State == GameState.Playing;
            if (player == null || player.IsDead || !playing)
            {
                if (agent.isOnNavMesh) agent.isStopped = true;
                if (state != State.Rise && state != State.Stagger) { if (state == State.Attack) SetState(State.Idle); Play("Locomotion", 0.25f); }
                SetSpeedParam(0f, dt);
                return;
            }

            Vector3 toP = player.transform.position - transform.position; toP.y = 0f;
            float dist = toP.magnitude;

            switch (state)
            {
                case State.Idle:
                    SetSpeedParam(0f, dt);
                    if (!dormant && dist < aggroRange && CanSee(player)) Aggro();
                    break;

                case State.Rise:
                    SetSpeedParam(0f, dt);
                    FaceTowards(toP, 120f, dt);
                    if (stateTime > 1.35f) SetState(State.Chase);
                    break;

                case State.Chase:
                    if (hasToken && stateTime > 2.5f) ReleaseToken();
                    if (agent.isOnNavMesh)
                    {
                        agent.isStopped = false;
                        agent.speed = chaseSpeed;
                        repathTimer -= dt;
                        if (repathTimer <= 0f) { repathTimer = 0.15f; agent.SetDestination(player.transform.position); }
                    }
                    Play("Locomotion", 0.2f);
                    FaceMovement(toP, dt);
                    SetSpeedParam(agent.velocity.magnitude, dt);
                    if (dist <= attackRange + radius && Time.time >= nextAttackTime)
                    {
                        if (TryToken()) StartAttack();
                        else SetState(State.Hold);
                    }
                    else if (dist <= holdDistance && Time.time < nextAttackTime)
                    {
                        SetState(State.Hold);
                    }
                    break;

                case State.Hold:
                    {
                        Play("Locomotion", 0.2f);
                        FaceTowards(toP, 360f, dt);
                        if (agent.isOnNavMesh)
                        {
                            agent.isStopped = false;
                            agent.speed = 1.4f;
                            repathTimer -= dt;
                            if (repathTimer <= 0f)
                            {
                                repathTimer = 0.4f;
                                Vector3 from = -toP.normalized;
                                Vector3 around = Quaternion.Euler(0f, 22f * strafeSign, 0f) * from;
                                Vector3 dest = player.transform.position + around * holdDistance;
                                NavMeshHit nh;
                                if (NavMesh.SamplePosition(dest, out nh, 1.5f, NavMesh.AllAreas)) agent.SetDestination(nh.position);
                                if (UnityEngine.Random.value < 0.08f) strafeSign = -strafeSign;
                            }
                        }
                        SetSpeedParam(agent.velocity.magnitude, dt);
                        tokenTimer -= dt;
                        if (tokenTimer <= 0f && Time.time >= nextAttackTime)
                        {
                            tokenTimer = 0.25f;
                            if (dist <= attackRange + radius + 1.6f && TryToken()) { SetState(State.Chase); }
                        }
                        if (dist > holdDistance + 2f || (stateTime > 2.5f && Time.time >= nextAttackTime)) SetState(State.Chase);
                    }
                    break;

                case State.Attack:
                    if (agent.isOnNavMesh) agent.isStopped = true;
                    SetSpeedParam(0f, dt);
                    float scaled = stateTime * attackAnimSpeed;
                    if (scaled < attackHitTime * 0.75f) FaceTowards(toP, kind == Kind.Warden ? 200f : 300f, dt);
                    eyeBoost = scaled < attackHitTime ? Mathf.Lerp(1f, 4f, scaled / attackHitTime) : Mathf.Lerp(eyeBoost, 1f, dt * 6f);
                    if (!attackHitDone && scaled >= attackHitTime)
                    {
                        attackHitDone = true;
                        AudioManager.PlayAt(heavyAttack ? Sfx.Id.SwingHeavy : Sfx.Id.Swing, transform.position + Vector3.up, 0.75f, kind == Kind.Warden ? 0.75f : 0.9f);
                        if (dist <= attackReach + 0.35f && Vector3.Angle(transform.forward, toP) <= attackArc * 0.5f)
                        {
                            player.health.TakeDamage(new DamageInfo { amount = damage, sourcePosition = transform.position, knockback = attackKnockback, heavy = heavyAttack });
                        }
                        if (heavyAttack)
                        {
                            Fx.Dust(transform.position + transform.forward * 2f, 14, 1.6f);
                            if (gm.Cam != null && dist < 8f) gm.Cam.Shake(0.35f);
                        }
                    }
                    if (scaled >= attackDuration)
                    {
                        nextAttackTime = Time.time + attackCooldown * UnityEngine.Random.Range(0.8f, 1.3f);
                        SetState(dist <= holdDistance ? State.Hold : State.Chase);
                        Play("Locomotion", 0.25f);
                    }
                    break;

                case State.Stagger:
                    SetSpeedParam(0f, dt);
                    staggerVel = Vector3.MoveTowards(staggerVel, Vector3.zero, 20f * dt);
                    if (agent.isOnNavMesh) agent.Move(staggerVel * dt);
                    if (stateTime >= hitStun) { SetState(State.Chase); Play("Locomotion", 0.2f); }
                    break;
            }
        }

        bool TryToken()
        {
            var gm = GameManager.Instance;
            if (gm == null) { hasToken = true; return true; }
            hasToken = gm.RequestAttackToken(this);
            return hasToken;
        }

        void StartAttack()
        {
            SetState(State.Attack);
            hasToken = true;
            attackHitDone = false;
            if (agent.isOnNavMesh) { agent.isStopped = true; agent.velocity = Vector3.zero; }
            Play("Attack", 0.1f, true);
            if (animator != null) animator.speed = attackAnimSpeed;
            AudioManager.PlayAt(Sfx.Id.Telegraph, transform.position + Vector3.up * 1.5f, kind == Kind.Warden ? 0.9f : 0.6f, kind == Kind.Warden ? 0.7f : UnityEngine.Random.Range(0.95f, 1.1f));
        }

        bool CanSee(PlayerController p)
        {
            Vector3 eye = transform.position + Vector3.up * 1.6f;
            Vector3 tgt = p.transform.position + Vector3.up * 1.2f;
            return !Physics.Linecast(eye, tgt, sightMask, QueryTriggerInteraction.Ignore);
        }

        void FaceMovement(Vector3 toPlayer, float dt)
        {
            Vector3 v = agent.velocity; v.y = 0f;
            if (v.sqrMagnitude > 0.2f) FaceTowards(v, 540f, dt);
            else FaceTowards(toPlayer, 360f, dt);
        }

        void FaceTowards(Vector3 dir, float degPerSec, float dt)
        {
            dir.y = 0f;
            if (dir.sqrMagnitude < 0.0001f) return;
            transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(dir.normalized), degPerSec * dt);
        }

        void SetSpeedParam(float v, float dt)
        {
            if (animator != null) animator.SetFloat("Speed", v / Mathf.Max(0.01f, animScale), 0.1f, dt);
        }

        void Play(string s, float fade, bool restart = false)
        {
            if (animator == null) return;
            if (!restart && curAnim == s) return;
            curAnim = s;
            animator.CrossFadeInFixedTime(s, fade, 0, 0f);
        }

        public bool TakeHit(float dmg, Vector3 src, float kb, bool heavy)
        {
            if (IsDead || state == State.Rise) return false;
            var info = new DamageInfo { amount = dmg, sourcePosition = src, knockback = kb, heavy = heavy };
            if (!health.TakeDamage(info)) return false;
            Vector3 away = transform.position - src; away.y = 0f;
            if (away.sqrMagnitude < 0.001f) away = -transform.forward;
            away.Normalize();
            flash = 1f;
            Vector3 hitPt = transform.position + Vector3.up * (1.15f * transform.localScale.y) - away * radius * 0.6f;
            Fx.HitSpark(hitPt, new Color(1f, 0.9f, 0.7f), heavy ? 26 : 16);
            Fx.BoneChips(hitPt, heavy ? 10 : 6);
            AudioManager.PlayAt(Sfx.Id.HitBone, hitPt, 0.9f, UnityEngine.Random.Range(0.9f, 1.12f) * (kind == Kind.Warden ? 0.8f : 1f));
            if (health.IsDead) { Die(away); return true; }
            if (state == State.Idle) Aggro();
            hitsTaken++;
            bool canStagger = heavy || hitsTaken >= poise;
            if (kind == Kind.Warden && state == State.Attack && !heavy) canStagger = false;
            if (canStagger)
            {
                hitsTaken = 0;
                SetState(State.Stagger);
                staggerVel = away * kb * (kind == Kind.Warden ? 0.5f : 1f);
                Play("Hit", 0.05f, true);
            }
            else if (agent.isOnNavMesh)
            {
                agent.Move(away * 0.15f);
            }
            return true;
        }

        void Die(Vector3 away)
        {
            IsDead = true;
            ReleaseToken();
            SetState(State.Dead);
            if (agent.isOnNavMesh) { agent.isStopped = true; agent.velocity = Vector3.zero; }
            agent.enabled = false;
            foreach (var c in GetComponentsInChildren<Collider>()) c.enabled = false;
            Play("Death", 0.08f, true);
            AudioManager.PlayAt(Sfx.Id.EnemyDie, transform.position + Vector3.up, 1f, kind == Kind.Warden ? 0.75f : UnityEngine.Random.Range(0.9f, 1.1f));
            Fx.BoneChips(transform.position + Vector3.up * 1f, kind == Kind.Warden ? 26 : 14);
            Fx.Dust(transform.position + Vector3.up * 0.2f, 14, 1.4f);
            HealthOrb.Spawn(transform.position + Vector3.up * 1.0f + away * 0.3f, orbHeal);
            var gm = GameManager.Instance;
            if (gm != null) gm.OnEnemyKilled(this);
            if (Died != null) Died(this);
        }

        void DeadUpdate()
        {
            if (stateTime > 2.6f)
            {
                transform.position += Vector3.down * Time.deltaTime * 0.6f;
                if (stateTime > 5f) Destroy(gameObject);
            }
        }

        void UpdateLook(float dt)
        {
            if (bodyRenderer == null || baseColors == null) return;
            flash = Mathf.Max(0f, flash - dt * 7f);
            if (!IsDead && state != State.Attack) eyeBoost = Mathf.Lerp(eyeBoost, 1f, dt * 4f);
            float eyes = IsDead ? Mathf.Max(0f, 1f - stateTime * 0.8f) : eyeBoost;
            for (int i = 0; i < baseColors.Length; i++)
            {
                mpb.Clear();
                if (flash > 0.001f) mpb.SetColor("_BaseColor", Color.Lerp(baseColors[i], new Color(2.2f, 2.2f, 2.2f, 1f), flash));
                if (i == eyeIndex) mpb.SetColor("_EmissionColor", eyeEmission * eyes);
                bodyRenderer.SetPropertyBlock(mpb, i);
            }
        }
    }
}
