package main

import "voxelcarve/common"

// OrthographicCamera implements orthographic (parallel) projection.
type OrthographicCamera struct {
	CameraBase
}

// NewOrthographicCamera creates an orthographic camera from sprite parameters.
func NewOrthographicCamera(yaw, pitch float64, up, right common.Vec3, width, height int, orthoScale, distance float64) *OrthographicCamera {
	position := computePosition(yaw, pitch, distance)
	viewMat := buildViewMatrix(position, up, right)

	fx := float64(width) / (2 * orthoScale)
	fy := float64(height) / (2 * orthoScale)
	cx := float64(width) / 2.0
	cy := float64(height) / 2.0

	return &OrthographicCamera{
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
func (c *OrthographicCamera) Project(point common.Vec3) (x, y float64) {
	x, y, _ = c.ProjectWithDepth(point)
	return x, y
}

// ProjectWithDepth transforms a 3D world point to 2D image coordinates and returns depth.
func (c *OrthographicCamera) ProjectWithDepth(point common.Vec3) (x, y, z float64) {
	camCoords := c.ViewMat.MulVec3(point)
	z = camCoords.Z

	x = c.Fx*camCoords.X + c.Cx
	y = c.Fy*camCoords.Y + c.Cy

	return x, y, z
}

// Mirror creates a new camera mirrored across the Y=0 plane.
func (c *OrthographicCamera) Mirror() Camera {
	mirroredPos := common.Vec3{c.Position.X, -c.Position.Y, c.Position.Z}
	mirroredUp := common.Vec3{c.Up.X, -c.Up.Y, c.Up.Z}
	mirroredRight := common.Vec3{-c.Right.X, c.Right.Y, -c.Right.Z}

	return &OrthographicCamera{
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

// IsPerspective returns false for orthographic cameras.
func (c *OrthographicCamera) IsPerspective() bool {
	return false
}

// Base returns the underlying CameraBase.
func (c *OrthographicCamera) Base() *CameraBase {
	return &c.CameraBase
}
