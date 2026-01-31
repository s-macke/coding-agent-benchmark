"""Symmetry utilities for Gaussian Splatting.

Supports mirror symmetry for Gaussians:
- Y-axis symmetry: reflects about the XZ plane (y=0) for left-right symmetry
- X-axis symmetry: reflects about the YZ plane (x=0) for front-back symmetry
- XY symmetry: combines both axes for models with bilateral and front-back symmetry

This allows storing only a fraction of Gaussians when the model has symmetry.
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

# SH coefficient indices that are odd under x-reflection (x → -x)
# These depend on x linearly or as xy, xz products
# Degree 1: index 2 (Y_1^1 ∝ x)
# Degree 2: index 4 (Y_2^-2 ∝ xy), index 8 (Y_2^2 ∝ x²-y², but actually xz)
# Note: For SH basis in standard form:
#   l=1: m=-1,0,1 → indices 1,2,3 → Y_1^-1 ∝ y, Y_1^0 ∝ z, Y_1^1 ∝ x
#   l=2: m=-2,-1,0,1,2 → indices 4,5,6,7,8 → xy, yz, z², xz, x²-y²
SH_ODD_X_INDICES = {
    0: [],           # degree 0: no odd terms
    1: [2],          # degree 1: index 2 (Y_1^1 ∝ x)
    2: [2, 4, 7],    # degree 2: indices 2, 4 (xy), 7 (xz)
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


# Y-axis symmetry aliases for explicit naming
mirror_positions_y = mirror_positions
mirror_quaternions_y = mirror_quaternions
mirror_sh_coeffs_y = mirror_sh_coeffs
mirror_gaussians_y = mirror_gaussians
expand_symmetric_y = expand_symmetric


# =============================================================================
# X-axis symmetry (front-back, about YZ plane where x=0)
# =============================================================================

def mirror_positions_x(means: Tensor) -> Tensor:
    """Mirror positions about the YZ plane (x=0).

    Args:
        means: [N, 3] positions

    Returns:
        [N, 3] mirrored positions with x negated
    """
    mirrored = means.clone()
    mirrored[:, 0] = -mirrored[:, 0]
    return mirrored


def mirror_quaternions_x(quats: Tensor) -> Tensor:
    """Mirror quaternions about the YZ plane (x=0).

    For a quaternion q = (w, qx, qy, qz), reflection about x=0 gives (w, qx, -qy, -qz).
    The reflection reverses rotation direction for axes in the mirror plane (y, z),
    so we negate qy and qz while keeping qx unchanged.

    Args:
        quats: [N, 4] quaternions in wxyz format

    Returns:
        [N, 4] mirrored quaternions
    """
    mirrored = quats.clone()
    mirrored[:, 2] = -mirrored[:, 2]  # negate qy
    mirrored[:, 3] = -mirrored[:, 3]  # negate qz
    return mirrored


def mirror_sh_coeffs_x(sh_coeffs: Tensor, sh_degree: int) -> Tensor:
    """Mirror SH coefficients about the YZ plane (x=0).

    SH basis functions that are odd in x need their coefficients negated.
    - Degree 1: Y_1^1 (index 2) ∝ x
    - Degree 2: Y_2^-2 (index 4) ∝ xy, Y_2^1 (index 7) ∝ xz

    Args:
        sh_coeffs: [N, K, 3] SH coefficients where K = (degree+1)^2
        sh_degree: SH degree (0, 1, or 2)

    Returns:
        [N, K, 3] mirrored SH coefficients
    """
    mirrored = sh_coeffs.clone()
    odd_indices = SH_ODD_X_INDICES.get(sh_degree, [])
    for idx in odd_indices:
        if idx < mirrored.shape[1]:
            mirrored[:, idx, :] = -mirrored[:, idx, :]
    return mirrored


def mirror_gaussians_x(gaussians: Gaussians) -> Gaussians:
    """Mirror Gaussians about the YZ plane (x=0).

    Creates a mirrored copy of all Gaussians with:
    - Positions: x negated
    - Quaternions: qy and qz components negated
    - SH coefficients: odd-x terms negated
    - Scales and opacities unchanged

    Args:
        gaussians: Original Gaussians

    Returns:
        New Gaussians mirrored about x=0
    """
    return Gaussians(
        means=mirror_positions_x(gaussians.means),
        scales=gaussians.scales.clone(),
        quats=mirror_quaternions_x(gaussians.quats),
        opacities=gaussians.opacities.clone(),
        sh_coeffs=mirror_sh_coeffs_x(gaussians.sh_coeffs, gaussians.sh_degree),
    )


def expand_symmetric_x(gaussians: Gaussians) -> Gaussians:
    """Expand symmetric Gaussians by adding their x-mirrored copies.

    Takes Gaussians (typically with x >= 0) and returns doubled Gaussians
    containing both original and x-mirrored copies.

    Args:
        gaussians: Gaussians to expand (canonical half)

    Returns:
        Gaussians with original + mirrored (2N total)
    """
    mirrored = mirror_gaussians_x(gaussians)
    return Gaussians(
        means=torch.cat([gaussians.means, mirrored.means], dim=0),
        scales=torch.cat([gaussians.scales, mirrored.scales], dim=0),
        quats=torch.cat([gaussians.quats, mirrored.quats], dim=0),
        opacities=torch.cat([gaussians.opacities, mirrored.opacities], dim=0),
        sh_coeffs=torch.cat([gaussians.sh_coeffs, mirrored.sh_coeffs], dim=0),
    )


def filter_positive_x(gaussians: Gaussians, include_zero: bool = True) -> Gaussians:
    """Filter Gaussians to keep only those with x >= 0 (or x > 0).

    Args:
        gaussians: Input Gaussians
        include_zero: If True, keep x >= 0; if False, keep x > 0

    Returns:
        Filtered Gaussians with only positive-x positions
    """
    if include_zero:
        mask = gaussians.means[:, 0] >= 0
    else:
        mask = gaussians.means[:, 0] > 0

    return Gaussians(
        means=gaussians.means[mask],
        scales=gaussians.scales[mask],
        quats=gaussians.quats[mask],
        opacities=gaussians.opacities[mask],
        sh_coeffs=gaussians.sh_coeffs[mask],
    )


# =============================================================================
# XY symmetry (both axes, quadrant symmetry)
# =============================================================================

def expand_symmetric_xy(gaussians: Gaussians) -> Gaussians:
    """Expand symmetric Gaussians by both X and Y mirroring.

    Takes Gaussians (typically with x >= 0 AND y >= 0) and returns 4x Gaussians
    containing original plus all mirrored quadrants.

    Order: original, y-mirrored, x-mirrored, xy-mirrored (both)

    Args:
        gaussians: Gaussians to expand (canonical quadrant)

    Returns:
        Gaussians with 4x expansion (4N total)
    """
    # First expand in Y (original + y-mirrored)
    y_expanded = expand_symmetric(gaussians)
    # Then expand the result in X (doubles again: original, y-mir, x-mir, xy-mir)
    return expand_symmetric_x(y_expanded)


def filter_positive_xy(gaussians: Gaussians, include_zero: bool = True) -> Gaussians:
    """Filter Gaussians to keep only those with x >= 0 AND y >= 0.

    Args:
        gaussians: Input Gaussians
        include_zero: If True, keep >= 0; if False, keep > 0

    Returns:
        Filtered Gaussians with only positive-x and positive-y positions
    """
    if include_zero:
        mask = (gaussians.means[:, 0] >= 0) & (gaussians.means[:, 1] >= 0)
    else:
        mask = (gaussians.means[:, 0] > 0) & (gaussians.means[:, 1] > 0)

    return Gaussians(
        means=gaussians.means[mask],
        scales=gaussians.scales[mask],
        quats=gaussians.quats[mask],
        opacities=gaussians.opacities[mask],
        sh_coeffs=gaussians.sh_coeffs[mask],
    )
