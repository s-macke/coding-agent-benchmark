"""Gaussian rendering functions."""

from typing import Tuple

import torch

# Rendering constants
MIN_SIGMA = 0.5
MIN_WEIGHT_THRESHOLD = 0.001
CLAMP_EPSILON = 1e-6


def render_gaussians_simple(means: torch.Tensor,
                            scales: torch.Tensor,
                            quats: torch.Tensor,
                            opacities: torch.Tensor,
                            colors: torch.Tensor,
                            viewmat: torch.Tensor,
                            K: torch.Tensor,
                            width: int,
                            height: int) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Simple differentiable Gaussian splatting renderer (CPU-friendly).

    Projects Gaussians and accumulates with alpha blending (back to front).

    Returns:
        render_rgb: [H, W, 3]
        render_alpha: [H, W, 1]
    """
    N = means.shape[0]
    device = means.device

    means_homo = torch.cat([means, torch.ones(N, 1, device=device)], dim=1)
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


def try_gsplat_render(means, scales, quats, opacities, colors,
                      viewmats, Ks, width, height, device):
    """
    Try to use gsplat for rendering if available.

    Returns:
        (render_colors, render_alphas) if successful, None otherwise
    """
    import os
    if os.environ.get('SKIP_GSPLAT', '').lower() in ('1', 'true', 'yes'):
        return None

    try:
        import gsplat

        actual_scales = torch.exp(scales)
        actual_opacities = torch.sigmoid(opacities)

        render_colors, render_alphas, meta = gsplat.rasterization(
            means=means,
            quats=quats,
            scales=actual_scales,
            opacities=actual_opacities,
            colors=colors,
            viewmats=viewmats,
            Ks=Ks,
            width=width,
            height=height,
            camera_model="ortho",
            packed=False,
        )
        return render_colors, render_alphas
    except Exception as e:
        print(f"  gsplat not available or failed: {e}")
        return None
