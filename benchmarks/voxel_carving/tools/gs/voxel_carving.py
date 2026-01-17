"""
Visual hull carving from silhouettes.

Carves a 3D voxel grid by projecting each voxel to all camera views
and checking if it lies within the silhouette.
"""

from typing import List

import torch

from .constants import ALPHA_THRESHOLD
from .camera import CameraCollection


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