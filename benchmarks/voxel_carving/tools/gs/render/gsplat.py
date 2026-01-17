"""Gaussian rendering using gsplat library."""

import os
from typing import Optional, Tuple

import torch

from ..cameras import Cameras
from ..gaussians import Gaussians


def render_gsplat(
    gaussians: Gaussians,
    cameras: Cameras,
) -> Optional[Tuple[torch.Tensor, torch.Tensor]]:
    """
    Try to use gsplat for rendering if available.

    Args:
        gaussians: Gaussians object with means, scales, quats, opacities, sh_coeffs
        cameras: Cameras object with viewmats, Ks, and camera_model

    Returns:
        (render_colors, render_alphas) if successful, None otherwise
    """

    try:
        import gsplat

        actual_scales = torch.exp(gaussians.scales)
        actual_opacities = torch.sigmoid(gaussians.opacities)

        # gsplat expects colors as SH coefficients [N, K, 3]
        render_colors, render_alphas, meta = gsplat.rasterization(
            means=gaussians.means,
            quats=gaussians.quats,
            scales=actual_scales,
            opacities=actual_opacities,
            colors=gaussians.sh_coeffs,
            viewmats=cameras.viewmats,
            Ks=cameras.Ks,
            width=cameras.width,
            height=cameras.height,
            camera_model=cameras.camera_model,
            packed=False,
            sh_degree=gaussians.sh_degree,
        )
        return render_colors, render_alphas
    except Exception as e:
        print(f"  gsplat not available or failed: {e}")
        return None
