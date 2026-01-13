# Wing Commander Ship Sprite Angles

Ship sprites are pre-rendered from multiple viewing angles to create the illusion of 3D rotation.

## Angle System

- **YAW (horizontal):** 7 angles covering 180° (mirrored for the other half)
- **PITCH (vertical):** 5 rows from below to above
- **Special views:** Pure top, pure bottom, and radar icon

### YAW Angles (columns)

| Position | Angle | View Description |
|----------|-------|------------------|
| 0 | 0° | Rear (engines visible) |
| 1 | ~30° | Rear-right |
| 2 | ~60° | Right-rear |
| 3 | ~90° | Right side (profile) |
| 4 | ~120° | Right-front |
| 5 | ~150° | Front-right |
| 6 | ~180° | Front (cockpit visible) |

### PITCH Angles (rows)

| Row | Pitch | View Description |
|-----|-------|------------------|
| 0 | ~-30° | Camera below, looking up |
| 1 | ~-15° | Slightly below level |
| 2 | 0° | Level view |
| 3 | ~+15° | Slightly above level |
| 4 | ~+30° | Camera above, looking down |

---

## SHIP.V06 Sprite Table

### Row 0: Camera Below (~-30° pitch)

| Yaw | Block | Filename |
|-----|-------|----------|
| 0° (Rear) | 00 | `SHIP_block00_sub00_w116_h72_x-56_y-34.png` |
| ~30° (Rear-right) | 01 | `SHIP_block01_sub00_w84_h90_x-41_y-51.png` |
| ~60° (Right-rear) | 02 | `SHIP_block02_sub00_w83_h88_x-37_y-49.png` |
| ~90° (Right side) | 03 | `SHIP_block03_sub00_w101_h72_x-50_y-33.png` |
| ~120° (Right-front) | 04 | `SHIP_block04_sub00_w118_h64_x-57_y-27.png` |
| ~150° (Front-right) | 05 | `SHIP_block05_sub00_w110_h67_x-50_y-33.png` |
| ~180° (Front) | 06 | `SHIP_block06_sub00_w86_h84_x-37_y-49.png` |

### Row 1: Slightly Below Level (~-15° pitch)

| Yaw | Block | Filename |
|-----|-------|----------|
| 0° (Rear) | 07 | `SHIP_block07_sub00_w86_h91_x-42_y-53.png` |
| ~30° (Rear-right) | 08 | `SHIP_block08_sub00_w87_h76_x-42_y-44.png` |
| ~60° (Right-rear) | 09 | `SHIP_block09_sub00_w86_h73_x-38_y-42.png` |
| ~90° (Right side) | 10 | `SHIP_block10_sub00_w111_h58_x-49_y-31.png` |
| ~120° (Right-front) | 11 | `SHIP_block11_sub00_w121_h50_x-59_y-22.png` |
| ~150° (Front-right) | 12 | `SHIP_block12_sub00_w104_h57_x-54_y-27.png` |
| ~180° (Front) | 13 | `SHIP_block13_sub00_w82_h65_x-36_y-38.png` |

### Row 2: Level View (0° pitch)

| Yaw | Block | Filename |
|-----|-------|----------|
| 0° (Rear) | 14 | `SHIP_block14_sub00_w83_h64_x-40_y-40.png` |
| ~30° (Rear-right) | 15 | `SHIP_block15_sub00_w80_h46_x-39_y-21.png` |
| ~60° (Right-rear) | 16 | `SHIP_block16_sub00_w80_h46_x-35_y-21.png` |
| ~90° (Right side) | 17 | `SHIP_block17_sub00_w105_h44_x-56_y-20.png` |
| ~120° (Right-front) | 18 | `SHIP_block18_sub00_w123_h41_x-60_y-19.png` |
| ~150° (Front-right) | 19 | `SHIP_block19_sub00_w113_h40_x-49_y-19.png` |
| ~180° (Front) | 20 | `SHIP_block20_sub00_w87_h41_x-37_y-20.png` |

### Row 3: Slightly Above Level (~+15° pitch)

| Yaw | Block | Filename |
|-----|-------|----------|
| 0° (Rear) | 21 | `SHIP_block21_sub00_w86_h40_x-42_y-20.png` |
| ~30° (Rear-right) | 22 | `SHIP_block22_sub00_w84_h58_x-41_y-27.png` |
| ~60° (Right-rear) | 23 | `SHIP_block23_sub00_w86_h61_x-36_y-27.png` |
| ~90° (Right side) | 24 | `SHIP_block24_sub00_w117_h60_x-51_y-24.png` |
| ~120° (Right-front) | 25 | `SHIP_block25_sub00_w125_h54_x-61_y-21.png` |
| ~150° (Front-right) | 26 | `SHIP_block26_sub00_w107_h59_x-56_y-28.png` |
| ~180° (Front) | 27 | `SHIP_block27_sub00_w79_h66_x-35_y-30.png` |

### Row 4: Camera Above (~+30° pitch)

| Yaw | Block | Filename |
|-----|-------|----------|
| 0° (Rear) | 28 | `SHIP_block28_sub00_w79_h67_x-38_y-30.png` |
| ~30° (Rear-right) | 29 | `SHIP_block29_sub00_w77_h96_x-37_y-46.png` |
| ~60° (Right-rear) | 30 | `SHIP_block30_sub00_w78_h93_x-35_y-46.png` |
| ~90° (Right side) | 31 | `SHIP_block31_sub00_w109_h71_x-54_y-37.png` |
| ~120° (Right-front) | 32 | `SHIP_block32_sub00_w127_h61_x-61_y-23.png` |
| ~150° (Front-right) | 33 | `SHIP_block33_sub00_w118_h70_x-53_y-28.png` |
| ~180° (Front) | 34 | `SHIP_block34_sub00_w84_h85_x-36_y-38.png` |

### Special Views

| Type | Block | Filename |
|------|-------|----------|
| Pure Bottom (-90°) | 35 | `SHIP_block35_sub00_w79_h95_x-38_y-44.png` |
| Pure Top (+90°) | 36 | `SHIP_block36_sub00_w127_h66_x-61_y-31.png` |
| Radar Icon (state 0) | 37 | `SHIP_block37_sub00_w54_h37_x-28_y-18.png` |
| Radar Icon (state 1) | 37 | `SHIP_block37_sub01_w54_h37_x-28_y-18.png` |
| Radar Icon (state 2) | 37 | `SHIP_block37_sub02_w56_h36_x-27_y-19.png` |

---

## Block Index Formula

To calculate the block index from pitch row and yaw position:

```
block = (row * 7) + yaw_position
```

Where:
- `row` = 0-4 (pitch level)
- `yaw_position` = 0-6 (horizontal angle)

Special blocks 35, 36, 37 are outside this grid.
