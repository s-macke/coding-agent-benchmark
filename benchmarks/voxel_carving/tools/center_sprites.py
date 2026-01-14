#!/usr/bin/env python3
"""
Convert ship sprites to 128x128 images with the center of rotation at the image center.

The x and y values in ship_sprites.json specify the offset from the sprite's top-left
corner to the ship's center of rotation. This tool creates new images where that
center point is placed at the center of a 128x128 canvas.

Usage:
    python center_sprites.py [--black-bg] [--output-dir DIR]

Options:
    --black-bg      Replace transparency with black background
    --output-dir    Output directory (default: centered_images)
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


def center_sprite(sprite_path, x_offset, y_offset, output_size=128, black_bg=False):
    """
    Create a new image with the sprite centered by its rotation point.

    Args:
        sprite_path: Path to the source sprite image
        x_offset: X offset from top-left to center of rotation (negative value)
        y_offset: Y offset from top-left to center of rotation (negative value)
        output_size: Size of the output square image
        black_bg: If True, replace transparency with black

    Returns:
        PIL.Image: The centered image
    """
    # Load the sprite
    sprite = Image.open(sprite_path).convert('RGBA')

    # Calculate where to place the sprite's top-left corner
    # so that the center of rotation ends up at the canvas center
    # x_offset is negative, e.g., -56 means center is 56 pixels right of top-left
    center = output_size // 2
    paste_x = center + x_offset  # e.g., 64 + (-56) = 8
    paste_y = center + y_offset  # e.g., 64 + (-34) = 30

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

    return canvas


def main():
    parser = argparse.ArgumentParser(
        description='Center ship sprites by their rotation point in 128x128 images.'
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
        '--size',
        type=int,
        default=128,
        help='Output image size (default: 128)'
    )
    args = parser.parse_args()

    # Determine paths relative to the script location
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent

    json_path = project_dir / 'ship_sprites.json'
    images_dir = project_dir / 'images'
    output_dir = project_dir / args.output_dir

    # Load sprite metadata
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    with open(json_path, 'r') as f:
        data = json.load(f)

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    print(f"Processing {len(data['sprites'])} sprites...")
    print(f"Output size: {args.size}x{args.size}")
    print(f"Output directory: {output_dir}")
    print(f"Black background: {args.black_bg}")
    print()

    processed = 0
    errors = 0
    centered_sprites = []
    center = args.size // 2

    for sprite in data['sprites']:
        filename = sprite['filename']
        x_offset = sprite['x']
        y_offset = sprite['y']
        block = sprite['block']

        input_path = images_dir / filename

        if not input_path.exists():
            print(f"  Warning: {filename} not found, skipping")
            errors += 1
            continue

        # Generate output filename
        output_filename = f"SHIP_block{block:02d}_centered.png"
        output_path = output_dir / output_filename

        try:
            centered = center_sprite(
                input_path,
                x_offset,
                y_offset,
                output_size=args.size,
                black_bg=args.black_bg
            )
            centered.save(output_path)
            processed += 1
            print(f"  Block {block:02d}: {filename} -> {output_filename}")

            # Build centered sprite metadata
            centered_sprite = {
                'block': sprite['block'],
                'row': sprite['row'],
                'yaw': sprite['yaw'],
                'pitch': sprite['pitch'],
                'width': args.size,
                'height': args.size,
                'x': -center,
                'y': -center,
                'filename': output_filename,
            }
            # Copy optional fields
            if 'type' in sprite:
                centered_sprite['type'] = sprite['type']
            if 'camera_up' in sprite:
                centered_sprite['camera_up'] = sprite['camera_up']
            if 'camera_right' in sprite:
                centered_sprite['camera_right'] = sprite['camera_right']

            centered_sprites.append(centered_sprite)

        except Exception as e:
            print(f"  Error processing {filename}: {e}")
            errors += 1

    # Write centered JSON
    output_json_path = project_dir / 'ship_sprites_centered.json'
    with open(output_json_path, 'w') as f:
        json.dump({'sprites': centered_sprites}, f, indent=2)

    print()
    print(f"Done! Processed {processed} sprites, {errors} errors.")
    print(f"Output saved to: {output_dir}")
    print(f"JSON saved to: {output_json_path}")


if __name__ == "__main__":
    main()