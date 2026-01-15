# Space Carving Implementation Specification

## Overview

Visual hull carving algorithm in Go that reconstructs a 3D voxel model from 37 sprite silhouettes using orthographic projection.

## Input

- `ship_sprites_centered.json` - Camera metadata with `camera_up`, `camera_right` vectors for 37 views
- `centered_images/` - 37 PNG images (128x128, RGBA)

## Output

- PLY point cloud file with occupied voxel centers

---

## Package Structure

```
voxelcarve/
├── main.go              # CLI entry point, orchestration
├── math.go              # Vec3, Mat4, linear algebra
├── camera.go            # Camera, view matrix, projection
├── sprite.go            # JSON sprite metadata loading
├── image.go             # PNG loading, silhouette extraction
├── voxel.go             # 3D voxel grid
├── carving.go           # Visual hull algorithm
└── export.go            # PLY export
```

---

## Module Specifications

### 1. math.go - Vector/Matrix Math

Provides basic 3D math primitives.

```go
type Vec3 struct { X, Y, Z float64 }
type Mat4 [16]float64

func (v Vec3) Add(w Vec3) Vec3
func (v Vec3) Sub(w Vec3) Vec3
func (v Vec3) Scale(s float64) Vec3
func (v Vec3) Dot(w Vec3) float64
func (v Vec3) Cross(w Vec3) Vec3
func (v Vec3) Normalize() Vec3
func (v Vec3) Length() float64
func (m Mat4) MulVec3(v Vec3) Vec3  // Transform point (assumes w=1)
```

### 2. camera.go - Camera & Projection

Handles camera setup and orthographic projection.

```go
type Camera struct {
    ViewMat    Mat4
    Width      int
    Height     int
    Fx, Fy     float64  // Orthographic focal lengths
    Cx, Cy     float64  // Principal point (image center)
    Position   Vec3     // Camera position (for mirroring)
    Up         Vec3     // Camera up vector (for mirroring)
    Right      Vec3     // Camera right vector (for mirroring)
}

func NewCamera(yaw, pitch float64, up, right Vec3,
               width, height int, orthoScale, distance float64) *Camera
func (c *Camera) Project(point Vec3) (x, y float64)
func (c *Camera) Mirror() *Camera  // For symmetry
```

**Internal functions:**
```go
func computePosition(yaw, pitch, distance float64) Vec3
func buildViewMatrix(position, up, right Vec3) Mat4
```

### 3. sprite.go - JSON Metadata Loading

Parses the sprite JSON file.

```go
type Sprite struct {
    Block       int        `json:"block"`
    Yaw         float64    `json:"yaw"`
    Pitch       float64    `json:"pitch"`
    Width       int        `json:"width"`
    Height      int        `json:"height"`
    Filename    string     `json:"filename"`
    CameraUp    [3]float64 `json:"camera_up"`
    CameraRight [3]float64 `json:"camera_right"`
}

type SpriteFile struct {
    Sprites []Sprite `json:"sprites"`
}

func LoadSprites(jsonPath string) ([]Sprite, error)
```

### 4. image.go - Silhouette Loading

Loads PNG images and extracts binary silhouette masks.

```go
type Silhouette struct {
    Width, Height int
    Mask          []bool  // row-major: Mask[y*Width + x]
}

func LoadSilhouette(path string, alphaThreshold float64) (*Silhouette, error)
func (s *Silhouette) Contains(x, y int) bool
func (s *Silhouette) InBounds(x, y float64) bool
func (s *Silhouette) MirrorHorizontal() *Silhouette  // For symmetry
```

### 5. voxel.go - Voxel Grid

3D binary occupancy grid.

```go
type VoxelGrid struct {
    Resolution int
    Extent     float64
    Occupied   []bool  // flattened [Resolution^3]
}

func NewVoxelGrid(resolution int, extent float64) *VoxelGrid
func (g *VoxelGrid) Index(ix, iy, iz int) int
func (g *VoxelGrid) Position(ix, iy, iz int) Vec3
func (g *VoxelGrid) Get(ix, iy, iz int) bool
func (g *VoxelGrid) Clear(ix, iy, iz int)
func (g *VoxelGrid) OccupiedPositions() []Vec3
func (g *VoxelGrid) OccupiedCount() int
```

### 6. carving.go - Visual Hull Algorithm

Core carving logic.

```go
func CarveVisualHull(grid *VoxelGrid, cameras []*Camera, silhouettes []*Silhouette, symmetry bool)
```

