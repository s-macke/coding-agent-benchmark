"""Orthographic projection camera."""

from typing import Tuple

import numpy as np
import torch
from PIL import Image

from .base import Camera, compute_camera_position


class OrthographicCamera(Camera):
    """Camera with orthographic (parallel) projection.

    In orthographic projection, objects appear the same size regardless
    of distance from the camera. This is useful for sprite rendering
    where perspective distortion is undesirable.
    """

    def __init__(
        self,
        position: np.ndarray,
        camera_up: np.ndarray,
        camera_right: np.ndarray,
        width: int,
        height: int,
        image: Image.Image,
        ortho_scale: float = 2.0,
    ):
        """Initialize orthographic camera.

        Args:
            position: [3,] camera position in world coordinates
            camera_up: [3,] up vector in world coordinates
            camera_right: [3,] right vector in world coordinates
            width: image width in pixels
            height: image height in pixels
            image: PIL Image captured from this camera view
            ortho_scale: world units visible in half the image
        """
        super().__init__(position, camera_up, camera_right, width, height, image)
        self.ortho_scale = ortho_scale

    @property
    def K(self) -> torch.Tensor:
        """3x3 intrinsic matrix for orthographic projection."""
        if self._K is None:
            fx = self.width / (2 * self.ortho_scale)
            fy = self.height / (2 * self.ortho_scale)
            cx = self.width / 2.0
            cy = self.height / 2.0

            self._K = torch.tensor(
                [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=torch.float32
            )
        return self._K

    def project(self, points: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Project 3D points using orthographic projection.

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

        # Apply intrinsic matrix (orthographic: ignore depth)
        K = self.K.to(device)
        fx, fy = K[0, 0], K[1, 1]
        cx, cy = K[0, 2], K[1, 2]

        proj_x = fx * cam_coords[:, 0] + cx
        proj_y = fy * cam_coords[:, 1] + cy

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
        ortho_scale: float = 2.0,
    ) -> "OrthographicCamera":
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
            ortho_scale: world units visible in half the image

        Returns:
            OrthographicCamera instance
        """
        position = compute_camera_position(yaw_deg, pitch_deg, distance)

        return cls(
            position=position,
            camera_up=np.asarray(camera_up, dtype=np.float32),
            camera_right=np.asarray(camera_right, dtype=np.float32),
            width=width,
            height=height,
            image=image,
            ortho_scale=ortho_scale,
        )
