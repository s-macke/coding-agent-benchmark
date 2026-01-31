#!/usr/bin/env python3
"""
Convert ship sprites to square images with the center of rotation at the image center.

The x and y values in ship_sprites.json specify the offset from the sprite's top-left
corner to the ship's center of rotation. This tool creates new images where that
center point is placed at the center of an auto-calculated canvas size.

The canvas size is automatically determined to be the minimum square size that can
contain all sprites when centered by their rotation point, ensuring no clipping.

Usage:
    python center_sprites.py --input-dir DIR [--black-bg] [--output-dir DIR] [--scale4x] [--crosshair]

Options:
    --input-dir     Input directory containing ship_sprites.json and images (required)
    --black-bg      Replace transparency with black background
    --output-dir    Output directory (default: centered_images)
    --scale4x       Scale output images by 4x using nearest neighbor
    --crosshair     Draw horizontal and vertical lines through the center
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


@dataclass
class InputSprite:
    """Raw sprite data loaded from JSON (before centering)."""
    block: int
    row: Optional[int]
    yaw: float
    pitch: float
    x: int  # offset from top-left to rotation center
    y: int
    filename: str
    camera_up: Tuple[float, float, float]
    camera_right: Tuple[float, float, float]
    type: Optional[str] = None


@dataclass
class CenteredSprite:
    """Output sprite metadata (after centering)."""
    block: int
    row: Optional[int]
    yaw: float
    pitch: float
    width: int
    height: int
    x: int  # always -center (rotation point at center)
    y: int
    filename: str
    camera_up: Tuple[float, float, float]
    camera_right: Tuple[float, float, float]
    type: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


def load_sprites(json_path: Path) -> List[InputSprite]:
    """Load sprite metadata from JSON file.

    Args:
        json_path: Path to JSON file with sprite metadata

    Returns:
        List of InputSprite objects

    Raises:
        FileNotFoundError: If JSON file not found
        KeyError: If required field missing from JSON
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    sprites = []
    for sprite in data['sprites']:
        sprites.append(InputSprite(
            block=sprite['block'],
            row=sprite.get('row'),
            yaw=sprite['yaw'],
            pitch=sprite['pitch'],
            x=sprite['x'],
            y=sprite['y'],
            filename=sprite['filename'],
            camera_up=tuple(sprite['camera_up']),
            camera_right=tuple(sprite['camera_right']),
            type=sprite.get('type'),
        ))

    return sprites


def calculate_optimal_size(sprites: List[InputSprite], images_dir: Path) -> int:
    """
    Calculate the optimal canvas size to fit all sprites when centered.

    For each sprite with width=W, height=H, x_offset=X (negative), y_offset=Y (negative):
    - Left extent: abs(X) (how far left of center)
    - Right extent: W + X (how far right of center)
    - Top extent: abs(Y) (how far above center)
    - Bottom extent: H + Y (how far below center)

    Returns the minimum square size: 2 * max(all extents)
    """
    max_extent = 0

    for sprite in sprites:
        sprite_path = images_dir / sprite.filename
        if not sprite_path.exists():
            continue

        # Get sprite dimensions
        with Image.open(sprite_path) as img:
            width, height = img.size

        # Calculate extents from center of rotation
        left_extent = abs(sprite.x)
        right_extent = width + sprite.x
        top_extent = abs(sprite.y)
        bottom_extent = height + sprite.y

        # Track maximum extent
        max_extent = max(max_extent, left_extent, right_extent, top_extent, bottom_extent)

    # Canvas size is 2 * max_extent to accommodate the largest extent on each side
    return 2 * max_extent


def center_sprite(
    sprite_path: Path,
    x_offset: int,
    y_offset: int,
    output_size: int,
    black_bg: bool = False,
    scale4x: bool = False,
    crosshair: bool = False,
) -> Image.Image:
    """
    Create a new image with the sprite centered by its rotation point.

    Args:
        sprite_path: Path to the source sprite image
        x_offset: X offset from top-left to center of rotation (negative value)
        y_offset: Y offset from top-left to center of rotation (negative value)
        output_size: Size of the output square image
        black_bg: If True, replace transparency with black
        scale4x: If True, scale output by 4x using nearest neighbor
        crosshair: If True, draw horizontal and vertical lines through center

    Returns:
        PIL.Image: The centered image
    """
    # Load the sprite
    sprite = Image.open(sprite_path).convert('RGBA')

    # Calculate where to place the sprite's top-left corner
    # so that the center of rotation ends up at the canvas center
    # x_offset is negative, e.g., -56 means center is 56 pixels right of top-left
    center = output_size // 2
    paste_x = center + x_offset-2  # e.g., 64 + (-56) = 8
    paste_y = center + y_offset-2  # e.g., 64 + (-34) = 30

    # Create the output canvas
    if black_bg:
        canvas = Image.new('RGBA', (output_size, output_size), (0, 0, 0, 255))
    else:
        canvas = Image.new('RGBA', (output_size, output_size), (0, 0, 0, 0))

    # Paste the sprite onto the canvas
    canvas.paste(sprite, (paste_x, paste_y), sprite)

    # If black background requested, composite onto black
    if black_bg:
        background = Image.new('RGBA', (output_size, output_size), (0, 0, 0, 255))
        canvas = Image.alpha_composite(background, canvas)

    # Scale by 4x using nearest neighbor (no interpolation)
    if scale4x:
        new_size = output_size * 4
        canvas = canvas.resize((new_size, new_size), Image.NEAREST)
        center = new_size // 2

    # Draw crosshair lines through center
    if crosshair:
        draw = ImageDraw.Draw(canvas)
        width, height = canvas.size
        line_color = (255, 0, 0, 255)  # Red
        # Horizontal line
        draw.line([(0, center), (width, center)], fill=line_color, width=1)
        # Vertical line
        draw.line([(center, 0), (center, height)], fill=line_color, width=1)

    return canvas