**Algorithm:**
```
for each view (camera, silhouette):
    for each voxel (ix, iy, iz):
        if not occupied: continue
        pos = grid.Position(ix, iy, iz)
        projX, projY = camera.Project(pos)
        if out of bounds OR not in silhouette:
            grid.Clear(ix, iy, iz)
```

### 7. export.go - PLY Output

Exports voxel centers as point cloud.

```go
func ExportPLY(points []Vec3, path string) error
```

**PLY Format:**
```
ply
format ascii 1.0
element vertex N
property float x
property float y
property float z
end_header
x1 y1 z1
x2 y2 z2
...
```

### 8. main.go - CLI & Orchestration

Entry point with command-line interface.

**CLI Flags:**
| Flag | Default | Description |
|------|---------|-------------|
| `-json` | `ship_sprites_centered.json` | JSON file path |
| `-images` | `centered_images` | Images directory |
| `-output` | `model.ply` | Output PLY path |
| `-resolution` | `128` | Voxel grid size |
| `-extent` | `1.5` | Grid extent (±value) |
| `-ortho` | `2.0` | Orthographic scale |
| `-distance` | `5.0` | Camera distance |
| `-alpha` | `0.5` | Alpha threshold |
| `-symmetry` | `false` | Enable Y-axis mirror symmetry |

**Workflow:**
1. Parse CLI flags
2. `LoadSprites()` from JSON
3. For each sprite: `LoadSilhouette()` + `NewCamera()`
4. `NewVoxelGrid()` + `CarveVisualHull()`
5. `ExportPLY()`

---

## Mathematical Details

### Camera Position from Angles

```go
camX = -distance * cos(yaw) * cos(pitch)
camY =  distance * sin(yaw) * cos(pitch)
camZ =  distance * sin(pitch)
```

Where:
- `yaw` is in radians (0° = rear, 180° = front)
- `pitch` is in radians (90° = below, -90° = above)

### View Matrix Construction

The view matrix transforms world coordinates to camera coordinates.

```go
forward = normalize(-position)  // Camera points at origin

// View matrix rows are camera basis vectors
viewMat[0:3]   = right      // Row 0: X axis
viewMat[4:7]   = up         // Row 1: Y axis
viewMat[8:11]  = forward    // Row 2: Z axis

// Translation component
viewMat[3]  = -dot(right, position)
viewMat[7]  = -dot(up, position)
viewMat[11] = -dot(forward, position)
```

### Orthographic Projection

```go
fx = width / (2 * orthoScale)
fy = height / (2 * orthoScale)
cx = width / 2.0
cy = height / 2.0

// Transform to camera space
camCoords = viewMat.MulVec3(worldPoint)

// Project to image plane
projX = fx * camCoords.X + cx
projY = fy * camCoords.Y + cy
```

---

## Reference Implementation

Based on `tools/sprite_to_3dgs.py`:
- Lines 78-98: `build_view_matrix()`
- Lines 101-116: `compute_camera_position()`
- Lines 119-130: `build_orthographic_K()`
- Lines 156-174: `project_points_orthographic()`
- Lines 177-215: `carve_visual_hull()`

---

## Symmetry Option

The sprites only cover yaw 0°-180° (right half of the viewing sphere). The ship has **Y-axis mirror symmetry** (left-right symmetry, since +Y is the right wing direction).

When `-symmetry` is enabled:
1. For each of the 37 views, a mirrored view is also created (74 total views)
2. Camera position/vectors are mirrored by negating Y components
3. Silhouettes are horizontally flipped
4. This enforces symmetric carving and improves reconstruction quality

**Mirror Transform:**
```go
mirroredPosition = Vec3{position.X, -position.Y, position.Z}
mirroredUp = Vec3{up.X, -up.Y, up.Z}
mirroredRight = Vec3{right.X, -right.Y, right.Z}
mirroredSilhouette = silhouette.MirrorHorizontal()
```

---

## Coordinate System

From `SHIP_ANGLES.md`:
- Ship nose points along **+X** axis
- Ship right wing points along **+Y** axis
- Ship top points along **+Z** axis
- YAW: 0° = rear (camera at -X), 180° = front (camera at +X)
- PITCH: 90° = below (camera at -Z), -90° = above (camera at +Z)

---

## Validation Criteria

1. Loads all 37 images successfully
2. Reports reasonable voxel count (~5-15% of total occupied)
3. Output PLY viewable in MeshLab/Blender showing ship shape
