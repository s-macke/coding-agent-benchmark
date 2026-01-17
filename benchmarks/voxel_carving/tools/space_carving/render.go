package main

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"math"
	"os"
	"path/filepath"
)

// RenderView renders the voxel model from a single camera viewpoint using Z-buffer.
func RenderView(grid *VoxelGrid, cam Camera) *image.RGBA {
	base := cam.Base()
	width, height := base.Width, base.Height
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	depthBuf := make([]float64, width*height)

	// Initialize depth to +infinity
	for i := range depthBuf {
		depthBuf[i] = math.MaxFloat64
	}

	// Voxel half-size in world units
	voxelSize := grid.VoxelSize()
	halfVoxel := voxelSize / 2

	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				v := grid.GetVoxel(ix, iy, iz)
				if v.Opacity <= 0.5 {
					continue
				}

				pos := grid.Position(ix, iy, iz)

				// Project voxel center and get depth
				x, y, z := cam.ProjectWithDepth(pos)

				// Skip if behind camera (for perspective)
				if cam.IsPerspective() && z <= 0 {
					continue
				}

				// Calculate projected voxel half-size in pixels
				var halfW, halfH float64
				if cam.IsPerspective() {
					// Perspective: size scales inversely with depth
					halfW = (halfVoxel * base.Fx) / z
					halfH = (halfVoxel * base.Fy) / z
				} else {
					// Orthographic: constant size
					halfW = halfVoxel * base.Fx
					halfH = halfVoxel * base.Fy
				}

				// Voxel covers pixels from (x-halfW, y-halfH) to (x+halfW, y+halfH)
				minX := int(math.Floor(x - halfW))
				maxX := int(math.Ceil(x + halfW))
				minY := int(math.Floor(y - halfH))
				maxY := int(math.Ceil(y + halfH))

				// Clamp to image bounds
				if minX < 0 {
					minX = 0
				}
				if maxX > width {
					maxX = width
				}
				if minY < 0 {
					minY = 0
				}
				if maxY > height {
					maxY = height
				}

				// Fill all pixels with depth test
				r, g, b, _ := v.Color().RGBA()
				col := color.RGBA{R: r, G: g, B: b, A: 255}
				for py := minY; py < maxY; py++ {
					for px := minX; px < maxX; px++ {
						idx := py*width + px
						if z < depthBuf[idx] {
							depthBuf[idx] = z
							img.SetRGBA(px, py, col)
						}
					}
				}
			}
		}
	}
	return img
}

// CreateComparison creates a side-by-side comparison image.
func CreateComparison(original, rendered *image.RGBA) *image.RGBA {
	w := original.Bounds().Dx()
	h := original.Bounds().Dy()

	// Create combined image (2x width)
	combined := image.NewRGBA(image.Rect(0, 0, w*2, h))

	// Draw original on left
	draw.Draw(combined, image.Rect(0, 0, w, h), original, image.Point{}, draw.Src)

	// Draw rendered on right
	draw.Draw(combined, image.Rect(w, 0, w*2, h), rendered, image.Point{}, draw.Src)

	return combined
}

// LoadPNG loads a PNG image and converts to RGBA.
func LoadPNG(path string) (*image.RGBA, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	img, err := png.Decode(file)
	if err != nil {
		return nil, err
	}

	// Convert to RGBA if needed
	rgba, ok := img.(*image.RGBA)
	if !ok {
		bounds := img.Bounds()
		rgba = image.NewRGBA(bounds)
		draw.Draw(rgba, bounds, img, bounds.Min, draw.Src)
	}
	return rgba, nil
}

// SavePNG saves an image as PNG.
func SavePNG(img image.Image, path string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, img)
}

// RenderAllViews renders comparison images for all camera views.
func RenderAllViews(grid *VoxelGrid, cameras []Camera,
	sprites []Sprite, imagesDir, outputDir string) error {

	// Create output directory
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}

	fmt.Printf("Rendering %d views to %s...\n", len(cameras), outputDir)

	for i, cam := range cameras {
		// Load original image
		originalPath := filepath.Join(imagesDir, sprites[i].Filename)
		original, err := LoadPNG(originalPath)
		if err != nil {
			return fmt.Errorf("failed to load original image %s: %w", originalPath, err)
		}

		// Render voxel model from this view
		rendered := RenderView(grid, cam)

		// Create side-by-side comparison
		comparison := CreateComparison(original, rendered)

		// Save comparison
		outputPath := filepath.Join(outputDir, fmt.Sprintf("view_%02d_comparison.png", i))
		if err := SavePNG(comparison, outputPath); err != nil {
			return fmt.Errorf("failed to save comparison %s: %w", outputPath, err)
		}

		fmt.Printf("  View %d: %s\n", i, outputPath)
	}

	return nil
}
