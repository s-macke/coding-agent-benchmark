package export

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"fmt"
	"os"

	"voxelcarve/voxelgrid"
)

// ExportVOX exports colored voxels as a MagicaVoxel .vox file.
func ExportVOX(grid *voxelgrid.VoxelGrid, path string) error {
	if grid.Resolution > 256 {
		return fmt.Errorf("grid resolution %d exceeds .vox maximum of 256", grid.Resolution)
	}

	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	w := bufio.NewWriter(file)

	// First pass: collect all colors and their frequencies
	colorFreq := make(map[uint32]int)
	type voxelPos struct {
		x, y, z uint8
		r, g, b uint8
	}
	var voxelPositions []voxelPos

	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				v := grid.GetVoxel(ix, iy, iz)
				if v.Opacity <= 0.5 || !grid.IsSurface(ix, iy, iz) {
					continue
				}

				r, g, b, _ := v.Color().RGBA()
				colorKey := PackRGB(uint8(r), uint8(g), uint8(b))
				colorFreq[colorKey]++

				voxelPositions = append(voxelPositions, voxelPos{
					x: uint8(ix), y: uint8(iy), z: uint8(iz),
					r: uint8(r), g: uint8(g), b: uint8(b),
				})
			}
		}
	}

	// Build palette (with quantization if needed)
	pal := BuildPalette(colorFreq)

	// Second pass: assign voxels to palette indices
	type voxelData struct {
		x, y, z    uint8
		colorIndex uint8
	}
	voxels := make([]voxelData, len(voxelPositions))
	for i, vp := range voxelPositions {
		voxels[i] = voxelData{
			x:          vp.x,
			y:          vp.y,
			z:          vp.z,
			colorIndex: pal.GetIndex(vp.r, vp.g, vp.b),
		}
	}

	palette := pal.ToRGBA()

	// Build SIZE chunk content
	sizeContent := new(bytes.Buffer)
	binary.Write(sizeContent, binary.LittleEndian, int32(grid.Resolution))
	binary.Write(sizeContent, binary.LittleEndian, int32(grid.Resolution))
	binary.Write(sizeContent, binary.LittleEndian, int32(grid.Resolution))

	// Build XYZI chunk content
	xyziContent := new(bytes.Buffer)
	binary.Write(xyziContent, binary.LittleEndian, int32(len(voxels)))
	for _, v := range voxels {
		xyziContent.Write([]byte{v.x, v.y, v.z, v.colorIndex})
	}

	// Build RGBA chunk content (256 colors × 4 bytes)
	rgbaContent := new(bytes.Buffer)
	for i := 0; i < 256; i++ {
		if i < len(palette) {
			rgbaContent.Write(palette[i][:])
		} else {
			rgbaContent.Write([]byte{0, 0, 0, 255}) // Default unused colors
		}
	}

	// Calculate MAIN chunk children size
	childrenSize := 12 + sizeContent.Len() + 12 + xyziContent.Len() + 12 + rgbaContent.Len()

	// Write file header
	w.Write([]byte("VOX "))
	binary.Write(w, binary.LittleEndian, int32(150)) // Version

	// Write MAIN chunk header
	w.Write([]byte("MAIN"))
	binary.Write(w, binary.LittleEndian, int32(0))            // Content size (0 for MAIN)
	binary.Write(w, binary.LittleEndian, int32(childrenSize)) // Children size

	// Write SIZE chunk
	w.Write([]byte("SIZE"))
	binary.Write(w, binary.LittleEndian, int32(sizeContent.Len()))
	binary.Write(w, binary.LittleEndian, int32(0))
	w.Write(sizeContent.Bytes())

	// Write XYZI chunk
	w.Write([]byte("XYZI"))
	binary.Write(w, binary.LittleEndian, int32(xyziContent.Len()))
	binary.Write(w, binary.LittleEndian, int32(0))
	w.Write(xyziContent.Bytes())

	// Write RGBA chunk
	w.Write([]byte("RGBA"))
	binary.Write(w, binary.LittleEndian, int32(rgbaContent.Len()))
	binary.Write(w, binary.LittleEndian, int32(0))
	w.Write(rgbaContent.Bytes())

	return w.Flush()
}
