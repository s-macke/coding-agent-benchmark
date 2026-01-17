"""Gaussian rendering with automatic fallback."""

from typing import Tuple

import torch

from .cameras import Cameras
from .gaussians import Gaussians
from .render_gsplat import render_gsplat
from .render_points_fast import render_points_fast


def render_gaussians(
    gaussians: Gaussians,
    cameras: Cameras,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Render gaussians with gsplat fallback to fast point renderer.

    Args:
        gaussians: Gaussians object
        cameras: Single camera (Cameras object)

    Returns:
        render_rgb: [H, W, 3]
        render_alpha: [H, W, 1]
    """
    result = render_gsplat(gaussians, cameras)
    if result is not None:
        return result[0][0], result[1][0]

    return render_points_fast(gaussians, cameras)
