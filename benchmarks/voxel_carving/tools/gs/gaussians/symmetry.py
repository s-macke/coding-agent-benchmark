"""Symmetry utilities for Gaussian Splatting.

Supports y-axis mirror symmetry where Gaussians are reflected about the XZ plane (y=0).
This allows storing only half the Gaussians when the model has bilateral symmetry.
"""

import torch
from torch import Tensor

from .gaussians import Gaussians


# SH coefficient indices that are odd under y-reflection (y → -y)
# These depend on y linearly or as xy, yz products
# Degree 1: index 1 (Y_1^-1 ∝ y)
# Degree 2: index 4 (Y_2^-2 ∝ xy), index 5 (Y_2^-1 ∝ yz)
SH_ODD_Y_INDICES = {
    0: [],           # degree 0: no odd terms
    1: [1],          # degree 1: index 1
    2: [1, 4, 5],    # degree 2: indices 1, 4, 5
}


def mirror_positions(means: Tensor) -> Tensor:
    """Mirror positions about the XZ plane (y=0).

    Args:
        means: [N, 3] positions

    Returns:
        [N, 3] mirrored positions with y negated
    """
    mirrored = means.clone()
    mirrored[:, 1] = -mirrored[:, 1]
    return mirrored


def mirror_quaternions(quats: Tensor) -> Tensor:
    """Mirror quaternions about the XZ plane (y=0).

    For a quaternion q = (w, qx, qy, qz), reflection about y=0 gives (w, -qx, qy, -qz).
    The reflection reverses rotation direction for axes in the mirror plane (x, z),
    so we negate qx and qz while keeping qy unchanged.

    Args:
        quats: [N, 4] quaternions in wxyz format

    Returns:
        [N, 4] mirrored quaternions
    """
    mirrored = quats.clone()
    mirrored[:, 1] = -mirrored[:, 1]  # negate qx
    mirrored[:, 3] = -mirrored[:, 3]  # negate qz
    return mirrored


def mirror_sh_coeffs(sh_coeffs: Tensor, sh_degree: int) -> Tensor:
    """Mirror SH coefficients about the XZ plane (y=0).

    SH basis functions that are odd in y need their coefficients negated.
    - Degree 1: Y_1^-1 (index 1) ∝ y
    - Degree 2: Y_2^-2 (index 4) ∝ xy, Y_2^-1 (index 5) ∝ yz

    Args:
        sh_coeffs: [N, K, 3] SH coefficients where K = (degree+1)^2
        sh_degree: SH degree (0, 1, or 2)

    Returns:
        [N, K, 3] mirrored SH coefficients
    """
    mirrored = sh_coeffs.clone()
    odd_indices = SH_ODD_Y_INDICES.get(sh_degree, [])
    for idx in odd_indices:
        if idx < mirrored.shape[1]:
            mirrored[:, idx, :] = -mirrored[:, idx, :]
    return mirrored


def mirror_gaussians(gaussians: Gaussians) -> Gaussians:
    """Mirror Gaussians about the XZ plane (y=0).

    Creates a mirrored copy of all Gaussians with:
    - Positions: y negated
    - Quaternions: qy component negated
    - SH coefficients: odd-y terms negated
    - Scales and opacities unchanged

    Args:
        gaussians: Original Gaussians

    Returns:
        New Gaussians mirrored about y=0
    """
    return Gaussians(
        means=mirror_positions(gaussians.means),
        scales=gaussians.scales.clone(),
        quats=mirror_quaternions(gaussians.quats),
        opacities=gaussians.opacities.clone(),
        sh_coeffs=mirror_sh_coeffs(gaussians.sh_coeffs, gaussians.sh_degree),
    )


def expand_symmetric(gaussians: Gaussians) -> Gaussians:
    """Expand symmetric Gaussians by adding their mirrored copies.

    Takes Gaussians (typically with y >= 0) and returns doubled Gaussians
    containing both original and y-mirrored copies.

    Args:
        gaussians: Gaussians to expand (canonical half)

    Returns:
        Gaussians with original + mirrored (2N total)
    """
    mirrored = mirror_gaussians(gaussians)
    return Gaussians(
        means=torch.cat([gaussians.means, mirrored.means], dim=0),
        scales=torch.cat([gaussians.scales, mirrored.scales], dim=0),
        quats=torch.cat([gaussians.quats, mirrored.quats], dim=0),
        opacities=torch.cat([gaussians.opacities, mirrored.opacities], dim=0),
        sh_coeffs=torch.cat([gaussians.sh_coeffs, mirrored.sh_coeffs], dim=0),
    )


def filter_positive_y(gaussians: Gaussians, include_zero: bool = True) -> Gaussians:
    """Filter Gaussians to keep only those with y >= 0 (or y > 0).

    Args:
        gaussians: Input Gaussians
        include_zero: If True, keep y >= 0; if False, keep y > 0

    Returns:
        Filtered Gaussians with only positive-y positions
    """
    if include_zero:
        mask = gaussians.means[:, 1] >= 0
    else:
        mask = gaussians.means[:, 1] > 0

    return Gaussians(
        means=gaussians.means[mask],
        scales=gaussians.scales[mask],
        quats=gaussians.quats[mask],
        opacities=gaussians.opacities[mask],
        sh_coeffs=gaussians.sh_coeffs[mask],
    )


# Alias for backward compatibility
filter_positive_x = filter_positive_y
