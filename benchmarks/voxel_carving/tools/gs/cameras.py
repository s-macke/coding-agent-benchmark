"""
Camera batch data for rendering.
"""

from dataclasses import dataclass
from typing import Literal, Union

import torch

CameraModel = Literal["ortho", "pinhole"]


@dataclass
class Cameras:
    """
    Camera batch data for rendering.

    Attributes:
        viewmats: [C, 4, 4] world-to-camera view matrices
        Ks: [C, 3, 3] intrinsic matrices
        camera_model: "ortho" for orthographic, "pinhole" for perspective
        width: image width in pixels
        height: image height in pixels
    """
    viewmats: torch.Tensor
    Ks: torch.Tensor
    camera_model: CameraModel
    width: int
    height: int

    def __len__(self) -> int:
        """Number of cameras."""
        return self.viewmats.shape[0]

    def to(self, device: torch.device) -> 'Cameras':
        """Move tensors to device."""
        return Cameras(
            viewmats=self.viewmats.to(device),
            Ks=self.Ks.to(device),
            camera_model=self.camera_model,
            width=self.width,
            height=self.height,
        )

    def __getitem__(self, idx: Union[int, slice, torch.Tensor]) -> 'Cameras':
        """Support indexing and slicing."""
        viewmats = self.viewmats[idx]
        Ks = self.Ks[idx]

        # Ensure batch dimension is preserved
        if viewmats.dim() == 2:
            viewmats = viewmats.unsqueeze(0)
            Ks = Ks.unsqueeze(0)

        return Cameras(
            viewmats=viewmats,
            Ks=Ks,
            camera_model=self.camera_model,
            width=self.width,
            height=self.height,
        )

    @property
    def is_perspective(self) -> bool:
        """True if using perspective projection."""
        return self.camera_model == "pinhole"

    def with_resolution(self, width: int, height: int) -> 'Cameras':
        """Return a copy with different resolution, scaling intrinsics.

        Args:
            width: new image width in pixels
            height: new image height in pixels

        Returns:
            New Cameras object with scaled intrinsics
        """
        scale_x = width / self.width
        scale_y = height / self.height

        # Scale intrinsic matrices: fx, cx scale with width; fy, cy scale with height
        new_Ks = self.Ks.clone()
        new_Ks[:, 0, 0] *= scale_x  # fx
        new_Ks[:, 0, 2] *= scale_x  # cx
        new_Ks[:, 1, 1] *= scale_y  # fy
        new_Ks[:, 1, 2] *= scale_y  # cy

        return Cameras(
            viewmats=self.viewmats,
            Ks=new_Ks,
            camera_model=self.camera_model,
            width=width,
            height=height,
        )
