"""Gaussian splatting package for sprite-to-3DGS conversion."""

from .constants import IMAGE_SIZE, SH_C0, ALPHA_THRESHOLD
from .sprites import load_sprites
from .camera import (
    # Classes
    Camera,
    OrthographicCamera,
    PerspectiveCamera,
    CameraCollection,
    CameraType,
    # Backwards-compatible functions
    build_cameras,
    build_view_matrix,
    build_orthographic_K,
    build_perspective_K,
    compute_camera_position,
    project_points_orthographic,
    project_points_perspective,
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
    'CameraType',
    # Camera functions (backwards compatible)
    'build_cameras',
    'build_view_matrix',
    'build_orthographic_K',
    'build_perspective_K',
    'compute_camera_position',
    'project_points_orthographic',
    'project_points_perspective',
    # Render
    'render_gaussians_simple',
    'try_gsplat_render',
]
