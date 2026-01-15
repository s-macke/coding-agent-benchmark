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
					continue
				}

				pos := grid.Position(ix, iy, iz)
				projX, projY := cam.Project(pos)

				if !sil.InBounds(projX, projY) || !sil.ContainsFloat(projX, projY) {
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

	// Build list of all cameras and images (including mirrored if symmetry)
	allCameras := make([]*Camera, 0, len(cameras)*2)
	allImages := make([]*SpriteImage, 0, len(images)*2)

	for i, cam := range cameras {
		allCameras = append(allCameras, cam)
		allImages = append(allImages, images[i])
	}

	if symmetry {
		for i, cam := range cameras {
			allCameras = append(allCameras, cam.Mirror())
			allImages = append(allImages, images[i].MirrorHorizontal())
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

				// Track color sums for averaging
				var sumR, sumG, sumB int
				count := 0

				for i, cam := range allCameras {
					img := allImages[i]
					projX, projY := cam.Project(pos)

					if img.InBounds(projX, projY) && img.ContainsFloat(projX, projY) {
						r, g, b := img.SampleColor(projX, projY)
						sumR += int(r)
						sumG += int(g)
						sumB += int(b)
						count++
					}
				}

				// Compute averaged color
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

	fmt.Printf("  Colored %d points from %d views\n", len(points), len(allCameras))
	return points
}
