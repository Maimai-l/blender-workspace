"""gouache - procedural gouache painting engine for Awakening II backgrounds.

See README.md. Modules: color (Oklab), noise, kernels (numba rasterisers),
canvas (Canvas + brush API), foliage, trees, ground, sky, atmos, layers, shots.
"""
from .color import C, mix, ramp, shade, jitter, aerial, smoothstep, DAWN
from .noise import rng_for, fbm, value_noise, noise1d
from .canvas import (Canvas, dabs, stroke, catmull, wobble, taper, normals, tube_fields,
                     grain, save_rgba, save_rgb, PAPER)
