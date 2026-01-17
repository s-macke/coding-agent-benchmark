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
from dataclasses import dataclass
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import torch

from .camera import CameraCollection, CameraType
from .constants import SPRITES_JSON, SPRITES_DIR
from .device import get_device
from .gaussians import Gaussians
from .ply import load_ply
from .sprites import load_cameras
from .render import render_gaussians


@dataclass
class RenderArgs:
    """Command-line arguments for rendering."""
    input: str
    output: str
    device: str
    camera_type: CameraType
    ortho_scale: float
    fov: float


def parse_args() -> RenderArgs:
    """Parse command-line arguments."""
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

    return RenderArgs(
        input=args.input,
        output=args.output,
        device=args.device,
        camera_type=CameraType(args.camera_type),
        ortho_scale=args.ortho_scale,
        fov=args.fov,
    )


def render_all_views(
    gaussians: Gaussians,
    cameras: CameraCollection,
    device: str = 'cuda',
) -> List[torch.Tensor]:
    """Render gaussian splats from all camera angles."""
    device = get_device(device)

    g = gaussians.to(device)
    cams = cameras.to_cameras().to(device)
    num_views = len(cams)

    renders = []
    for i in range(num_views):
        print(f"  Rendering view {i + 1}/{num_views}...", end='\r')
        rgb, alpha = render_gaussians(g, cams[i])
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
    args = parse_args()
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
