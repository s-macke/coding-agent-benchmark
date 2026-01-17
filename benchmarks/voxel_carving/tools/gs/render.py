"""Gaussian rendering functions."""

from typing import Optional, Tuple

import torch
import torch.nn.functional as F

from .gaussians import Gaussians
from .sh import eval_sh

# Rendering constants
MIN_SIGMA = 0.5
MIN_WEIGHT_THRESHOLD = 0.001
CLAMP_EPSILON = 1e-6


def render_gaussians_simple(
    gaussians: Gaussians,
    viewmat: torch.Tensor,
    K: torch.Tensor,
    width: int,
    height: int,
    camera_pos: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Simple differentiable Gaussian splatting renderer (CPU-friendly).

    Projects Gaussians and accumulates with alpha blending (back to front).

    Args:
        gaussians: Gaussians object with means, scales, quats, opacities, sh_coeffs
        viewmat: [4, 4] view matrix
        K: [3, 3] intrinsic matrix
        width: image width
        height: image height
        camera_pos: [3] camera position in world coords (computed from viewmat if None)

    Returns:
        render_rgb: [H, W, 3]
        render_alpha: [H, W, 1]
    """
    means = gaussians.means
    scales = gaussians.scales
    opacities = gaussians.opacities
    sh_coeffs = gaussians.sh_coeffs
    sh_degree = gaussians.sh_degree

    n = means.shape[0]
    device = means.device

    # Compute camera position from view matrix if not provided
    if camera_pos is None:
        # viewmat is world-to-camera, so camera position is -R^T @ t
        rot = viewmat[:3, :3]
        trans = viewmat[:3, 3]
        camera_pos = -rot.T @ trans

    # Compute viewing directions (Gaussian to camera, normalized)
    view_dirs = camera_pos.unsqueeze(0) - means  # [N, 3]
    view_dirs = F.normalize(view_dirs, dim=-1)

    # Evaluate SH to get colors
    colors = eval_sh(sh_coeffs, view_dirs, degree=sh_degree)  # [N, 3]

    means_homo = torch.cat([means, torch.ones(n, 1, device=device)], dim=1)
    cam_means = (viewmat @ means_homo.T).T[:, :3]

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = fx * cam_means[:, 0] + cx
    proj_y = fy * cam_means[:, 1] + cy
    depths = -cam_means[:, 2]  # Negative z is forward

    actual_scales = torch.exp(scales)
    actual_opacities = torch.sigmoid(opacities)

    sorted_indices = torch.argsort(depths, descending=True)

    render_rgb = torch.zeros(height, width, 3, device=device)
    render_alpha = torch.zeros(height, width, 1, device=device)

    y_coords, x_coords = torch.meshgrid(
        torch.arange(height, device=device, dtype=torch.float32),
        torch.arange(width, device=device, dtype=torch.float32),
        indexing='ij'
    )

    for idx in sorted_indices:
        px, py = proj_x[idx], proj_y[idx]
        scale = actual_scales[idx]
        opacity = actual_opacities[idx]
        color = colors[idx]

        sigma = (scale[0] + scale[1]) / 2 * fx.abs()
        sigma = sigma.clamp(min=MIN_SIGMA)

        dx = x_coords - px
        dy = y_coords - py
        dist_sq = dx * dx + dy * dy

        weight = torch.exp(-0.5 * dist_sq / (sigma * sigma + CLAMP_EPSILON))
        weight = weight * opacity

        transmittance = 1.0 - render_alpha[:, :, 0]
        alpha_contrib = weight * transmittance

        render_rgb += alpha_contrib.unsqueeze(-1) * color.unsqueeze(0).unsqueeze(0)
        render_alpha[:, :, 0] += alpha_contrib

    render_alpha = render_alpha.clamp(0, 1)

    return render_rgb, render_alpha


def try_gsplat_render(
    gaussians: Gaussians,
    viewmats: torch.Tensor,
    Ks: torch.Tensor,
    width: int,
    height: int,
):
    """
    Try to use gsplat for rendering if available.

    Args:
        gaussians: Gaussians object with means, scales, quats, opacities, sh_coeffs
        viewmats: [C, 4, 4] view matrices
        Ks: [C, 3, 3] intrinsic matrices
        width: image width
        height: image height

    Returns:
        (render_colors, render_alphas) if successful, None otherwise
    """
    import os
    if os.environ.get('SKIP_GSPLAT', '').lower() in ('1', 'true', 'yes'):
        return None

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
            viewmats=viewmats,
            Ks=Ks,
            width=width,
            height=height,
            camera_model="ortho",
            packed=False,
            sh_degree=gaussians.sh_degree,
        )
        return render_colors, render_alphas
    except Exception as e:
        print(f"  gsplat not available or failed: {e}")
        return None
