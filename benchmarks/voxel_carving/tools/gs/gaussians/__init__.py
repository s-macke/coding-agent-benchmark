"""Gaussian representation and utilities."""

from .gaussians import Gaussians
from .sh import eval_sh, rgb_to_sh, sh_to_rgb, init_sh_from_rgb, SH_C0, SH_DEGREE
from .ply import load_ply, export_ply
from .symmetry import (
    # Y-axis symmetry (left-right, about XZ plane)
    mirror_gaussians,
    expand_symmetric,
    filter_positive_y,
    # X-axis symmetry (front-back, about YZ plane)
    mirror_gaussians_x,
    expand_symmetric_x,
    filter_positive_x,
    # XY symmetry (both axes, quadrant)
    expand_symmetric_xy,
    filter_positive_xy,
)

__all__ = [
    "Gaussians",
    "eval_sh", "rgb_to_sh", "sh_to_rgb", "init_sh_from_rgb", "SH_C0", "SH_DEGREE",
    "load_ply", "export_ply",
    # Y-axis symmetry
    "mirror_gaussians", "expand_symmetric", "filter_positive_y",
    # X-axis symmetry
    "mirror_gaussians_x", "expand_symmetric_x", "filter_positive_x",
    # XY symmetry
    "expand_symmetric_xy", "filter_positive_xy",
]
