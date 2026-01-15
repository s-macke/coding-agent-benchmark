package main

import "fmt"

// CarveVisualHull performs space carving from multiple silhouettes.
// For each view, voxels that project outside the silhouette are marked as empty.
func CarveVisualHull(grid *VoxelGrid, cameras []*Camera, silhouettes []*Silhouette) {
	fmt.Printf("Carving with %d views...\n", len(cameras))

	for viewIdx, cam := range cameras {
		sil := silhouettes[viewIdx]
		carved := 0

		for ix := 0; ix < grid.Resolution; ix++ {
			for iy := 0; iy < grid.Resolution; iy++ {
				for iz := 0; iz < grid.Resolution; iz++ {
					if !grid.Get(ix, iy, iz) {
						continue // Already carved
					}

					// Get voxel center in world coordinates
					pos := grid.Position(ix, iy, iz)

					// Project to 2D
					projX, projY := cam.Project(pos)

					// Check if projection is in silhouette
					inBounds := sil.InBounds(projX, projY)
					inSilhouette := inBounds && sil.ContainsFloat(projX, projY)

					// Carve if outside silhouette
					if !inSilhouette {
						grid.Clear(ix, iy, iz)
						carved++
					}
				}
			}
		}

		fmt.Printf("  View %d: carved %d voxels\n", viewIdx, carved)
	}

	fmt.Printf("Visual hull: %d voxels occupied\n", grid.OccupiedCount())
}
