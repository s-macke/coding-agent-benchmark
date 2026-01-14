#!/usr/bin/env python3
"""
Simple 3D Ship renderer matching Wing Commander sprite camera angles.

Camera system:
- YAW: 0° = rear (engines), 90° = right side, 180° = front (cockpit)
- PITCH: 90° = from below, 0° = level, -90° = from above
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import json


def create_ship_geometry():
    """Create a detailed spaceship shape (Wing Commander style fighter)."""

    faces = []
    colors = []

    # Color palette
    hull_dark = '#404550'
    hull_mid = '#606570'
    hull_light = '#808590'
    accent = '#354050'
    cockpit_color = '#40a0c0'
    engine_glow = '#ff6600'
    engine_inner = '#ffaa00'

    # === FUSELAGE - tapered hexagonal cross-section ===

    # Front nose point
    nose_tip = [1.4, 0, 0]

    # Nose section (hexagonal)
    nose_ring = [
        [0.9, 0, 0.12],      # top
        [0.9, 0.10, 0.06],   # top-right
        [0.9, 0.10, -0.06],  # bottom-right
        [0.9, 0, -0.10],     # bottom
        [0.9, -0.10, -0.06], # bottom-left
        [0.9, -0.10, 0.06],  # top-left
    ]

    # Mid fuselage (wider)
    mid_ring = [
        [0.3, 0, 0.18],      # top
        [0.3, 0.16, 0.10],   # top-right
        [0.3, 0.16, -0.10],  # bottom-right
        [0.3, 0, -0.14],     # bottom
        [0.3, -0.16, -0.10], # bottom-left
        [0.3, -0.16, 0.10],  # top-left
    ]

    # Rear fuselage
    rear_ring = [
        [-0.6, 0, 0.16],     # top
        [-0.6, 0.14, 0.08],  # top-right
        [-0.6, 0.14, -0.10], # bottom-right
        [-0.6, 0, -0.14],    # bottom
        [-0.6, -0.14, -0.10],# bottom-left
        [-0.6, -0.14, 0.08], # top-left
    ]

    # Nose cone triangles
    for i in range(6):
        faces.append([nose_tip, nose_ring[i], nose_ring[(i+1) % 6]])
        colors.append(hull_light if i in [0, 5] else hull_mid)

    # Fuselage panels nose to mid
    for i in range(6):
        faces.append([nose_ring[i], nose_ring[(i+1) % 6], mid_ring[(i+1) % 6], mid_ring[i]])
        colors.append(hull_light if i == 0 else (hull_dark if i == 3 else hull_mid))

    # Fuselage panels mid to rear
    for i in range(6):
        faces.append([mid_ring[i], mid_ring[(i+1) % 6], rear_ring[(i+1) % 6], rear_ring[i]])
        colors.append(hull_light if i == 0 else (hull_dark if i == 3 else hull_mid))

    # Rear cap
    faces.append(rear_ring)
    colors.append(hull_dark)

    # === COCKPIT CANOPY ===

    cockpit_base = [
        [0.85, -0.08, 0.12],
        [0.85, 0.08, 0.12],
        [0.45, 0.12, 0.18],
        [0.45, -0.12, 0.18],
    ]
    cockpit_top = [
        [0.75, -0.06, 0.22],
        [0.75, 0.06, 0.22],
        [0.50, 0.08, 0.26],
        [0.50, -0.08, 0.26],
    ]

    # Cockpit sides
    faces.append([cockpit_base[0], cockpit_base[1], cockpit_top[1], cockpit_top[0]])  # front
    faces.append([cockpit_base[1], cockpit_base[2], cockpit_top[2], cockpit_top[1]])  # right
    faces.append([cockpit_base[2], cockpit_base[3], cockpit_top[3], cockpit_top[2]])  # back
    faces.append([cockpit_base[3], cockpit_base[0], cockpit_top[0], cockpit_top[3]])  # left
    faces.append([cockpit_top[0], cockpit_top[1], cockpit_top[2], cockpit_top[3]])    # top
    colors.extend([cockpit_color] * 5)

    # === MAIN WINGS ===

    def create_wing(side=1):
        """Create wing geometry. side=1 for right, side=-1 for left."""
        wing_faces = []
        wing_colors = []

        y = side
        # Wing profile points
        wing_root_top = [
            [0.2, y * 0.16, 0.02],
            [-0.3, y * 0.16, 0.02],
        ]
        wing_root_bot = [
            [0.2, y * 0.16, -0.04],
            [-0.3, y * 0.16, -0.04],
        ]
        wing_tip_top = [
            [-0.2, y * 1.1, 0.0],
            [-0.6, y * 1.1, 0.0],
        ]
        wing_tip_bot = [
            [-0.2, y * 1.1, -0.02],
            [-0.6, y * 1.1, -0.02],
        ]

        # Top surface
        wing_faces.append([wing_root_top[0], wing_tip_top[0], wing_tip_top[1], wing_root_top[1]])
        wing_colors.append(hull_mid)

        # Bottom surface
        wing_faces.append([wing_root_bot[0], wing_root_bot[1], wing_tip_bot[1], wing_tip_bot[0]])
        wing_colors.append(hull_dark)

        # Leading edge
        wing_faces.append([wing_root_top[0], wing_root_bot[0], wing_tip_bot[0], wing_tip_top[0]])
        wing_colors.append(hull_light)

        # Trailing edge
        wing_faces.append([wing_root_top[1], wing_tip_top[1], wing_tip_bot[1], wing_root_bot[1]])
        wing_colors.append(accent)

        # Wing tip
        wing_faces.append([wing_tip_top[0], wing_tip_top[1], wing_tip_bot[1], wing_tip_bot[0]])
        wing_colors.append(hull_mid)

        return wing_faces, wing_colors

    # Add both wings
    for side in [1, -1]:
        wf, wc = create_wing(side)
        faces.extend(wf)
        colors.extend(wc)

    # === VERTICAL STABILIZERS (tail fins) ===

    def create_tail_fin(side=1):
        fin_faces = []
        fin_colors = []

        y = side * 0.12
        fin_base = [
            [-0.3, y, 0.16],
            [-0.6, y, 0.14],
        ]
        fin_top = [
            [-0.4, y, 0.38],
            [-0.65, y, 0.30],
        ]

        # Outer surface
        fin_faces.append([fin_base[0], fin_base[1], fin_top[1], fin_top[0]])
        fin_colors.append(hull_mid)

        # Add thickness
        thickness = 0.02
        fin_base_inner = [[p[0], p[1] - side * thickness, p[2]] for p in fin_base]
        fin_top_inner = [[p[0], p[1] - side * thickness, p[2]] for p in fin_top]

        fin_faces.append([fin_base_inner[0], fin_top_inner[0], fin_top_inner[1], fin_base_inner[1]])
        fin_colors.append(hull_dark)

        # Top edge
        fin_faces.append([fin_top[0], fin_top[1], fin_top_inner[1], fin_top_inner[0]])
        fin_colors.append(accent)

        # Leading edge
        fin_faces.append([fin_base[0], fin_top[0], fin_top_inner[0], fin_base_inner[0]])
        fin_colors.append(hull_light)

        return fin_faces, fin_colors

    for side in [1, -1]:
        ff, fc = create_tail_fin(side)
        faces.extend(ff)
        colors.extend(fc)

    # === ENGINE NACELLES ===

    def create_engine(y_pos):
        eng_faces = []
        eng_colors = []

        # Engine housing
        eng_front = [
            [-0.1, y_pos - 0.06, -0.06],
            [-0.1, y_pos + 0.06, -0.06],
            [-0.1, y_pos + 0.06, 0.04],
            [-0.1, y_pos - 0.06, 0.04],
        ]
        eng_back = [
            [-0.7, y_pos - 0.08, -0.08],
            [-0.7, y_pos + 0.08, -0.08],
            [-0.7, y_pos + 0.08, 0.04],
            [-0.7, y_pos - 0.08, 0.04],
        ]

        # Engine housing sides
        for i in range(4):
            eng_faces.append([eng_front[i], eng_front[(i+1)%4], eng_back[(i+1)%4], eng_back[i]])
            eng_colors.append(hull_dark if i == 1 else accent)

        # Engine exhaust (glowing)
        eng_faces.append(eng_back)
        eng_colors.append(engine_glow)

        # Inner glow
        inner_back = [
            [-0.72, y_pos - 0.05, -0.05],
            [-0.72, y_pos + 0.05, -0.05],
            [-0.72, y_pos + 0.05, 0.02],
            [-0.72, y_pos - 0.05, 0.02],
        ]
        eng_faces.append(inner_back)
        eng_colors.append(engine_inner)

        return eng_faces, eng_colors

    # Twin engines
    for y_pos in [-0.28, 0.28]:
        ef, ec = create_engine(y_pos)
        faces.extend(ef)
        colors.extend(ec)

    # === WING-MOUNTED WEAPONS/PODS ===

    def create_weapon_pod(y_pos):
        pod_faces = []
        pod_colors = []

        # Small weapon pod under wing
        pod_front = [0.0, y_pos, -0.06]
        pod_back = [-0.25, y_pos, -0.06]
        pod_radius = 0.03

        # Simple rectangular pod
        pf = [
            [pod_front[0], pod_front[1] - pod_radius, pod_front[2] - pod_radius],
            [pod_front[0], pod_front[1] + pod_radius, pod_front[2] - pod_radius],
            [pod_front[0], pod_front[1] + pod_radius, pod_front[2] + pod_radius],
            [pod_front[0], pod_front[1] - pod_radius, pod_front[2] + pod_radius],
        ]
        pb = [
            [pod_back[0], pod_back[1] - pod_radius, pod_back[2] - pod_radius],
            [pod_back[0], pod_back[1] + pod_radius, pod_back[2] - pod_radius],
            [pod_back[0], pod_back[1] + pod_radius, pod_back[2] + pod_radius],
            [pod_back[0], pod_back[1] - pod_radius, pod_back[2] + pod_radius],
        ]

        for i in range(4):
            pod_faces.append([pf[i], pf[(i+1)%4], pb[(i+1)%4], pb[i]])
            pod_colors.append(accent)

        # Front cap
        pod_faces.append(pf)
        pod_colors.append(hull_light)

        return pod_faces, pod_colors

    for y_pos in [-0.5, 0.5]:
        pf, pc = create_weapon_pod(y_pos)
        faces.extend(pf)
        colors.extend(pc)

    return faces, colors


def yaw_pitch_to_camera_position(yaw_deg, pitch_deg, distance=5.0):
    """
    Convert Wing Commander yaw/pitch angles to camera position.

    Wing Commander convention:
    - YAW 0° = rear view (looking at engines from behind)
    - YAW 90° = right side view
    - YAW 180° = front view (looking at cockpit)
    - PITCH 90° = from below (looking up at belly)
    - PITCH 0° = level view
    - PITCH -90° = from above (looking down at top)

    Ship orientation: nose points along +X axis
    """
    yaw_rad = np.radians(yaw_deg)
    pitch_rad = np.radians(pitch_deg)

    # Camera position on sphere
    # At yaw=0 (rear), camera is at -X looking toward +X
    # At yaw=180 (front), camera is at +X looking toward -X
    # At yaw=90 (right side), camera is at +Y looking toward -Y

    # Pitch affects elevation: positive pitch = below, negative = above
    cos_pitch = np.cos(pitch_rad)
    sin_pitch = np.sin(pitch_rad)

    # Horizontal position based on yaw (yaw=0 is behind ship at -X)
    cam_x = -distance * np.cos(yaw_rad) * cos_pitch
    cam_y = distance * np.sin(yaw_rad) * cos_pitch
    cam_z = distance * sin_pitch  # Positive pitch = below = negative z in our setup

    return cam_x, cam_y, cam_z


def render_ship_view(ax, faces, colors, yaw, pitch, title=""):
    """Render the ship from a specific viewing angle."""
    ax.clear()

    # Create polygon collection
    poly = Poly3DCollection(faces, facecolors=colors, edgecolors='black', linewidths=0.5)
    ax.add_collection3d(poly)

    # Set viewing angle
    # matplotlib uses elevation (up/down) and azimuth (rotation around z)
    # We need to convert our yaw/pitch to these

    # For matplotlib:
    # elev = angle above/below the xy plane
    # azim = rotation around z axis

    # Our pitch: 90 = below, 0 = level, -90 = above
    # matplotlib elev: 90 = from above, 0 = level, -90 = from below
    elev = -pitch  # Invert because matplotlib's convention is opposite

    # Our yaw: 0 = rear (-X), 90 = right (+Y), 180 = front (+X)
    # matplotlib azim: rotation around z-axis
    # As yaw decreases 180→0, camera moves counterclockwise (front→right→rear)
    azim = 180 - yaw  # Correct rotation direction

    # Special handling for pure top/bottom views (pitch ±90°)
    # At these angles, yaw is meaningless and we need roll to orient correctly
    roll = 0
    if pitch == 90:  # Pure bottom view (block 0)
        roll = -90  # 90° counter-clockwise
    elif pitch == -90:  # Pure top view (block 36)
        roll = 90  # 90° clockwise

    ax.view_init(elev=elev, azim=azim, roll=roll)

    # Set axis limits
    limit = 1.5
    ax.set_xlim([-limit, limit])
    ax.set_ylim([-limit, limit])
    ax.set_zlim([-limit, limit])

    # Equal aspect ratio
    ax.set_box_aspect([1, 1, 1])

    # Labels
    ax.set_xlabel('X (nose →)')
    ax.set_ylabel('Y (right →)')
    ax.set_zlabel('Z (up →)')

    ax.set_title(f'{title}\nYaw: {yaw}°, Pitch: {pitch}°')

    # Hide grid for cleaner look
    ax.grid(False)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False


def main():
    """Render the ship from multiple angles matching the sprite system."""

    # Load sprite data
    with open('ship_sprites.json', 'r') as f:
        sprite_data = json.load(f)

    # Create ship geometry
    faces, colors = create_ship_geometry()

    # Select representative views to render
    views = [
        # Level views (row 2)
        {"yaw": 180, "pitch": 0, "desc": "Front (Row 2)"},
        {"yaw": 90, "pitch": 0, "desc": "Right Side (Row 2)"},
        {"yaw": 0, "pitch": 0, "desc": "Rear (Row 2)"},

        # From below (row 0)
        {"yaw": 180, "pitch": 60, "desc": "Front Below (Row 0)"},
        {"yaw": 90, "pitch": 60, "desc": "Right Below (Row 0)"},

        # From above (row 4)
        {"yaw": 180, "pitch": -60, "desc": "Front Above (Row 4)"},
        {"yaw": 90, "pitch": -60, "desc": "Right Above (Row 4)"},

        # Extreme views
        {"yaw": 0, "pitch": 90, "desc": "Pure Bottom"},
        {"yaw": 0, "pitch": -90, "desc": "Pure Top"},
    ]

    # Create figure with subplots
    fig = plt.figure(figsize=(15, 10))

    for i, view in enumerate(views):
        ax = fig.add_subplot(3, 3, i + 1, projection='3d')
        render_ship_view(ax, faces, colors, view["yaw"], view["pitch"], view["desc"])

    plt.tight_layout()
    plt.savefig('ship_rendered_views.png', dpi=150, bbox_inches='tight')
    plt.show()

    print("Saved: ship_rendered_views.png")

    # Also create a full grid of all 37 sprite angles
    print("\nRendering all 37 sprite angles...")

    fig2 = plt.figure(figsize=(20, 18))
    fig2.subplots_adjust(hspace=0.35)

    for sprite in sprite_data["sprites"]:
        block = sprite["block"]
        yaw = sprite["yaw"]
        pitch = sprite["pitch"]

        ax = fig2.add_subplot(6, 7, block + 1, projection='3d')
        render_ship_view(ax, faces, colors, yaw, pitch, f"Block {block}")
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.set_zlabel('')

    plt.tight_layout()
    plt.savefig('ship_all_angles.png', dpi=100, bbox_inches='tight')
    print("Saved: ship_all_angles.png")


if __name__ == "__main__":
    main()