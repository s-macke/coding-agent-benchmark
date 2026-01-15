#!/usr/bin/env python3
"""
Render Gaussian Splats from PLY file and compare to original sprites.

Usage:
    python -m gs.render_gaussians [options]

Options:
    --input PATH        Input PLY file (default: ship_gaussians.ply)
    --output PATH       Output comparison image (default: gaussians_comparison.png)
    --device DEVICE     cuda or cpu (default: cuda if available)
"""

import argparse
import struct
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import torch

from .constants import IMAGE_SIZE, SH_C0
from .sprites import load_sprites
from .camera import build_cameras
from .render import try_gsplat_render


def load_ply(path: str) -> Tuple[torch.Tensor, ...]:
    """
    Load gaussian parameters from PLY file.

    Returns:
        means: [N, 3] positions
        scales: [N, 3] log-scales
        quats: [N, 4] quaternions (wxyz)
        opacities: [N] logit opacities
        colors: [N, 3] RGB colors
    """
    with open(path, 'rb') as f:
        # Parse header
        line = f.readline().decode().strip()
        if line != 'ply':
            raise ValueError(f"Not a PLY file: {path}")

        num_vertices = 0
        while True:
            line = f.readline().decode().strip()
            if line.startswith('element vertex'):
                num_vertices = int(line.split()[-1])
            elif line == 'end_header':
                break

        if num_vertices == 0:
            raise ValueError("No vertices found in PLY file")

        # Read binary data: 14 floats per gaussian
        # xyz, f_dc_0-2, opacity, scale_0-2, rot_0-3
        means = np.zeros((num_vertices, 3), dtype=np.float32)
        sh_dc = np.zeros((num_vertices, 3), dtype=np.float32)
        opacities = np.zeros(num_vertices, dtype=np.float32)
        scales = np.zeros((num_vertices, 3), dtype=np.float32)
        quats = np.zeros((num_vertices, 4), dtype=np.float32)

        for i in range(num_vertices):
            data = struct.unpack('<14f', f.read(14 * 4))
            means[i] = data[0:3]
            sh_dc[i] = data[3:6]
            opacities[i] = data[6]
            scales[i] = data[7:10]
            # Convert quaternion from xyzw (file) to wxyz (internal)
            quats[i] = [data[13], data[10], data[11], data[12]]  # w, x, y, z

    # Convert SH DC back to RGB: color = sh * C0 + 0.5
    colors = sh_dc * SH_C0 + 0.5
    colors = np.clip(colors, 0, 1)

    return (
        torch.from_numpy(means),
        torch.from_numpy(scales),
        torch.from_numpy(quats),
        torch.from_numpy(opacities),
        torch.from_numpy(colors),
    )


def render_points_fast(
    means: torch.Tensor,
    opacities: torch.Tensor,
    colors: torch.Tensor,
    viewmat: torch.Tensor,
    K: torch.Tensor,
    width: int,
    height: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Fast point-based renderer using scatter_add (fully vectorized).

    Renders gaussians as colored points with depth sorting.
    """
    device = means.device
    N = means.shape[0]

    # Transform to camera space
    means_homo = torch.cat([means, torch.ones(N, 1, device=device)], dim=1)
    cam_means = (viewmat @ means_homo.T).T[:, :3]

    # Orthographic projection
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = (fx * cam_means[:, 0] + cx).long()
    proj_y = (fy * cam_means[:, 1] + cy).long()
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


def render_all_views(
    means: torch.Tensor,
    scales: torch.Tensor,
    quats: torch.Tensor,
    opacities: torch.Tensor,
    colors: torch.Tensor,
    viewmats: torch.Tensor,
    Ks: torch.Tensor,
    device: str = 'cuda',
) -> List[torch.Tensor]:
    """Render gaussian splats from all camera angles."""
    if device == 'cuda' and not torch.cuda.is_available():
        print("  CUDA not available, using CPU")
        device = 'cpu'

    device = torch.device(device)

    means = means.to(device)
    scales = scales.to(device)
    quats = quats.to(device)
    opacities = opacities.to(device)
    colors = colors.to(device)
    viewmats = viewmats.to(device)
    Ks = Ks.to(device)

    # Check if gsplat works
    gsplat_result = try_gsplat_render(
        means, scales, quats, opacities, colors,
        viewmats[:1], Ks[:1], IMAGE_SIZE, IMAGE_SIZE, device
    )
    use_gsplat = gsplat_result is not None

    if use_gsplat:
        print("  Using gsplat renderer")
    else:
        print("  Using fast point renderer (gsplat not available)")

    renders = []
    num_views = viewmats.shape[0]

    if use_gsplat:
        # Render all views at once with gsplat
        result = try_gsplat_render(
            means, scales, quats, opacities, colors,
            viewmats, Ks, IMAGE_SIZE, IMAGE_SIZE, device
        )
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
            rgb, alpha = render_points_fast(
                means, opacities, colors,
                viewmats[i], Ks[i], IMAGE_SIZE, IMAGE_SIZE
            )
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
    parser.add_argument('--ortho-scale', type=float, default=2.0, help='Orthographic scale')
    args = parser.parse_args()

    project_dir = Path(__file__).parent.parent.parent

    # Load gaussians from PLY
    ply_path = project_dir / args.input
    print(f"Loading gaussians from {ply_path}...")
    means, scales, quats, opacities, colors = load_ply(str(ply_path))
    print(f"  Loaded {means.shape[0]} gaussians")

    # Load original sprites and camera data
    print("Loading sprites and camera data...")
    images, metadata = load_sprites(
        project_dir / 'ship_sprites_centered.json',
        project_dir / 'centered_images'
    )
    print(f"  Loaded {len(images)} sprites")

    # Build camera matrices
    print("Building camera matrices...")
    viewmats, Ks = build_cameras(metadata, ortho_scale=args.ortho_scale)

    # Render all views
    print("Rendering gaussian splats...")
    renders = render_all_views(
        means, scales, quats, opacities, colors,
        viewmats, Ks, device=args.device
    )

    # Create comparison grid
    output_path = project_dir / args.output
    print(f"Creating comparison grid...")
    create_comparison_grid(images, renders, str(output_path))

    print("Done!")


if __name__ == '__main__':
    main()
