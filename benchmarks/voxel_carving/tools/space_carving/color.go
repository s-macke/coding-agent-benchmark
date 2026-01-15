package main

// Color represents an RGBA color with float64 components in 0-1 range.
type Color struct {
	R, G, B, A float64
}

// RGBA returns the color components scaled to 0-255 range as uint8.
func (c Color) RGBA() (r, g, b, a uint8) {
	return uint8(c.R * 255), uint8(c.G * 255), uint8(c.B * 255), uint8(c.A * 255)
}
