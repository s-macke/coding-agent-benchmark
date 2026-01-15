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

	writer := bufio.NewWriter(file)

	// Write header
	fmt.Fprintf(writer, "ply\n")
	fmt.Fprintf(writer, "format ascii 1.0\n")
	fmt.Fprintf(writer, "element vertex %d\n", len(points))
	fmt.Fprintf(writer, "property float x\n")
	fmt.Fprintf(writer, "property float y\n")
	fmt.Fprintf(writer, "property float z\n")
	fmt.Fprintf(writer, "end_header\n")

	// Write vertex data
	for _, p := range points {
		fmt.Fprintf(writer, "%f %f %f\n", p.X, p.Y, p.Z)
	}

	return writer.Flush()
}
