package main

import "math"

// Camera represents an orthographic camera with view matrix and projection parameters.
type Camera struct {
	ViewMat Mat4
	Width   int
	Height  int
	Fx, Fy  float64 // Orthographic focal lengths
	Cx, Cy  float64 // Principal point (image center)
}

// NewCamera creates a camera from sprite parameters.
func NewCamera(yaw, pitch float64, up, right Vec3, width, height int, orthoScale, distance float64) *Camera {
	position := computePosition(yaw, pitch, distance)
	viewMat := buildViewMatrix(position, up, right)

	fx := float64(width) / (2 * orthoScale)
	fy := float64(height) / (2 * orthoScale)
	cx := float64(width) / 2.0
	cy := float64(height) / 2.0

	return &Camera{
		ViewMat: viewMat,
		Width:   width,
		Height:  height,
		Fx:      fx,
		Fy:      fy,
		Cx:      cx,
		Cy:      cy,
	}
}

// computePosition calculates camera position from yaw and pitch angles.
// Following SHIP_ANGLES.md conventions:
// - YAW 0 = rear (camera at -X), 180 = front (camera at +X)
// - PITCH 90 = below (camera at -Z), -90 = above (camera at +Z)
func computePosition(yawDeg, pitchDeg, distance float64) Vec3 {
	yaw := yawDeg * math.Pi / 180.0
	pitch := pitchDeg * math.Pi / 180.0

	return Vec3{
		X: -distance * math.Cos(yaw) * math.Cos(pitch),
		Y: distance * math.Sin(yaw) * math.Cos(pitch),
		Z: distance * math.Sin(pitch),
	}
}

// buildViewMatrix constructs the 4x4 world-to-camera view matrix.
// The camera looks at origin (0, 0, 0).
func buildViewMatrix(position, up, right Vec3) Mat4 {
	// Forward vector points from camera toward origin
	forward := position.Negate().Normalize()

	// Build view matrix: rows are right, up, forward in camera space
	var mat Mat4

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

// Project transforms a 3D world point to 2D image coordinates using orthographic projection.
func (c *Camera) Project(point Vec3) (x, y float64) {
	// Transform to camera space
	camCoords := c.ViewMat.MulVec3(point)

	// Orthographic projection
	x = c.Fx*camCoords.X + c.Cx
	y = c.Fy*camCoords.Y + c.Cy

	return x, y
}
