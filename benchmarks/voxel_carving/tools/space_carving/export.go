package main

import (
	"bufio"
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

// ExportColoredPLY exports colored points as an ASCII PLY point cloud with RGB.
func ExportColoredPLY(points []ColoredPoint, path string) error {
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
	fmt.Fprintln(w, "property uchar red")
	fmt.Fprintln(w, "property uchar green")
	fmt.Fprintln(w, "property uchar blue")
	fmt.Fprintln(w, "end_header")

	for _, p := range points {
		fmt.Fprintf(w, "%f %f %f %d %d %d\n",
			p.Position.X, p.Position.Y, p.Position.Z,
			p.R, p.G, p.B)
	}

	return w.Flush()
}

// ExportMeshPLY exports colored voxels as a PLY mesh with cube geometry.
// Each voxel becomes a cube with 8 vertices and 6 quad faces.
func ExportMeshPLY(points []ColoredPoint, voxelSize float64, path string) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	w := bufio.NewWriter(file)

	numVoxels := len(points)
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

	half := voxelSize / 2.0

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

	for _, p := range points {
		for _, off := range offsets {
			fmt.Fprintf(w, "%f %f %f %d %d %d\n",
				p.Position.X+off[0],
				p.Position.Y+off[1],
				p.Position.Z+off[2],
				p.R, p.G, p.B)
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

	for voxelIdx := 0; voxelIdx < numVoxels; voxelIdx++ {
		baseVertex := voxelIdx * 8
		for _, face := range faceIndices {
			fmt.Fprintf(w, "4 %d %d %d %d\n",
				baseVertex+face[0],
				baseVertex+face[1],
				baseVertex+face[2],
				baseVertex+face[3])
		}
	}

	return w.Flush()
}
