package main

// ColoredPoint represents a 3D point with RGB color.
type ColoredPoint struct {
	Position Vec3
	R, G, B  uint8
}

// VoxelGrid represents a 3D binary occupancy grid.
type VoxelGrid struct {
	Resolution int
	Extent     float64
	Occupied   []bool  // flattened [Resolution^3]
	voxelSize  float64 // size of each voxel
}

// NewVoxelGrid creates a new voxel grid with all voxels initially occupied.
func NewVoxelGrid(resolution int, extent float64) *VoxelGrid {
	n := resolution * resolution * resolution
	occupied := make([]bool, n)
	for i := range occupied {
		occupied[i] = true
	}

	return &VoxelGrid{
		Resolution: resolution,
		Extent:     extent,
		Occupied:   occupied,
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

// Get returns the occupancy of a voxel.
func (g *VoxelGrid) Get(ix, iy, iz int) bool {
	return g.Occupied[g.Index(ix, iy, iz)]
}

// Set sets the occupancy of a voxel.
func (g *VoxelGrid) Set(ix, iy, iz int, occupied bool) {
	g.Occupied[g.Index(ix, iy, iz)] = occupied
}

// Clear marks a voxel as unoccupied (carved away).
func (g *VoxelGrid) Clear(ix, iy, iz int) {
	g.Occupied[g.Index(ix, iy, iz)] = false
}

// VoxelSize returns the size of each voxel.
func (g *VoxelGrid) VoxelSize() float64 {
	return g.voxelSize
}

// OccupiedCount returns the number of occupied voxels.
func (g *VoxelGrid) OccupiedCount() int {
	count := 0
	for _, occ := range g.Occupied {
		if occ {
			count++
		}
	}
	return count
}

// OccupiedPositions returns world positions of all occupied voxels.
func (g *VoxelGrid) OccupiedPositions() []Vec3 {
	positions := make([]Vec3, 0, g.OccupiedCount())
	for ix := 0; ix < g.Resolution; ix++ {
		for iy := 0; iy < g.Resolution; iy++ {
			for iz := 0; iz < g.Resolution; iz++ {
				if g.Get(ix, iy, iz) {
					positions = append(positions, g.Position(ix, iy, iz))
				}
			}
		}
	}
	return positions
}
