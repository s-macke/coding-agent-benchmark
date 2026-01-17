package main

import (
	"fmt"
	"math"

	"voxelcarve/common"
)

// Camera defines the interface for camera projection operations.
type Camera interface {
	Project(point common.Vec3) (x, y float64)
	ProjectWithDepth(point common.Vec3) (x, y, z float64)
	Mirror() Camera
	IsPerspective() bool
	Base() *CameraBase
}

// CameraBase contains shared data for all camera types.
type CameraBase struct {
	ViewMat  common.Mat4
	Width    int
	Height   int
	Fx, Fy   float64     // Focal lengths (pixels)
	Cx, Cy   float64     // Principal point (image center)
	Position common.Vec3 // Camera position (for mirroring)
	Up       common.Vec3 // Camera up vector (for mirroring)
	Right    common.Vec3 // Camera right vector (for mirroring)
}

// computePosition calculates camera position from yaw and pitch angles.
// YAW 0 = rear (camera at -X), 180 = front (camera at +X)
// PITCH 90 = below (camera at -Z), -90 = above (camera at +Z)
func computePosition(yawDeg, pitchDeg, distance float64) common.Vec3 {
	yaw := yawDeg * math.Pi / 180.0
	pitch := pitchDeg * math.Pi / 180.0
	cosPitch := math.Cos(pitch)

	return common.Vec3{
		X: -distance * math.Cos(yaw) * cosPitch,
		Y: distance * math.Sin(yaw) * cosPitch,
		Z: distance * math.Sin(pitch),
	}
}

// validateOrthogonalBasis checks that right, up, and forward vectors form an orthonormal basis.
// Panics if vectors are not mutually perpendicular or not unit length.
func validateOrthogonalBasis(right, up, forward common.Vec3) {
	const epsilon = 1e-6

	// Check unit length
	if d := math.Abs(right.Length() - 1.0); d > epsilon {
		panic(fmt.Sprintf("camera basis not normalized: |right| = %v", right.Length()))
	}
	if d := math.Abs(up.Length() - 1.0); d > epsilon {
		panic(fmt.Sprintf("camera basis not normalized: |up| = %v", up.Length()))
	}
	if d := math.Abs(forward.Length() - 1.0); d > epsilon {
		panic(fmt.Sprintf("camera basis not normalized: |forward| = %v", forward.Length()))
	}

	// Check orthogonality
	if d := math.Abs(right.Dot(up)); d > epsilon {
		panic(fmt.Sprintf("camera basis not orthogonal: right·up = %v", d))
	}
	if d := math.Abs(right.Dot(forward)); d > epsilon {
		panic(fmt.Sprintf("camera basis not orthogonal: right·forward = %v", d))
	}
	if d := math.Abs(up.Dot(forward)); d > epsilon {
		panic(fmt.Sprintf("camera basis not orthogonal: up·forward = %v", d))
	}
}

// buildViewMatrix constructs the 4x4 world-to-camera view matrix.
// The camera looks at origin (0, 0, 0).
func buildViewMatrix(position, up, right common.Vec3) common.Mat4 {
	// Forward vector points from camera toward origin
	forward := position.Negate().Normalize()
	validateOrthogonalBasis(right, up, forward)

	// Build view matrix: rows are right, up, forward in camera space
	var mat common.Mat4

	// Row 0: right
	mat[0] = right.X
	mat[1] = right.Y
	mat[2] = right.Z
	mat[3] = -right.Dot(position)

	// Row 1: up
	mat[4] = up.X
	mat[5] = up.Y
	mat[6] = up.Z
	mat[7] = -up.Dot(position)

	// Row 2: forward
	mat[8] = forward.X
	mat[9] = forward.Y
	mat[10] = forward.Z
	mat[11] = -forward.Dot(position)

	// Row 3: homogeneous
	mat[12] = 0
	mat[13] = 0
	mat[14] = 0
	mat[15] = 1

	return mat
}
