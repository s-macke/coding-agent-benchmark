#!/usr/bin/env python3
"""
Generate ship_sprites.json from image filenames.

Parses image filenames in format: SHIP_block{NN}_sub{NN}_w{W}_h{H}_x{X}_y{Y}.png
Supports both V08 (37 blocks) and V21 (17 blocks) layouts with auto-detection.

Usage:
    python generate_sprites_json.py --input-dir images/SHIP.V08
    python generate_sprites_json.py --input-dir images/SHIP.V21
"""

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class CameraData:
    """Camera parameters for a sprite block."""
    row: Optional[int]
    yaw: int
    pitch: int
    camera_up: Tuple[float, float, float]
    camera_right: Tuple[float, float, float]
    type: Optional[str] = None


@dataclass
class ParsedFilename:
    """Data extracted from sprite filename."""
    block: int
    sub: int
    width: int
    height: int
    x: int
    y: int


@dataclass
class SpriteData:
    """Complete sprite metadata for JSON output."""
    block: int
    row: Optional[int]
    yaw: int
    pitch: int
    width: int
    height: int
    x: int
    y: int
    filename: str
    camera_up: Tuple[float, float, float]
    camera_right: Tuple[float, float, float]
    type: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


# Camera data for V08 layout: 37 blocks (full 360-degree coverage)
# Block 0: bottom, Blocks 1-7: pitch 60, Blocks 8-14: pitch 30,
# Blocks 15-21: pitch 0, Blocks 22-28: pitch -30, Blocks 29-35: pitch -60, Block 36: top
CAMERA_DATA_V08: List[CameraData] = [
    # block 0: bottom view
    CameraData(row=None, yaw=0, pitch=90, type='bottom',
               camera_up=(0, -1, 0), camera_right=(-1, 0, 0)),
    # blocks 1-7: row 0 (pitch 60)
    CameraData(row=0, yaw=180, pitch=60,
               camera_up=(-0.866025, -0.0, 0.5), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=0, yaw=150, pitch=60,
               camera_up=(-0.75, -0.433013, 0.5), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=0, yaw=120, pitch=60,
               camera_up=(-0.433013, -0.75, 0.5), camera_right=(-0.866025, 0.5, 0.0)),
    CameraData(row=0, yaw=90, pitch=60,
               camera_up=(0.0, -0.866025, 0.5), camera_right=(-1.0, -0.0, 0.0)),
    CameraData(row=0, yaw=60, pitch=60,
               camera_up=(0.433013, -0.75, 0.5), camera_right=(-0.866025, -0.5, 0.0)),
    CameraData(row=0, yaw=30, pitch=60,
               camera_up=(0.75, -0.433013, 0.5), camera_right=(-0.5, -0.866025, 0.0)),
    CameraData(row=0, yaw=0, pitch=60,
               camera_up=(0.866025, 0.0, 0.5), camera_right=(0.0, -1.0, 0.0)),
    # blocks 8-14: row 1 (pitch 30)
    CameraData(row=1, yaw=0, pitch=30,
               camera_up=(0.5, 0.0, 0.866025), camera_right=(0.0, -1.0, 0.0)),
    CameraData(row=1, yaw=30, pitch=30,
               camera_up=(0.433013, -0.25, 0.866025), camera_right=(-0.5, -0.866025, 0.0)),
    CameraData(row=1, yaw=60, pitch=30,
               camera_up=(0.25, -0.433013, 0.866025), camera_right=(-0.866025, -0.5, 0.0)),
    CameraData(row=1, yaw=90, pitch=30,
               camera_up=(0.0, -0.5, 0.866025), camera_right=(-1.0, -0.0, 0.0)),
    CameraData(row=1, yaw=120, pitch=30,
               camera_up=(-0.25, -0.433013, 0.866025), camera_right=(-0.866025, 0.5, 0.0)),
    CameraData(row=1, yaw=150, pitch=30,
               camera_up=(-0.433013, -0.25, 0.866025), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=1, yaw=180, pitch=30,
               camera_up=(-0.5, -0.0, 0.866025), camera_right=(-0.0, 1.0, 0.0)),
    # blocks 15-21: row 2 (pitch 0)
    CameraData(row=2, yaw=180, pitch=0, type='front',
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=2, yaw=150, pitch=0,
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=2, yaw=120, pitch=0,
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.866025, 0.5, 0.0)),
    CameraData(row=2, yaw=90, pitch=0,
               camera_up=(0.0, 0.0, 1.0), camera_right=(-1.0, -0.0, 0.0)),
    CameraData(row=2, yaw=60, pitch=0,
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.866025, -0.5, 0.0)),
    CameraData(row=2, yaw=30, pitch=0,
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.5, -0.866025, 0.0)),
    CameraData(row=2, yaw=0, pitch=0,
               camera_up=(-0.0, 0.0, 1.0), camera_right=(0.0, -1.0, 0.0)),
    # blocks 22-28: row 3 (pitch -30)
    CameraData(row=3, yaw=0, pitch=-30,
               camera_up=(-0.5, 0.0, 0.866025), camera_right=(0.0, -1.0, 0.0)),
    CameraData(row=3, yaw=30, pitch=-30,
               camera_up=(-0.433013, 0.25, 0.866025), camera_right=(-0.5, -0.866025, 0.0)),
    CameraData(row=3, yaw=60, pitch=-30,
               camera_up=(-0.25, 0.433013, 0.866025), camera_right=(-0.866025, -0.5, 0.0)),
    CameraData(row=3, yaw=90, pitch=-30,
               camera_up=(-0.0, 0.5, 0.866025), camera_right=(-1.0, -0.0, 0.0)),
    CameraData(row=3, yaw=120, pitch=-30,
               camera_up=(0.25, 0.433013, 0.866025), camera_right=(-0.866025, 0.5, 0.0)),
    CameraData(row=3, yaw=150, pitch=-30,
               camera_up=(0.433013, 0.25, 0.866025), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=3, yaw=180, pitch=-30,
               camera_up=(0.5, 0.0, 0.866025), camera_right=(-0.0, 1.0, 0.0)),
    # blocks 29-35: row 4 (pitch -60)
    CameraData(row=4, yaw=180, pitch=-60,
               camera_up=(0.866025, 0.0, 0.5), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=4, yaw=150, pitch=-60,
               camera_up=(0.75, 0.433013, 0.5), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=4, yaw=120, pitch=-60,
               camera_up=(0.433013, 0.75, 0.5), camera_right=(-0.866025, 0.5, 0.0)),
    CameraData(row=4, yaw=90, pitch=-60,
               camera_up=(-0.0, 0.866025, 0.5), camera_right=(-1.0, -0.0, 0.0)),
    CameraData(row=4, yaw=60, pitch=-60,
               camera_up=(-0.433013, 0.75, 0.5), camera_right=(-0.866025, -0.5, 0.0)),
    CameraData(row=4, yaw=30, pitch=-60,
               camera_up=(-0.75, 0.433013, 0.5), camera_right=(-0.5, -0.866025, 0.0)),
    CameraData(row=4, yaw=0, pitch=-60,
               camera_up=(-0.866025, 0.0, 0.5), camera_right=(0.0, -1.0, 0.0)),
    # block 36: top view
    CameraData(row=None, yaw=0, pitch=-90, type='top',
               camera_up=(0, 1, 0), camera_right=(-1, 0, 0)),
]

