package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
)

// ExportPLY exports occupied voxel centers as an ASCII PLY point cloud.
func ExportPLY(points []Vec3, path string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	w := bufio.NewWriter(file)

	fmt.Fprintln(w, "ply")
	fmt.Fprintln(w, "format ascii 1.0")
	fmt.Fprintf(w, "element vertex %d\n", len(points))
	fmt.Fprintln(w, "property float x")
	fmt.Fprintln(w, "property float y")
	fmt.Fprintln(w, "property float z")
	fmt.Fprintln(w, "end_header")

	for _, p := range points {
		fmt.Fprintf(w, "%f %f %f\n", p.X, p.Y, p.Z)
	}

	return w.Flush()
}

// ExportColoredPLY exports colored voxels from grid as an ASCII PLY point cloud with RGB.
func ExportColoredPLY(grid *VoxelGrid, path string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	w := bufio.NewWriter(file)

	count := grid.SurfaceCount()

	fmt.Fprintln(w, "ply")
	fmt.Fprintln(w, "format ascii 1.0")
	fmt.Fprintf(w, "element vertex %d\n", count)
	fmt.Fprintln(w, "property float x")
	fmt.Fprintln(w, "property float y")
	fmt.Fprintln(w, "property float z")
	fmt.Fprintln(w, "property uchar red")
	fmt.Fprintln(w, "property uchar green")
	fmt.Fprintln(w, "property uchar blue")
	fmt.Fprintln(w, "end_header")

	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				v := grid.GetVoxel(ix, iy, iz)
				if v.Opacity <= 0.5 || !grid.IsSurface(ix, iy, iz) {
					continue
				}
				pos := grid.Position(ix, iy, iz)
				r, g, b, _ := v.Color().RGBA()
				fmt.Fprintf(w, "%f %f %f %d %d %d\n",
					pos.X, pos.Y, pos.Z, r, g, b)
			}
		}
	}

	return w.Flush()
}

// ExportMeshPLY exports colored voxels as a PLY mesh with cube geometry.
// Each voxel becomes a cube with 8 vertices and 6 quad faces.
func ExportMeshPLY(grid *VoxelGrid, path string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	w := bufio.NewWriter(file)

	numVoxels := grid.SurfaceCount()
	numVertices := numVoxels * 8
	numFaces := numVoxels * 6

	fmt.Fprintln(w, "ply")
	fmt.Fprintln(w, "format ascii 1.0")
	fmt.Fprintf(w, "element vertex %d\n", numVertices)
	fmt.Fprintln(w, "property float x")
	fmt.Fprintln(w, "property float y")
	fmt.Fprintln(w, "property float z")
	fmt.Fprintln(w, "property uchar red")
	fmt.Fprintln(w, "property uchar green")
	fmt.Fprintln(w, "property uchar blue")
	fmt.Fprintf(w, "element face %d\n", numFaces)
	fmt.Fprintln(w, "property list uchar int vertex_indices")
	fmt.Fprintln(w, "end_header")

	half := grid.VoxelSize() / 2.0

	// Cube corner offsets relative to center (ordered for consistent face winding)
	offsets := [8][3]float64{
		{-half, -half, -half}, // 0: back-left-bottom
		{+half, -half, -half}, // 1: back-right-bottom
		{+half, +half, -half}, // 2: front-right-bottom
		{-half, +half, -half}, // 3: front-left-bottom
		{-half, -half, +half}, // 4: back-left-top
		{+half, -half, +half}, // 5: back-right-top
		{+half, +half, +half}, // 6: front-right-top
		{-half, +half, +half}, // 7: front-left-top
	}

	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				v := grid.GetVoxel(ix, iy, iz)
				if v.Opacity <= 0.5 || !grid.IsSurface(ix, iy, iz) {
					continue
				}
				pos := grid.Position(ix, iy, iz)
				r, g, b, _ := v.Color().RGBA()
				for _, off := range offsets {
					fmt.Fprintf(w, "%f %f %f %d %d %d\n",
						pos.X+off[0],
						pos.Y+off[1],
						pos.Z+off[2],
						r, g, b)
				}
			}
		}
	}

	// Face definitions: 6 quads per cube, CCW winding for outward normals
	faceIndices := [6][4]int{
		{0, 3, 2, 1}, // bottom (-Z)
		{4, 5, 6, 7}, // top (+Z)
		{0, 1, 5, 4}, // back (-Y)
		{2, 3, 7, 6}, // front (+Y)
		{0, 4, 7, 3}, // left (-X)
		{1, 2, 6, 5}, // right (+X)
	}

	voxelIdx := 0
	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				if grid.Get(ix, iy, iz) <= 0.5 || !grid.IsSurface(ix, iy, iz) {
					continue
				}
				baseVertex := voxelIdx * 8
				for _, face := range faceIndices {
					fmt.Fprintf(w, "4 %d %d %d %d\n",
						baseVertex+face[0],
						baseVertex+face[1],
						baseVertex+face[2],
						baseVertex+face[3])
				}
				voxelIdx++
			}
		}
	}

	return w.Flush()
}

// ExportVOX exports colored voxels as a MagicaVoxel .vox file.
func ExportVOX(grid *VoxelGrid, path string) error {
	if grid.Resolution > 256 {
		return fmt.Errorf("grid resolution %d exceeds .vox maximum of 256", grid.Resolution)
	}

	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	w := bufio.NewWriter(file)

	// Collect surface voxels and build color palette
	type voxelData struct {
		x, y, z    uint8
		colorIndex uint8
	}
	var voxels []voxelData
	colorToIndex := make(map[uint32]uint8) // RGB packed -> palette index
	var palette [][4]uint8                 // RGBA values
	nextIndex := uint8(1)                  // Index 0 is reserved (empty)

	for ix := 0; ix < grid.Resolution; ix++ {
		for iy := 0; iy < grid.Resolution; iy++ {
			for iz := 0; iz < grid.Resolution; iz++ {
				v := grid.GetVoxel(ix, iy, iz)
				if v.Opacity <= 0.5 || !grid.IsSurface(ix, iy, iz) {
					continue
				}

				r, g, b, _ := v.Color().RGBA()
				colorKey := uint32(r)<<16 | uint32(g)<<8 | uint32(b)

				idx, exists := colorToIndex[colorKey]
				if !exists {
					if nextIndex == 0 { // Wrapped around, too many colors
						return fmt.Errorf("too many unique colors (>255)")
					}
					idx = nextIndex
					colorToIndex[colorKey] = idx
					palette = append(palette, [4]uint8{uint8(r), uint8(g), uint8(b), 255})
					nextIndex++
				}

				voxels = append(voxels, voxelData{
					x:          uint8(ix),
					y:          uint8(iy),
					z:          uint8(iz),
					colorIndex: idx,
				})
			}
		}
	}

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
