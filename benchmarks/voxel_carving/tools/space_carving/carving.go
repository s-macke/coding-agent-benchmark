package main

import "fmt"

// CarveVisualHull performs space carving from multiple silhouettes.
// For each view, voxels that project outside the silhouette are marked as empty.
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
		fmt.Printf("  View %d: carved %d voxels\n", viewIdx, carved)
	}

	// Carve with mirrored views if symmetry enabled
	if symmetry {
		for viewIdx, cam := range cameras {
			img := images[viewIdx]
			mirroredCam := cam.Mirror()
			carved := carveFromView(grid, mirroredCam, img, true)
			fmt.Printf("  View %d (mirrored): carved %d voxels\n", viewIdx, carved)
		}
	}

	fmt.Printf("Visual hull: %d voxels occupied\n", grid.OccupiedCount())
}

// carveFromView carves voxels that don't project into a single silhouette.
// If mirrorX is true, flips X coordinate to simulate mirrored image.
func carveFromView(grid *VoxelGrid, cam *Camera, img *SpriteImage, mirrorX bool) int {
	carved := 0
	imgWidth := float64(img.Width() - 1)

	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				if !grid.Get(ix, iy, iz) {
					continue
				}

				pos := grid.Position(ix, iy, iz)
				projX, projY := cam.Project(pos)

				if mirrorX {
					projX = imgWidth - projX
				}

				if !img.InBounds(projX, projY) || !img.ContainsFloat(projX, projY) {
					grid.Clear(ix, iy, iz)
					carved++
				}
			}
		}
	}

	return carved
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
				if !grid.Get(ix, iy, iz) {
					continue
				}

				pos := grid.Position(ix, iy, iz)
				var sumR, sumG, sumB int
				count := 0

				for _, v := range views {
					projX, projY := v.cam.Project(pos)
					if v.mirrorX {
						projX = float64(v.img.Width()-1) - projX
					}

					if v.img.InBounds(projX, projY) && v.img.ContainsFloat(projX, projY) {
						r, g, b, _ := v.img.SampleColor(projX, projY).RGBA()
						sumR += int(r >> 8)
						sumG += int(g >> 8)
						sumB += int(b >> 8)
						count++
					}
				}

				var r, g, b uint8
				if count > 0 {
					r = uint8(sumR / count)
					g = uint8(sumG / count)
					b = uint8(sumB / count)
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
