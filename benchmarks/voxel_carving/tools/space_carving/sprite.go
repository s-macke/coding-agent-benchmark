package main

import (
	"encoding/json"
	"os"
)

// Sprite represents metadata for a single sprite view.
type Sprite struct {
	Block       int        `json:"block"`
	Row         *int       `json:"row"` // nullable for special views
	Yaw         float64    `json:"yaw"`
	Pitch       float64    `json:"pitch"`
	Width       int        `json:"width"`
	Height      int        `json:"height"`
	X           int        `json:"x"`
	Y           int        `json:"y"`
	Filename    string     `json:"filename"`
	Type        string     `json:"type,omitempty"`
	CameraUp    [3]float64 `json:"camera_up"`
	CameraRight [3]float64 `json:"camera_right"`
}

// SpriteFile represents the root JSON structure.
type SpriteFile struct {
	Sprites []Sprite `json:"sprites"`
}

// LoadSprites loads sprite metadata from a JSON file.
func LoadSprites(jsonPath string) ([]Sprite, error) {
	data, err := os.ReadFile(jsonPath)
	if err != nil {
		return nil, err
	}

	var file SpriteFile
	if err := json.Unmarshal(data, &file); err != nil {
		return nil, err
	}

	return file.Sprites, nil
}

// CameraUpVec returns the camera up vector as Vec3.
func (s *Sprite) CameraUpVec() Vec3 {
	return Vec3{s.CameraUp[0], s.CameraUp[1], s.CameraUp[2]}
}

// CameraRightVec returns the camera right vector as Vec3.
func (s *Sprite) CameraRightVec() Vec3 {
	return Vec3{s.CameraRight[0], s.CameraRight[1], s.CameraRight[2]}
}
