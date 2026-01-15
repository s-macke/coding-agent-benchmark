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

				alpha := img.SampleAlpha(projX, projY)
				if alpha < 1.0 {
					grid.MultiplyOpacity(ix, iy, iz, alpha)
					reduced++
				}
			}
		}
	}

	return reduced
}

// SampleColors samples RGB colors for all occupied voxels by projecting to views.
// Returns colored points with averaged R, G, B values from all visible views.
func SampleColors(grid *VoxelGrid, cameras []*Camera, images []*SpriteImage, symmetry bool) []ColoredPoint {
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

	points := make([]ColoredPoint, 0, grid.OccupiedCount())

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
					projX, projY := v.cam.Project(pos)
					if v.mirrorX {
						projX = float64(v.img.Width()) - projX
					}

					alpha := v.img.SampleAlpha(projX, projY)
					if alpha > 0.01 {
						r, g, b, _ := v.img.SampleColor(projX, projY).RGBA()
						// Weight by alpha for better color blending
						sumR += float64(r>>8) * alpha
						sumG += float64(g>>8) * alpha
						sumB += float64(b>>8) * alpha
						totalWeight += alpha
					}
				}

				var r, g, b uint8
				if totalWeight > 0 {
					r = uint8(sumR / totalWeight)
					g = uint8(sumG / totalWeight)
					b = uint8(sumB / totalWeight)
				}

				points = append(points, ColoredPoint{
					Position: pos,
					R:        r,
					G:        g,
					B:        b,
				})
			}
		}
	}

	fmt.Printf("  Colored %d points from %d views\n", len(points), len(views))
	return points
}
