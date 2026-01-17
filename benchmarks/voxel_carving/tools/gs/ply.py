"""PLY file I/O for Gaussian Splatting."""

import struct
from typing import Tuple

import numpy as np
import torch

from .constants import SH_C0


def load_ply(path: str) -> Tuple[torch.Tensor, ...]:
    """
    Load gaussian parameters from PLY file.

    Returns:
        means: [N, 3] positions
        scales: [N, 3] log-scales
        quats: [N, 4] quaternions (wxyz)
        opacities: [N] logit opacities
        colors: [N, 3] RGB colors
    """
    with open(path, 'rb') as f:
        # Parse header
        line = f.readline().decode().strip()
        if line != 'ply':
            raise ValueError(f"Not a PLY file: {path}")

        num_vertices = 0
        while True:
            line = f.readline().decode().strip()
            if line.startswith('element vertex'):
                num_vertices = int(line.split()[-1])
            elif line == 'end_header':
                break

        if num_vertices == 0:
            raise ValueError("No vertices found in PLY file")

        # Read binary data: 14 floats per gaussian
        # xyz, f_dc_0-2, opacity, scale_0-2, rot_0-3
        means = np.zeros((num_vertices, 3), dtype=np.float32)
        sh_dc = np.zeros((num_vertices, 3), dtype=np.float32)
        opacities = np.zeros(num_vertices, dtype=np.float32)
        scales = np.zeros((num_vertices, 3), dtype=np.float32)
        quats = np.zeros((num_vertices, 4), dtype=np.float32)

        for i in range(num_vertices):
            data = struct.unpack('<14f', f.read(14 * 4))
            means[i] = data[0:3]
            sh_dc[i] = data[3:6]
            opacities[i] = data[6]
            scales[i] = data[7:10]
            # Convert quaternion from xyzw (file) to wxyz (internal)
            quats[i] = [data[13], data[10], data[11], data[12]]  # w, x, y, z

    # Convert SH DC back to RGB: color = sh * C0 + 0.5
    colors = sh_dc * SH_C0 + 0.5
    colors = np.clip(colors, 0, 1)

    return (
        torch.from_numpy(means),
        torch.from_numpy(scales),
        torch.from_numpy(quats),
        torch.from_numpy(opacities),
        torch.from_numpy(colors),
    )


def export_ply(means: torch.Tensor,
               scales: torch.Tensor,
               quats: torch.Tensor,
               opacities: torch.Tensor,
               colors: torch.Tensor,
               output_path: str) -> None:
    """Export Gaussians to standard PLY format compatible with 3DGS viewers."""
    N = means.shape[0]

    means_np = means.numpy()
    scales_np = scales.numpy()
    quats_np = quats.numpy()
    opacities_np = opacities.numpy()

    # Convert colors to SH DC coefficients: SH0 = (color - 0.5) / C0
    sh0_np = (colors.numpy() - 0.5) / SH_C0

    with open(output_path, 'wb') as f:
        # Header
        header = f"""ply
format binary_little_endian 1.0
element vertex {N}
property float x
property float y
property float z
property float f_dc_0
property float f_dc_1
property float f_dc_2
property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""
        f.write(header.encode())

        # Binary data
        for i in range(N):
            f.write(struct.pack('<fff', *means_np[i]))
            f.write(struct.pack('<fff', *sh0_np[i]))
            f.write(struct.pack('<f', opacities_np[i]))
            f.write(struct.pack('<fff', *scales_np[i]))
            # Convert quaternion from wxyz to xyzw format
            q = quats_np[i]
            f.write(struct.pack('<ffff', q[1], q[2], q[3], q[0]))

    print(f"Saved {N} Gaussians to {output_path}")
