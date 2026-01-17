"""Spherical Harmonics utilities for Gaussian Splatting.

Supports SH up to degree 2 (9 coefficients per color channel).
"""

import torch
from torch import Tensor

# SH basis function constants
# These are the normalization factors for real spherical harmonics
SH_C0 = 0.28209479177387814  # 1 / (2 * sqrt(pi))
SH_C1 = 0.4886025119029199   # sqrt(3) / (2 * sqrt(pi))
SH_C2_0 = 1.0925484305920792   # sqrt(15) / (2 * sqrt(pi))
SH_C2_1 = -1.0925484305920792  # -sqrt(15) / (2 * sqrt(pi))
SH_C2_2 = 0.31539156525252005  # sqrt(5) / (4 * sqrt(pi))
SH_C2_3 = -1.0925484305920792  # -sqrt(15) / (2 * sqrt(pi))
SH_C2_4 = 0.5462742152960396   # sqrt(15) / (4 * sqrt(pi))

# Number of coefficients per degree
SH_DEGREE_COEFFS = {0: 1, 1: 4, 2: 9, 3: 16}

# Default SH degree for view-dependent color
SH_DEGREE = 2


def rgb_to_sh(rgb: Tensor) -> Tensor:
    """Convert RGB color to SH DC (degree 0) coefficient.

    Args:
        rgb: [..., 3] RGB values in [0, 1]

    Returns:
        [..., 3] SH DC coefficients
    """
    return (rgb - 0.5) / SH_C0


def sh_to_rgb(sh: Tensor) -> Tensor:
    """Convert SH DC (degree 0) coefficient to RGB color.

    Args:
        sh: [..., 3] SH DC coefficients

    Returns:
        [..., 3] RGB values (not clamped)
    """
    return sh * SH_C0 + 0.5


def eval_sh_deg0(sh: Tensor, dirs: Tensor) -> Tensor:
    """Evaluate degree 0 SH (constant/DC term only).

    Args:
        sh: [N, 1, 3] or [N, 3] SH coefficients (DC only)
        dirs: [N, 3] normalized viewing directions (unused for deg 0)

    Returns:
        [N, 3] RGB colors
    """
    if sh.dim() == 3:
        sh = sh[:, 0, :]  # [N, 3]
    return SH_C0 * sh + 0.5


def eval_sh_deg1(sh: Tensor, dirs: Tensor) -> Tensor:
    """Evaluate degree 0-1 SH.

    Args:
        sh: [N, 4, 3] SH coefficients (degrees 0-1)
        dirs: [N, 3] normalized viewing directions

    Returns:
        [N, 3] RGB colors
    """
    x = dirs[:, 0:1]  # [N, 1]
    y = dirs[:, 1:2]
    z = dirs[:, 2:3]

    result = SH_C0 * sh[:, 0]  # DC term
    result = result - SH_C1 * y * sh[:, 1]
    result = result + SH_C1 * z * sh[:, 2]
    result = result - SH_C1 * x * sh[:, 3]

    return result + 0.5


def eval_sh_deg2(sh: Tensor, dirs: Tensor) -> Tensor:
    """Evaluate degree 0-2 SH.

    Args:
        sh: [N, 9, 3] SH coefficients (degrees 0-2)
        dirs: [N, 3] normalized viewing directions

    Returns:
        [N, 3] RGB colors
    """
    x = dirs[:, 0:1]  # [N, 1]
    y = dirs[:, 1:2]
    z = dirs[:, 2:3]

    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    yz = y * z
    xz = x * z

    # Degree 0
    result = SH_C0 * sh[:, 0]

    # Degree 1
    result = result - SH_C1 * y * sh[:, 1]
    result = result + SH_C1 * z * sh[:, 2]
    result = result - SH_C1 * x * sh[:, 3]

    # Degree 2
    result = result + SH_C2_0 * xy * sh[:, 4]
    result = result + SH_C2_1 * yz * sh[:, 5]
    result = result + SH_C2_2 * (2.0 * zz - xx - yy) * sh[:, 6]
    result = result + SH_C2_3 * xz * sh[:, 7]
    result = result + SH_C2_4 * (xx - yy) * sh[:, 8]

    return result + 0.5


def eval_sh(sh: Tensor, dirs: Tensor, degree: int = 2) -> Tensor:
    """Evaluate SH at given directions.

    Args:
        sh: [N, K, 3] SH coefficients where K = (degree+1)^2
        dirs: [N, 3] normalized viewing directions (Gaussian to camera)

    Returns:
        [N, 3] RGB colors (clamped to [0, 1])
    """
    if degree == 0:
        rgb = eval_sh_deg0(sh, dirs)
    elif degree == 1:
        rgb = eval_sh_deg1(sh, dirs)
    elif degree == 2:
        rgb = eval_sh_deg2(sh, dirs)
    else:
        raise ValueError(f"SH degree {degree} not supported (max 2)")

    return torch.clamp(rgb, 0.0, 1.0)


def init_sh_from_rgb(rgb: Tensor, sh_degree: int = 2) -> Tensor:
    """Initialize SH coefficients from RGB colors.

    Sets the DC term to match the RGB color, higher order terms to zero.

    Args:
        rgb: [N, 3] RGB values in [0, 1]
        sh_degree: SH degree (0, 1, or 2)

    Returns:
        [N, K, 3] SH coefficients where K = (sh_degree+1)^2
    """
    n = rgb.shape[0]
    num_coeffs = (sh_degree + 1) ** 2

    sh = torch.zeros(n, num_coeffs, 3, dtype=rgb.dtype, device=rgb.device)
    sh[:, 0, :] = rgb_to_sh(rgb)

    return sh
