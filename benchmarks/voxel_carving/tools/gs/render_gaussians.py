#!/usr/bin/env python3
"""
Render Gaussian Splats from PLY file and compare to original sprites.

Usage:
    python -m gs.render_gaussians [options]

Options:
    --input PATH        Input PLY file (default: ship_gaussians.ply)
    --output PATH       Output comparison image (default: gaussians_comparison.png)
    --device DEVICE     cuda or cpu (default: cuda if available)
    --camera-type TYPE  orthographic or perspective (default: orthographic)
    --ortho-scale FLOAT Orthographic scale (default: 2.0)
    --fov FLOAT         Perspective field of view in degrees (default: 60.0)
"""

import argparse
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import torch

from .cameras import Cameras
from .camera import CameraCollection
from .constants import IMAGE_SIZE, SPRITES_JSON, SPRITES_DIR
from .device import get_device
from .gaussians import Gaussians
from .ply import load_ply
from .sprites import load_cameras
from .render import try_gsplat_render
from .sh import eval_sh

import torch.nn.functional as F


def render_points_fast(
    gaussians: Gaussians,
    cameras: Cameras,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Fast point-based renderer using scatter_add (fully vectorized).

    Renders gaussians as colored points with depth sorting.
    Renders the first camera in the Cameras batch.

    Args:
        gaussians: Gaussians object with means, opacities, sh_coeffs
        cameras: Cameras object (uses first camera if batch)
    """
    means = gaussians.means
    opacities = gaussians.opacities
    sh_coeffs = gaussians.sh_coeffs
    sh_degree = gaussians.sh_degree

    # Get single camera
    viewmat = cameras.viewmats[0] if cameras.viewmats.dim() == 3 else cameras.viewmats
    K = cameras.Ks[0] if cameras.Ks.dim() == 3 else cameras.Ks
    width = cameras.width
    height = cameras.height
    perspective = cameras.is_perspective

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

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    depths = -cam_means[:, 2]

    if perspective:
        # Perspective projection (divide by depth)
        z = depths.clamp(min=1e-6)
        proj_x = (fx * cam_means[:, 0] / z + cx).long()
        proj_y = (fy * cam_means[:, 1] / z + cy).long()
    else:
        # Orthographic projection
        proj_x = (fx * cam_means[:, 0] + cx).long()
        proj_y = (fy * cam_means[:, 1] + cy).long()

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


def render_all_views(
    gaussians: Gaussians,
    cameras: CameraCollection,
    device: str = 'cuda',
) -> List[torch.Tensor]:
    """Render gaussian splats from all camera angles."""
    device = get_device(device)

    g = gaussians.to(device)
    cams = cameras.to_cameras().to(device)
    sh_degree = g.sh_degree

    # Check if gsplat works
    gsplat_result = try_gsplat_render(g, cams[:1])
    use_gsplat = gsplat_result is not None

    if use_gsplat:
        print(f"  Using gsplat renderer (SH degree {sh_degree})")
    else:
        proj_type = "perspective" if cams.is_perspective else "orthographic"
        print(f"  Using fast point renderer ({proj_type}, SH degree {sh_degree})")

    renders = []
    num_views = len(cams)

    if use_gsplat:
        # Render all views at once with gsplat
        result = try_gsplat_render(g, cams)
        if result is not None:
            render_colors, render_alphas = result
            for i in range(num_views):
                rgba = torch.cat([render_colors[i], render_alphas[i]], dim=-1)
                renders.append(rgba.cpu())
        else:
            use_gsplat = False

    if not use_gsplat:
        # Use fast point renderer
        for i in range(num_views):
            print(f"  Rendering view {i + 1}/{num_views}...", end='\r')
            rgb, alpha = render_points_fast(g, cams[i])
            rgba = torch.cat([rgb, alpha], dim=-1)
            renders.append(rgba.cpu())
        print()

    return renders


def create_comparison_grid(
    originals: List[torch.Tensor],
    renders: List[torch.Tensor],
    output_path: str,
) -> None:
    """Create side-by-side comparison grid and save to file."""
    num_images = len(originals)

    # Layout: 6 columns x 7 rows for 37 views (+ 5 empty)
    cols = 6
    rows = 7

    # Each cell shows original (left) and rendered (right)
    fig, axes = plt.subplots(rows, cols * 2, figsize=(cols * 4, rows * 2))
    fig.suptitle('Original (left) vs Rendered Gaussians (right)', fontsize=14)

    for idx in range(rows * cols):
        row = idx // cols
        col = idx % cols

        ax_orig = axes[row, col * 2]
        ax_render = axes[row, col * 2 + 1]

        if idx < num_images:
            # Original sprite
            orig_img = originals[idx].numpy()
            ax_orig.imshow(orig_img)
            ax_orig.set_title(f'#{idx}', fontsize=8)

            # Rendered gaussian
            render_img = renders[idx].numpy()
            render_img = np.clip(render_img, 0, 1)
            ax_render.imshow(render_img)

        ax_orig.axis('off')
        ax_render.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Saved comparison grid to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Render Gaussian Splats from PLY')
    parser.add_argument('--input', default='ship_gaussians.ply', help='Input PLY file')
    parser.add_argument('--output', default='gaussians_comparison.png', help='Output image')
    parser.add_argument('--device', default='cuda', help='Device (cuda or cpu)')
    parser.add_argument('--camera-type', choices=['orthographic', 'perspective'],
                        default='orthographic', help='Camera projection type')
    parser.add_argument('--ortho-scale', type=float, default=2.0,
                        help='Orthographic scale (only for orthographic camera)')
    parser.add_argument('--fov', type=float, default=60.0,
                        help='Field of view in degrees (only for perspective camera)')
    args = parser.parse_args()

    project_dir = Path(__file__).parent.parent.parent

    # Load gaussians from PLY
    ply_path = project_dir / args.input
    print(f"Loading gaussians from {ply_path}...")
    gaussians = load_ply(str(ply_path))
    print(f"  Loaded {gaussians.num_gaussians} gaussians ({gaussians.sh_coeffs.shape[1]} SH coefficients)")

    # Load sprites and build cameras
    print("Loading sprites and cameras...")
    cameras = load_cameras(
        project_dir / SPRITES_JSON,
        project_dir / SPRITES_DIR,
        camera_type=args.camera_type,
        ortho_scale=args.ortho_scale,
        fov_deg=args.fov,
    )
    print(f"  Loaded {len(cameras)} cameras")

    # Render all views
    print("Rendering gaussian splats...")
    renders = render_all_views(gaussians, cameras, device=args.device)

    # Create comparison grid
    output_path = project_dir / args.output
    print(f"Creating comparison grid...")
    create_comparison_grid(cameras.images, renders, str(output_path))

    print("Done!")


if __name__ == '__main__':
    main()
