"""Camera mathematics for view and projection matrices."""

from typing import List, Tuple

import numpy as np
import torch

from .constants import IMAGE_SIZE


def build_view_matrix(camera_pos: np.ndarray,
                      camera_up: np.ndarray,
                      camera_right: np.ndarray) -> torch.Tensor:
    """
    Build a 4x4 world-to-camera view matrix.

    The camera looks at origin (0, 0, 0).
    gsplat uses +Z as forward direction in camera space.
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


def compute_camera_position(yaw_deg: float, pitch_deg: float, distance: float = 5.0) -> np.ndarray:
    """
    Compute camera position from yaw and pitch angles.

    Following SHIP_ANGLES.md conventions:
    - YAW 0 = rear (camera at -X), 180 = front (camera at +X)
    - PITCH 90 = below (camera at -Z), -90 = above (camera at +Z)
    """
    yaw_rad = np.radians(yaw_deg)
    pitch_rad = np.radians(pitch_deg)

    cam_x = -distance * np.cos(yaw_rad) * np.cos(pitch_rad)
    cam_y = distance * np.sin(yaw_rad) * np.cos(pitch_rad)
    cam_z = distance * np.sin(pitch_rad)

    return np.array([cam_x, cam_y, cam_z], dtype=np.float32)


def build_orthographic_K(width: int, height: int, ortho_scale: float) -> torch.Tensor:
    """Build intrinsic matrix for orthographic projection."""
    fx = width / (2 * ortho_scale)
    fy = height / (2 * ortho_scale)
    cx = width / 2.0
    cy = height / 2.0

    return torch.tensor([
        [fx, 0.0, cx],
        [0.0, fy, cy],
        [0.0, 0.0, 1.0]
    ], dtype=torch.float32)


def build_cameras(metadata: List[dict], ortho_scale: float = 2.0,
                  distance: float = 5.0) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Build view matrices and intrinsic matrices for all cameras.

    Returns:
        viewmats: [C, 4, 4] view matrices
        Ks: [C, 3, 3] intrinsic matrices
    """
    viewmats = []
    Ks = []

    for sprite in metadata:
        cam_pos = compute_camera_position(sprite['yaw'], sprite['pitch'], distance)
        viewmat = build_view_matrix(cam_pos, sprite['camera_up'], sprite['camera_right'])
        viewmats.append(viewmat)

        K = build_orthographic_K(IMAGE_SIZE, IMAGE_SIZE, ortho_scale)
        Ks.append(K)

    return torch.stack(viewmats), torch.stack(Ks)


def project_points_orthographic(points: torch.Tensor, viewmat: torch.Tensor,
                                K: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Project 3D points to 2D using orthographic projection.

    Returns:
        proj_x, proj_y: Projected 2D coordinates
    """
    N = points.shape[0]
    points_homo = torch.cat([points, torch.ones(N, 1, device=points.device)], dim=1)
    cam_coords = (viewmat @ points_homo.T).T[:, :3]

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = fx * cam_coords[:, 0] + cx
    proj_y = fy * cam_coords[:, 1] + cy

    return proj_x, proj_y
