package main

import "fmt"

// CarveVisualHull performs space carving from multiple silhouettes.
// For each view, voxels that project outside the silhouette are marked as empty.
// If symmetry is true, also uses mirrored views (doubles effective views).
func CarveVisualHull(grid *VoxelGrid, cameras []*Camera, silhouettes []*Silhouette, symmetry bool) {
	numViews := len(cameras)
	if symmetry {
		numViews *= 2
	}
	fmt.Printf("Carving with %d views (symmetry=%v)...\n", numViews, symmetry)

	// Carve with original views
	for viewIdx, cam := range cameras {
		sil := silhouettes[viewIdx]
		carved := carveFromView(grid, cam, sil)
		fmt.Printf("  View %d: carved %d voxels\n", viewIdx, carved)
	}

	// Carve with mirrored views if symmetry enabled
	if symmetry {
		for viewIdx, cam := range cameras {
			sil := silhouettes[viewIdx]
			mirroredCam := cam.Mirror()
			mirroredSil := sil.MirrorHorizontal()
			carved := carveFromView(grid, mirroredCam, mirroredSil)
			fmt.Printf("  View %d (mirrored): carved %d voxels\n", viewIdx, carved)
		}
	}

	fmt.Printf("Visual hull: %d voxels occupied\n", grid.OccupiedCount())
}

// carveFromView carves voxels that don't project into a single silhouette.
func carveFromView(grid *VoxelGrid, cam *Camera, sil *Silhouette) int {
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

	return carved
}
