package main

import (
	"image"
	"image/color"
	"image/png"
	"math"
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

// InBounds checks if the coordinates are within image bounds.
// Pixel centers are at 0.5 offsets, so valid range is [0, Width) and [0, Height).
func (s *SpriteImage) InBounds(x, y float64) bool {
	return x >= 0 && x < float64(s.Width()) && y >= 0 && y < float64(s.Height())
}

// alpha returns the alpha value (0-1) at integer pixel coordinates.
func (s *SpriteImage) alpha(x, y int) float64 {
	bounds := s.img.Bounds()
	if x < 0 || x >= bounds.Dx() || y < 0 || y >= bounds.Dy() {
		return 0
	}
	_, _, _, a := s.img.At(bounds.Min.X+x, bounds.Min.Y+y).RGBA()
	return float64(a) / 65535.0
}

// rgbaAt returns RGBA values (0-1) at integer pixel coordinates.
func (s *SpriteImage) rgbaAt(x, y int) (r, g, b, a float64) {
	bounds := s.img.Bounds()
	if x < 0 || x >= bounds.Dx() || y < 0 || y >= bounds.Dy() {
		return 0, 0, 0, 0
	}
	ri, gi, bi, ai := s.img.At(bounds.Min.X+x, bounds.Min.Y+y).RGBA()
	return float64(ri) / 65535.0, float64(gi) / 65535.0, float64(bi) / 65535.0, float64(ai) / 65535.0
}

// SampleAlpha returns bilinear interpolated alpha (0-1) at float coordinates.
// Returns 0 for out-of-bounds coordinates.
func (s *SpriteImage) SampleAlpha(x, y float64) float64 {
	if x < 0 || x >= float64(s.Width()) || y < 0 || y >= float64(s.Height()) {
		return 0
	}

	x0, y0 := int(math.Floor(x)), int(math.Floor(y))
	x1, y1 := x0+1, y0+1
	fx, fy := x-float64(x0), y-float64(y0)

	a00 := s.alpha(x0, y0)
	a10 := s.alpha(x1, y0)
	a01 := s.alpha(x0, y1)
	a11 := s.alpha(x1, y1)

	return (1-fx)*(1-fy)*a00 + fx*(1-fy)*a10 +
		(1-fx)*fy*a01 + fx*fy*a11
}

// SampleColor returns bilinear interpolated color at float coordinates.
func (s *SpriteImage) SampleColor(x, y float64) color.Color {
	if x < 0 || x >= float64(s.Width()) || y < 0 || y >= float64(s.Height()) {
		return color.RGBA{}
	}

	x0, y0 := int(math.Floor(x)), int(math.Floor(y))
	x1, y1 := x0+1, y0+1
	fx, fy := x-float64(x0), y-float64(y0)

	r00, g00, b00, a00 := s.rgbaAt(x0, y0)
	r10, g10, b10, a10 := s.rgbaAt(x1, y0)
	r01, g01, b01, a01 := s.rgbaAt(x0, y1)
	r11, g11, b11, a11 := s.rgbaAt(x1, y1)

	w00 := (1 - fx) * (1 - fy)
	w10 := fx * (1 - fy)
	w01 := (1 - fx) * fy
	w11 := fx * fy

	r := w00*r00 + w10*r10 + w01*r01 + w11*r11
	g := w00*g00 + w10*g10 + w01*g01 + w11*g11
	b := w00*b00 + w10*b10 + w01*b01 + w11*b11
	a := w00*a00 + w10*a10 + w01*a01 + w11*a11

	return color.RGBA{
		R: uint8(r * 255),
		G: uint8(g * 255),
		B: uint8(b * 255),
		A: uint8(a * 255),
	}
}
