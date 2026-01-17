"""Camera module for Gaussian splatting.

This module provides camera classes for different projection types:
- OrthographicCamera: parallel projection (no perspective distortion)
- PerspectiveCamera: pinhole camera model with perspective

Example usage:
    from gs.camera import OrthographicCamera, CameraCollection

    # Single camera
    cam = OrthographicCamera.from_angles(yaw_deg=0, pitch_deg=0,
                                         camera_up=[0,0,1], camera_right=[0,1,0])
    proj_x, proj_y = cam.project(points)

    # Multiple cameras from metadata
    cameras = CameraCollection.from_metadata(sprite_metadata)
    for camera in cameras:
        proj_x, proj_y = camera.project(points)
"""

from .base import Camera, compute_camera_position
from .orthographic import OrthographicCamera
from .perspective import PerspectiveCamera
from .collection import CameraCollection, CameraType

__all__ = [
    "Camera",
    "OrthographicCamera",
    "PerspectiveCamera",
    "CameraCollection",
    "CameraType",
    "compute_camera_position",
]
