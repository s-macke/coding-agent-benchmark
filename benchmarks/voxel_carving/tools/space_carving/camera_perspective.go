package main

import "math"

// PerspectiveCamera implements perspective projection.
type PerspectiveCamera struct {
	CameraBase
}

// NewPerspectiveCamera creates a perspective camera from sprite parameters.
// fovYDeg is the vertical field of view in degrees.
func NewPerspectiveCamera(yaw, pitch float64, up, right Vec3, width, height int, fovYDeg, distance float64) *PerspectiveCamera {
	position := computePosition(yaw, pitch, distance)
	viewMat := buildViewMatrix(position, up, right)

	// Compute focal length from vertical FOV: fy = (height/2) / tan(fovY/2)
	fovYRad := fovYDeg * math.Pi / 180.0
	fy := float64(height) / (2 * math.Tan(fovYRad/2))
	fx := fy // Square pixels
	cx := float64(width) / 2.0
	cy := float64(height) / 2.0

	return &PerspectiveCamera{
		CameraBase: CameraBase{
			ViewMat:  viewMat,
			Width:    width,
			Height:   height,
			Fx:       fx,
			Fy:       fy,
			Cx:       cx,
			Cy:       cy,
			Position: position,
			Up:       up,
			Right:    right,
		},
	}
}

// Project transforms a 3D world point to 2D image coordinates.
func (c *PerspectiveCamera) Project(point Vec3) (x, y float64) {
	x, y, _ = c.ProjectWithDepth(point)
	return x, y
}

// ProjectWithDepth transforms a 3D world point to 2D image coordinates and returns depth.
func (c *PerspectiveCamera) ProjectWithDepth(point Vec3) (x, y, z float64) {
	camCoords := c.ViewMat.MulVec3(point)
	z = camCoords.Z

	if z > 0 {
		x = c.Fx*(camCoords.X/z) + c.Cx
		y = c.Fy*(camCoords.Y/z) + c.Cy
	} else {
		// Point behind camera
		x = -1
		y = -1
	}

	return x, y, z
}

// Mirror creates a new camera mirrored across the Y=0 plane.
func (c *PerspectiveCamera) Mirror() Camera {
	mirroredPos := Vec3{c.Position.X, -c.Position.Y, c.Position.Z}
	mirroredUp := Vec3{c.Up.X, -c.Up.Y, c.Up.Z}
	mirroredRight := Vec3{-c.Right.X, c.Right.Y, -c.Right.Z}

	return &PerspectiveCamera{
		CameraBase: CameraBase{
			ViewMat:  buildViewMatrix(mirroredPos, mirroredUp, mirroredRight),
			Width:    c.Width,
			Height:   c.Height,
			Fx:       c.Fx,
			Fy:       c.Fy,
			Cx:       c.Cx,
			Cy:       c.Cy,
			Position: mirroredPos,
			Up:       mirroredUp,
			Right:    mirroredRight,
		},
	}
}

// IsPerspective returns true for perspective cameras.
func (c *PerspectiveCamera) IsPerspective() bool {
	return true
}

// Base returns the underlying CameraBase.
func (c *PerspectiveCamera) Base() *CameraBase {
	return &c.CameraBase
}
