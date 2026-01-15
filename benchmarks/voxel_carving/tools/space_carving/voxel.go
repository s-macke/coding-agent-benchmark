package main

// Voxel represents a single voxel with opacity and color.
type Voxel struct {
	Opacity float64
	R, G, B float64
}

// Color returns the voxel's color as a Color struct.
func (v *Voxel) Color() Color {
	return Color{R: v.R, G: v.G, B: v.B, A: 1.0}
}

// VoxelGrid represents a 3D grid of voxels.
type VoxelGrid struct {
	Resolution int
	Extent     float64
	Voxels     []Voxel // flattened [Resolution^3]
	voxelSize  float64 // size of each voxel
}

// NewVoxelGrid creates a new voxel grid with all voxels initially fully opaque.
func NewVoxelGrid(resolution int, extent float64) *VoxelGrid {
	n := resolution * resolution * resolution
	voxels := make([]Voxel, n)
	for i := range voxels {
		voxels[i].Opacity = 1.0
	}

	return &VoxelGrid{
		Resolution: resolution,
		Extent:     extent,
		Voxels:     voxels,
		voxelSize:  (2 * extent) / float64(resolution),
	}
}

// Index returns the flat index for 3D coordinates.
func (g *VoxelGrid) Index(ix, iy, iz int) int {
	return ix*g.Resolution*g.Resolution + iy*g.Resolution + iz
}

// Position returns the world position of a voxel center.
func (g *VoxelGrid) Position(ix, iy, iz int) Vec3 {
	// Map index to [-extent, extent]
	x := -g.Extent + (float64(ix)+0.5)*g.voxelSize
	y := -g.Extent + (float64(iy)+0.5)*g.voxelSize
	z := -g.Extent + (float64(iz)+0.5)*g.voxelSize
	return Vec3{x, y, z}
}

// Get returns the opacity of a voxel (0-1).
func (g *VoxelGrid) Get(ix, iy, iz int) float64 {
	return g.Voxels[g.Index(ix, iy, iz)].Opacity
}

// GetVoxel returns a pointer to the voxel at the given coordinates.
func (g *VoxelGrid) GetVoxel(ix, iy, iz int) *Voxel {
	return &g.Voxels[g.Index(ix, iy, iz)]
}

// Set sets the opacity of a voxel.
func (g *VoxelGrid) Set(ix, iy, iz int, opacity float64) {
	g.Voxels[g.Index(ix, iy, iz)].Opacity = opacity
}

// SetColor sets the color of a voxel.
func (g *VoxelGrid) SetColor(ix, iy, iz int, r, g_, b float64) {
	v := &g.Voxels[g.Index(ix, iy, iz)]
	v.R = r
	v.G = g_
	v.B = b
}

// MultiplyOpacity multiplies the voxel's opacity by a factor.
func (g *VoxelGrid) MultiplyOpacity(ix, iy, iz int, factor float64) {
	idx := g.Index(ix, iy, iz)
	g.Voxels[idx].Opacity *= factor
}

// VoxelSize returns the size of each voxel.
func (g *VoxelGrid) VoxelSize() float64 {
	return g.voxelSize
}

// OccupiedCount returns the number of voxels with opacity > 0.5.
func (g *VoxelGrid) OccupiedCount() int {
	count := 0
	for _, v := range g.Voxels {
		if v.Opacity > 0.5 {
			count++
		}
	}
	return count
}

// IsSurface returns true if the voxel has at least one empty neighbor.
// Edge voxels are always considered surface voxels.
func (g *VoxelGrid) IsSurface(ix, iy, iz int) bool {
	res := g.Resolution
	// Check 6 neighbors
	neighbors := [][3]int{
		{ix - 1, iy, iz}, {ix + 1, iy, iz},
		{ix, iy - 1, iz}, {ix, iy + 1, iz},
		{ix, iy, iz - 1}, {ix, iy, iz + 1},
	}
	for _, n := range neighbors {
		nx, ny, nz := n[0], n[1], n[2]
		// Out of bounds = empty (surface)
		if nx < 0 || nx >= res || ny < 0 || ny >= res || nz < 0 || nz >= res {
			return true
		}
		// Empty neighbor = surface
		if g.Get(nx, ny, nz) <= 0.5 {
			return true
		}
	}
	return false
}

// SurfaceCount returns the number of surface voxels.
func (g *VoxelGrid) SurfaceCount() int {
	count := 0
	for ix := 0; ix < g.Resolution; ix++ {
		for iy := 0; iy < g.Resolution; iy++ {
			for iz := 0; iz < g.Resolution; iz++ {
				if g.Get(ix, iy, iz) > 0.5 && g.IsSurface(ix, iy, iz) {
					count++
				}
			}
		}
	}
	return count
}

// WorldToGrid converts world coordinates to grid indices (not clamped).
func (g *VoxelGrid) WorldToGrid(pos Vec3) (float64, float64, float64) {
	fx := (pos.X + g.Extent) / g.voxelSize
	fy := (pos.Y + g.Extent) / g.voxelSize
	fz := (pos.Z + g.Extent) / g.voxelSize
	return fx, fy, fz
}

