"""Camera pose optimization module for Gaussian splatting.

Implements per-camera pose adjustments using learnable embeddings,
following the approach from gsplat's simple_trainer.py.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


def rotation_6d_to_matrix(d6: Tensor) -> Tensor:
    """Convert 6D rotation representation to 3x3 rotation matrix.

    Uses the continuous 6D representation from "On the Continuity of
    Rotation Representations in Neural Networks" (Zhou et al., CVPR 2019).

    The 6D representation consists of two 3D vectors that are orthogonalized
    via Gram-Schmidt to form the first two columns of a rotation matrix.
    The third column is computed via cross product.

    Args:
        d6: [..., 6] tensor of 6D rotation representations

    Returns:
        [..., 3, 3] rotation matrices
    """
    a1, a2 = d6[..., :3], d6[..., 3:6]

    # Gram-Schmidt orthogonalization
    b1 = F.normalize(a1, dim=-1)
    b2 = F.normalize(a2 - (b1 * a2).sum(-1, keepdim=True) * b1, dim=-1)
    b3 = torch.cross(b1, b2, dim=-1)

    return torch.stack([b1, b2, b3], dim=-2)


class CameraOptModule(nn.Module):
    """Per-camera pose adjustment module.

    Learns a small pose delta (translation + rotation) for each camera
    to refine initial camera poses during training.

    The pose is parameterized as:
    - 3D translation delta
    - 6D rotation delta (continuous representation)

    Adjustments are applied by matrix multiplication with the original
    camera-to-world transform.
    """

    def __init__(self, num_cameras: int):
        """Initialize pose optimization module.

        Args:
            num_cameras: Number of cameras to optimize
        """
        super().__init__()
        # 9 parameters per camera: 3 translation + 6 rotation
        self.embeds = nn.Embedding(num_cameras, 9)

        # Identity rotation in 6D representation: first two columns of I_3x3
        # [1, 0, 0, 0, 1, 0] -> first col [1,0,0], second col [0,1,0]
        self.register_buffer(
            "identity_rot6d",
            torch.tensor([1.0, 0.0, 0.0, 0.0, 1.0, 0.0], dtype=torch.float32)
        )

    def zero_init(self) -> None:
        """Initialize all pose adjustments to zero (identity transform)."""
        nn.init.zeros_(self.embeds.weight)

    def forward(
        self,
        camtoworlds: Tensor,
        camera_ids: Tensor,
    ) -> Tensor:
        """Apply learned pose adjustments to camera-to-world matrices.

        Args:
            camtoworlds: [B, 4, 4] or [4, 4] camera-to-world matrices
            camera_ids: [B] or scalar tensor of camera indices

        Returns:
            Adjusted camera-to-world matrices with same shape as input
        """
        # Handle single camera case
        squeeze_output = camtoworlds.dim() == 2
        if squeeze_output:
            camtoworlds = camtoworlds.unsqueeze(0)
            camera_ids = camera_ids.unsqueeze(0) if camera_ids.dim() == 0 else camera_ids

        batch_size = camtoworlds.shape[0]
        device = camtoworlds.device

        # Get pose deltas [B, 9]
        delta = self.embeds(camera_ids)

        # Split into translation and rotation
        dx = delta[:, :3]  # [B, 3]
        drot6d = delta[:, 3:] + self.identity_rot6d  # [B, 6]

        # Convert 6D rotation to matrix
        rot_mat = rotation_6d_to_matrix(drot6d)  # [B, 3, 3]

        # Build 4x4 transformation matrix
        transform = torch.eye(4, device=device, dtype=camtoworlds.dtype)
        transform = transform.unsqueeze(0).expand(batch_size, -1, -1).clone()
        transform[:, :3, :3] = rot_mat
        transform[:, :3, 3] = dx

        # Apply adjustment: new_c2w = old_c2w @ delta_transform
        result = torch.bmm(camtoworlds, transform)

        if squeeze_output:
            result = result.squeeze(0)

        return result

    def forward_viewmats(
        self,
        viewmats: Tensor,
        camera_ids: Tensor,
    ) -> Tensor:
        """Apply learned pose adjustments to world-to-camera (view) matrices.

        This is a convenience method that handles the coordinate conversion:
        viewmat = inverse(camtoworld)

        Args:
            viewmats: [B, 4, 4] or [4, 4] world-to-camera matrices
            camera_ids: [B] or scalar tensor of camera indices

        Returns:
            Adjusted world-to-camera matrices with same shape as input
        """
        # viewmat -> camtoworld
        camtoworlds = torch.linalg.inv(viewmats)

        # Apply adjustment
        adjusted_c2w = self.forward(camtoworlds, camera_ids)

        # camtoworld -> viewmat
        return torch.linalg.inv(adjusted_c2w)
