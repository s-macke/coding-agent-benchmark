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

# Image and rendering constants
IMAGE_SIZE = 128
ALPHA_THRESHOLD = 0.5

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
MIN_SIGMA = 0.5
MIN_WEIGHT_THRESHOLD = 0.001
CLAMP_EPSILON = 1e-6

# PLY export constants
SH_C0 = 0.28209479177387814


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
    gsplat uses +Z as forward direction in camera space.
    """
    forward = -camera_pos / np.linalg.norm(camera_pos)
    up = np.array(camera_up)
    right = np.array(camera_right)

    # Rows are: right (X), up (Y), forward (Z) in camera space
    rotation = np.stack([right, up, forward], axis=0)

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
    """Build intrinsic matrix for orthographic projection."""
    fx = width / (2 * ortho_scale)
    fy = height / (2 * ortho_scale)
    cx = width / 2.0
    cy = height / 2.0

    return torch.tensor([
        [fx, 0.0, cx],
        [0.0, fy, cy],
        [0.0, 0.0, 1.0]
    ], dtype=torch.float32)


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
        cam_pos = compute_camera_position(sprite['yaw'], sprite['pitch'], distance)
        viewmat = build_view_matrix(cam_pos, sprite['camera_up'], sprite['camera_right'])
        viewmats.append(viewmat)

        K = build_orthographic_K(IMAGE_SIZE, IMAGE_SIZE, ortho_scale)
        Ks.append(K)

    return torch.stack(viewmats), torch.stack(Ks)


def project_points_orthographic(points: torch.Tensor, viewmat: torch.Tensor,
                                K: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Project 3D points to 2D using orthographic projection.

    Returns:
        proj_x, proj_y: Projected 2D coordinates
    """
    N = points.shape[0]
    points_homo = torch.cat([points, torch.ones(N, 1, device=points.device)], dim=1)
    cam_coords = (viewmat @ points_homo.T).T[:, :3]

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = fx * cam_coords[:, 0] + cx
    proj_y = fy * cam_coords[:, 1] + cy

    return proj_x, proj_y


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

    Projects Gaussians and accumulates with alpha blending (back to front).

    Returns:
        render_rgb: [H, W, 3]
        render_alpha: [H, W, 1]
    """
    N = means.shape[0]
    device = means.device

    means_homo = torch.cat([means, torch.ones(N, 1, device=device)], dim=1)
    cam_means = (viewmat @ means_homo.T).T[:, :3]

    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]

    proj_x = fx * cam_means[:, 0] + cx
    proj_y = fy * cam_means[:, 1] + cy
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


def try_gsplat_render(means, scales, quats, opacities, colors,
                      viewmats, Ks, width, height, device):
    """
    Try to use gsplat for rendering if available.

    Returns:
        (render_colors, render_alphas) if successful, None otherwise
    """
    try:
        import gsplat

        actual_scales = torch.exp(scales)
        actual_opacities = torch.sigmoid(opacities)

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

    project_dir = Path(__file__).parent.parent

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