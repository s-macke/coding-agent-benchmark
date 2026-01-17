package export

import (
	"sort"
)

// RGB represents a color with 8-bit channels.
type RGB struct {
	R, G, B uint8
}

// ColorPalette holds a quantized palette and mappings from original colors.
type ColorPalette struct {
	Colors  []RGB            // The palette colors (max 255)
	Mapping map[uint32]uint8 // Original color key -> palette index (1-based)
}

// PackRGB packs RGB values into a uint32 key.
func PackRGB(r, g, b uint8) uint32 {
	return uint32(r)<<16 | uint32(g)<<8 | uint32(b)
}

// colorEntry holds a color and its frequency.
type colorEntry struct {
	color RGB
	count int
}

// colorBucket is a group of colors for median cut.
type colorBucket struct {
	entries []colorEntry
}

// rangeAxis returns the range (max-min) for each color channel.
func (b *colorBucket) rangeAxis() (rRange, gRange, bRange int) {
	if len(b.entries) == 0 {
		return 0, 0, 0
	}
	minR, maxR := int(b.entries[0].color.R), int(b.entries[0].color.R)
	minG, maxG := int(b.entries[0].color.G), int(b.entries[0].color.G)
	minB, maxB := int(b.entries[0].color.B), int(b.entries[0].color.B)

	for _, e := range b.entries[1:] {
		r, g, bb := int(e.color.R), int(e.color.G), int(e.color.B)
		if r < minR {
			minR = r
		}
		if r > maxR {
			maxR = r
		}
		if g < minG {
			minG = g
		}
		if g > maxG {
			maxG = g
		}
		if bb < minB {
			minB = bb
		}
		if bb > maxB {
			maxB = bb
		}
	}
	return maxR - minR, maxG - minG, maxB - minB
}

// longestAxis returns 0 for R, 1 for G, 2 for B.
func (b *colorBucket) longestAxis() int {
	rr, gr, br := b.rangeAxis()
	if rr >= gr && rr >= br {
		return 0
	}
	if gr >= br {
		return 1
	}
	return 2
}

// average returns the weighted average color of the bucket.
func (b *colorBucket) average() RGB {
	if len(b.entries) == 0 {
		return RGB{}
	}
	var sumR, sumG, sumB, totalCount int
	for _, e := range b.entries {
		sumR += int(e.color.R) * e.count
		sumG += int(e.color.G) * e.count
		sumB += int(e.color.B) * e.count
		totalCount += e.count
	}
	if totalCount == 0 {
		totalCount = 1
	}
	return RGB{
		R: uint8(sumR / totalCount),
		G: uint8(sumG / totalCount),
		B: uint8(sumB / totalCount),
	}
}

// split divides the bucket at the median of the longest axis.
func (b *colorBucket) split() (*colorBucket, *colorBucket) {
	if len(b.entries) <= 1 {
		return b, nil
	}

	axis := b.longestAxis()

	// Sort by the longest axis
	sort.Slice(b.entries, func(i, j int) bool {
		switch axis {
		case 0:
			return b.entries[i].color.R < b.entries[j].color.R
		case 1:
			return b.entries[i].color.G < b.entries[j].color.G
		default:
			return b.entries[i].color.B < b.entries[j].color.B
		}
	})

	// Find median by count
	totalCount := 0
	for _, e := range b.entries {
		totalCount += e.count
	}

	halfCount := totalCount / 2
	cumCount := 0
	splitIdx := len(b.entries) / 2 // fallback

	for i, e := range b.entries {
		cumCount += e.count
		if cumCount >= halfCount {
			splitIdx = i + 1
			break
		}
	}

	// Ensure we don't create empty buckets
	if splitIdx == 0 {
		splitIdx = 1
	}
	if splitIdx >= len(b.entries) {
		splitIdx = len(b.entries) - 1
	}

	left := &colorBucket{entries: b.entries[:splitIdx]}
	right := &colorBucket{entries: b.entries[splitIdx:]}
	return left, right
}

