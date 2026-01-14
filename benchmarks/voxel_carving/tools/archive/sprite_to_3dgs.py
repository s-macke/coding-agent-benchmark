#!/usr/bin/env python3
"""
Convert Wing Commander ship sprites to 3D Gaussian Splatting.

Usage:
    python tools/sprite_to_3dgs.py [options]

Options:
    --output PATH       Output PLY file (default: ship_gaussians.ply)
    --iterations N      Training iterations (default: 5000)
    --num-gaussians N   Max Gaussian count (default: 5000)
    --lr FLOAT          Learning rate (default: 0.01)
    --resolution N      Voxel grid resolution for visual hull (default: 64)
    --device DEVICE     cuda or cpu (default: cuda if available)
"""

import argparse
import json
import struct
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


def load_sprites(json_path: Path, images_dir: Path) -> Tuple[List[torch.Tensor], List[dict]]:
    """
    Load sprite images and their metadata.

    Returns:
        images: List of [H, W, 4] RGBA tensors (float32, 0-1)
        metadata: List of dicts with camera parameters
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    images = []
    metadata = []

    for sprite in data['sprites']:
        # Load image
        img_path = images_dir / sprite['filename']
        img = Image.open(img_path).convert('RGBA')
        img_tensor = torch.from_numpy(np.array(img)).float() / 255.0
        images.append(img_tensor)
        metadata.append(sprite)

    return images, metadata


def build_view_matrix(camera_pos: np.ndarray,
                      camera_up: np.ndarray,
                      camera_right: np.ndarray) -> torch.Tensor:
    """
    Build a 4x4 world-to-camera view matrix.

    The camera looks at origin (0, 0, 0).
    """
    # Forward vector (from camera to origin)
    forward = -camera_pos / np.linalg.norm(camera_pos)

    # Ensure orthonormal basis
    up = np.array(camera_up)
    right = np.array(camera_right)

    # Build rotation matrix (columns are right, up, -forward in world coords)
    # But for view matrix we need the transpose (world-to-camera)
    rotation = np.stack([right, up, -forward], axis=0)  # 3x3, rows are camera axes

    # Build 4x4 view matrix
    viewmat = np.eye(4, dtype=np.float32)
    viewmat[:3, :3] = rotation
    viewmat[:3, 3] = -rotation @ camera_pos

    return torch.from_numpy(viewmat)


def compute_camera_position(yaw_deg: float, pitch_deg: float, distance: float = 5.0) -> np.ndarray:
    """
    Compute camera position from yaw and pitch angles.

    Following SHIP_ANGLES.md conventions:
    - YAW 0 = rear (camera at -X), 180 = front (camera at +X)
    - PITCH 90 = below (camera at -Z), -90 = above (camera at +Z)
    """
    yaw_rad = np.radians(yaw_deg)
    pitch_rad = np.radians(pitch_deg)

    cam_x = -distance * np.cos(yaw_rad) * np.cos(pitch_rad)
    cam_y = distance * np.sin(yaw_rad) * np.cos(pitch_rad)
    cam_z = distance * np.sin(pitch_rad)

    return np.array([cam_x, cam_y, cam_z], dtype=np.float32)


def build_orthographic_K(width: int, height: int, ortho_scale: float) -> torch.Tensor:
    """
    Build intrinsic matrix for orthographic projection.

    For ortho cameras:
    - fx = width / (2 * ortho_scale)
    - fy = height / (2 * ortho_scale)
    - cx, cy = image center
    """
    fx = width / (2 * ortho_scale)
    fy = height / (2 * ortho_scale)
    cx = width / 2.0
    cy = height / 2.0

    K = torch.tensor([
        [fx, 0.0, cx],
        [0.0, fy, cy],
        [0.0, 0.0, 1.0]
    ], dtype=torch.float32)

    return K


def build_cameras(metadata: List[dict], ortho_scale: float = 2.0,
                  distance: float = 5.0) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Build view matrices and intrinsic matrices for all cameras.

    Returns:
        viewmats: [C, 4, 4] view matrices
        Ks: [C, 3, 3] intrinsic matrices
    """
    viewmats = []
    Ks = []

    for sprite in metadata:
        # Camera position
        cam_pos = compute_camera_position(sprite['yaw'], sprite['pitch'], distance)

        # View matrix
        viewmat = build_view_matrix(
            cam_pos,
            sprite['camera_up'],
            sprite['camera_right']
        )
        viewmats.append(viewmat)

        # Intrinsic matrix (same for all views)
        K = build_orthographic_K(128, 128, ortho_scale)
        Ks.append(K)

    return torch.stack(viewmats), torch.stack(Ks)


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
    # Create voxel grid
    coords = torch.linspace(-extent, extent, resolution)
    grid_x, grid_y, grid_z = torch.meshgrid(coords, coords, coords, indexing='ij')
    grid = torch.stack([grid_x, grid_y, grid_z], dim=-1).reshape(-1, 3)  # [R^3, 3]

    # Start with all voxels occupied
    occupied = torch.ones(grid.shape[0], dtype=torch.bool)

    print(f"  Carving with {len(images)} views...")

    for i, (img, viewmat, K) in enumerate(zip(images, viewmats, Ks)):
        # Get silhouette mask from alpha channel
        mask = img[:, :, 3] > 0.5  # [H, W]

        # Transform grid points to camera space
        # Homogeneous coordinates
        grid_homo = torch.cat([grid, torch.ones(grid.shape[0], 1)], dim=1)  # [N, 4]
        cam_coords = (viewmat @ grid_homo.T).T[:, :3]  # [N, 3]

        # Orthographic projection
        fx, fy = K[0, 0].item(), K[1, 1].item()
        cx, cy = K[0, 2].item(), K[1, 2].item()

        proj_x = fx * cam_coords[:, 0] + cx
        proj_y = fy * cam_coords[:, 1] + cy

        # Check bounds
        H, W = mask.shape
        in_bounds = (proj_x >= 0) & (proj_x < W - 1) & (proj_y >= 0) & (proj_y < H - 1)

        # Sample silhouette (use nearest neighbor)
        px = proj_x.long().clamp(0, W - 1)
        py = proj_y.long().clamp(0, H - 1)

        in_silhouette = torch.zeros(grid.shape[0], dtype=torch.bool)
        in_silhouette[in_bounds] = mask[py[in_bounds], px[in_bounds]]

        # Carve: remove voxels outside silhouette
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
    # Subsample if too many points
    if points.shape[0] > num_gaussians:
        idx = torch.randperm(points.shape[0])[:num_gaussians]
        points = points[idx]
    elif points.shape[0] == 0:
        # Fallback: create random points if visual hull is empty
        print("  Warning: Visual hull empty, using random initialization")
        points = (torch.rand(num_gaussians, 3) - 0.5) * 2.0

    N = points.shape[0]

    # Positions
    means = points.clone()

    # Scales (log scale, small isotropic)
    # Voxel size ~ 3.0 / resolution, use slightly smaller Gaussians
    initial_scale = -3.5  # exp(-3.5) ~ 0.03
    scales = torch.full((N, 3), initial_scale, dtype=torch.float32)

    # Quaternions (wxyz format, identity rotation)
    quats = torch.zeros((N, 4), dtype=torch.float32)
    quats[:, 0] = 1.0  # w=1, x=y=z=0

    # Opacities (logit form)
    opacities = torch.full((N,), 0.5, dtype=torch.float32)  # sigmoid(0.5) ~ 0.62

    # Initialize colors by averaging visible colors from all views
    colors = torch.full((N, 3), 0.5, dtype=torch.float32)
    color_counts = torch.zeros(N, dtype=torch.float32)

    for img, viewmat, K in zip(images, viewmats, Ks):
        # Project points to image
        means_homo = torch.cat([means, torch.ones(N, 1)], dim=1)
        cam_coords = (viewmat @ means_homo.T).T[:, :3]

        fx, fy = K[0, 0].item(), K[1, 1].item()
        cx, cy = K[0, 2].item(), K[1, 2].item()

        proj_x = fx * cam_coords[:, 0] + cx
        proj_y = fy * cam_coords[:, 1] + cy

        H, W = img.shape[:2]
        in_bounds = (proj_x >= 0) & (proj_x < W - 1) & (proj_y >= 0) & (proj_y < H - 1)

        px = proj_x.long().clamp(0, W - 1)
        py = proj_y.long().clamp(0, H - 1)

        # Sample colors where visible (alpha > 0.5)
        alpha = img[:, :, 3]
        rgb = img[:, :, :3]

        visible = in_bounds & (alpha[py, px] > 0.5)

        colors[visible] += rgb[py[visible], px[visible]]
        color_counts[visible] += 1

    # Average colors
    valid_colors = color_counts > 0
    colors[valid_colors] /= color_counts[valid_colors].unsqueeze(1)

    return means, scales, quats, opacities, colors


