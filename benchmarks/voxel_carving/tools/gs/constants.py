"""Shared constants for Gaussian splatting."""

# Image and rendering constants
IMAGE_SIZE = 128
ALPHA_THRESHOLD = 0.5

# Spherical harmonics constants
SH_DEGREE = 2  # SH degree for view-dependent color (0, 1, or 2)
SH_C0 = 0.28209479177387814  # DC normalization factor

# Sprite data paths (relative to project root)
SPRITES_JSON = 'ship_sprites_centered.json'
SPRITES_DIR = 'centered_images'
