# Wing Commander Ship Sprite Angles

Ship sprites are pre-rendered from multiple viewing angles to create the illusion of 3D rotation.

## Angle System

- **YAW (horizontal):** 7 angles covering 180° (0° to 180°)
- **PITCH (vertical):** 5 rows from bottom to top, plus 2 extreme views
- **Special views:** Pure bottom (block 0) and pure top (block 36)

### Mirror Symmetry

The sprites only cover the right half of the viewing sphere (yaw 0° to 180°). Views from the left side (yaw 180° to 360°) are generated at runtime by horizontally mirroring the corresponding right-side sprite. For example:
- Yaw 210° uses the yaw 150° sprite, mirrored
- Yaw 270° uses the yaw 90° sprite, mirrored
- Yaw 330° uses the yaw 30° sprite, mirrored

This reduces storage requirements by nearly half while maintaining full 360° rotation capability.

### YAW Angles (columns)

| Position | Angle | View Description        |
|----------|-------|-------------------------|
| 0        | 180°  | Front (cockpit visible) |
| 1        | 150°  | Front-right             |
| 2        | 120°  | Right-front             |
| 3        | 90°   | Right side (profile)    |
| 4        | 60°   | Right-rear              |
| 5        | 30°   | Rear-right              |
| 6        | 0°    | Rear (engines visible)  |

### PITCH Angles (rows)

| Row | Pitch | View Description |
|-----|-------|------------------|
| -   | 90°   | Pure bottom      |
| 0   | 60°   | Below level      |
| 1   | 30°   | Slightly below   |
| 2   | 0°    | Level view       |
| 3   | -30°  | Slightly above   |
| 4   | -60°  | Above level      |
| -   | -90°  | Pure top         |

---

## SHIP.V06 Sprite Table

### Special View: Pure Bottom (90° pitch)

| Type        | Block | Width | Height | X   | Y   | Filename                                    |
|-------------|-------|-------|--------|-----|-----|---------------------------------------------|
| Pure Bottom | 00    | 116   | 72     | -56 | -34 | `SHIP_block00_sub00_w116_h72_x-56_y-34.png` |

### Row 0: Below Level (60° pitch)

| Yaw                | Block | Width | Height | X   | Y   | Filename                                    |
|--------------------|-------|-------|--------|-----|-----|---------------------------------------------|
| 180° (Front)       | 01    | 84    | 90     | -41 | -51 | `SHIP_block01_sub00_w84_h90_x-41_y-51.png`  |
| 150° (Front-right) | 02    | 83    | 88     | -37 | -49 | `SHIP_block02_sub00_w83_h88_x-37_y-49.png`  |
| 120° (Right-front) | 03    | 101   | 72     | -50 | -33 | `SHIP_block03_sub00_w101_h72_x-50_y-33.png` |
| 90° (Right side)   | 04    | 118   | 64     | -57 | -27 | `SHIP_block04_sub00_w118_h64_x-57_y-27.png` |
| 60° (Right-rear)   | 05    | 110   | 67     | -50 | -33 | `SHIP_block05_sub00_w110_h67_x-50_y-33.png` |
| 30° (Rear-right)   | 06    | 86    | 84     | -37 | -49 | `SHIP_block06_sub00_w86_h84_x-37_y-49.png`  |
| 0° (Rear)          | 07    | 86    | 91     | -42 | -53 | `SHIP_block07_sub00_w86_h91_x-42_y-53.png`  |

### Row 1: Slightly Below Level (30° pitch) — Reversed yaw order

| Yaw                | Block | Width | Height | X   | Y   | Filename                                    |
|--------------------|-------|-------|--------|-----|-----|---------------------------------------------|
| 0° (Rear)          | 08    | 87    | 76     | -42 | -44 | `SHIP_block08_sub00_w87_h76_x-42_y-44.png`  |
| 30° (Rear-right)   | 09    | 86    | 73     | -38 | -42 | `SHIP_block09_sub00_w86_h73_x-38_y-42.png`  |
| 60° (Right-rear)   | 10    | 111   | 58     | -49 | -31 | `SHIP_block10_sub00_w111_h58_x-49_y-31.png` |
| 90° (Right side)   | 11    | 121   | 50     | -59 | -22 | `SHIP_block11_sub00_w121_h50_x-59_y-22.png` |
| 120° (Right-front) | 12    | 104   | 57     | -54 | -27 | `SHIP_block12_sub00_w104_h57_x-54_y-27.png` |
| 150° (Front-right) | 13    | 82    | 65     | -36 | -38 | `SHIP_block13_sub00_w82_h65_x-36_y-38.png`  |
| 180° (Front)       | 14    | 83    | 64     | -40 | -40 | `SHIP_block14_sub00_w83_h64_x-40_y-40.png`  |

