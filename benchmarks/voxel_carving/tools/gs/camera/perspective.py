"""Perspective projection camera."""

from typing import Tuple

import numpy as np
import torch
from PIL import Image

from .base import Camera, compute_camera_position


class PerspectiveCamera(Camera):
    """Camera with perspective (pinhole) projection.

    In perspective projection, objects appear smaller as they get
    further from the camera, creating realistic depth perception.
    """

    def __init__(
        self,
        position: np.ndarray,
        camera_up: np.ndarray,
        camera_right: np.ndarray,
        width: int,
        height: int,
        image: Image.Image,
        fov_deg: float = 60.0,
        near: float = 0.1,
        far: float = 100.0,
    ):
        """Initialize perspective camera.

        Args:
            position: [3,] camera position in world coordinates
            camera_up: [3,] up vector in world coordinates
            camera_right: [3,] right vector in world coordinates
            width: image width in pixels
            height: image height in pixels
            image: PIL Image captured from this camera view
            fov_deg: vertical field of view in degrees
            near: near clipping plane distance
            far: far clipping plane distance
        """
        super().__init__(position, camera_up, camera_right, width, height, image)
        self.fov_deg = fov_deg
        self.near = near
        self.far = far

    @property
    def K(self) -> torch.Tensor:
        """3x3 intrinsic matrix for perspective projection."""
        if self._K is None:
            fov_rad = np.radians(self.fov_deg)
            fy = self.height / (2 * np.tan(fov_rad / 2))
            fx = fy  # Square pixels
            cx = self.width / 2.0
            cy = self.height / 2.0

            self._K = torch.tensor(
                [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=torch.float32
            )
        return self._K

    def project(self, points: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Project 3D points using perspective projection.

        Args:
            points: [N, 3] points in world coordinates

        Returns:
            proj_x: [N,] x pixel coordinates
            proj_y: [N,] y pixel coordinates
        """
        N = points.shape[0]
        device = points.device

        # Transform to camera coordinates
        viewmat = self.viewmat.to(device)
        points_homo = torch.cat([points, torch.ones(N, 1, device=device)], dim=1)
        cam_coords = (viewmat @ points_homo.T).T[:, :3]

        # Perspective divide (positive z is forward in camera space)
        z = cam_coords[:, 2].clamp(min=1e-6)

        # Apply intrinsic matrix with perspective divide
        K = self.K.to(device)
        fx, fy = K[0, 0], K[1, 1]
        cx, cy = K[0, 2], K[1, 2]

        proj_x = fx * cam_coords[:, 0] / z + cx
        proj_y = fy * cam_coords[:, 1] / z + cy

        return proj_x, proj_y

    @classmethod
    def from_angles(
        cls,
        yaw_deg: float,
        pitch_deg: float,
        camera_up: np.ndarray,
        camera_right: np.ndarray,
        image: Image.Image,
        distance: float = 5.0,
        width: int = 128,
        height: int = 128,
        fov_deg: float = 60.0,
        near: float = 0.1,
        far: float = 100.0,
    ) -> "PerspectiveCamera":
        """Create camera from yaw/pitch angles.

        Args:
            yaw_deg: yaw angle in degrees (0 = rear, 180 = front)
            pitch_deg: pitch angle in degrees (90 = below, -90 = above)
            camera_up: [3,] up vector
            camera_right: [3,] right vector
            image: PIL Image captured from this camera view
            distance: distance from origin
            width: image width in pixels
            height: image height in pixels
            fov_deg: vertical field of view in degrees
            near: near clipping plane distance
            far: far clipping plane distance

        Returns:
            PerspectiveCamera instance
        """
        position = compute_camera_position(yaw_deg, pitch_deg, distance)

        return cls(
            position=position,
            camera_up=np.asarray(camera_up, dtype=np.float32),
            camera_right=np.asarray(camera_right, dtype=np.float32),
            width=width,
            height=height,
            image=image,
            fov_deg=fov_deg,
            near=near,
            far=far,
        )
