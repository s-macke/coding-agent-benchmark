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
    --camera-type TYPE  orthographic or perspective (default: orthographic)
    --ortho-scale FLOAT Orthographic scale (default: 2.0)
    --fov FLOAT         Perspective field of view in degrees (default: 60.0)
"""

import argparse
from pathlib import Path
from typing import List

import torch
import torch.nn.functional as F

from .constants import IMAGE_SIZE, ALPHA_THRESHOLD, SPRITES_JSON, SPRITES_DIR, SH_DEGREE
from .device import get_device
from .gaussians import Gaussians
from .ply import export_ply
from .sprites import load_sprites
from .camera import CameraCollection, CameraOptModule
from .render import render_gaussians_simple, try_gsplat_render
from .sh import init_sh_from_rgb
from .voxel_carving import carve_visual_hull

# Gaussian initialization constants
INITIAL_LOG_SCALE = -3.5  # exp(-3.5) ~ 0.03
INITIAL_OPACITY_LOGIT = 0.5  # sigmoid(0.5) ~ 0.62

# Training constants
SCALE_LR_MULTIPLIER = 0.1
QUAT_LR_MULTIPLIER = 0.1
OPACITY_LR_MULTIPLIER = 0.5
SH0_LR_MULTIPLIER = 0.25  # DC term learning rate multiplier
SHN_LR_MULTIPLIER = 0.0125  # Higher-order SH (1/20 of SH0, from gsplat)
ALPHA_LOSS_WEIGHT = 0.5
OPACITY_REG_WEIGHT = 0.01
LOG_INTERVAL = 500
MAX_VIEWS_PER_ITERATION = 8

# Camera pose optimization constants
POSE_OPT_LR = 1e-5  # Base learning rate for pose optimization
POSE_OPT_WEIGHT_DECAY = 1e-6  # Regularization for pose parameters

# Rendering constants
CLAMP_EPSILON = 1e-6


def init_gaussians(
    points: torch.Tensor,
    images: List[torch.Tensor],
    cameras: CameraCollection,
    num_gaussians: int = 5000,
    sh_degree: int = SH_DEGREE,
) -> Gaussians:
    """
    Initialize Gaussian parameters from point cloud.

    Args:
        points: [M, 3] candidate positions from visual hull
        images: list of [H, W, 4] RGBA images
        cameras: camera collection
        num_gaussians: maximum number of Gaussians
        sh_degree: spherical harmonics degree

    Returns:
        Gaussians object with initialized parameters
    """
    if points.shape[0] > num_gaussians:
        idx = torch.randperm(points.shape[0])[:num_gaussians]
        points = points[idx]
    elif points.shape[0] == 0:
        print("  Warning: Visual hull empty, using random initialization")
        points = (torch.rand(num_gaussians, 3) - 0.5) * 2.0

    n = points.shape[0]

    means = points.clone()
    scales = torch.full((n, 3), INITIAL_LOG_SCALE, dtype=torch.float32)

    quats = torch.zeros((n, 4), dtype=torch.float32)
    quats[:, 0] = 1.0  # Identity quaternion (w=1)

    opacities = torch.full((n,), INITIAL_OPACITY_LOGIT, dtype=torch.float32)

    # Accumulate colors from visible views
    colors = torch.full((n, 3), 0.5, dtype=torch.float32)
    color_counts = torch.zeros(n, dtype=torch.float32)

    for img, camera in zip(images, cameras):
        proj_x, proj_y = camera.project(means)

        h, w = img.shape[:2]
        in_bounds = (proj_x >= 0) & (proj_x < w - 1) & (proj_y >= 0) & (proj_y < h - 1)

        px = proj_x.long().clamp(0, w - 1)
        py = proj_y.long().clamp(0, h - 1)

        alpha = img[:, :, 3]
        rgb = img[:, :, :3]

        visible = in_bounds & (alpha[py, px] > ALPHA_THRESHOLD)

        colors[visible] += rgb[py[visible], px[visible]]
        color_counts[visible] += 1

    valid_colors = color_counts > 0
    colors[valid_colors] /= color_counts[valid_colors].unsqueeze(1)

    # Convert RGB to SH coefficients (DC term only, higher orders = 0)
    sh_coeffs = init_sh_from_rgb(colors, sh_degree=sh_degree)

    return Gaussians(
        means=means,
        scales=scales,
        quats=quats,
        opacities=opacities,
        sh_coeffs=sh_coeffs,
    )


def train_gaussians(
    images: List[torch.Tensor],
    cameras: CameraCollection,
    init_gaussians: Gaussians,
    num_iterations: int = 5000,
    lr: float = 0.01,
    device: str = 'cuda',
    pose_opt: bool = False,
    fix_positions: bool = False,
) -> Gaussians:
    """
    Optimize Gaussian parameters to match target sprite views.

    Args:
        images: list of [H, W, 4] target RGBA images
        cameras: camera collection
        init_gaussians: initial Gaussians to optimize
        num_iterations: training iterations
        lr: base learning rate
        device: cuda or cpu
        pose_opt: if True, also optimize camera poses
        fix_positions: if True, keep Gaussian positions fixed

    Returns:
        Optimized Gaussians object
    """
    device = get_device(device)
    sh_degree = init_gaussians.sh_degree

    targets = torch.stack(images).to(device)
    target_rgb = targets[:, :, :, :3]
    target_alpha = targets[:, :, :, 3:4]

    # Get stacked tensors for batch rendering
    viewmats = cameras.viewmats.to(device)
    intrinsics = cameras.Ks.to(device)

    means = init_gaussians.means.clone().to(device)
    if not fix_positions:
        means.requires_grad_(True)
    scales = init_gaussians.scales.clone().to(device).requires_grad_(True)
    quats = init_gaussians.quats.clone().to(device).requires_grad_(True)
    opacities = init_gaussians.opacities.clone().to(device).requires_grad_(True)

    # Split SH coefficients into DC (sh0) and higher order (shN)
    sh_coeffs = init_gaussians.sh_coeffs.clone().to(device)
    sh0 = sh_coeffs[:, :1, :].clone().requires_grad_(True)  # [N, 1, 3]
    shN = sh_coeffs[:, 1:, :].clone().requires_grad_(True)  # [N, K-1, 3]

    # Build optimizer param groups
    param_groups = [
        {'params': scales, 'lr': lr * SCALE_LR_MULTIPLIER},
        {'params': quats, 'lr': lr * QUAT_LR_MULTIPLIER},
        {'params': opacities, 'lr': lr * OPACITY_LR_MULTIPLIER},
        {'params': sh0, 'lr': lr * SH0_LR_MULTIPLIER},
        {'params': shN, 'lr': lr * SHN_LR_MULTIPLIER},
    ]
    if not fix_positions:
        param_groups.insert(0, {'params': means, 'lr': lr})
    else:
        print("  Gaussian positions fixed")

    optimizer = torch.optim.Adam(param_groups)

    num_views = viewmats.shape[0]

    # Setup camera pose optimization if enabled
    pose_adjust = None
    pose_optimizer = None
    if pose_opt:
        import math
        pose_adjust = CameraOptModule(num_views).to(device)
        pose_adjust.zero_init()
        pose_optimizer = torch.optim.Adam(
            pose_adjust.parameters(),
            lr=POSE_OPT_LR * math.sqrt(num_views),
            weight_decay=POSE_OPT_WEIGHT_DECAY,
        )
        print(f"  Camera pose optimization enabled ({num_views} cameras)")

    # Test if gsplat works
    sh_full = torch.cat([sh0, shN], dim=1)
    test_gaussians = Gaussians(means, scales, quats, opacities, sh_full)
    gsplat_result = try_gsplat_render(
        test_gaussians, viewmats[:1], intrinsics[:1], IMAGE_SIZE, IMAGE_SIZE,
    )
    use_gsplat = gsplat_result is not None

    print(f"  Using {'gsplat' if use_gsplat else 'simple'} renderer "
          f"(SH degree {sh_degree}){'' if use_gsplat else ' (slower)'}")

    for iteration in range(num_iterations):
        optimizer.zero_grad()
        if pose_optimizer is not None:
            pose_optimizer.zero_grad()

        # Concatenate SH coefficients and create Gaussians for rendering
        sh_full = torch.cat([sh0, shN], dim=1)
        current_gaussians = Gaussians(means, scales, quats, opacities, sh_full)

        if use_gsplat:
            # Apply pose adjustment if enabled
            current_viewmats = viewmats
            if pose_adjust is not None:
                camera_ids = torch.arange(num_views, device=device)
                current_viewmats = pose_adjust.forward_viewmats(viewmats, camera_ids)

            result = try_gsplat_render(
                current_gaussians, current_viewmats, intrinsics, IMAGE_SIZE, IMAGE_SIZE,
            )
            if result is None:
                use_gsplat = False
                continue
            render_colors, render_alphas = result
            target_rgb_batch = target_rgb
            target_alpha_batch = target_alpha
        else:
            view_indices = torch.randperm(num_views)[:min(MAX_VIEWS_PER_ITERATION, num_views)]

            render_colors_list = []
            render_alphas_list = []

            for vi in view_indices:
                # Apply pose adjustment if enabled
                current_viewmat = viewmats[vi]
                if pose_adjust is not None:
                    camera_id = torch.tensor(vi.item(), device=device)
                    current_viewmat = pose_adjust.forward_viewmats(
                        viewmats[vi].unsqueeze(0), camera_id.unsqueeze(0)
                    ).squeeze(0)

                rc, ra = render_gaussians_simple(
                    current_gaussians, current_viewmat, intrinsics[vi], IMAGE_SIZE, IMAGE_SIZE,
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
        if pose_optimizer is not None:
            pose_optimizer.step()

        with torch.no_grad():
            quats.data = F.normalize(quats.data, dim=-1)

        if iteration % LOG_INTERVAL == 0:
            print(f"  Iter {iteration}: loss={loss.item():.4f}, "
                  f"rgb={rgb_loss.item():.4f}, alpha={alpha_loss.item():.4f}")

    # Reconstruct full SH coefficients
    sh_coeffs_out = torch.cat([sh0, shN], dim=1)

    return Gaussians(
        means=means.detach().cpu(),
        scales=scales.detach().cpu(),
        quats=quats.detach().cpu(),
        opacities=opacities.detach().cpu(),
        sh_coeffs=sh_coeffs_out.detach().cpu(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description='Convert sprites to 3D Gaussian Splatting')
    parser.add_argument('--output', default='ship_gaussians.ply', help='Output PLY file')
    parser.add_argument('--iterations', type=int, default=5000, help='Training iterations')
    parser.add_argument('--num-gaussians', type=int, default=5000, help='Max Gaussian count')
    parser.add_argument('--lr', type=float, default=0.01, help='Learning rate')
    parser.add_argument('--resolution', type=int, default=64, help='Voxel grid resolution')
    parser.add_argument('--device', default='cuda', help='Device (cuda or cpu)')
    parser.add_argument('--camera-type', choices=['orthographic', 'perspective'],
                        default='orthographic', help='Camera projection type')
    parser.add_argument('--ortho-scale', type=float, default=2.0,
                        help='Orthographic scale (only for orthographic camera)')
    parser.add_argument('--fov', type=float, default=60.0,
                        help='Field of view in degrees (only for perspective camera)')
    parser.add_argument('--pose-opt', action='store_true',
                        help='Enable camera pose optimization during training')
    parser.add_argument('--fix-positions', action='store_true',
                        help='Keep Gaussian positions fixed during training')
    args = parser.parse_args()

    project_dir = Path(__file__).parent.parent.parent

    print("Loading sprites and camera data...")
    images, metadata = load_sprites(
        project_dir / SPRITES_JSON,
        project_dir / SPRITES_DIR
    )
    print(f"  Loaded {len(images)} sprites")

    print(f"Building {args.camera_type} cameras...")
    cameras = CameraCollection.from_metadata(
        metadata,
        camera_type=args.camera_type,
        ortho_scale=args.ortho_scale,
        fov_deg=args.fov,
    )
    print(f"  Built {len(cameras)} cameras")

    print("Carving visual hull...")
    points = carve_visual_hull(images, cameras, resolution=args.resolution)

    print("Initializing Gaussians...")
    gaussians = init_gaussians(
        points, images, cameras, num_gaussians=args.num_gaussians
    )
    print(f"  Initialized {gaussians.num_gaussians} Gaussians (SH degree {gaussians.sh_degree})")

    print(f"Training for {args.iterations} iterations...")
    gaussians = train_gaussians(
        images, cameras, gaussians,
        num_iterations=args.iterations,
        lr=args.lr,
        device=args.device,
        pose_opt=args.pose_opt,
        fix_positions=args.fix_positions,
    )

    output_path = project_dir / args.output
    print(f"Exporting to {output_path}...")
    export_ply(gaussians, str(output_path))

    print("Done!")


if __name__ == '__main__':
    main()
