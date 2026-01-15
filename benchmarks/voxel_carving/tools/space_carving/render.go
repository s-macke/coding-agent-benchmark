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
func RenderView(coloredPoints []ColoredPoint, cam *Camera, voxelSize float64) *image.RGBA {
	width, height := cam.Width, cam.Height
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	depth := make([]float64, width*height)

	// Initialize depth to +infinity
	for i := range depth {
		depth[i] = math.MaxFloat64
	}

	// Projected voxel half-size in pixels
	halfW := (voxelSize / 2) * cam.Fx
	halfH := (voxelSize / 2) * cam.Fy

	for _, p := range coloredPoints {
		// Transform to camera space
		camCoords := cam.ViewMat.MulVec3(p.Position)
		z := camCoords.Z // Depth (smaller = closer)

		// Project voxel center to 2D
		x := cam.Fx*camCoords.X + cam.Cx
		y := cam.Fy*camCoords.Y + cam.Cy

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
		col := color.RGBA{R: p.R, G: p.G, B: p.B, A: 255}
		for py := minY; py < maxY; py++ {
			for px := minX; px < maxX; px++ {
				idx := py*width + px
				if z < depth[idx] {
					depth[idx] = z
					img.SetRGBA(px, py, col)
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
func RenderAllViews(coloredPoints []ColoredPoint, cameras []*Camera,
	sprites []Sprite, voxelSize float64, imagesDir, outputDir string) error {

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
		rendered := RenderView(coloredPoints, cam, voxelSize)

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
