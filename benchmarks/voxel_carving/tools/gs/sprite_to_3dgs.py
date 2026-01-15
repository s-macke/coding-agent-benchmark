#!/usr/bin/env python3
"""
Convert Wing Commander ship sprites to 3D Gaussian Splatting.

Usage:
    python -m gs.sprite_to_3dgs [options]

Options:
    --output PATH       Output PLY file (default: ship_gaussians.ply)
    --iterations N      Training iterations (default: 5000)
    --num-gaussians N   Max Gaussian count (default: 5000)
    --lr FLOAT          Learning rate (default: 0.01)
    --resolution N      Voxel grid resolution for visual hull (default: 64)
    --device DEVICE     cuda or cpu (default: cuda if available)
"""

import argparse
import struct
from pathlib import Path
from typing import List, Tuple

import torch
import torch.nn.functional as F

from .constants import IMAGE_SIZE, ALPHA_THRESHOLD, SH_C0
from .sprites import load_sprites
from .camera import build_cameras, project_points_orthographic
from .render import render_gaussians_simple, try_gsplat_render

# Gaussian initialization constants
INITIAL_LOG_SCALE = -3.5  # exp(-3.5) ~ 0.03
INITIAL_OPACITY_LOGIT = 0.5  # sigmoid(0.5) ~ 0.62

# Training constants
SCALE_LR_MULTIPLIER = 0.1
QUAT_LR_MULTIPLIER = 0.1
OPACITY_LR_MULTIPLIER = 0.5
ALPHA_LOSS_WEIGHT = 0.5
OPACITY_REG_WEIGHT = 0.01
LOG_INTERVAL = 500
MAX_VIEWS_PER_ITERATION = 8

# Rendering constants
CLAMP_EPSILON = 1e-6


def carve_visual_hull(images: List[torch.Tensor],
                      viewmats: torch.Tensor,
                      Ks: torch.Tensor,
                      resolution: int = 64,
                      extent: float = 1.5) -> torch.Tensor:
    """
    Carve visual hull from silhouettes using orthographic projection.

    Returns:
        points: [N, 3] 3D points inside visual hull
    """
    coords = torch.linspace(-extent, extent, resolution)
    grid_x, grid_y, grid_z = torch.meshgrid(coords, coords, coords, indexing='ij')
    grid = torch.stack([grid_x, grid_y, grid_z], dim=-1).reshape(-1, 3)

    occupied = torch.ones(grid.shape[0], dtype=torch.bool)

    print(f"  Carving with {len(images)} views...")

    for img, viewmat, K in zip(images, viewmats, Ks):
        mask = img[:, :, 3] > ALPHA_THRESHOLD
        H, W = mask.shape

        proj_x, proj_y = project_points_orthographic(grid, viewmat, K)

        in_bounds = (proj_x >= 0) & (proj_x < W - 1) & (proj_y >= 0) & (proj_y < H - 1)

        px = proj_x.long().clamp(0, W - 1)
        py = proj_y.long().clamp(0, H - 1)

        in_silhouette = torch.zeros(grid.shape[0], dtype=torch.bool)
        in_silhouette[in_bounds] = mask[py[in_bounds], px[in_bounds]]

        occupied = occupied & in_silhouette

    points = grid[occupied]
    print(f"  Visual hull: {points.shape[0]} voxels occupied out of {grid.shape[0]}")

    return points