// colorDistance returns squared Euclidean distance between two colors.
func colorDistance(a, b RGB) int {
	dr := int(a.R) - int(b.R)
	dg := int(a.G) - int(b.G)
	db := int(a.B) - int(b.B)
	return dr*dr + dg*dg + db*db
}

// nearestPaletteIndex finds the closest color in the palette.
func nearestPaletteIndex(color RGB, palette []RGB) uint8 {
	bestIdx := 0
	bestDist := colorDistance(color, palette[0])

	for i := 1; i < len(palette); i++ {
		d := colorDistance(color, palette[i])
		if d < bestDist {
			bestDist = d
			bestIdx = i
		}
	}
	return uint8(bestIdx + 1) // 1-based index for .vox format
}

// BuildPalette creates a color palette from a map of colors.
// If there are more than 255 unique colors, it uses median cut quantization.
func BuildPalette(colors map[uint32]int) *ColorPalette {
	if len(colors) == 0 {
		return &ColorPalette{
			Colors:  []RGB{},
			Mapping: make(map[uint32]uint8),
		}
	}

	// Convert map to entries
	entries := make([]colorEntry, 0, len(colors))
	for key, count := range colors {
		r := uint8((key >> 16) & 0xFF)
		g := uint8((key >> 8) & 0xFF)
		b := uint8(key & 0xFF)
		entries = append(entries, colorEntry{
			color: RGB{R: r, G: g, B: b},
			count: count,
		})
	}

	var palette []RGB
	mapping := make(map[uint32]uint8)

	if len(entries) <= 255 {
		// No quantization needed - use colors directly
		palette = make([]RGB, len(entries))
		for i, e := range entries {
			palette[i] = e.color
			key := PackRGB(e.color.R, e.color.G, e.color.B)
			mapping[key] = uint8(i + 1) // 1-based index
		}
	} else {
		// Median cut quantization
		buckets := []*colorBucket{{entries: entries}}

		// Split until we have 255 buckets
		for len(buckets) < 255 {
			// Find bucket with largest range to split
			bestIdx := 0
			bestRange := 0
			for i, bucket := range buckets {
				if len(bucket.entries) <= 1 {
					continue
				}
				rr, gr, br := bucket.rangeAxis()
				maxRange := rr
				if gr > maxRange {
					maxRange = gr
				}
				if br > maxRange {
					maxRange = br
				}
				if maxRange > bestRange {
					bestRange = maxRange
					bestIdx = i
				}
			}

			if bestRange == 0 {
				break // No more splittable buckets
			}

			// Split the chosen bucket
			left, right := buckets[bestIdx].split()
			if right == nil {
				break
			}

			buckets[bestIdx] = left
			buckets = append(buckets, right)
		}

		// Create palette from bucket averages
		palette = make([]RGB, len(buckets))
		for i, bucket := range buckets {
			palette[i] = bucket.average()
		}

		// Map original colors to nearest palette entry
		for key := range colors {
			r := uint8((key >> 16) & 0xFF)
			g := uint8((key >> 8) & 0xFF)
			b := uint8(key & 0xFF)
			mapping[key] = nearestPaletteIndex(RGB{R: r, G: g, B: b}, palette)
		}
	}

	return &ColorPalette{
		Colors:  palette,
		Mapping: mapping,
	}
}

// GetIndex returns the palette index for a color (1-based).
func (p *ColorPalette) GetIndex(r, g, b uint8) uint8 {
	key := PackRGB(r, g, b)
	return p.Mapping[key]
}

// ToRGBA returns the palette as RGBA values for .vox export.
func (p *ColorPalette) ToRGBA() [][4]uint8 {
	result := make([][4]uint8, len(p.Colors))
	for i, c := range p.Colors {
		result[i] = [4]uint8{c.R, c.G, c.B, 255}
	}
	return result
}
