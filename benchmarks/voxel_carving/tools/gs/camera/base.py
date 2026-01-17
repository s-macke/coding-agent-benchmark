"""Abstract base class for cameras."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np
import torch


class Camera(ABC):
    """Abstract base class for cameras.

    All camera types share a view matrix (world-to-camera transform)
    but differ in their intrinsic matrix and projection method.
    """

    def __init__(
        self,
        position: np.ndarray,
        camera_up: np.ndarray,
        camera_right: np.ndarray,
        width: int,
        height: int,
    ):
        """Initialize camera with position and orientation.

        Args:
            position: [3,] camera position in world coordinates
            camera_up: [3,] up vector in world coordinates
            camera_right: [3,] right vector in world coordinates
            width: image width in pixels
            height: image height in pixels
        """
        self.position = np.asarray(position, dtype=np.float32)
        self.camera_up = np.asarray(camera_up, dtype=np.float32)
        self.camera_right = np.asarray(camera_right, dtype=np.float32)
        self.width = width
        self.height = height

        # Cached matrices (lazy computed)
        self._viewmat: Optional[torch.Tensor] = None
        self._K: Optional[torch.Tensor] = None

    @property
    def viewmat(self) -> torch.Tensor:
        """4x4 world-to-camera view matrix.

        The camera looks at the origin (0, 0, 0).
        Uses +Z as forward direction in camera space (gsplat convention).
        """
        if self._viewmat is None:
            self._viewmat = self._build_view_matrix()
        return self._viewmat

    @property
    @abstractmethod
    def K(self) -> torch.Tensor:
        """3x3 intrinsic matrix (camera-type specific)."""
        pass

    @abstractmethod
    def project(self, points: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Project 3D world points to 2D pixel coordinates.

        Args:
            points: [N, 3] points in world coordinates

        Returns:
            proj_x: [N,] x pixel coordinates
            proj_y: [N,] y pixel coordinates
        """
        pass

    def _build_view_matrix(self) -> torch.Tensor:
        """Build 4x4 world-to-camera view matrix."""
        forward = -self.position / np.linalg.norm(self.position)
        up = self.camera_up
        right = self.camera_right

        # Rows are: right (X), up (Y), forward (Z) in camera space
        rotation = np.stack([right, up, forward], axis=0)

        viewmat = np.eye(4, dtype=np.float32)
        viewmat[:3, :3] = rotation
        viewmat[:3, 3] = -rotation @ self.position

        return torch.from_numpy(viewmat)

    def _invalidate_cache(self) -> None:
        """Invalidate cached matrices when parameters change."""
        self._viewmat = None
        self._K = None


def compute_camera_position(
    yaw_deg: float, pitch_deg: float, distance: float = 5.0
) -> np.ndarray:
    """Compute camera position from yaw and pitch angles.

    Following SHIP_ANGLES.md conventions:
    - YAW 0 = rear (camera at -X), 180 = front (camera at +X)
    - PITCH 90 = below (camera at -Z), -90 = above (camera at +Z)

    Args:
        yaw_deg: yaw angle in degrees
        pitch_deg: pitch angle in degrees
        distance: distance from origin

    Returns:
        [3,] camera position in world coordinates
    """
    yaw_rad = np.radians(yaw_deg)
    pitch_rad = np.radians(pitch_deg)

    cam_x = -distance * np.cos(yaw_rad) * np.cos(pitch_rad)
    cam_y = distance * np.sin(yaw_rad) * np.cos(pitch_rad)
    cam_z = distance * np.sin(pitch_rad)

    return np.array([cam_x, cam_y, cam_z], dtype=np.float32)
