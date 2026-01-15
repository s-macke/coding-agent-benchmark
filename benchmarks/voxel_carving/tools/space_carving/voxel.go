package main

// ColoredPoint represents a 3D point with RGB color.
type ColoredPoint struct {
	Position Vec3
	R, G, B  uint8
}

// VoxelGrid represents a 3D occupancy grid with continuous opacity.
type VoxelGrid struct {
	Resolution int
	Extent     float64
	Opacity    []float64 // flattened [Resolution^3], values 0-1
	voxelSize  float64   // size of each voxel
}

// NewVoxelGrid creates a new voxel grid with all voxels initially fully opaque.
func NewVoxelGrid(resolution int, extent float64) *VoxelGrid {
	n := resolution * resolution * resolution
	opacity := make([]float64, n)
	for i := range opacity {
		opacity[i] = 1.0
	}

	return &VoxelGrid{
		Resolution: resolution,
		Extent:     extent,
		Opacity:    opacity,
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
	return g.Opacity[g.Index(ix, iy, iz)]
}

// Set sets the opacity of a voxel.
func (g *VoxelGrid) Set(ix, iy, iz int, opacity float64) {
	g.Opacity[g.Index(ix, iy, iz)] = opacity
}

// MultiplyOpacity multiplies the voxel's opacity by a factor.
func (g *VoxelGrid) MultiplyOpacity(ix, iy, iz int, factor float64) {
	idx := g.Index(ix, iy, iz)
	g.Opacity[idx] *= factor
}

// VoxelSize returns the size of each voxel.
func (g *VoxelGrid) VoxelSize() float64 {
	return g.voxelSize
}

// OccupiedCount returns the number of voxels with opacity > 0.5.
func (g *VoxelGrid) OccupiedCount() int {
	count := 0
	for _, occ := range g.Opacity {
		if occ > 0.5 {
			count++
		}
	}
	return count
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
