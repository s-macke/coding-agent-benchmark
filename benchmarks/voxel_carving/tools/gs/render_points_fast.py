"""Fast point-based Gaussian renderer."""

from typing import Tuple

import torch
import torch.nn.functional as F

from .cameras import Cameras
from .gaussians import Gaussians, eval_sh
from .projection import project_points


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
    opacities = gaussians.opacities
    sh_coeffs = gaussians.sh_coeffs
    sh_degree = gaussians.sh_degree

    device = means.device
    n = means.shape[0]

    # Compute camera position for SH evaluation
    rot = viewmat[:3, :3]
    trans = viewmat[:3, 3]
    camera_pos = -rot.T @ trans

    # Compute viewing directions (Gaussian to camera)
    view_dirs = camera_pos.unsqueeze(0) - means  # [N, 3]
    view_dirs = F.normalize(view_dirs, dim=-1)

    # Evaluate SH to get colors
    colors = eval_sh(sh_coeffs, view_dirs, degree=sh_degree)  # [N, 3]

    # Transform to camera space
    means_homo = torch.cat([means, torch.ones(n, 1, device=device)], dim=1)
    cam_means = (viewmat @ means_homo.T).T[:, :3]

    # Project to pixel coordinates
    proj_x, proj_y = project_points(cam_means, K, is_perspective)
    proj_x = proj_x.long()
    proj_y = proj_y.long()
    depths = -cam_means[:, 2]

    # Filter to valid pixels
    valid = (proj_x >= 0) & (proj_x < width) & (proj_y >= 0) & (proj_y < height)
    proj_x = proj_x[valid]
    proj_y = proj_y[valid]
    depths = depths[valid]
    valid_colors = colors[valid]
    valid_opacities = torch.sigmoid(opacities[valid])

    # Initialize output with white background
    render_rgb = torch.ones(height, width, 3, device=device)
    render_alpha = torch.zeros(height, width, 1, device=device)

    flat_rgb = render_rgb.view(-1, 3)
    flat_alpha = render_alpha.view(-1, 1)

    # Sort back-to-front and paint (last write wins = frontmost on top)
    back_to_front = torch.argsort(depths, descending=True)
    px_btf = proj_x[back_to_front]
    py_btf = proj_y[back_to_front]
    colors_btf = valid_colors[back_to_front]
    opacities_btf = valid_opacities[back_to_front]

    pixel_idx = py_btf * width + px_btf
    flat_rgb[pixel_idx] = colors_btf
    flat_alpha[pixel_idx] = opacities_btf.unsqueeze(1)

    render_rgb = flat_rgb.view(height, width, 3)
    render_alpha = flat_alpha.view(height, width, 1)

    return render_rgb, render_alpha


def render_points_fast(
    gaussians: Gaussians,
    cameras: Cameras,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Fast point-based renderer using scatter_add (fully vectorized).

    Renders gaussians as colored points with depth sorting.
    Supports batched cameras.

    Args:
        gaussians: Gaussians object with means, opacities, sh_coeffs
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
