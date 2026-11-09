"""Awakening II birds: a hand-designed Japanese white-eye drawn by code (see README.md)."""
from .model import DEFAULT_POSE, CM_PER_UNIT, build_rig
from .draw import Light, render, draw, composite, Sprite, detail_for
from .palette import ZONES, INK, build_palette
from .poses import POSES, pose, blend, flap_pose, WINGS, FLAP, FLAP4
from .anim import Track, draw_state, landing, flee, crossing, follow_path, EASES
from .flock import burst, circling, draw_flock, FlockSim, flock_pose
