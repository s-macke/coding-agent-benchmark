package main

import (
	"image/png"
	"os"
)

// Silhouette represents a binary mask extracted from an image's alpha channel.
type Silhouette struct {
	Width  int
	Height int
	Mask   []bool // row-major: Mask[y*Width + x]
}

// SpriteImage holds both silhouette mask and RGB color data.
type SpriteImage struct {
	Width   int
	Height  int
	Mask    []bool  // row-major: Mask[y*Width + x]
	R, G, B []uint8 // RGB channels, row-major
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

// LoadSpriteImage loads a PNG image and extracts both alpha mask and RGB colors.
func LoadSpriteImage(path string, alphaThreshold float64) (*SpriteImage, error) {
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
	size := width * height
	mask := make([]bool, size)
	r := make([]uint8, size)
	g := make([]uint8, size)
	b := make([]uint8, size)

	threshold := uint32(alphaThreshold * 65535)

	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			idx := y*width + x
			red, green, blue, alpha := img.At(bounds.Min.X+x, bounds.Min.Y+y).RGBA()
			mask[idx] = alpha > threshold
			// Convert from 16-bit to 8-bit
			r[idx] = uint8(red >> 8)
			g[idx] = uint8(green >> 8)
			b[idx] = uint8(blue >> 8)
		}
	}

	return &SpriteImage{
		Width:  width,
		Height: height,
		Mask:   mask,
		R:      r,
		G:      g,
		B:      b,
	}, nil
}

// SampleColor returns the RGB color at the given float coordinates.
// Uses nearest-neighbor sampling (floor).
func (s *SpriteImage) SampleColor(x, y float64) (uint8, uint8, uint8) {
	ix := int(x)
	iy := int(y)
	if ix < 0 || ix >= s.Width || iy < 0 || iy >= s.Height {
		return 0, 0, 0
	}
	idx := iy*s.Width + ix
	return s.R[idx], s.G[idx], s.B[idx]
}

// Contains returns true if the pixel at (x, y) is inside the silhouette.
func (s *SpriteImage) Contains(x, y int) bool {
	if x < 0 || x >= s.Width || y < 0 || y >= s.Height {
		return false
	}
	return s.Mask[y*s.Width+x]
}

// InBounds checks if the coordinates are within image bounds.
func (s *SpriteImage) InBounds(x, y float64) bool {
	return x >= 0 && x < float64(s.Width)-1 && y >= 0 && y < float64(s.Height)-1
}

// ContainsFloat returns true if the pixel at float coordinates is inside the silhouette.
func (s *SpriteImage) ContainsFloat(x, y float64) bool {
	return s.Contains(int(x), int(y))
}

// MirrorHorizontal creates a new SpriteImage that is horizontally flipped.
func (s *SpriteImage) MirrorHorizontal() *SpriteImage {
	size := len(s.Mask)
	mask := make([]bool, size)
	r := make([]uint8, size)
	g := make([]uint8, size)
	b := make([]uint8, size)

	for y := 0; y < s.Height; y++ {
		for x := 0; x < s.Width; x++ {
			mirroredX := s.Width - 1 - x
			dstIdx := y*s.Width + x
			srcIdx := y*s.Width + mirroredX
			mask[dstIdx] = s.Mask[srcIdx]
			r[dstIdx] = s.R[srcIdx]
			g[dstIdx] = s.G[srcIdx]
			b[dstIdx] = s.B[srcIdx]
		}
	}

	return &SpriteImage{
		Width:  s.Width,
		Height: s.Height,
		Mask:   mask,
		R:      r,
		G:      g,
		B:      b,
	}
}

// MirrorHorizontal creates a new silhouette that is horizontally flipped.
func (s *Silhouette) MirrorHorizontal() *Silhouette {
	mask := make([]bool, len(s.Mask))

	for y := 0; y < s.Height; y++ {
		for x := 0; x < s.Width; x++ {
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
