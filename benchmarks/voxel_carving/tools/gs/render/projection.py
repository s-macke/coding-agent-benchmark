"""Point projection utilities."""

from typing import Tuple

import torch


def project_points(
    cam_coords: torch.Tensor,
    K: torch.Tensor,
    is_perspective: bool = False,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Project camera-space points to pixel coordinates.

    Args:
        cam_coords: [N, 3] points in camera space
        K: [3, 3] intrinsic matrix
        is_perspective: if True, divide by depth

    Returns:
        proj_x, proj_y: [N,] pixel coordinates
    """
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    if is_perspective:
        z = (-cam_coords[:, 2]).clamp(min=1e-6)
        proj_x = fx * cam_coords[:, 0] / z + cx
        proj_y = fy * cam_coords[:, 1] / z + cy
    else:
        proj_x = fx * cam_coords[:, 0] + cx
        proj_y = fy * cam_coords[:, 1] + cy

    return proj_x, proj_y
