"""Gaussian splatting package for sprite-to-3DGS conversion."""

from .constants import IMAGE_SIZE, SH_C0, ALPHA_THRESHOLD
from .sprites import load_sprites
from .camera import (
    Camera,
    OrthographicCamera,
    PerspectiveCamera,
    CameraCollection,
    CameraType,
    compute_camera_position,
)
from .render import render_gaussians_simple, try_gsplat_render

__all__ = [
    # Constants
    'IMAGE_SIZE',
    'SH_C0',
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
    'render_gaussians_simple',
    'try_gsplat_render',
]
