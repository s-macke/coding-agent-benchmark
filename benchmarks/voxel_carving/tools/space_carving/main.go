package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

func fatalf(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}

func main() {
	jsonPath := flag.String("json", "ship_sprites_centered.json", "JSON file path")
	imagesDir := flag.String("images", "centered_images", "Images directory")
	outputPath := flag.String("output", "model.ply", "Output PLY path")
	resolution := flag.Int("resolution", 128, "Voxel grid size")
	extent := flag.Float64("extent", 1.5, "Grid extent (±value)")
	orthoScale := flag.Float64("ortho", 2.0, "Orthographic scale")
	distance := flag.Float64("distance", 5.0, "Camera distance")
	alphaThreshold := flag.Float64("alpha", 0.5, "Alpha threshold")
	symmetry := flag.Bool("symmetry", false, "Enable Y-axis mirror symmetry")
	mesh := flag.Bool("mesh", false, "Export as mesh with cube faces (instead of point cloud)")
	flag.Parse()

	fmt.Printf("Loading sprites from %s...\n", *jsonPath)
	sprites, err := LoadSprites(*jsonPath)
	if err != nil {
		fatalf("Error loading sprites: %v", err)
	}
	fmt.Printf("  Loaded %d sprites\n", len(sprites))

	fmt.Println("Loading images and building cameras...")
	cameras := make([]*Camera, len(sprites))
	silhouettes := make([]*Silhouette, len(sprites))
	spriteImages := make([]*SpriteImage, len(sprites))

	for i, sprite := range sprites {
		imgPath := filepath.Join(*imagesDir, sprite.Filename)

		sil, err := LoadSilhouette(imgPath, *alphaThreshold)
		if err != nil {
			fatalf("Error loading image %s: %v", imgPath, err)
		}
		silhouettes[i] = sil

		sprImg, err := LoadSpriteImage(imgPath, *alphaThreshold)
		if err != nil {
			fatalf("Error loading sprite image %s: %v", imgPath, err)
		}
		spriteImages[i] = sprImg

		cameras[i] = NewCamera(
			sprite.Yaw,
			sprite.Pitch,
			sprite.CameraUpVec(),
			sprite.CameraRightVec(),
			sprite.Width,
			sprite.Height,
			*orthoScale,
			*distance,
		)
	}
	fmt.Printf("  Loaded %d images\n", len(silhouettes))

	fmt.Printf("Creating %dx%dx%d voxel grid (extent ±%.2f)...\n",
		*resolution, *resolution, *resolution, *extent)
	grid := NewVoxelGrid(*resolution, *extent)
	fmt.Printf("  Initial voxels: %d\n", grid.OccupiedCount())

	fmt.Println("Carving visual hull...")
	CarveVisualHull(grid, cameras, silhouettes, *symmetry)

	coloredPoints := SampleColors(grid, cameras, spriteImages, *symmetry)

	fmt.Printf("Exporting %d colored voxels to %s...\n", len(coloredPoints), *outputPath)
	if *mesh {
		fmt.Println("  Format: PLY mesh (cubes with faces)")
		err = ExportMeshPLY(coloredPoints, grid.VoxelSize(), *outputPath)
	} else {
		fmt.Println("  Format: PLY point cloud")
		err = ExportColoredPLY(coloredPoints, *outputPath)
	}
	if err != nil {
		fatalf("Error exporting PLY: %v", err)
	}

	fmt.Println("Done!")
}
