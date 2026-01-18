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

import math
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from .cameras import Cameras
from .constants import SPRITES_JSON, SPRITES_DIR
from .device import get_device
from .gaussians import Gaussians, export_ply, expand_symmetric, filter_positive_y
from .sprites import load_cameras
from .camera import CameraCollection, CameraOptModule, rotation_6d_to_matrix
from .losses import ssim
from .render import render_gaussians, render_gaussians_simple, render_gsplat
from .train_args import LossType, TrainConfig, parse_args
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
CHECKPOINT_INTERVAL = 5000

# Camera pose optimization constants
POSE_OPT_LR = 1e-5  # Base learning rate for pose optimization
POSE_OPT_WEIGHT_DECAY = 1e-6  # Regularization for pose parameters

# Rendering constants
CLAMP_EPSILON = 1e-6


def render_all_views(
    gaussians: Gaussians,
    cameras: CameraCollection,
    render_dir: Path,
    device: torch.device,
    resolution: int = 512,
) -> None:
    """Render all camera views and save as PNG images.

    Args:
        gaussians: Gaussian splat model to render
        cameras: camera collection defining viewpoints
        render_dir: directory to save rendered images
        device: torch device for rendering
        resolution: output image resolution (default 512x512)
    """
    render_dir.mkdir(exist_ok=True)
    render_cams = cameras.to_cameras().with_resolution(resolution, resolution).to(device)
    gaussians_gpu = gaussians.to(device)

    num_views = len(render_cams)
    for i in range(num_views):
        rgb, alpha = render_gaussians(gaussians_gpu, render_cams[i])
        rgb = rgb * alpha  # composite over black
        img = (rgb.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
        Image.fromarray(img).save(render_dir / f"view_{i:02d}.png")


def print_pose_adjustments(
    pose_adjust: CameraOptModule,
    cameras: CameraCollection,
) -> None:
    """Print learned camera pose adjustments compared to original values.

    Args:
        pose_adjust: trained pose optimization module
        cameras: original camera collection
    """
    num_views = len(cameras)
    print("\nCamera pose adjustments:")
    print(f"  {'Cam':>3}  {'------- Original -------':^26}  {'-------- Delta --------':^25}")
    print(f"  {'':>3}  {'pitch':>7} {'yaw':>7} {'dist':>6} {'fov':>5}  {'pitch':>8} {'yaw':>8} {'dist':>8}")
    with torch.no_grad():
        weights = pose_adjust.embeds.weight
        for cam_idx in range(num_views):
            cam = cameras[cam_idx]
            orig_pitch = cam.pitch_deg if cam.pitch_deg is not None else 0.0
            orig_yaw = cam.yaw_deg if cam.yaw_deg is not None else 0.0
            orig_dist = float(np.linalg.norm(cam.position))

            # FOV for perspective, ortho_scale for orthographic
            if hasattr(cam, 'fov_deg'):
                fov_str = f"{cam.fov_deg:.0f}°"
            else:
                fov_str = "ortho"

            delta = weights[cam_idx]
            dx = delta[:3]  # translation delta
            drot6d = delta[3:] + pose_adjust.identity_rot6d
            rot_mat = rotation_6d_to_matrix(drot6d)

            delta_yaw = math.degrees(math.atan2(rot_mat[1, 0].item(), rot_mat[0, 0].item()))
            delta_pitch = math.degrees(math.atan2(
                -rot_mat[2, 0].item(),
                math.sqrt(rot_mat[2, 1].item()**2 + rot_mat[2, 2].item()**2)
            ))
            delta_dist = float(torch.linalg.norm(dx))

            print(f"  {cam_idx:3d}  {orig_pitch:+7.1f} {orig_yaw:+7.1f} {orig_dist:6.2f} {fov_str:>5}  "
                  f"{delta_pitch:+8.3f} {delta_yaw:+8.3f} {delta_dist:+8.4f}")


def train_gaussians(
    cameras: CameraCollection,
    init_gaussians: Gaussians,
    config: TrainConfig,
    output_path: Optional[Path] = None,
    render_dir: Optional[Path] = None,
) -> Gaussians:
    """
    Optimize Gaussian parameters to match target sprite views.

    Args:
        cameras: camera collection with images
        init_gaussians: initial Gaussians to optimize
        config: training configuration
        output_path: optional path for saving checkpoints
        render_dir: optional directory for rendering checkpoint images

    Returns:
        Optimized Gaussians object
    """
    device = get_device(config.device)
    sh_degree = init_gaussians.sh_degree

    # For symmetric mode, filter to canonical half (y >= 0)
    if config.symmetric:
        init_gaussians = filter_positive_y(init_gaussians)
        print(f"  Symmetric mode: using {init_gaussians.num_gaussians} canonical Gaussians (y >= 0)")

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
    if config.symmetric:
        test_gaussians = expand_symmetric(test_gaussians)
    gsplat_result = render_gsplat(test_gaussians, cams[:1])
    use_gsplat = gsplat_result is not None

    print(f"  Using {'gsplat' if use_gsplat else 'simple'} renderer "
          f"(SH degree {sh_degree}){'' if use_gsplat else ' (slower)'}")
    print(f"  Loss type: {config.loss_type.value}")

    for iteration in range(config.num_iterations):
        optimizer.zero_grad()
        if pose_optimizer is not None:
            pose_optimizer.zero_grad()

        # Concatenate SH coefficients and create Gaussians for rendering
        sh_full = torch.cat([sh0, shN], dim=1)
        current_gaussians = Gaussians(means, scales, quats, opacities, sh_full)

        # For symmetric mode, expand canonical half to full model before rendering
        if config.symmetric:
            current_gaussians = expand_symmetric(current_gaussians)

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

        if use_gsplat:
            render_colors, render_alphas = render_gsplat(current_gaussians, current_cams)
        else:
            render_colors, render_alphas = render_gaussians_simple(current_gaussians, current_cams)

        # L1 loss (masked by alpha)
        l1_loss = (torch.abs(render_colors - target_rgb) * target_alpha).mean()

        if config.loss_type == LossType.L1_SSIM:
            # SSIM loss on RGB (permute to [N,C,H,W] for conv2d)
            render_rgb_nchw = render_colors.permute(0, 3, 1, 2)
            target_rgb_nchw = target_rgb.permute(0, 3, 1, 2)
            ssim_val = ssim(render_rgb_nchw, target_rgb_nchw)
            ssim_loss = 1 - ssim_val
            # Combined RGB loss (0.8 * L1 + 0.2 * SSIM, standard 3DGS weights)
            rgb_loss = 0.8 * l1_loss + 0.2 * ssim_loss
        else:
            ssim_val = torch.tensor(0.0, device=l1_loss.device)
            rgb_loss = l1_loss

        alpha_loss = F.binary_cross_entropy(
            render_alphas.clamp(CLAMP_EPSILON, 1 - CLAMP_EPSILON),
            target_alpha,
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

        if iteration % LOG_INTERVAL == 0 or iteration == config.num_iterations - 1:
            log_msg = (f"  Iter {iteration}: loss={loss.item():.4f}, "
                       f"rgb={rgb_loss.item():.4f}, alpha={alpha_loss.item():.4f}")
            if config.loss_type == LossType.L1_SSIM:
                log_msg += f", ssim={ssim_val.item():.4f}"
            print(log_msg)

        # Save model, render views, and show pose adjustments every CHECKPOINT_INTERVAL
        if iteration > 0 and iteration % CHECKPOINT_INTERVAL == 0:
            if output_path is not None or render_dir is not None:
                sh_full = torch.cat([sh0, shN], dim=1)
                checkpoint_gaussians = Gaussians(
                    means=means.detach(),
                    scales=scales.detach(),
                    quats=quats.detach(),
                    opacities=opacities.detach(),
                    sh_coeffs=sh_full.detach(),
                )
                # Expand symmetric model for saving/rendering
                if config.symmetric:
                    checkpoint_gaussians = expand_symmetric(checkpoint_gaussians)
                if output_path is not None:
                    export_ply(checkpoint_gaussians, str(output_path))
                    print(f"  Saved {output_path}")
                if render_dir is not None:
                    render_all_views(checkpoint_gaussians, cameras, render_dir, device)
                    print(f"  Rendered views to {render_dir}")
            if pose_adjust is not None:
                print_pose_adjustments(pose_adjust, cameras)

    # Print camera pose comparison if optimization was enabled
    if pose_adjust is not None:
        print_pose_adjustments(pose_adjust, cameras)

    # Reconstruct full SH coefficients
    sh_coeffs_out = torch.cat([sh0, shN], dim=1)

    result = Gaussians(
        means=means.detach().cpu(),
        scales=scales.detach().cpu(),
        quats=quats.detach().cpu(),
        opacities=opacities.detach().cpu(),
        sh_coeffs=sh_coeffs_out.detach().cpu(),
    )

    # Expand symmetric model for final output
    if config.symmetric:
        result = expand_symmetric(result)

    return result


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
        distance=args.distance,
    )
    print(f"  Loaded {len(cameras)} cameras")

    gaussians = initialize_from_visual_hull(
        cameras,
        resolution=args.resolution,
        num_gaussians=args.num_gaussians,
    )

    output_path = project_dir / args.output
    render_dir = project_dir / args.render_dir if args.render else None

    print(f"Training for {args.train.num_iterations} iterations...")
    gaussians = train_gaussians(cameras, gaussians, args.train, output_path, render_dir)

    print(f"Exporting to {output_path}...")
    export_ply(gaussians, str(output_path))

    if render_dir is not None:
        print("Rendering final views at 512x512...")
        device = get_device(args.train.device)
        render_all_views(gaussians, cameras, render_dir, device)
        print(f"  Saved {len(cameras)} images to {render_dir}")

    print("Done!")


if __name__ == '__main__':
    main()
