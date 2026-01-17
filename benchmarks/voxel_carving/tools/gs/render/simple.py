"""Simple differentiable Gaussian splatting renderer."""

from typing import Tuple

import torch
import torch.nn.functional as F

from ..cameras import Cameras
from ..gaussians import Gaussians, eval_sh
from .projection import project_points

# Rendering constants
MIN_SIGMA = 0.5
MIN_WEIGHT_THRESHOLD = 0.001
CLAMP_EPSILON = 1e-6


def _render_single(
    gaussians: Gaussians,
    viewmat: torch.Tensor,
    K: torch.Tensor,
    width: int,
    height: int,
    is_perspective: bool,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Render a single camera view."""
    means = gaussians.means
    scales = gaussians.scales
    opacities = gaussians.opacities
    sh_coeffs = gaussians.sh_coeffs
    sh_degree = gaussians.sh_degree

    n = means.shape[0]
    device = means.device

    # Compute camera position from view matrix
    rot = viewmat[:3, :3]
    trans = viewmat[:3, 3]
    camera_pos = -rot.T @ trans

    # Compute viewing directions (Gaussian to camera, normalized)
    view_dirs = camera_pos.unsqueeze(0) - means  # [N, 3]
    view_dirs = F.normalize(view_dirs, dim=-1)

    # Evaluate SH to get colors
    colors = eval_sh(sh_coeffs, view_dirs, degree=sh_degree)  # [N, 3]

    # Transform to camera space
    means_homo = torch.cat([means, torch.ones(n, 1, device=device)], dim=1)
    cam_means = (viewmat @ means_homo.T).T[:, :3]

    # Project to pixel coordinates
    proj_x, proj_y = project_points(cam_means, K, is_perspective)
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

    fx = K[0, 0]

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


def render_gaussians_simple(
    gaussians: Gaussians,
    cameras: Cameras,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Simple differentiable Gaussian splatting renderer (CPU-friendly).

    Projects Gaussians and accumulates with alpha blending (back to front).
    Supports batched cameras.

    Args:
        gaussians: Gaussians object with means, scales, quats, opacities, sh_coeffs
        cameras: Cameras object (single or batch)

    Returns:
        render_rgb: [N, H, W, 3] for batched, [H, W, 3] for single
        render_alpha: [N, H, W, 1] for batched, [H, W, 1] for single
    """
    width = cameras.width
    height = cameras.height
    is_perspective = cameras.is_perspective

    # Check if batched
    if cameras.viewmats.dim() == 2:
        # Single camera
        return _render_single(
            gaussians, cameras.viewmats, cameras.Ks, width, height, is_perspective
        )

    # Batched cameras
    num_cameras = cameras.viewmats.shape[0]
    results_rgb = []
    results_alpha = []

    for i in range(num_cameras):
        rgb, alpha = _render_single(
            gaussians, cameras.viewmats[i], cameras.Ks[i], width, height, is_perspective
        )
        results_rgb.append(rgb)
        results_alpha.append(alpha)

    return torch.stack(results_rgb), torch.stack(results_alpha)
