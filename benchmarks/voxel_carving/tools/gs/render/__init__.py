"""Gaussian rendering modules."""

from typing import Tuple

import torch

from ..cameras import Cameras
from ..gaussians import Gaussians
from .gsplat import render_gsplat
from .points_fast import render_points_fast
from .simple import render_gaussians_simple
from .projection import project_points


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


__all__ = [
    'render_gaussians',
    'render_gsplat',
    'render_gaussians_simple',
    'render_points_fast',
    'project_points',
]
