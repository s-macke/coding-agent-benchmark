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

from pathlib import Path

import torch
import torch.nn.functional as F

from .cameras import Cameras
from .constants import SPRITES_JSON, SPRITES_DIR
from .device import get_device
from .gaussians import Gaussians, export_ply
from .sprites import load_cameras
from .camera import CameraCollection, CameraOptModule
from .render_simple import render_gaussians_simple
from .render_gsplat import render_gsplat
from .train_args import TrainConfig, parse_args
from .voxel_carving import initialize_from_visual_hull

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


def train_gaussians(
    cameras: CameraCollection,
    init_gaussians: Gaussians,
    config: TrainConfig,
) -> Gaussians:
    """
    Optimize Gaussian parameters to match target sprite views.

    Args:
        cameras: camera collection with images
        init_gaussians: initial Gaussians to optimize
        config: training configuration

    Returns:
        Optimized Gaussians object
    """
    device = get_device(config.device)
    sh_degree = init_gaussians.sh_degree

    images = cameras.images
    targets = torch.stack(images).to(device)
    target_rgb = targets[:, :, :, :3]
    target_alpha = targets[:, :, :, 3:4]

    # Convert cameras to Cameras dataclass
    cams = cameras.to_cameras().to(device)

    means = init_gaussians.means.clone().to(device)
    if not config.fix_positions:
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
        {'params': scales, 'lr': config.lr * SCALE_LR_MULTIPLIER},
        {'params': quats, 'lr': config.lr * QUAT_LR_MULTIPLIER},
        {'params': opacities, 'lr': config.lr * OPACITY_LR_MULTIPLIER},
        {'params': sh0, 'lr': config.lr * SH0_LR_MULTIPLIER},
        {'params': shN, 'lr': config.lr * SHN_LR_MULTIPLIER},
    ]
    if not config.fix_positions:
        param_groups.insert(0, {'params': means, 'lr': config.lr})
    else:
        print("  Gaussian positions fixed")

    optimizer = torch.optim.Adam(param_groups)

    num_views = len(cams)

    # Setup camera pose optimization if enabled
    pose_adjust = None
    pose_optimizer = None
    if config.pose_opt:
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
    gsplat_result = render_gsplat(test_gaussians, cams[:1])
    use_gsplat = gsplat_result is not None

    print(f"  Using {'gsplat' if use_gsplat else 'simple'} renderer "
          f"(SH degree {sh_degree}){'' if use_gsplat else ' (slower)'}")

    for iteration in range(config.num_iterations):
        optimizer.zero_grad()
        if pose_optimizer is not None:
            pose_optimizer.zero_grad()

        # Concatenate SH coefficients and create Gaussians for rendering
        sh_full = torch.cat([sh0, shN], dim=1)
        current_gaussians = Gaussians(means, scales, quats, opacities, sh_full)

        if use_gsplat:
            # Apply pose adjustment if enabled
            current_cams = cams
            if pose_adjust is not None:
                camera_ids = torch.arange(num_views, device=device)
                adjusted_viewmats = pose_adjust.forward_viewmats(cams.viewmats, camera_ids)
                current_cams = Cameras(
                    viewmats=adjusted_viewmats,
                    Ks=cams.Ks,
                    camera_model=cams.camera_model,
                    width=cams.width,
                    height=cams.height,
                )

            result = render_gsplat(current_gaussians, current_cams)
            render_colors, render_alphas = result
            target_rgb_batch = target_rgb
            target_alpha_batch = target_alpha
        else:
            view_indices = torch.randperm(num_views)[:min(MAX_VIEWS_PER_ITERATION, num_views)]

            render_colors_list = []
            render_alphas_list = []

            for vi in view_indices:
                # Apply pose adjustment if enabled
                current_viewmat = cams.viewmats[vi]
                if pose_adjust is not None:
                    camera_id = torch.tensor(vi.item(), device=device)
                    current_viewmat = pose_adjust.forward_viewmats(
                        cams.viewmats[vi].unsqueeze(0), camera_id.unsqueeze(0)
                    ).squeeze(0)

                # Create single-camera Cameras object
                single_cam = Cameras(
                    viewmats=current_viewmat.unsqueeze(0),
                    Ks=cams.Ks[vi].unsqueeze(0),
                    camera_model=cams.camera_model,
                    width=cams.width,
                    height=cams.height,
                )
                rc, ra = render_gaussians_simple(current_gaussians, single_cam)
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
    args = parse_args()
    project_dir = Path(__file__).parent.parent.parent

    print("Loading sprites and cameras...")
    cameras = load_cameras(
        project_dir / SPRITES_JSON,
        project_dir / SPRITES_DIR,
        camera_type=args.camera_type,
        ortho_scale=args.ortho_scale,
        fov_deg=args.fov,
    )
    print(f"  Loaded {len(cameras)} cameras")

    gaussians = initialize_from_visual_hull(
        cameras,
        resolution=args.resolution,
        num_gaussians=args.num_gaussians,
    )

    print(f"Training for {args.train.num_iterations} iterations...")
    gaussians = train_gaussians(cameras, gaussians, args.train)

    output_path = project_dir / args.output
    print(f"Exporting to {output_path}...")
    export_ply(gaussians, str(output_path))

    print("Done!")


if __name__ == '__main__':
    main()
