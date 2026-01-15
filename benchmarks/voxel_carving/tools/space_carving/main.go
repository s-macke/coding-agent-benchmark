package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	// CLI flags
	jsonPath := flag.String("json", "ship_sprites_centered.json", "JSON file path")
	imagesDir := flag.String("images", "centered_images", "Images directory")
	outputPath := flag.String("output", "model.ply", "Output PLY path")
	resolution := flag.Int("resolution", 128, "Voxel grid size")
	extent := flag.Float64("extent", 1.5, "Grid extent (±value)")
	orthoScale := flag.Float64("ortho", 2.0, "Orthographic scale")
	distance := flag.Float64("distance", 5.0, "Camera distance")
	alphaThreshold := flag.Float64("alpha", 0.5, "Alpha threshold")

	flag.Parse()

	// Load sprite metadata
	fmt.Printf("Loading sprites from %s...\n", *jsonPath)
	sprites, err := LoadSprites(*jsonPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading sprites: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("  Loaded %d sprites\n", len(sprites))

	// Load silhouettes and create cameras
	fmt.Println("Loading images and building cameras...")
	cameras := make([]*Camera, len(sprites))
	silhouettes := make([]*Silhouette, len(sprites))

	for i, sprite := range sprites {
		imgPath := filepath.Join(*imagesDir, sprite.Filename)
		sil, err := LoadSilhouette(imgPath, *alphaThreshold)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error loading image %s: %v\n", imgPath, err)
			os.Exit(1)
		}
		silhouettes[i] = sil

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

	// Create voxel grid
	fmt.Printf("Creating %dx%dx%d voxel grid (extent ±%.2f)...\n",
		*resolution, *resolution, *resolution, *extent)
	grid := NewVoxelGrid(*resolution, *extent)
	fmt.Printf("  Initial voxels: %d\n", grid.OccupiedCount())

	// Perform carving
	fmt.Println("Carving visual hull...")
	CarveVisualHull(grid, cameras, silhouettes)

	// Export result
	points := grid.OccupiedPositions()
	fmt.Printf("Exporting %d points to %s...\n", len(points), *outputPath)
	if err := ExportPLY(points, *outputPath); err != nil {
		fmt.Fprintf(os.Stderr, "Error exporting PLY: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("Done!")
}
