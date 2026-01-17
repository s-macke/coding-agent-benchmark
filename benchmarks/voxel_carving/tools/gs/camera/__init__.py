"""Camera module for view and projection matrices.

This module provides camera classes for different projection types:
- OrthographicCamera: parallel projection (no perspective distortion)
- PerspectiveCamera: pinhole camera model with perspective

Example usage:
    from gs.camera import OrthographicCamera, CameraCollection

    # Single camera
    cam = OrthographicCamera.from_angles(yaw_deg=0, pitch_deg=0,
                                         camera_up=[0,0,1], camera_right=[0,1,0])
    proj_x, proj_y = cam.project(points)

    # Multiple cameras from metadata
    cameras = CameraCollection.from_metadata(sprite_metadata)
    for camera in cameras:
        proj_x, proj_y = camera.project(points)
"""

from typing import List, Tuple

import numpy as np
import torch

from .base import Camera, compute_camera_position
from .orthographic import OrthographicCamera
from .perspective import PerspectiveCamera
from .collection import CameraCollection, CameraType
from ..constants import IMAGE_SIZE


__all__ = [
    # Classes
    "Camera",
    "OrthographicCamera",
    "PerspectiveCamera",
    "CameraCollection",
    "CameraType",
    # Backwards-compatible functions
    "build_cameras",
    "build_view_matrix",
    "build_orthographic_K",
    "build_perspective_K",
    "compute_camera_position",
    "project_points_orthographic",
    "project_points_perspective",
]


# =============================================================================
# Backwards-compatible functions
# =============================================================================


def build_view_matrix(
    camera_pos: np.ndarray, camera_up: np.ndarray, camera_right: np.ndarray
) -> torch.Tensor:
    """Build a 4x4 world-to-camera view matrix.

    The camera looks at origin (0, 0, 0).
    gsplat uses +Z as forward direction in camera space.

    Args:
        camera_pos: [3,] camera position
        camera_up: [3,] up vector
        camera_right: [3,] right vector

    Returns:
        [4, 4] view matrix
    """
    forward = -camera_pos / np.linalg.norm(camera_pos)
    up = np.array(camera_up)
    right = np.array(camera_right)

    # Rows are: right (X), up (Y), forward (Z) in camera space
    rotation = np.stack([right, up, forward], axis=0)

    viewmat = np.eye(4, dtype=np.float32)
    viewmat[:3, :3] = rotation
    viewmat[:3, 3] = -rotation @ camera_pos

    return torch.from_numpy(viewmat)


def build_orthographic_K(width: int, height: int, ortho_scale: float) -> torch.Tensor:
    """Build intrinsic matrix for orthographic projection.

    Args:
        width: image width in pixels
        height: image height in pixels
        ortho_scale: world units visible in half the image

    Returns:
        [3, 3] intrinsic matrix
    """
    fx = width / (2 * ortho_scale)
    fy = height / (2 * ortho_scale)
    cx = width / 2.0
    cy = height / 2.0

    return torch.tensor(
        [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=torch.float32
    )


def build_cameras(
    metadata: List[dict], ortho_scale: float = 2.0, distance: float = 5.0
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Build view matrices and intrinsic matrices for all cameras.

    This is a backwards-compatible function that returns tensors.
    For the new class-based API, use CameraCollection.from_metadata().

    Args:
        metadata: list of sprite metadata dicts
        ortho_scale: world units visible in half the image
        distance: camera distance from origin

    Returns:
        viewmats: [C, 4, 4] view matrices
        Ks: [C, 3, 3] intrinsic matrices
    """
    collection = CameraCollection.from_metadata(
        metadata, ortho_scale=ortho_scale, distance=distance
    )
    return collection.to_tensors()


def project_points_orthographic(
    points: torch.Tensor, viewmat: torch.Tensor, K: torch.Tensor
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Project 3D points to 2D using orthographic projection.

    This is a backwards-compatible standalone function.
    For the new class-based API, use camera.project().

    Args:
        points: [N, 3] points in world coordinates
        viewmat: [4, 4] view matrix
        K: [3, 3] intrinsic matrix

    Returns:
        proj_x: [N,] x pixel coordinates
        proj_y: [N,] y pixel coordinates
    """
    N = points.shape[0]
    points_homo = torch.cat([points, torch.ones(N, 1, device=points.device)], dim=1)
    cam_coords = (viewmat @ points_homo.T).T[:, :3]

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = fx * cam_coords[:, 0] + cx
    proj_y = fy * cam_coords[:, 1] + cy

    return proj_x, proj_y


def build_perspective_K(
    width: int, height: int, fov_deg: float = 60.0
) -> torch.Tensor:
    """Build intrinsic matrix for perspective projection.

    Args:
        width: image width in pixels
        height: image height in pixels
        fov_deg: vertical field of view in degrees

    Returns:
        [3, 3] intrinsic matrix
    """
    fov_rad = np.radians(fov_deg)
    fy = height / (2 * np.tan(fov_rad / 2))
    fx = fy  # Square pixels
    cx = width / 2.0
    cy = height / 2.0

    return torch.tensor(
        [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=torch.float32
    )


def project_points_perspective(
    points: torch.Tensor, viewmat: torch.Tensor, K: torch.Tensor
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Project 3D points to 2D using perspective projection.

    This is a backwards-compatible standalone function.
    For the new class-based API, use camera.project().

    Args:
        points: [N, 3] points in world coordinates
        viewmat: [4, 4] view matrix
        K: [3, 3] intrinsic matrix

    Returns:
        proj_x: [N,] x pixel coordinates
        proj_y: [N,] y pixel coordinates
    """
    N = points.shape[0]
    points_homo = torch.cat([points, torch.ones(N, 1, device=points.device)], dim=1)
    cam_coords = (viewmat @ points_homo.T).T[:, :3]

    # Perspective divide (z is depth, negative because camera looks along -z)
    z = -cam_coords[:, 2].clamp(min=1e-6)

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = fx * cam_coords[:, 0] / z + cx
    proj_y = fy * cam_coords[:, 1] / z + cy

    return proj_x, proj_y
