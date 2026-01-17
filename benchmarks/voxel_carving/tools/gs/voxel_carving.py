"""
Visual hull carving and Gaussian initialization from silhouettes.

Carves a 3D voxel grid by projecting each voxel to all camera views
and checking if it lies within the silhouette, then initializes
Gaussians from the resulting point cloud.
"""

from typing import List

import torch

from .constants import ALPHA_THRESHOLD
from .camera import CameraCollection
from .gaussians import Gaussians, init_sh_from_rgb, SH_DEGREE

# Gaussian initialization constants
INITIAL_LOG_SCALE = -3.5  # exp(-3.5) ~ 0.03
INITIAL_OPACITY_LOGIT = 0.5  # sigmoid(0.5) ~ 0.62


def carve_visual_hull(images: List[torch.Tensor],
                      cameras: CameraCollection,
                      resolution: int = 64,
                      extent: float = 1.5) -> torch.Tensor:
    """
    Carve visual hull from silhouettes using camera projection.

    Args:
        images: list of [H, W, 4] RGBA images
        cameras: camera collection with projection methods
        resolution: voxel grid resolution per axis
        extent: half-size of the voxel grid in world units

    Returns:
        points: [N, 3] 3D points inside visual hull
    """
    coords = torch.linspace(-extent, extent, resolution)
    grid_x, grid_y, grid_z = torch.meshgrid(coords, coords, coords, indexing='ij')
    grid = torch.stack([grid_x, grid_y, grid_z], dim=-1).reshape(-1, 3)

    occupied = torch.ones(grid.shape[0], dtype=torch.bool)

    print(f"  Carving with {len(cameras)} views...")

    for img, camera in zip(images, cameras):
        mask = img[:, :, 3] > ALPHA_THRESHOLD
        H, W = mask.shape

        proj_x, proj_y = camera.project(grid)

        in_bounds = (proj_x >= 0) & (proj_x < W - 1) & (proj_y >= 0) & (proj_y < H - 1)

        px = proj_x.long().clamp(0, W - 1)
        py = proj_y.long().clamp(0, H - 1)

        in_silhouette = torch.zeros(grid.shape[0], dtype=torch.bool)
        in_silhouette[in_bounds] = mask[py[in_bounds], px[in_bounds]]

        occupied = occupied & in_silhouette

    points = grid[occupied]
    print(f"  Visual hull: {points.shape[0]} voxels occupied out of {grid.shape[0]}")

    return points


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


def initialize_from_visual_hull(
    cameras: CameraCollection,
    resolution: int = 64,
    extent: float = 1.5,
    num_gaussians: int = 5000,
    sh_degree: int = SH_DEGREE,
) -> Gaussians:
    """
    Carve visual hull and initialize Gaussians from it.

    Combines carve_visual_hull() and init_gaussians() into one step.

    Args:
        cameras: camera collection with images and projection methods
        resolution: voxel grid resolution per axis
        extent: half-size of the voxel grid in world units
        num_gaussians: maximum number of Gaussians
        sh_degree: spherical harmonics degree

    Returns:
        Gaussians object initialized from visual hull points
    """
    images = cameras.images

    print("Carving visual hull...")
    points = carve_visual_hull(images, cameras, resolution, extent)

    print("Initializing Gaussians...")
    gaussians = init_gaussians(points, images, cameras, num_gaussians, sh_degree)
    print(f"  Initialized {gaussians.num_gaussians} Gaussians (SH degree {gaussians.sh_degree})")

    return gaussians