"""Gaussian splatting package for sprite-to-3DGS conversion."""

from .constants import IMAGE_SIZE, SH_C0, ALPHA_THRESHOLD
from .sprites import load_sprites
from .camera import (
    # Classes
    Camera,
    OrthographicCamera,
    PerspectiveCamera,
    CameraCollection,
    # Backwards-compatible functions
    build_cameras,
    build_view_matrix,
    build_orthographic_K,
    compute_camera_position,
    project_points_orthographic,
)
from .render import render_gaussians_simple, try_gsplat_render

__all__ = [
    # Constants
    'IMAGE_SIZE',
    'SH_C0',
    'ALPHA_THRESHOLD',
    # Sprites
    'load_sprites',
    # Camera classes
    'Camera',
    'OrthographicCamera',
    'PerspectiveCamera',
    'CameraCollection',
    # Camera functions (backwards compatible)
    'build_cameras',
    'build_view_matrix',
    'build_orthographic_K',
    'compute_camera_position',
    'project_points_orthographic',
    # Render
    'render_gaussians_simple',
    'try_gsplat_render',
]
