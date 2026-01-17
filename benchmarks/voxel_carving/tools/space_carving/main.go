package main

import (
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"

	"voxelcarve/camera"
	"voxelcarve/common"
	"voxelcarve/voxelgrid"
)

func fatalf(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}

func isCardinalAngle(yaw, pitch float64) bool {
	// Top or bottom
	if pitch == 90 || pitch == -90 {
		return true
	}
	// Horizontal plane at 90° yaw intervals
	if pitch == 0 {
		yawMod := math.Mod(yaw, 90)
		return yawMod == 0
	}
	return false
}

func filterCardinalSprites(sprites []Sprite) []Sprite {
	var result []Sprite
	for _, s := range sprites {
		if isCardinalAngle(s.Yaw, s.Pitch) {
			result = append(result, s)
		}
	}
	return result
}

func main() {
	jsonPath := flag.String("json", "ship_sprites_centered.json", "JSON file path")
	imagesDir := flag.String("images", "centered_images", "Images directory")
	outputPath := flag.String("output", "model.ply", "Output path (default: model.vox if -vox, else model.ply)")
	resolution := flag.Int("resolution", 128, "Voxel grid size")
	extent := flag.Float64("extent", 1.5, "Grid extent (±value)")
	orthoScale := flag.Float64("ortho", 2.0, "Orthographic scale")
	distance := flag.Float64("distance", 5.0, "Camera distance")
	alphaThreshold := flag.Float64("alpha", 0.5, "Alpha threshold")
	symmetry := flag.Bool("symmetry", false, "Enable Y-axis mirror symmetry")
	minVotes := flag.Int("min-votes", 2, "Minimum views that must agree to carve a voxel")
	mesh := flag.Bool("mesh", false, "Export as mesh with cube faces (instead of point cloud)")
	vox := flag.Bool("vox", false, "Export as MagicaVoxel .vox format")
	render := flag.Bool("render", false, "Render comparison images for each view")
	renderDir := flag.String("renderdir", "renders", "Output directory for rendered images")
	cardinal := flag.Bool("cardinal", false, "Use only cardinal camera directions (6 orthogonal views)")
	cameraType := flag.String("camera", "", "Camera type: 'orthographic' or 'perspective' (required)")
	fov := flag.Float64("fov", 60.0, "Vertical field of view in degrees (for perspective mode)")
	flag.Parse()

	// Adjust default output filename based on format
	if *vox && *outputPath == "model.ply" {
		*outputPath = "model.vox"
	}

	// Check for unknown arguments
	if flag.NArg() > 0 {
		fmt.Fprintf(os.Stderr, "Error: unknown argument(s): %v\n", flag.Args())
		flag.Usage()
		os.Exit(1)
	}

	// Validate required camera type
	if *cameraType != "orthographic" && *cameraType != "perspective" {
		fatalf("Error: -camera flag is required and must be 'orthographic' or 'perspective'")
	}

	fmt.Printf("Loading sprites from %s...\n", *jsonPath)
	sprites, err := LoadSprites(*jsonPath)
	if err != nil {
		fatalf("Error loading sprites: %v", err)
	}
	fmt.Printf("  Loaded %d sprites\n", len(sprites))

	if *cardinal {
		sprites = filterCardinalSprites(sprites)
		fmt.Printf("  Filtered to %d cardinal views\n", len(sprites))
	}

	projType := "orthographic"
	if *cameraType == "perspective" {
		projType = fmt.Sprintf("perspective (FOV=%.1f°)", *fov)
	}
	fmt.Printf("Loading images and building cameras (%s)...\n", projType)
	cameras := make([]camera.Camera, len(sprites))
	images := make([]*common.SpriteImage, len(sprites))

	for i, sprite := range sprites {
		imgPath := filepath.Join(*imagesDir, sprite.Filename)

		img, err := common.LoadSpriteImage(imgPath, *alphaThreshold)
		if err != nil {
			fatalf("Error loading image %s: %v", imgPath, err)
		}
		images[i] = img

		if *cameraType == "perspective" {
			cameras[i] = camera.NewPerspectiveCamera(
				sprite.Yaw,
				sprite.Pitch,
				sprite.CameraUpVec(),
				sprite.CameraRightVec(),
				sprite.Width,
				sprite.Height,
				*fov,
				*distance,
			)
		} else {
			cameras[i] = camera.NewOrthographicCamera(
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
	}
	fmt.Printf("  Loaded %d images\n", len(images))

	fmt.Printf("Creating %dx%dx%d voxel grid (extent ±%.2f)...\n",
		*resolution, *resolution, *resolution, *extent)
	grid := voxelgrid.NewVoxelGrid(*resolution, *extent)
	fmt.Printf("  Initial voxels: %d\n", grid.OccupiedCount())

	fmt.Println("Carving visual hull...")
	CarveVisualHull(grid, cameras, images, *symmetry, *minVotes)

	SampleColors(grid, cameras, images, *symmetry)

	fmt.Printf("Exporting %d colored voxels to %s...\n", grid.OccupiedCount(), *outputPath)
	if *vox {
		fmt.Println("  Format: MagicaVoxel .vox")
		err = ExportVOX(grid, *outputPath)
	} else if *mesh {
		fmt.Println("  Format: PLY mesh (cubes with faces)")
		err = ExportMeshPLY(grid, *outputPath)
	} else {
		fmt.Println("  Format: PLY point cloud")
		err = ExportColoredPLY(grid, *outputPath)
	}
	if err != nil {
		fatalf("Error exporting: %v", err)
	}

	if *render {
		err = RenderAllViews(grid, cameras, sprites, *imagesDir, *renderDir)
		if err != nil {
			fatalf("Error rendering views: %v", err)
		}
	}

	fmt.Println("Done!")
}