### Row 2: Level View (0° pitch)

| Yaw                | Block | Width | Height | X   | Y   | Filename                                    |
|--------------------|-------|-------|--------|-----|-----|---------------------------------------------|
| 180° (Front)       | 15    | 80    | 46     | -39 | -21 | `SHIP_block15_sub00_w80_h46_x-39_y-21.png`  |
| 150° (Front-right) | 16    | 80    | 46     | -35 | -21 | `SHIP_block16_sub00_w80_h46_x-35_y-21.png`  |
| 120° (Right-front) | 17    | 105   | 44     | -56 | -20 | `SHIP_block17_sub00_w105_h44_x-56_y-20.png` |
| 90° (Right side)   | 18    | 123   | 41     | -60 | -19 | `SHIP_block18_sub00_w123_h41_x-60_y-19.png` |
| 60° (Right-rear)   | 19    | 113   | 40     | -49 | -19 | `SHIP_block19_sub00_w113_h40_x-49_y-19.png` |
| 30° (Rear-right)   | 20    | 87    | 41     | -37 | -20 | `SHIP_block20_sub00_w87_h41_x-37_y-20.png`  |
| 0° (Rear)          | 21    | 86    | 40     | -42 | -20 | `SHIP_block21_sub00_w86_h40_x-42_y-20.png`  |

### Row 3: Slightly Above Level (-30° pitch) — Reversed yaw order

| Yaw                | Block | Width | Height | X   | Y   | Filename                                    |
|--------------------|-------|-------|--------|-----|-----|---------------------------------------------|
| 0° (Rear)          | 22    | 84    | 58     | -41 | -27 | `SHIP_block22_sub00_w84_h58_x-41_y-27.png`  |
| 30° (Rear-right)   | 23    | 86    | 61     | -36 | -27 | `SHIP_block23_sub00_w86_h61_x-36_y-27.png`  |
| 60° (Right-rear)   | 24    | 117   | 60     | -51 | -24 | `SHIP_block24_sub00_w117_h60_x-51_y-24.png` |
| 90° (Right side)   | 25    | 125   | 54     | -61 | -21 | `SHIP_block25_sub00_w125_h54_x-61_y-21.png` |
| 120° (Right-front) | 26    | 107   | 59     | -56 | -28 | `SHIP_block26_sub00_w107_h59_x-56_y-28.png` |
| 150° (Front-right) | 27    | 79    | 66     | -35 | -30 | `SHIP_block27_sub00_w79_h66_x-35_y-30.png`  |
| 180° (Front)       | 28    | 79    | 67     | -38 | -30 | `SHIP_block28_sub00_w79_h67_x-38_y-30.png`  |

### Row 4: Above Level (-60° pitch)

| Yaw                | Block | Width | Height | X   | Y   | Filename                                    |
|--------------------|-------|-------|--------|-----|-----|---------------------------------------------|
| 180° (Front)       | 29    | 77    | 96     | -37 | -46 | `SHIP_block29_sub00_w77_h96_x-37_y-46.png`  |
| 150° (Front-right) | 30    | 78    | 93     | -35 | -46 | `SHIP_block30_sub00_w78_h93_x-35_y-46.png`  |
| 120° (Right-front) | 31    | 109   | 71     | -54 | -37 | `SHIP_block31_sub00_w109_h71_x-54_y-37.png` |
| 90° (Right side)   | 32    | 127   | 61     | -61 | -23 | `SHIP_block32_sub00_w127_h61_x-61_y-23.png` |
| 60° (Right-rear)   | 33    | 118   | 70     | -53 | -28 | `SHIP_block33_sub00_w118_h70_x-53_y-28.png` |
| 30° (Rear-right)   | 34    | 84    | 85     | -36 | -38 | `SHIP_block34_sub00_w84_h85_x-36_y-38.png`  |
| 0° (Rear)          | 35    | 79    | 95     | -38 | -44 | `SHIP_block35_sub00_w79_h95_x-38_y-44.png`  |

### Special View: Pure Top (-90° pitch)

| Type     | Block | Width | Height | X   | Y   | Filename                                    |
|----------|-------|-------|--------|-----|-----|---------------------------------------------|
| Pure Top | 36    | 127   | 66     | -61 | -31 | `SHIP_block36_sub00_w127_h66_x-61_y-31.png` |

---

## Sprite Origin (Center of Rotation)

The `x` and `y` values in `ship_sprites.json` specify the center of rotation for each sprite. These are offsets from the sprite's top-left corner to the ship's center point. For example, a sprite with `x: -56, y: -34` means the ship's center is located 56 pixels to the right and 34 pixels down from the top-left corner of the sprite image.

When rendering, position the sprite so that this offset point aligns with the ship's screen position. This ensures the ship rotates around its center rather than a corner.

---

## Block Index Formula

