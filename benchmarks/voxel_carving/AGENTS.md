# Wing Commander 1 Reverse Engineering

This project reverse engineers Wing Commander 1 ship sprites to reconstruct 3D models from the 2D sprite sheets. The original game used pre-rendered sprites from 37 different viewing angles to simulate 3D ships. By analyzing these angles and their camera vectors, we can use voxel carving and other techniques to recreate the original 3D geometry.

# Project Structure

## Specification

- `SHIP_ANGLES.md` - Documents the sprite angle system, coordinate conventions, and camera setup

## Data

- `ship_sprites.json` - Sprite metadata including dimensions, x/y rotation offsets, and camera vectors
- `images/` - Original ship sprite PNG files

## Tools

### center_sprites.py

Convert sprites to 128x128 images with the center of rotation at the image center. Also generates `ship_sprites_centered.json` with updated metadata.

```bash
python tools/center_sprites.py                      # transparent background
python tools/center_sprites.py --black-bg           # black background
python tools/center_sprites.py --size 256           # custom size (default: 128)
python tools/center_sprites.py --output-dir OUTPUT  # custom output directory
```

Output:
- `centered_images/` - Centered sprite images
- `ship_sprites_centered.json` - Updated metadata for centered sprites

### add_vectors_to_json.py

Calculate and add camera up/right vectors to `ship_sprites.json` based on yaw/pitch angles.

```bash
python tools/add_vectors_to_json.py
```

### ship_3d.py

Render a 3D ship model from all 37 sprite viewing angles using matplotlib.

```bash
python tools/ship_3d.py
```

Output:
- `ship_rendered_views.png` - 9 representative views
- `ship_all_angles.png` - All 37 sprite angles in a grid

## Environment

- `venv/` - Python virtual environment with dependencies (Pillow, matplotlib)