// RayBoxIntersect returns t values where ray enters/exits the grid bounds.
// Uses slab method for AABB intersection.
func (g *VoxelGrid) RayBoxIntersect(origin, dir Vec3) (tMin, tMax float64) {
	invDir := Vec3{1.0 / dir.X, 1.0 / dir.Y, 1.0 / dir.Z}

	t1 := (-g.Extent - origin.X) * invDir.X
	t2 := (g.Extent - origin.X) * invDir.X
	t3 := (-g.Extent - origin.Y) * invDir.Y
	t4 := (g.Extent - origin.Y) * invDir.Y
	t5 := (-g.Extent - origin.Z) * invDir.Z
	t6 := (g.Extent - origin.Z) * invDir.Z

	tMin = max(max(min(t1, t2), min(t3, t4)), min(t5, t6))
	tMax = min(min(max(t1, t2), max(t3, t4)), max(t5, t6))

	return tMin, tMax
}

// IsVisibleFrom checks if voxel (ix,iy,iz) is visible from camPos using DDA.
// Returns true if the ray from camPos hits this voxel first (no occlusion).
func (g *VoxelGrid) IsVisibleFrom(ix, iy, iz int, camPos Vec3) bool {
	target := g.Position(ix, iy, iz)

	// Ray direction from camera toward voxel
	dir := target.Sub(camPos).Normalize()

	// Find where ray enters the grid
	tMin, tMax := g.RayBoxIntersect(camPos, dir)
	if tMax < 0 || tMin > tMax {
		return false // Ray doesn't hit grid
	}

	// Start just inside the grid
	tStart := max(0, tMin) + 0.0001
	start := camPos.Add(dir.Scale(tStart))

	// Convert to grid coordinates
	fx, fy, fz := g.WorldToGrid(start)

	// Current voxel indices
	x, y, z := int(fx), int(fy), int(fz)

	// Clamp starting position to grid bounds
	res := g.Resolution
	x = max(0, min(res-1, x))
	y = max(0, min(res-1, y))
	z = max(0, min(res-1, z))

	// Step direction
	stepX, stepY, stepZ := 1, 1, 1
	if dir.X < 0 {
		stepX = -1
	}
	if dir.Y < 0 {
		stepY = -1
	}
	if dir.Z < 0 {
		stepZ = -1
	}

	// Distance to next voxel boundary (in t units)
	// tDelta: how far along ray to cross one voxel
	tDeltaX := g.voxelSize / abs(dir.X)
	tDeltaY := g.voxelSize / abs(dir.Y)
	tDeltaZ := g.voxelSize / abs(dir.Z)

	// tMax: t value at next voxel boundary
	var tMaxX, tMaxY, tMaxZ float64
	if stepX > 0 {
		tMaxX = ((float64(x+1)*g.voxelSize - g.Extent) - start.X) / dir.X
	} else {
		tMaxX = ((float64(x)*g.voxelSize - g.Extent) - start.X) / dir.X
	}
	if stepY > 0 {
		tMaxY = ((float64(y+1)*g.voxelSize - g.Extent) - start.Y) / dir.Y
	} else {
		tMaxY = ((float64(y)*g.voxelSize - g.Extent) - start.Y) / dir.Y
	}
	if stepZ > 0 {
		tMaxZ = ((float64(z+1)*g.voxelSize - g.Extent) - start.Z) / dir.Z
	} else {
		tMaxZ = ((float64(z)*g.voxelSize - g.Extent) - start.Z) / dir.Z
	}

	// DDA traversal
	maxSteps := res * 3 // Safety limit
	for i := 0; i < maxSteps; i++ {
		// Check if current voxel is occupied
		if x >= 0 && x < res && y >= 0 && y < res && z >= 0 && z < res {
			if g.Get(x, y, z) > 0.5 {
				// Hit an occupied voxel - is it our target?
				return x == ix && y == iy && z == iz
			}
		}

		// Step to next voxel (smallest tMax)
		if tMaxX < tMaxY {
			if tMaxX < tMaxZ {
				x += stepX
				tMaxX += tDeltaX
			} else {
				z += stepZ
				tMaxZ += tDeltaZ
			}
		} else {
			if tMaxY < tMaxZ {
				y += stepY
				tMaxY += tDeltaY
			} else {
				z += stepZ
				tMaxZ += tDeltaZ
			}
		}

		// Check if we've exited the grid
		if x < 0 || x >= res || y < 0 || y >= res || z < 0 || z >= res {
			break
		}
	}

	return false
}

// abs returns the absolute value of x.
func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

// OccupiedPositions returns world positions of all voxels with opacity > 0.5.
func (g *VoxelGrid) OccupiedPositions() []Vec3 {
	positions := make([]Vec3, 0, g.OccupiedCount())
	for ix := 0; ix < g.Resolution; ix++ {
		for iy := 0; iy < g.Resolution; iy++ {
			for iz := 0; iz < g.Resolution; iz++ {
				if g.Get(ix, iy, iz) > 0.5 {
					positions = append(positions, g.Position(ix, iy, iz))
				}
			}
		}
	}
	return positions
}
