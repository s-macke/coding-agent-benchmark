"""Camera collection for batch operations."""

from typing import Iterator, List, Literal, Optional, Tuple

import torch

from .base import Camera
from .orthographic import OrthographicCamera
from .perspective import PerspectiveCamera
from ..constants import IMAGE_SIZE

CameraType = Literal["orthographic", "perspective"]


class CameraCollection:
    """Collection of cameras with tensor conversion for batch rendering.

    Provides iteration over individual cameras while also supporting
    conversion to stacked tensor format for batch operations like gsplat.
    """

    def __init__(self, cameras: List[Camera]):
        """Initialize collection from list of cameras.

        Args:
            cameras: list of Camera objects
        """
        self._cameras = cameras
        self._viewmats: Optional[torch.Tensor] = None
        self._camtoworlds: Optional[torch.Tensor] = None
        self._Ks: Optional[torch.Tensor] = None

    def __len__(self) -> int:
        """Return number of cameras."""
        return len(self._cameras)

    def __getitem__(self, index: int) -> Camera:
        """Get camera by index."""
        return self._cameras[index]

    def __iter__(self) -> Iterator[Camera]:
        """Iterate over cameras."""
        return iter(self._cameras)

    @property
    def viewmats(self) -> torch.Tensor:
        """[C, 4, 4] stacked view matrices (world-to-camera)."""
        if self._viewmats is None:
            self._viewmats = torch.stack([c.viewmat for c in self._cameras])
        return self._viewmats

    @property
    def camtoworlds(self) -> torch.Tensor:
        """[C, 4, 4] stacked camera-to-world matrices (inverse of viewmats)."""
        if self._camtoworlds is None:
            self._camtoworlds = torch.linalg.inv(self.viewmats)
        return self._camtoworlds

    @property
    def Ks(self) -> torch.Tensor:
        """[C, 3, 3] stacked intrinsic matrices."""
        if self._Ks is None:
            self._Ks = torch.stack([c.K for c in self._cameras])
        return self._Ks

    def to_tensors(self) -> Tuple[torch.Tensor, torch.Tensor]:
        """Return (viewmats, Ks) tuple for backwards compatibility.

        Returns:
            viewmats: [C, 4, 4] view matrices
            Ks: [C, 3, 3] intrinsic matrices
        """
        return self.viewmats, self.Ks

    def to_cameras(self) -> 'Cameras':
        """Convert to Cameras dataclass for rendering.

        Returns:
            Cameras object with viewmats, Ks, and camera_model
        """
        from ..cameras import Cameras

        if len(self._cameras) == 0:
            raise ValueError("Cannot convert empty CameraCollection to Cameras")

        camera_model = "pinhole" if isinstance(self._cameras[0], PerspectiveCamera) else "ortho"
        return Cameras(
            viewmats=self.viewmats,
            Ks=self.Ks,
            camera_model=camera_model,
            width=self._cameras[0].width,
            height=self._cameras[0].height,
        )

    @classmethod
    def from_metadata(
        cls,
        metadata: List[dict],
        camera_type: CameraType = "orthographic",
        ortho_scale: float = 2.0,
        fov_deg: float = 60.0,
        near: float = 0.1,
        far: float = 100.0,
        distance: float = 5.0,
        width: int = IMAGE_SIZE,
        height: int = IMAGE_SIZE,
    ) -> "CameraCollection":
        """Build camera collection from sprite metadata.

        Args:
            metadata: list of sprite metadata dicts with yaw, pitch,
                     camera_up, and camera_right fields
            camera_type: "orthographic" or "perspective"
            ortho_scale: (orthographic only) world units visible in half the image
            fov_deg: (perspective only) vertical field of view in degrees
            near: (perspective only) near clipping plane distance
            far: (perspective only) far clipping plane distance
            distance: camera distance from origin
            width: image width in pixels
            height: image height in pixels

        Returns:
            CameraCollection with camera instances of the specified type
        """
        cameras = []
        for sprite in metadata:
            if camera_type == "orthographic":
                camera = OrthographicCamera.from_angles(
                    yaw_deg=sprite["yaw"],
                    pitch_deg=sprite["pitch"],
                    camera_up=sprite["camera_up"],
                    camera_right=sprite["camera_right"],
                    distance=distance,
                    width=width,
                    height=height,
                    ortho_scale=ortho_scale,
                )
            elif camera_type == "perspective":
                camera = PerspectiveCamera.from_angles(
                    yaw_deg=sprite["yaw"],
                    pitch_deg=sprite["pitch"],
                    camera_up=sprite["camera_up"],
                    camera_right=sprite["camera_right"],
                    distance=distance,
                    width=width,
                    height=height,
                    fov_deg=fov_deg,
                    near=near,
                    far=far,
                )
            else:
                raise ValueError(f"Unknown camera type: {camera_type}")
            cameras.append(camera)
        return cls(cameras)
