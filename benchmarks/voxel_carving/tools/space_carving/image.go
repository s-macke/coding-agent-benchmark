package main

import (
	"image"
	"image/color"
	"image/png"
	"os"
)

// SpriteImage wraps an image.Image with alpha threshold for silhouette checks.
type SpriteImage struct {
	img       image.Image
	threshold uint32
}

// LoadSpriteImage loads a PNG image and wraps it with the given alpha threshold.
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

	return &SpriteImage{
		img:       img,
		threshold: uint32(alphaThreshold * 65535),
	}, nil
}

// Width returns the image width.
func (s *SpriteImage) Width() int {
	return s.img.Bounds().Dx()
}

// Height returns the image height.
func (s *SpriteImage) Height() int {
	return s.img.Bounds().Dy()
}

// Contains returns true if the pixel at (x, y) is inside the silhouette.
func (s *SpriteImage) Contains(x, y int) bool {
	bounds := s.img.Bounds()
	if x < 0 || x >= bounds.Dx() || y < 0 || y >= bounds.Dy() {
		return false
	}
	_, _, _, a := s.img.At(bounds.Min.X+x, bounds.Min.Y+y).RGBA()
	return a > s.threshold
}

// InBounds checks if the coordinates are within image bounds.
func (s *SpriteImage) InBounds(x, y float64) bool {
	return x >= 0 && x < float64(s.Width())-1 && y >= 0 && y < float64(s.Height())-1
}

// ContainsFloat returns true if the pixel at float coordinates is inside the silhouette.
func (s *SpriteImage) ContainsFloat(x, y float64) bool {
	return s.Contains(int(x), int(y))
}

// SampleColor returns the color at the given float coordinates.
func (s *SpriteImage) SampleColor(x, y float64) color.Color {
	ix, iy := int(x), int(y)
	bounds := s.img.Bounds()
	if ix < 0 || ix >= bounds.Dx() || iy < 0 || iy >= bounds.Dy() {
		return color.RGBA{}
	}
	return s.img.At(bounds.Min.X+ix, bounds.Min.Y+iy)
}
