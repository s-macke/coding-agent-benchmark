"""Sprite and JSON loading functions."""

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
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
        img_path = images_dir / sprite['filename']
        img = Image.open(img_path).convert('RGBA')
        img_tensor = torch.from_numpy(np.array(img)).float() / 255.0
        images.append(img_tensor)
        metadata.append(sprite)

    return images, metadata