# Camera data for V21 layout: 17 blocks (left-right symmetry, only left half)
# Block 0: bottom, Blocks 1-3: pitch 60, Blocks 4-6: pitch 30,
# Blocks 7-9: pitch 0, Blocks 10-12: pitch -30, Blocks 13-15: pitch -60, Block 16: top
CAMERA_DATA_V21: List[CameraData] = [
    # block 0: bottom view
    CameraData(row=None, yaw=0, pitch=90, type='bottom',
               camera_up=(0, -1, 0), camera_right=(-1, 0, 0)),
    # blocks 1-3: row 0 (pitch 60), yaw: 180, 150, 120
    CameraData(row=0, yaw=180, pitch=60,
               camera_up=(-0.866025, -0.0, 0.5), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=0, yaw=150, pitch=60,
               camera_up=(-0.75, -0.433013, 0.5), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=0, yaw=120, pitch=60,
               camera_up=(-0.433013, -0.75, 0.5), camera_right=(-0.866025, 0.5, 0.0)),
    # blocks 4-6: row 1 (pitch 30), yaw: 180, 150, 120
    CameraData(row=1, yaw=180, pitch=30,
               camera_up=(-0.5, -0.0, 0.866025), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=1, yaw=150, pitch=30,
               camera_up=(-0.433013, -0.25, 0.866025), camera_right=(0.5, -0.866025, 0.0)),
    CameraData(row=1, yaw=120, pitch=30,
               camera_up=(-0.25, -0.433013, 0.866025), camera_right=(0.866025, -0.5, 0.0)),
    # blocks 7-9: row 2 (pitch 0), yaw: 180 (front), 150, 120
    CameraData(row=2, yaw=180, pitch=0, type='front',
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=2, yaw=150, pitch=0,
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=2, yaw=120, pitch=0,
               camera_up=(0.0, 0.0, 1.0), camera_right=(-0.866025, 0.5, 0.0)),
    # blocks 10-12: row 3 (pitch -30), yaw: 180, 150, 120
    CameraData(row=3, yaw=180, pitch=-30,
               camera_up=(0.5, 0.0, 0.866025), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=3, yaw=150, pitch=-30,
               camera_up=(0.433013, 0.25, 0.866025), camera_right=(0.5, -0.866025, 0.0)),
    CameraData(row=3, yaw=120, pitch=-30,
               camera_up=(0.25, 0.433013, 0.866025), camera_right=(0.866025, -0.5, 0.0)),
    # blocks 13-15: row 4 (pitch -60), yaw: 180, 150, 120
    CameraData(row=4, yaw=180, pitch=-60,
               camera_up=(0.866025, 0.0, 0.5), camera_right=(-0.0, 1.0, 0.0)),
    CameraData(row=4, yaw=150, pitch=-60,
               camera_up=(0.75, 0.433013, 0.5), camera_right=(-0.5, 0.866025, 0.0)),
    CameraData(row=4, yaw=120, pitch=-60,
               camera_up=(0.433013, 0.75, 0.5), camera_right=(-0.866025, 0.5, 0.0)),
    # block 16: top view
    CameraData(row=None, yaw=0, pitch=-90, type='top',
               camera_up=(0, 1, 0), camera_right=(-1, 0, 0)),
]