The sprites use a **zigzag (boustrophedon) pattern** where odd rows have reversed yaw order:

```
block = 1 + (row * 7) + position_in_row

// Yaw angle depends on row parity:
if row is even (0, 2, 4):
    yaw = 180 - (position_in_row * 30)  // 180° → 0°
else (rows 1, 3):
    yaw = position_in_row * 30          // 0° → 180°
```

Where:
- `row` = 0-4 (pitch level)
- `position_in_row` = 0-6 (position within the row)

**Row yaw ordering:**
- Rows 0, 2, 4 (even): yaw goes 180° → 150° → 120° → 90° → 60° → 30° → 0°
- Rows 1, 3 (odd): yaw goes 0° → 30° → 60° → 90° → 120° → 150° → 180°

Special blocks:
- Block 0 = Pure bottom (90° pitch)
- Block 36 = Pure top (-90° pitch)

---

## Camera Setup Pseudocode

The camera is positioned on a sphere around the ship, always looking at the origin (ship center).

### Coordinate System

```
Ship orientation:
- Nose points along +X axis
- Right wing points along +Y axis
- Top of ship points along +Z axis

Angles:
- YAW: 0° = rear (camera at -X), 90° = right side (camera at +Y), 180° = front (camera at +X)
- PITCH: 90° = below (camera at -Z), 0° = level, -90° = above (camera at +Z)
```

### Camera Position Calculation

```python
def get_camera_vectors(yaw_deg, pitch_deg, distance):
    """
    Calculate camera position and orientation vectors.

    Returns: (camera_position, look_at, up_vector, right_vector)
    """
    yaw = radians(yaw_deg)
    pitch = radians(pitch_deg)

    # Camera position on sphere around origin
    # At yaw=0 (rear view), camera is behind ship at -X
    # At yaw=180 (front view), camera is in front at +X
    cam_x = -distance * cos(yaw) * cos(pitch)
    cam_y =  distance * sin(yaw) * cos(pitch)
    cam_z =  distance * sin(pitch)

    camera_position = (cam_x, cam_y, cam_z)
    look_at = (0, 0, 0)  # Always looking at ship center

    # Forward vector (from camera toward ship)
    forward = normalize(look_at - camera_position)

    # === UP AND RIGHT VECTOR CALCULATION ===

    if pitch == 90:  # SPECIAL CASE: Pure bottom view (Block 0)
        # Looking straight up at belly
        # Ship's nose (+X) should point RIGHT on screen
        up = (0, -1, 0)      # Camera's up points toward -Y (ship's left)
        right = (1, 0, 0)    # Camera's right points toward +X (ship's nose)

    elif pitch == -90:  # SPECIAL CASE: Pure top view (Block 36)
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

    return camera_position, look_at, up, right
```

### Special Cases Explained

**Block 0 (Pure Bottom, pitch = 90°):**
- Camera is directly below the ship, looking up
- At this angle, yaw is meaningless (gimbal lock)
- We define: ship's nose points RIGHT, ship's right wing points DOWN
- This requires a 90° counter-clockwise roll from the default orientation

**Block 36 (Pure Top, pitch = -90°):**
- Camera is directly above the ship, looking down
- At this angle, yaw is meaningless (gimbal lock)
- We define: ship's nose points LEFT, ship's right wing points DOWN
- This requires a 90° clockwise roll from the default orientation

### View Matrix Construction

```python
def build_view_matrix(camera_pos, look_at, up):
    """
    Build a 4x4 view matrix for rendering.
    """
    forward = normalize(look_at - camera_pos)
    right = normalize(cross(forward, up))
    up = cross(right, forward)

    # View matrix (camera transform inverse)
    return Matrix4x4(
        right.x,    right.y,    right.z,    -dot(right, camera_pos),
        up.x,       up.y,       up.z,       -dot(up, camera_pos),
        -forward.x, -forward.y, -forward.z,  dot(forward, camera_pos),
        0,          0,          0,           1
    )
```

### Rotation Angles for matplotlib/OpenGL

For rendering libraries that use elevation/azimuth/roll:

```python
def get_euler_angles(yaw_deg, pitch_deg):
    """
    Convert Wing Commander angles to rendering library angles.
    """
    # Elevation (vertical angle from horizon)
    elevation = -pitch_deg  # Invert: WC pitch 90° (below) = elevation -90°

    # Azimuth (horizontal rotation)
    azimuth = 180 - yaw_deg  # WC yaw 180° (front) = azimuth 0°

    # Roll (rotation around view axis)
    if pitch_deg == 90:      # Pure bottom
        roll = -90           # 90° counter-clockwise
    elif pitch_deg == -90:   # Pure top
        roll = 90            # 90° clockwise
    else:
        roll = 0

    return elevation, azimuth, roll
```

---
