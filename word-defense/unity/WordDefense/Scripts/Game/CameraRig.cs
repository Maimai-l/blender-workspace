using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace WordDefense
{
    /// <summary>Camera with trauma-based shake and a slow idle drift.</summary>
    public class CameraRig : MonoBehaviour
    {
        public static CameraRig Instance;
        Vector3 basePos;
        Quaternion baseRot;
        float trauma;
        float punch;

        void Awake()
        {
            Instance = this;
            basePos = transform.position;
            baseRot = transform.rotation;
        }

        public static void Shake(float amount)
        {
            if (Instance) Instance.trauma = Mathf.Min(1f, Instance.trauma + amount);
        }

        public static void Punch(float amount)
        {
            if (Instance) Instance.punch = Mathf.Max(Instance.punch, amount);
        }

        void LateUpdate()
        {
            float dt = Time.unscaledDeltaTime > 0f ? Time.unscaledDeltaTime : Time.deltaTime;
            trauma = Mathf.MoveTowards(trauma, 0f, dt * 1.4f);
            punch = Mathf.MoveTowards(punch, 0f, dt * 1.2f);
            float s = trauma * trauma;
            float t = Time.realtimeSinceStartup;
            Vector3 drift = new Vector3(Mathf.Sin(t * 0.13f) * 0.25f, Mathf.Sin(t * 0.17f) * 0.12f, 0f);
            Vector3 jitter = new Vector3(Mathf.PerlinNoise(t * 22f, 0.3f) - 0.5f, Mathf.PerlinNoise(0.7f, t * 22f) - 0.5f, 0f) * (s * 1.1f);
            transform.position = basePos + baseRot * (drift + jitter) + baseRot * Vector3.forward * (punch * 2.5f);
            transform.rotation = baseRot * Quaternion.Euler(0f, 0f, (Mathf.PerlinNoise(t * 18f, 5f) - 0.5f) * s * 3f);
        }
    }
}