def main():
    parser = argparse.ArgumentParser(
        description='Center ship sprites by their rotation point with auto-calculated canvas size.'
    )
    parser.add_argument(
        '--input-dir',
        required=True,
        help='Input directory containing ship_sprites.json and images'
    )
    parser.add_argument(
        '--black-bg',
        action='store_true',
        help='Replace transparency with black background'
    )
    parser.add_argument(
        '--output-dir',
        default='centered_images',
        help='Output directory (default: centered_images)'
    )
    parser.add_argument(
        '--scale4x',
        action='store_true',
        help='Scale output images by 4x using nearest neighbor (no interpolation)'
    )
    parser.add_argument(
        '--crosshair',
        action='store_true',
        help='Draw horizontal and vertical lines through the center'
    )
    parser.add_argument(
        '--orthogonal-only',
        action='store_true',
        help='Only include orthogonal views (pitch 0/±90, yaw 0/90/180)'
    )
    parser.add_argument(
        '--any-cardinal',
        action='store_true',
        help='Only include views where at least one angle is cardinal (-90/0/90/180/270)'
    )
    args = parser.parse_args()

    # Determine paths relative to the script location
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent

    input_dir = Path(args.input_dir)
    json_path = input_dir / 'ship_sprites.json'
    images_dir = input_dir
    output_dir = project_dir / args.output_dir

    # Load sprite metadata
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    sprites_to_process = load_sprites(json_path)

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    # Filter sprites
    if args.orthogonal_only:
        orthogonal_pitches = {-90, 0, 90}
        orthogonal_yaws = {0, 90, 180}
        sprites_to_process = [
            s for s in sprites_to_process
            if s.pitch in orthogonal_pitches and s.yaw in orthogonal_yaws
            #if s.pitch in orthogonal_pitches or s.yaw == 0
            #if s.yaw == 0
        ]

    if args.any_cardinal:
        cardinal_angles = {-90, 0, 90, 180, 270}
        sprites_to_process = [
            s for s in sprites_to_process
            if s.pitch in cardinal_angles or s.yaw in cardinal_angles
        ]

    # Calculate optimal canvas size from filtered sprites
    output_size = calculate_optimal_size(sprites_to_process, images_dir)

    print(f"Processing {len(sprites_to_process)} sprites...")
    print(f"Output size: {output_size}x{output_size}" + (f" (scaled to {output_size*4}x{output_size*4})" if args.scale4x else ""))
    print(f"Output directory: {output_dir}")
    print(f"Black background: {args.black_bg}")
    print(f"Scale 4x: {args.scale4x}")
    print(f"Crosshair: {args.crosshair}")
    print()

    processed = 0
    errors = 0
    centered_sprites: List[CenteredSprite] = []

    for sprite in sprites_to_process:
        input_path = images_dir / sprite.filename

        if not input_path.exists():
            print(f"  Warning: {sprite.filename} not found, skipping")
            errors += 1
            continue

        # Generate output filename
        output_filename = f"SHIP_block{sprite.block:02d}_centered.png"
        output_path = output_dir / output_filename

        try:
            centered_img = center_sprite(
                input_path,
                sprite.x,
                sprite.y,
                output_size=output_size,
                black_bg=args.black_bg,
                scale4x=args.scale4x,
                crosshair=args.crosshair,
            )
            centered_img.save(output_path)
            processed += 1
            print(f"  Block {sprite.block:02d}: {sprite.filename} -> {output_filename}")

            # Build centered sprite metadata
            actual_size = output_size * 4 if args.scale4x else output_size
            actual_center = actual_size // 2
            centered_sprite = CenteredSprite(
                block=sprite.block,
                row=sprite.row,
                yaw=sprite.yaw,
                pitch=sprite.pitch,
                width=actual_size,
                height=actual_size,
                x=-actual_center,
                y=-actual_center,
                filename=output_filename,
                type=sprite.type,
                camera_up=sprite.camera_up,
                camera_right=sprite.camera_right,
            )

            centered_sprites.append(centered_sprite)

        except Exception as e:
            print(f"  Error processing {sprite.filename}: {e}")
            errors += 1

    # Write centered JSON
    output_json_path = project_dir / 'ship_sprites_centered.json'
    with open(output_json_path, 'w') as f:
        json.dump({'sprites': [s.to_dict() for s in centered_sprites]}, f, indent=2)

    print()
    print(f"Done! Processed {processed} sprites, {errors} errors.")
    print(f"Output saved to: {output_dir}")
    print(f"JSON saved to: {output_json_path}")


if __name__ == "__main__":
    main()