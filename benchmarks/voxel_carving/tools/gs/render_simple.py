"""Simple differentiable Gaussian splatting renderer."""

from typing import Tuple

import torch
import torch.nn.functional as F

from .cameras import Cameras
from .gaussians import Gaussians
from .projection import project_points
from .sh import eval_sh

# Rendering constants
MIN_SIGMA = 0.5
MIN_WEIGHT_THRESHOLD = 0.001
CLAMP_EPSILON = 1e-6


def render_gaussians_simple(
    gaussians: Gaussians,
    cameras: Cameras,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Simple differentiable Gaussian splatting renderer (CPU-friendly).

    Projects Gaussians and accumulates with alpha blending (back to front).
    Renders the first camera in the Cameras batch.

    Args:
        gaussians: Gaussians object with means, scales, quats, opacities, sh_coeffs
        cameras: Cameras object (uses first camera if batch)

    Returns:
        render_rgb: [H, W, 3]
        render_alpha: [H, W, 1]
    """
    means = gaussians.means
    scales = gaussians.scales
    opacities = gaussians.opacities
    sh_coeffs = gaussians.sh_coeffs
    sh_degree = gaussians.sh_degree

    # Get single camera viewmat and K
    viewmat = cameras.viewmats[0] if cameras.viewmats.dim() == 3 else cameras.viewmats
    K = cameras.Ks[0] if cameras.Ks.dim() == 3 else cameras.Ks
    width = cameras.width
    height = cameras.height

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
    proj_x, proj_y = project_points(cam_means, K, cameras.is_perspective)
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
