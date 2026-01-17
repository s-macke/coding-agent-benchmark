"""Gaussian splatting package for sprite-to-3DGS conversion."""

from .constants import IMAGE_SIZE, ALPHA_THRESHOLD
from .gaussians import SH_C0, SH_DEGREE
from .sprites import load_sprites
from .camera import (
    Camera,
    OrthographicCamera,
    PerspectiveCamera,
    CameraCollection,
    CameraType,
    compute_camera_position,
)
from .render import render_gaussians
from .render_simple import render_gaussians_simple
from .render_gsplat import try_gsplat_render
from .gaussians import eval_sh, rgb_to_sh, sh_to_rgb, init_sh_from_rgb

__all__ = [
    # Constants
    'IMAGE_SIZE',
    'SH_C0',
    'SH_DEGREE',
    'ALPHA_THRESHOLD',
    # Sprites
    'load_sprites',
    # Camera
    'Camera',
    'OrthographicCamera',
    'PerspectiveCamera',
    'CameraCollection',
    'CameraType',
    'compute_camera_position',
    # Render
    'render_gaussians',
    'render_gaussians_simple',
    'try_gsplat_render',
    # Spherical Harmonics
    'eval_sh',
    'rgb_to_sh',
    'sh_to_rgb',
    'init_sh_from_rgb',
]