def init_gaussians(points: torch.Tensor,
                   images: List[torch.Tensor],
                   viewmats: torch.Tensor,
                   Ks: torch.Tensor,
                   num_gaussians: int = 5000) -> Tuple[torch.Tensor, ...]:
    """
    Initialize Gaussian parameters from point cloud.

    Returns:
        means: [N, 3] positions
        scales: [N, 3] log-scales
        quats: [N, 4] quaternions (wxyz)
        opacities: [N] logit opacities
        colors: [N, 3] RGB colors
    """
    if points.shape[0] > num_gaussians:
        idx = torch.randperm(points.shape[0])[:num_gaussians]
        points = points[idx]
    elif points.shape[0] == 0:
        print("  Warning: Visual hull empty, using random initialization")
        points = (torch.rand(num_gaussians, 3) - 0.5) * 2.0

    N = points.shape[0]

    means = points.clone()
    scales = torch.full((N, 3), INITIAL_LOG_SCALE, dtype=torch.float32)

    quats = torch.zeros((N, 4), dtype=torch.float32)
    quats[:, 0] = 1.0  # Identity quaternion (w=1)

    opacities = torch.full((N,), INITIAL_OPACITY_LOGIT, dtype=torch.float32)

    colors = torch.full((N, 3), 0.5, dtype=torch.float32)
    color_counts = torch.zeros(N, dtype=torch.float32)

    for img, viewmat, K in zip(images, viewmats, Ks):
        proj_x, proj_y = project_points_orthographic(means, viewmat, K)

        H, W = img.shape[:2]
        in_bounds = (proj_x >= 0) & (proj_x < W - 1) & (proj_y >= 0) & (proj_y < H - 1)

        px = proj_x.long().clamp(0, W - 1)
        py = proj_y.long().clamp(0, H - 1)

        alpha = img[:, :, 3]
        rgb = img[:, :, :3]

        visible = in_bounds & (alpha[py, px] > ALPHA_THRESHOLD)

        colors[visible] += rgb[py[visible], px[visible]]
        color_counts[visible] += 1

    valid_colors = color_counts > 0
    colors[valid_colors] /= color_counts[valid_colors].unsqueeze(1)

    return means, scales, quats, opacities, colors


def train_gaussians(images: List[torch.Tensor],
                    viewmats: torch.Tensor,
                    Ks: torch.Tensor,
                    init_means: torch.Tensor,
                    init_scales: torch.Tensor,
                    init_quats: torch.Tensor,
                    init_opacities: torch.Tensor,
                    init_colors: torch.Tensor,
                    num_iterations: int = 5000,
                    lr: float = 0.01,
                    device: str = 'cuda') -> Tuple[torch.Tensor, ...]:
    """Optimize Gaussian parameters to match target sprite views."""
    if device == 'cuda' and not torch.cuda.is_available():
        print("  CUDA not available, using CPU")
        device = 'cpu'

    device = torch.device(device)

    targets = torch.stack(images).to(device)
    target_rgb = targets[:, :, :, :3]
    target_alpha = targets[:, :, :, 3:4]

    viewmats = viewmats.to(device)
    Ks = Ks.to(device)

    means = init_means.clone().to(device).requires_grad_(True)
    scales = init_scales.clone().to(device).requires_grad_(True)
    quats = init_quats.clone().to(device).requires_grad_(True)
    opacities = init_opacities.clone().to(device).requires_grad_(True)
    colors = init_colors.clone().to(device).requires_grad_(True)

    optimizer = torch.optim.Adam([
        {'params': means, 'lr': lr},
        {'params': scales, 'lr': lr * SCALE_LR_MULTIPLIER},
        {'params': quats, 'lr': lr * QUAT_LR_MULTIPLIER},
        {'params': opacities, 'lr': lr * OPACITY_LR_MULTIPLIER},
        {'params': colors, 'lr': lr},
    ])

    C = viewmats.shape[0]

    gsplat_result = try_gsplat_render(
        means, scales, quats, opacities, colors,
        viewmats[:1], Ks[:1], IMAGE_SIZE, IMAGE_SIZE, device
    )
    use_gsplat = gsplat_result is not None

    print(f"  Using {'gsplat' if use_gsplat else 'simple'} renderer{'' if use_gsplat else ' (slower)'}")

    for iteration in range(num_iterations):
        optimizer.zero_grad()

        if use_gsplat:
            result = try_gsplat_render(
                means, scales, quats, opacities, colors,
                viewmats, Ks, IMAGE_SIZE, IMAGE_SIZE, device
            )
            if result is None:
                use_gsplat = False
                continue
            render_colors, render_alphas = result
            target_rgb_batch = target_rgb
            target_alpha_batch = target_alpha
        else:
            view_indices = torch.randperm(C)[:min(MAX_VIEWS_PER_ITERATION, C)]

            render_colors_list = []
            render_alphas_list = []

            for vi in view_indices:
                rc, ra = render_gaussians_simple(
                    means, scales, quats, opacities, colors,
                    viewmats[vi], Ks[vi], IMAGE_SIZE, IMAGE_SIZE
                )
                render_colors_list.append(rc)
                render_alphas_list.append(ra)

            render_colors = torch.stack(render_colors_list)
            render_alphas = torch.stack(render_alphas_list)
            target_rgb_batch = target_rgb[view_indices]
            target_alpha_batch = target_alpha[view_indices]

        rgb_loss = (torch.abs(render_colors - target_rgb_batch) * target_alpha_batch).mean()

        alpha_loss = F.binary_cross_entropy(
            render_alphas.clamp(CLAMP_EPSILON, 1 - CLAMP_EPSILON),
            target_alpha_batch,
            reduction='mean'
        )

        opacity_reg = torch.sigmoid(opacities).mean() * OPACITY_REG_WEIGHT

        loss = rgb_loss + alpha_loss * ALPHA_LOSS_WEIGHT + opacity_reg

        loss.backward()
        optimizer.step()

        with torch.no_grad():
            quats.data = F.normalize(quats.data, dim=-1)

        if iteration % LOG_INTERVAL == 0:
            print(f"  Iter {iteration}: loss={loss.item():.4f}, "
                  f"rgb={rgb_loss.item():.4f}, alpha={alpha_loss.item():.4f}")

    return (means.detach().cpu(), scales.detach().cpu(), quats.detach().cpu(),
            opacities.detach().cpu(), colors.detach().cpu())


