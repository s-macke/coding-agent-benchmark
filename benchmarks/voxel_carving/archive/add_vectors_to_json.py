#!/usr/bin/env python3
"""
Add camera up and right vectors to ship_sprites.json.
"""

import json
import math


def normalize(v):
    """Normalize a 3D vector."""
    length = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if length == 0:
        return (0, 0, 0)
    return (v[0]/length, v[1]/length, v[2]/length)


def cross(a, b):
    """Cross product of two 3D vectors."""
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0]
    )


def sub(a, b):
    """Subtract two 3D vectors."""
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def get_camera_vectors(yaw_deg, pitch_deg, distance=5.0):
    """
    Calculate camera position and orientation vectors.

    Coordinate system:
    - Ship nose points along +X
    - Ship right wing points along +Y
    - Ship top points along +Z

    Angles:
    - YAW: 0° = rear (camera at -X), 90° = right side (camera at +Y), 180° = front (camera at +X)
    - PITCH: 90° = below (camera at -Z), 0° = level, -90° = above (camera at +Z)
    """
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    # Camera position on sphere around origin
    cam_x = -distance * math.cos(yaw) * math.cos(pitch)
    cam_y = distance * math.sin(yaw) * math.cos(pitch)
    cam_z = distance * math.sin(pitch)

    camera_pos = (cam_x, cam_y, cam_z)
    look_at = (0, 0, 0)

    # Forward vector (from camera toward ship)
    forward = normalize(sub(look_at, camera_pos))

    # === UP AND RIGHT VECTOR CALCULATION ===

    if pitch_deg == 90:  # SPECIAL CASE: Pure bottom view (Block 0)
        # Looking straight up at belly
        # Ship's nose (+X) should point RIGHT on screen
        up = (0, -1, 0)      # Camera's up points toward -Y (ship's left)
        right = (1, 0, 0)    # Camera's right points toward +X (ship's nose)

    elif pitch_deg == -90:  # SPECIAL CASE: Pure top view (Block 36)
        # Looking straight down at top
        # Ship's nose (+X) should point LEFT on screen
        up = (0, 1, 0)       # Camera's up points toward +Y (ship's right)
        right = (-1, 0, 0)   # Camera's right points toward -X (ship's tail)

    else:  # NORMAL CASE: All other views
        # World up is +Z
        world_up = (0, 0, 1)

        # Right vector = forward × world_up (cross product)
        right = normalize(cross(forward, world_up))

        # Up vector = right × forward
        up = normalize(cross(right, forward))

    return camera_pos, up, right


def round_vector(v, decimals=6):
    """Round vector components to avoid floating point noise."""
    return [round(x, decimals) for x in v]


def main():
    # Read existing JSON
    with open('ship_sprites.json', 'r') as f:
        data = json.load(f)

    # Add vectors to each sprite
    for sprite in data['sprites']:
        yaw = sprite['yaw']
        pitch = sprite['pitch']

        camera_pos, up, right = get_camera_vectors(yaw, pitch)

        # Add vectors to sprite data
        sprite['camera_up'] = round_vector(up)
        sprite['camera_right'] = round_vector(right)

    # Write updated JSON
    with open('ship_sprites.json', 'w') as f:
        json.dump(data, f, indent=2)

    print("Updated ship_sprites.json with camera vectors.")

    # Print a few examples
    print("\nExamples:")
    for block in [0, 15, 18, 21, 36]:
        sprite = data['sprites'][block]
        print(f"  Block {block} (yaw={sprite['yaw']}°, pitch={sprite['pitch']}°):")
        print(f"    up    = {sprite['camera_up']}")
        print(f"    right = {sprite['camera_right']}")


if __name__ == "__main__":
    main()