def render_gaussians_simple(means: torch.Tensor,
                            scales: torch.Tensor,
                            quats: torch.Tensor,
                            opacities: torch.Tensor,
                            colors: torch.Tensor,
                            viewmat: torch.Tensor,
                            K: torch.Tensor,
                            width: int,
                            height: int) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Simple differentiable Gaussian splatting renderer (CPU-friendly).

    This is a basic implementation for when gsplat CUDA is not available.
    Projects Gaussians and accumulates with alpha blending.

    Returns:
        render_rgb: [H, W, 3]
        render_alpha: [H, W, 1]
    """
    N = means.shape[0]
    device = means.device

    # Transform means to camera space
    means_homo = torch.cat([means, torch.ones(N, 1, device=device)], dim=1)
    cam_means = (viewmat @ means_homo.T).T[:, :3]  # [N, 3]

    # Project to image plane (orthographic)
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = fx * cam_means[:, 0] + cx  # [N]
    proj_y = fy * cam_means[:, 1] + cy  # [N]
    depths = -cam_means[:, 2]  # [N], negative z is forward

    # Get scales (convert from log-scale)
    actual_scales = torch.exp(scales)  # [N, 3]

    # Get opacities (convert from logit)
    actual_opacities = torch.sigmoid(opacities)  # [N]

    # Sort by depth (back to front for alpha blending)
    sorted_indices = torch.argsort(depths, descending=True)

    # Create output buffers
    render_rgb = torch.zeros(height, width, 3, device=device)
    render_alpha = torch.zeros(height, width, 1, device=device)

    # Create pixel coordinate grids
    y_coords, x_coords = torch.meshgrid(
        torch.arange(height, device=device, dtype=torch.float32),
        torch.arange(width, device=device, dtype=torch.float32),
        indexing='ij'
    )

    # Render each Gaussian (back to front)
    for idx in sorted_indices:
        px, py = proj_x[idx], proj_y[idx]
        scale = actual_scales[idx]  # [3]
        opacity = actual_opacities[idx]
        color = colors[idx]  # [3]

        # Projected scale in image space (use average of x,y scales)
        sigma = (scale[0] + scale[1]) / 2 * fx.abs()  # Scale by focal length
        sigma = sigma.clamp(min=0.5)  # Minimum sigma for stability

        # Compute Gaussian weights for all pixels
        dx = x_coords - px
        dy = y_coords - py
        dist_sq = dx * dx + dy * dy

        # Gaussian weight
        weight = torch.exp(-0.5 * dist_sq / (sigma * sigma + 1e-6))
        weight = weight * opacity

        # Clip to reasonable area (optimization)
        # Only render where weight > 0.001
        mask = weight > 0.001

        # Alpha blending: front-to-back would be:
        # color_out = color_out + (1 - alpha_out) * alpha_in * color_in
        # But we're going back-to-front, so just accumulate
        transmittance = 1.0 - render_alpha[:, :, 0]
        alpha_contrib = weight * transmittance

        render_rgb += alpha_contrib.unsqueeze(-1) * color.unsqueeze(0).unsqueeze(0)
        render_alpha[:, :, 0] += alpha_contrib

    render_alpha = render_alpha.clamp(0, 1)

    return render_rgb, render_alpha


def try_gsplat_render(means, scales, quats, opacities, colors,
                      viewmats, Ks, width, height, device):
    """
    Try to use gsplat for rendering if available and working.

    Returns:
        (render_colors, render_alphas) if successful, None otherwise
    """
    try:
        import gsplat

        # Prepare parameters
        actual_scales = torch.exp(scales)
        actual_opacities = torch.sigmoid(opacities)

        # Try gsplat rasterization
        render_colors, render_alphas, meta = gsplat.rasterization(
            means=means,
            quats=quats,
            scales=actual_scales,
            opacities=actual_opacities,
            colors=colors,
            viewmats=viewmats,
            Ks=Ks,
            width=width,
            height=height,
            camera_model="ortho",
            packed=False,
        )
        return render_colors, render_alphas
    except Exception as e:
        print(f"  gsplat not available or failed: {e}")
        return None


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
    """
    Optimize Gaussian parameters to match target sprite views.
    """
    # Check device
    if device == 'cuda' and not torch.cuda.is_available():
        print("  CUDA not available, using CPU")
        device = 'cpu'

    device = torch.device(device)

    # Stack target images [C, H, W, 4]
    targets = torch.stack(images).to(device)
    target_rgb = targets[:, :, :, :3]
    target_alpha = targets[:, :, :, 3:4]

    viewmats = viewmats.to(device)
    Ks = Ks.to(device)

    # Parameters to optimize
    means = init_means.clone().to(device).requires_grad_(True)
    scales = init_scales.clone().to(device).requires_grad_(True)
    quats = init_quats.clone().to(device).requires_grad_(True)
    opacities = init_opacities.clone().to(device).requires_grad_(True)
    colors = init_colors.clone().to(device).requires_grad_(True)

    # Optimizer with different learning rates
    optimizer = torch.optim.Adam([
        {'params': means, 'lr': lr},
        {'params': scales, 'lr': lr * 0.1},
        {'params': quats, 'lr': lr * 0.1},
        {'params': opacities, 'lr': lr * 0.5},
        {'params': colors, 'lr': lr},
    ])

    width, height = 128, 128
    C = viewmats.shape[0]

    # Check if gsplat works
    gsplat_available = try_gsplat_render(
        means, scales, quats, opacities, colors,
        viewmats[:1], Ks[:1], width, height, device
    ) is not None

    if gsplat_available:
        print("  Using gsplat renderer")
    else:
        print("  Using simple renderer (slower)")

    for iteration in range(num_iterations):
        optimizer.zero_grad()

        if gsplat_available:
            # Use gsplat
            result = try_gsplat_render(
                means, scales, quats, opacities, colors,
                viewmats, Ks, width, height, device
            )
            if result is not None:
                render_colors, render_alphas = result
            else:
                gsplat_available = False
                continue

        if not gsplat_available:
            # Fall back to simple renderer (render a subset for speed)
            render_colors_list = []
            render_alphas_list = []

            # Only render a few views per iteration for speed
            view_indices = torch.randperm(C)[:min(8, C)]

            actual_scales = torch.exp(scales)
            actual_opacities = torch.sigmoid(opacities)

            for vi in view_indices:
                rc, ra = render_gaussians_simple(
                    means, scales, quats, opacities, colors,
                    viewmats[vi], Ks[vi], width, height
                )
                render_colors_list.append(rc)
                render_alphas_list.append(ra)

            render_colors = torch.stack(render_colors_list)
            render_alphas = torch.stack(render_alphas_list)

            # Adjust target to match subset
            target_rgb_subset = target_rgb[view_indices]
            target_alpha_subset = target_alpha[view_indices]
        else:
            target_rgb_subset = target_rgb
            target_alpha_subset = target_alpha

        # Compute losses
        # RGB loss (L1, weighted by target alpha)
        rgb_loss = (torch.abs(render_colors - target_rgb_subset) * target_alpha_subset).mean()

        # Alpha loss (BCE)
        alpha_loss = F.binary_cross_entropy(
            render_alphas.clamp(1e-6, 1 - 1e-6),
            target_alpha_subset,
            reduction='mean'
        )

        # Regularization: encourage sparse opacities
        opacity_reg = torch.sigmoid(opacities).mean() * 0.01

        # Total loss
        loss = rgb_loss + alpha_loss * 0.5 + opacity_reg

        loss.backward()
        optimizer.step()

        # Normalize quaternions after update
        with torch.no_grad():
            quats.data = F.normalize(quats.data, dim=-1)

        if iteration % 500 == 0:
            print(f"  Iter {iteration}: loss={loss.item():.4f}, "
                  f"rgb={rgb_loss.item():.4f}, alpha={alpha_loss.item():.4f}")

    return (means.detach().cpu(), scales.detach().cpu(), quats.detach().cpu(),
            opacities.detach().cpu(), colors.detach().cpu())


def export_ply(means: torch.Tensor,
               scales: torch.Tensor,
               quats: torch.Tensor,
               opacities: torch.Tensor,
               colors: torch.Tensor,
               output_path: str):
    """
    Export Gaussians to standard PLY format compatible with 3DGS viewers.
    """
    N = means.shape[0]

    # Convert to numpy
    means_np = means.numpy()
    scales_np = scales.numpy()  # Keep as log-scale
    quats_np = quats.numpy()  # wxyz format
    opacities_np = opacities.numpy()  # Keep as logit

    # Convert colors to SH DC coefficients
    # SH0 = (color - 0.5) / C0 where C0 = 0.28209479177387814
    C0 = 0.28209479177387814
    sh0_np = (colors.numpy() - 0.5) / C0

    with open(output_path, 'wb') as f:
        # Write header
        f.write(b"ply\n")
        f.write(b"format binary_little_endian 1.0\n")
        f.write(f"element vertex {N}\n".encode())
        f.write(b"property float x\n")
        f.write(b"property float y\n")
        f.write(b"property float z\n")
        # SH coefficients (DC term for RGB)
        f.write(b"property float f_dc_0\n")
        f.write(b"property float f_dc_1\n")
        f.write(b"property float f_dc_2\n")
        # Opacity
        f.write(b"property float opacity\n")
        # Scales (log-scale)
        f.write(b"property float scale_0\n")
        f.write(b"property float scale_1\n")
        f.write(b"property float scale_2\n")
        # Rotation quaternion (wxyz -> stored as xyzw for compatibility)
        f.write(b"property float rot_0\n")
        f.write(b"property float rot_1\n")
        f.write(b"property float rot_2\n")
        f.write(b"property float rot_3\n")
        f.write(b"end_header\n")

        # Write data
        for i in range(N):
            # Position
            f.write(struct.pack('<fff', *means_np[i]))
            # SH DC (RGB)
            f.write(struct.pack('<fff', *sh0_np[i]))
            # Opacity (logit form)
            f.write(struct.pack('<f', opacities_np[i]))
            # Scales (log-scale)
            f.write(struct.pack('<fff', *scales_np[i]))
            # Rotation (convert wxyz to xyzw for standard format)
            q = quats_np[i]  # [w, x, y, z]
            f.write(struct.pack('<ffff', q[1], q[2], q[3], q[0]))  # [x, y, z, w]

    print(f"Saved {N} Gaussians to {output_path}")


def main():
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

    # 1. Load data
    print("Loading sprites and camera data...")
    images, metadata = load_sprites(
        project_dir / 'ship_sprites_centered.json',
        project_dir / 'centered_images'
    )
    print(f"  Loaded {len(images)} sprites")

    # 2. Build camera matrices
    print("Building camera matrices...")
    viewmats, Ks = build_cameras(metadata, ortho_scale=args.ortho_scale)
    print(f"  Built {viewmats.shape[0]} view matrices")

    # 3. Initialize Gaussians via visual hull
    print("Carving visual hull...")
    points = carve_visual_hull(images, viewmats, Ks, resolution=args.resolution)

    print("Initializing Gaussians...")
    means, scales, quats, opacities, colors = init_gaussians(
        points, images, viewmats, Ks, num_gaussians=args.num_gaussians
    )
    print(f"  Initialized {means.shape[0]} Gaussians")

    # 4. Optimize
    print(f"Training for {args.iterations} iterations...")
    means, scales, quats, opacities, colors = train_gaussians(
        images, viewmats, Ks,
        means, scales, quats, opacities, colors,
        num_iterations=args.iterations,
        lr=args.lr,
        device=args.device,
    )

    # 5. Export
    output_path = project_dir / args.output
    print(f"Exporting to {output_path}...")
    export_ply(means, scales, quats, opacities, colors, str(output_path))

    print("Done!")


if __name__ == '__main__':
    main()
