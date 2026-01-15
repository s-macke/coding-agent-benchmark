package main

import (
	"image"
	"image/png"
	"os"
)

// Silhouette represents a binary mask extracted from an image's alpha channel.
type Silhouette struct {
	Width  int
	Height int
	Mask   []bool // row-major: Mask[y*Width + x]
}

// LoadSilhouette loads a PNG image and extracts the alpha channel as a binary mask.
func LoadSilhouette(path string, alphaThreshold float64) (*Silhouette, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	img, err := png.Decode(file)
	if err != nil {
		return nil, err
	}

	bounds := img.Bounds()
	width := bounds.Dx()
	height := bounds.Dy()
	mask := make([]bool, width*height)

	threshold := uint32(alphaThreshold * 65535)

	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			_, _, _, a := img.At(bounds.Min.X+x, bounds.Min.Y+y).RGBA()
			mask[y*width+x] = a > threshold
		}
	}

	return &Silhouette{
		Width:  width,
		Height: height,
		Mask:   mask,
	}, nil
}

// Contains returns true if the pixel at (x, y) is inside the silhouette.
func (s *Silhouette) Contains(x, y int) bool {
	if x < 0 || x >= s.Width || y < 0 || y >= s.Height {
		return false
	}
	return s.Mask[y*s.Width+x]
}

// InBounds checks if the coordinates are within image bounds.
func (s *Silhouette) InBounds(x, y float64) bool {
	return x >= 0 && x < float64(s.Width)-1 && y >= 0 && y < float64(s.Height)-1
}

// ContainsFloat returns true if the pixel at float coordinates is inside the silhouette.
// Uses floor to convert to integer coordinates.
func (s *Silhouette) ContainsFloat(x, y float64) bool {
	ix := int(x)
	iy := int(y)
	return s.Contains(ix, iy)
}

// MirrorHorizontal creates a new silhouette that is horizontally flipped.
// This is used for exploiting the ship's left-right symmetry.
func (s *Silhouette) MirrorHorizontal() *Silhouette {
	mask := make([]bool, len(s.Mask))

	for y := 0; y < s.Height; y++ {
		for x := 0; x < s.Width; x++ {
			// Map x to (Width - 1 - x) for horizontal flip
			mirroredX := s.Width - 1 - x
			mask[y*s.Width+x] = s.Mask[y*s.Width+mirroredX]
		}
	}

	return &Silhouette{
		Width:  s.Width,
		Height: s.Height,
		Mask:   mask,
	}
}

// Ensure image package is imported for bounds type
var _ image.Image
