"""Sprite data loading functions."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from .camera import CameraCollection

from .camera import CameraType


@dataclass
class SpriteData:
    """Typed sprite metadata from JSON with associated image.

    All fields except row and type are required.
    """
    block: int
    yaw: float
    pitch: float
    width: int
    height: int
    x: int
    y: int
    filename: str
    camera_up: Tuple[float, float, float]
    camera_right: Tuple[float, float, float]
    image: Image.Image
    row: Optional[int] = None
    type: Optional[str] = None


def load_sprites(json_path: Path, images_dir: Path) -> List[SpriteData]:
    """Load sprites with metadata and PIL Images.

    Args:
        json_path: Path to JSON file with sprite metadata
        images_dir: Directory containing sprite images

    Returns:
        List of SpriteData objects with loaded images

    Raises:
        KeyError: If required field missing from JSON
        FileNotFoundError: If image file not found
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    sprites = []

    for sprite in data['sprites']:
        img_path = images_dir / sprite['filename']
        img = Image.open(img_path).convert('RGBA')

        sprites.append(SpriteData(
            block=sprite['block'],
            yaw=sprite['yaw'],
            pitch=sprite['pitch'],
            width=sprite['width'],
            height=sprite['height'],
            x=sprite['x'],
            y=sprite['y'],
            filename=sprite['filename'],
            camera_up=tuple(sprite['camera_up']),
            camera_right=tuple(sprite['camera_right']),
            image=img,
            row=sprite.get('row'),
            type=sprite.get('type'),
        ))

    return sprites


def load_cameras(
    json_path: Path,
    images_dir: Path,
    camera_type: CameraType = CameraType.ORTHOGRAPHIC,
    ortho_scale: float = 2.0,
    fov_deg: float = 60.0,
) -> "CameraCollection":
    """Load sprites and build camera collection.

    Convenience function combining load_sprites() and CameraCollection.from_sprites().

    Args:
        json_path: Path to JSON file with sprite metadata
        images_dir: Directory containing sprite images
        camera_type: CameraType.ORTHOGRAPHIC or CameraType.PERSPECTIVE
        ortho_scale: (orthographic) world units visible in half the image
        fov_deg: (perspective) vertical field of view in degrees

    Returns:
        CameraCollection with cameras and images
    """
    from .camera import CameraCollection

    sprites = load_sprites(json_path, images_dir)
    return CameraCollection.from_sprites(
        sprites,
        camera_type=camera_type,
        ortho_scale=ortho_scale,
        fov_deg=fov_deg,
    )
