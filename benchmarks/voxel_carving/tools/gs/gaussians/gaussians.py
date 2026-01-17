"""
Gaussian Splatting data structures.
"""

from dataclasses import dataclass

import torch


@dataclass
class Gaussians:
    """
    Container for 3D Gaussian Splatting parameters.

    Attributes:
        means: [N, 3] positions
        scales: [N, 3] log-scales
        quats: [N, 4] quaternions (wxyz format)
        opacities: [N] logit opacities
        sh_coeffs: [N, K, 3] spherical harmonics coefficients
    """
    means: torch.Tensor
    scales: torch.Tensor
    quats: torch.Tensor
    opacities: torch.Tensor
    sh_coeffs: torch.Tensor

    @property
    def num_gaussians(self) -> int:
        """Number of Gaussians."""
        return self.means.shape[0]

    @property
    def sh_degree(self) -> int:
        """Spherical harmonics degree (0, 1, or 2)."""
        k = self.sh_coeffs.shape[1]
        if k == 1:
            return 0
        elif k == 4:
            return 1
        elif k == 9:
            return 2
        else:
            raise ValueError(f"Unexpected SH coefficient count: {k}")

    def to(self, device: torch.device) -> 'Gaussians':
        """Move all tensors to device."""
        return Gaussians(
            means=self.means.to(device),
            scales=self.scales.to(device),
            quats=self.quats.to(device),
            opacities=self.opacities.to(device),
            sh_coeffs=self.sh_coeffs.to(device),
        )

    def detach(self) -> 'Gaussians':
        """Detach all tensors from computation graph."""
        return Gaussians(
            means=self.means.detach(),
            scales=self.scales.detach(),
            quats=self.quats.detach(),
            opacities=self.opacities.detach(),
            sh_coeffs=self.sh_coeffs.detach(),
        )

    def cpu(self) -> 'Gaussians':
        """Move all tensors to CPU."""
        return self.to(torch.device('cpu'))
