package main

import "fmt"

// CarveVisualHull performs space carving from multiple silhouettes.
// For each view, voxel opacity is multiplied by the sampled alpha.
// If symmetry is true, also uses mirrored views (doubles effective views).
func CarveVisualHull(grid *VoxelGrid, cameras []*Camera, images []*SpriteImage, symmetry bool) {
	numViews := len(cameras)
	if symmetry {
		numViews *= 2
	}
	fmt.Printf("Carving with %d views (symmetry=%v)...\n", numViews, symmetry)

	// Carve with original views
	for viewIdx, cam := range cameras {
		img := images[viewIdx]
		carved := carveFromView(grid, cam, img, false)
		fmt.Printf("  View %d: reduced opacity for %d voxels\n", viewIdx, carved)
	}

	// Carve with mirrored views if symmetry enabled
	if symmetry {
		for viewIdx, cam := range cameras {
			img := images[viewIdx]
			mirroredCam := cam.Mirror()
			carved := carveFromView(grid, mirroredCam, img, true)
			fmt.Printf("  View %d (mirrored): reduced opacity for %d voxels\n", viewIdx, carved)
		}
	}

	fmt.Printf("Visual hull: %d voxels with opacity > 0.5\n", grid.OccupiedCount())
}

// carveFromView multiplies voxel opacity by sampled alpha from the image.
// If mirrorX is true, flips X coordinate to simulate mirrored image.
// Returns count of voxels whose opacity was reduced (alpha < 1).
func carveFromView(grid *VoxelGrid, cam *Camera, img *SpriteImage, mirrorX bool) int {
	reduced := 0
	imgWidth := float64(img.Width())

	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				opacity := grid.Get(ix, iy, iz)
				if opacity < 0.001 {
					continue // Already fully transparent
				}

				pos := grid.Position(ix, iy, iz)
				projX, projY := cam.Project(pos)

				if mirrorX {
					projX = imgWidth - projX
				}

				c := img.Sample(projX, projY)
				if c.A < 1.0 {
					grid.MultiplyOpacity(ix, iy, iz, c.A)
					reduced++
				}
			}
		}
	}

	return reduced
}

// SampleColors samples RGB colors for all occupied voxels by projecting to views.
// Colors are stored directly in the grid using minimum value per channel.
func SampleColors(grid *VoxelGrid, cameras []*Camera, images []*SpriteImage, symmetry bool) {
	fmt.Println("Sampling colors...")

	// Build list of cameras with mirror flags
	type viewInfo struct {
		cam     *Camera
		img     *SpriteImage
		mirrorX bool
	}

	views := make([]viewInfo, 0, len(cameras)*2)
	for i, cam := range cameras {
		views = append(views, viewInfo{cam, images[i], false})
	}
	if symmetry {
		for i, cam := range cameras {
			views = append(views, viewInfo{cam.Mirror(), images[i], true})
		}
	}

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
					if !grid.IsVisibleFrom(ix, iy, iz, v.cam.Position) {
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
