using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace WordDefense
{
    /// <summary>The cannon on the gate bastion: turns toward the target, recoils when firing.</summary>
    public class Cannon : MonoBehaviour
    {
        Transform yaw, barrel, muzzle;
        Quaternion yawRest, barrelRest;
        Vector3 barrelPos;
        float yawDeg, pitchDeg, recoil;
        Vector3 aim;
        float aimUntil = -1f;

        public void Setup()
        {
            foreach (Transform t in GetComponentsInChildren<Transform>(true))
            {
                if (t.name == "CannonYaw") yaw = t;
                else if (t.name == "CannonBarrel") barrel = t;
                else if (t.name == "Muzzle") muzzle = t;
            }
            if (yaw) yawRest = yaw.localRotation;
            if (barrel) { barrelRest = barrel.localRotation; barrelPos = barrel.localPosition; }
            yawDeg = 0f; pitchDeg = 12f;
        }

        public Vector3 MuzzlePos { get { return muzzle ? muzzle.position : transform.position + Vector3.up; } }
        public Vector3 Forward { get { return barrel ? barrel.forward : transform.forward; } }

        public void AimAt(Vector3 world, float hold = 0.6f)
        {
            aim = world;
            aimUntil = Time.time + hold;
        }

        void Update()
        {
            float dt = Time.deltaTime;
            float wantYaw = 0f, wantPitch = 14f;
            if (Time.time < aimUntil)
            {
                Vector3 local = transform.InverseTransformPoint(aim);
                wantYaw = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
                float dist = new Vector2(local.x, local.z).magnitude;
                wantPitch = Mathf.Lerp(10f, 32f, Mathf.InverseLerp(6f, 40f, dist));
            }
            else
            {
                wantYaw = Mathf.Sin(Time.time * 0.35f) * 25f - 10f;
            }
            yawDeg = Mathf.MoveTowardsAngle(yawDeg, wantYaw, dt * 260f);
            pitchDeg = Mathf.MoveTowards(pitchDeg, wantPitch, dt * 90f);
            recoil = Mathf.MoveTowards(recoil, 0f, dt * 4f);
            if (yaw) yaw.localRotation = yawRest * Quaternion.Euler(0f, yawDeg, 0f);
            if (barrel)
            {
                barrel.localRotation = barrelRest * Quaternion.Euler(-pitchDeg, 0f, 0f);
                barrel.localPosition = barrelPos - barrel.localRotation * Vector3.forward * (recoil * 0.22f);
            }
        }

        public void Fire()
        {
            recoil = 1f;
            Fx.MuzzleFlash(MuzzlePos, Forward);
        }
    }
}
