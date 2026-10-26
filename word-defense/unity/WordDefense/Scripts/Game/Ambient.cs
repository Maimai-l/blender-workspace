using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace WordDefense
{
    /// <summary>Small ambient motions: spinning windmill and portal core, bobbing crystals, drifting clouds.</summary>
    public class Ambient : MonoBehaviour
    {
        public enum Mode { Spin, Bob, Drift, Pulse }
        public Mode mode;
        public Vector3 axis = Vector3.forward;
        public float speed = 30f;
        public float amount = 0.2f;
        public float offset;
        Vector3 basePos;
        Quaternion baseRot;
        Vector3 baseScale;

        void Start()
        {
            basePos = transform.localPosition;
            baseRot = transform.localRotation;
            baseScale = transform.localScale;
            offset += UnityEngine.Random.value * 10f;
        }

        void Update()
        {
            float t = Time.time + offset;
            switch (mode)
            {
                case Mode.Spin: transform.localRotation = baseRot * Quaternion.AngleAxis(t * speed, axis); break;
                case Mode.Bob:
                    transform.localPosition = basePos + Vector3.up * Mathf.Sin(t * speed) * amount;
                    transform.localRotation = baseRot * Quaternion.Euler(0f, t * 25f, 0f);
                    break;
                case Mode.Drift: transform.localPosition = basePos + new Vector3(Mathf.Sin(t * speed) * amount, Mathf.Sin(t * speed * 0.7f) * amount * 0.15f, 0f); break;
                case Mode.Pulse: transform.localScale = baseScale * (1f + Mathf.Sin(t * speed) * amount); break;
            }
        }
    }
}
