package main

import (
	"fmt"

	"voxelcarve/camera"
	"voxelcarve/common"
	"voxelcarve/voxelgrid"
)

// viewInfo holds camera and image info for a single view.
type viewInfo struct {
	cam     camera.Camera
	img     *common.SpriteImage
	mirrorX bool
}

// buildViews creates a list of all views including mirrored ones if symmetry is enabled.
func buildViews(cameras []camera.Camera, images []*common.SpriteImage, symmetry bool) []viewInfo {
	views := make([]viewInfo, 0, len(cameras)*2)
	for i, cam := range cameras {
		views = append(views, viewInfo{cam, images[i], false})
	}
	if symmetry {
		for i, cam := range cameras {
			views = append(views, viewInfo{cam.Mirror(), images[i], true})
		}
	}
	return views
}

// CarveVisualHull performs space carving from multiple silhouettes using vote counting.
// A voxel is carved only if at least minVotes views agree (alpha < 0.5).
// If symmetry is true, also uses mirrored views (doubles effective views).
func CarveVisualHull(grid *voxelgrid.VoxelGrid, cameras []camera.Camera, images []*common.SpriteImage, symmetry bool, minVotes int) {
	views := buildViews(cameras, images, symmetry)
	fmt.Printf("Carving with %d views (symmetry=%v, minVotes=%d)...\n", len(views), symmetry, minVotes)

	carved := 0
	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				if grid.Get(ix, iy, iz) < 0.001 {
					continue // Already fully transparent
				}

				pos := grid.Position(ix, iy, iz)
				carveVotes := 0

				for _, v := range views {
					projX, projY := v.cam.Project(pos)
					if v.mirrorX {
						projX = float64(v.img.Width()) - projX
					}

					c := v.img.Sample(projX, projY)
					if c.A < 0.5 {
						carveVotes++
					}
				}

				if carveVotes >= minVotes {
					grid.Set(ix, iy, iz, 0)
					carved++
				}
			}
		}
	}

	fmt.Printf("  Carved %d voxels (required %d+ votes)\n", carved, minVotes)
	fmt.Printf("Visual hull: %d voxels with opacity > 0.5\n", grid.OccupiedCount())
}

// SampleColors samples RGB colors for all occupied voxels by projecting to views.
// Colors are stored directly in the grid using minimum value per channel.
func SampleColors(grid *voxelgrid.VoxelGrid, cameras []camera.Camera, images []*common.SpriteImage, symmetry bool) {
	fmt.Println("Sampling colors...")

	views := buildViews(cameras, images, symmetry)

	colored := 0
	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				if grid.Get(ix, iy, iz) <= 0.5 {
					continue
				}

				pos := grid.Position(ix, iy, iz)
				var sumR, sumG, sumB float64
				var totalWeight float64

				for _, v := range views {
					// Check if voxel is visible from this camera using DDA
					if !grid.IsVisibleFrom(ix, iy, iz, v.cam.Base().Position) {
						continue // Occluded, skip this view
					}

					projX, projY := v.cam.Project(pos)
					if v.mirrorX {
						projX = float64(v.img.Width()) - projX
					}

					c := v.img.Sample(projX, projY)
					if c.A > 0.01 {
						// Weight by alpha for better color blending
						sumR += c.R * c.A
						sumG += c.G * c.A
						sumB += c.B * c.A
						totalWeight += c.A
					}
				}

				if totalWeight > 0 {
					grid.SetColor(ix, iy, iz, sumR/totalWeight, sumG/totalWeight, sumB/totalWeight)
					colored++
				}
			}
		}
	}

	fmt.Printf("  Colored %d voxels from %d views\n", colored, len(views))
}
