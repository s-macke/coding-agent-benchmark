#!/usr/bin/env python3
"""
Convert ship sprites to 128x128 images with the center of rotation at the image center.

The x and y values in ship_sprites.json specify the offset from the sprite's top-left
corner to the ship's center of rotation. This tool creates new images where that
center point is placed at the center of a 128x128 canvas.

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
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


def center_sprite(sprite_path, x_offset, y_offset, output_size=128, black_bg=False, scale4x=False, crosshair=False):
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
        description='Center ship sprites by their rotation point in 128x128 images.'
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
        '--size',
        type=int,
        default=128,
        help='Output image size (default: 128)'
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

    with open(json_path, 'r') as f:
        data = json.load(f)

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    print(f"Processing {len(data['sprites'])} sprites...")
    print(f"Output size: {args.size}x{args.size}" + (f" (scaled to {args.size*4}x{args.size*4})" if args.scale4x else ""))
    print(f"Output directory: {output_dir}")
    print(f"Black background: {args.black_bg}")
    print(f"Scale 4x: {args.scale4x}")
    print(f"Crosshair: {args.crosshair}")
    print()

    processed = 0
    errors = 0
    centered_sprites = []
    center = args.size // 2

    sprites_to_process = data['sprites']

    if args.orthogonal_only:
        orthogonal_pitches = {-90, 0, 90}
        orthogonal_yaws = {0, 90, 180}
        sprites_to_process = [
            s for s in sprites_to_process
            #if s['pitch'] in orthogonal_pitches and s['yaw'] in orthogonal_yaws
            #if s['pitch'] in orthogonal_pitches or s['yaw'] == 0
            if s['pitch'] in orthogonal_pitches
            #if s['yaw'] == 0
        ]
        print(f"Filtered to {len(sprites_to_process)} orthogonal views")

    if args.any_cardinal:
        cardinal_angles = {-90, 0, 90, 180, 270}
        sprites_to_process = [
            s for s in sprites_to_process
            if s['pitch'] in cardinal_angles or s['yaw'] in cardinal_angles
        ]
        print(f"Filtered to {len(sprites_to_process)} views with at least one cardinal angle")

    for sprite in sprites_to_process:
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
                black_bg=args.black_bg,
                scale4x=args.scale4x,
                crosshair=args.crosshair
            )
            centered.save(output_path)
            processed += 1
            print(f"  Block {block:02d}: {filename} -> {output_filename}")

            # Build centered sprite metadata
            actual_size = args.size * 4 if args.scale4x else args.size
            actual_center = actual_size // 2
            centered_sprite = {
                'block': sprite['block'],
                'row': sprite['row'],
                'yaw': sprite['yaw'],
                'pitch': sprite['pitch'],
                'width': actual_size,
                'height': actual_size,
                'x': -actual_center,
                'y': -actual_center,
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