def export_ply(means: torch.Tensor,
               scales: torch.Tensor,
               quats: torch.Tensor,
               opacities: torch.Tensor,
               colors: torch.Tensor,
               output_path: str) -> None:
    """Export Gaussians to standard PLY format compatible with 3DGS viewers."""
    N = means.shape[0]

    means_np = means.numpy()
    scales_np = scales.numpy()
    quats_np = quats.numpy()
    opacities_np = opacities.numpy()

    # Convert colors to SH DC coefficients: SH0 = (color - 0.5) / C0
    sh0_np = (colors.numpy() - 0.5) / SH_C0

    with open(output_path, 'wb') as f:
        # Header
        header = f"""ply
format binary_little_endian 1.0
element vertex {N}
property float x
property float y
property float z
property float f_dc_0
property float f_dc_1
property float f_dc_2
property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""
        f.write(header.encode())

        # Binary data
        for i in range(N):
            f.write(struct.pack('<fff', *means_np[i]))
            f.write(struct.pack('<fff', *sh0_np[i]))
            f.write(struct.pack('<f', opacities_np[i]))
            f.write(struct.pack('<fff', *scales_np[i]))
            # Convert quaternion from wxyz to xyzw format
            q = quats_np[i]
            f.write(struct.pack('<ffff', q[1], q[2], q[3], q[0]))

    print(f"Saved {N} Gaussians to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Convert sprites to 3D Gaussian Splatting')
    parser.add_argument('--output', default='ship_gaussians.ply', help='Output PLY file')
    parser.add_argument('--iterations', type=int, default=5000, help='Training iterations')
    parser.add_argument('--num-gaussians', type=int, default=5000, help='Max Gaussian count')
    parser.add_argument('--lr', type=float, default=0.01, help='Learning rate')
    parser.add_argument('--resolution', type=int, default=64, help='Voxel grid resolution')
    parser.add_argument('--device', default='cuda', help='Device (cuda or cpu)')
    parser.add_argument('--ortho-scale', type=float, default=2.0, help='Orthographic scale')
    args = parser.parse_args()

    project_dir = Path(__file__).parent.parent.parent

    print("Loading sprites and camera data...")
    images, metadata = load_sprites(
        project_dir / 'ship_sprites_centered.json',
        project_dir / 'centered_images'
    )
    print(f"  Loaded {len(images)} sprites")

    print("Building camera matrices...")
    viewmats, Ks = build_cameras(metadata, ortho_scale=args.ortho_scale)
    print(f"  Built {viewmats.shape[0]} view matrices")

    print("Carving visual hull...")
    points = carve_visual_hull(images, viewmats, Ks, resolution=args.resolution)

    print("Initializing Gaussians...")
    means, scales, quats, opacities, colors = init_gaussians(
        points, images, viewmats, Ks, num_gaussians=args.num_gaussians
    )
    print(f"  Initialized {means.shape[0]} Gaussians")

    print(f"Training for {args.iterations} iterations...")
    means, scales, quats, opacities, colors = train_gaussians(
        images, viewmats, Ks,
        means, scales, quats, opacities, colors,
        num_iterations=args.iterations,
        lr=args.lr,
        device=args.device,
    )

    output_path = project_dir / args.output
    print(f"Exporting to {output_path}...")
    export_ply(means, scales, quats, opacities, colors, str(output_path))

    print("Done!")


if __name__ == '__main__':
    main()