def parse_filename(filename: str) -> Optional[ParsedFilename]:
    """Parse SHIP_block00_sub00_w152_h77_x-74_y-37.png format."""
    pattern = r'SHIP_block(\d+)_sub(\d+)_w(\d+)_h(\d+)_x(-?\d+)_y(-?\d+)\.png'
    match = re.match(pattern, filename)
    if match:
        return ParsedFilename(
            block=int(match.group(1)),
            sub=int(match.group(2)),
            width=int(match.group(3)),
            height=int(match.group(4)),
            x=int(match.group(5)),
            y=int(match.group(6)),
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate ship_sprites.json from image filenames'
    )
    parser.add_argument('--input-dir', required=True,
                        help='Directory containing SHIP_block*.png images')
    parser.add_argument('--output', '-o',
                        help='Output JSON file (default: <input-dir>/ship_sprites.json)')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist")
        return 1

    # Count images to auto-detect layout
    images = sorted(input_dir.glob('SHIP_block*.png'))
    image_count = len(images)

    # Select camera data based on image count
    if image_count == 17:
        camera_data = CAMERA_DATA_V21
        layout = "V21"
    elif image_count == 37:
        camera_data = CAMERA_DATA_V08
        layout = "V08"
    else:
        print(f"Error: Found {image_count} images, expected 17 (V21) or 37 (V08)")
        return 1

    print(f"Detected {layout} layout with {image_count} images")

    sprites: List[SpriteData] = []
    for img in images:
        parsed = parse_filename(img.name)
        if parsed is None:
            print(f"Warning: Could not parse filename '{img.name}'")
            continue

        block = parsed.block
        if block >= len(camera_data):
            print(f"Warning: Block {block} exceeds camera data range (0-{len(camera_data)-1})")
            continue

        cam = camera_data[block]
        sprite = SpriteData(
            block=block,
            row=cam.row,
            yaw=cam.yaw,
            pitch=cam.pitch,
            width=parsed.width,
            height=parsed.height,
            x=parsed.x,
            y=parsed.y,
            filename=img.name,
            type=cam.type,
            camera_up=cam.camera_up,
            camera_right=cam.camera_right,
        )

        sprites.append(sprite)

    sprites.sort(key=lambda s: s.block)

    output_path = Path(args.output) if args.output else input_dir / 'ship_sprites.json'
    with open(output_path, 'w') as f:
        json.dump({'sprites': [s.to_dict() for s in sprites]}, f, indent=2)

    print(f"Generated {output_path} with {len(sprites)} sprites")
    return 0


if __name__ == '__main__':
    exit(main())
