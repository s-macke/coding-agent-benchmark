"""PLY file I/O for Gaussian Splatting with Spherical Harmonics support."""

import struct

import numpy as np
import torch

from .gaussians import Gaussians
from .sh import SH_C0, SH_DEGREE


def load_ply(path: str, sh_degree: int = SH_DEGREE) -> Gaussians:
    """
    Load gaussian parameters from PLY file.

    Supports both DC-only (legacy) and full SH coefficient files.

    Args:
        path: Path to PLY file
        sh_degree: Target SH degree for output (0, 1, or 2)

    Returns:
        Gaussians object containing means, scales, quats, opacities, sh_coeffs
    """
    with open(path, 'rb') as f:
        # Parse header
        line = f.readline().decode().strip()
        if line != 'ply':
            raise ValueError(f"Not a PLY file: {path}")

        num_vertices = 0
        properties = []
        while True:
            line = f.readline().decode().strip()
            if line.startswith('element vertex'):
                num_vertices = int(line.split()[-1])
            elif line.startswith('property'):
                parts = line.split()
                properties.append(parts[-1])  # property name
            elif line == 'end_header':
                break

        if num_vertices == 0:
            raise ValueError("No vertices found in PLY file")

        # Count how many f_rest properties we have
        num_f_rest = sum(1 for p in properties if p.startswith('f_rest_'))
        has_full_sh = num_f_rest > 0
        file_sh_coeffs = 1 + (num_f_rest // 3) if has_full_sh else 1

        # Calculate total floats per vertex based on properties
        num_floats = len(properties)

        # Read all binary data
        means = np.zeros((num_vertices, 3), dtype=np.float32)
        sh_dc = np.zeros((num_vertices, 3), dtype=np.float32)
        sh_rest = np.zeros((num_vertices, num_f_rest), dtype=np.float32) if has_full_sh else None
        opacities = np.zeros(num_vertices, dtype=np.float32)
        scales = np.zeros((num_vertices, 3), dtype=np.float32)
        quats = np.zeros((num_vertices, 4), dtype=np.float32)

        for i in range(num_vertices):
            data = struct.unpack(f'<{num_floats}f', f.read(num_floats * 4))

            # Standard layout: xyz, f_dc_0-2, [f_rest_0-N], opacity, scale_0-2, rot_0-3
            means[i] = data[0:3]
            sh_dc[i] = data[3:6]

            if has_full_sh:
                sh_rest[i] = data[6:6 + num_f_rest]
                offset = 6 + num_f_rest
            else:
                offset = 6

            opacities[i] = data[offset]
            scales[i] = data[offset + 1:offset + 4]
            # Convert quaternion from xyzw (file) to wxyz (internal)
            quats[i] = [data[offset + 7], data[offset + 4],
                        data[offset + 5], data[offset + 6]]

    # Build SH coefficient tensor
    target_coeffs = (sh_degree + 1) ** 2

    if has_full_sh:
        # Reshape f_rest from channel-grouped to [N, K-1, 3]
        # File stores: f_rest_0-7 (all R), f_rest_8-15 (all G), f_rest_16-23 (all B)
        num_coeffs_per_channel = num_f_rest // 3
        sh_rest_reshaped = sh_rest.reshape(num_vertices, 3, num_coeffs_per_channel)
        sh_rest_reshaped = sh_rest_reshaped.transpose(0, 2, 1)  # [N, 3, K-1] -> [N, K-1, 3]
        all_sh = np.concatenate([sh_dc[:, np.newaxis, :], sh_rest_reshaped], axis=1)

        # Truncate or pad to target degree
        file_coeffs = all_sh.shape[1]
        if file_coeffs >= target_coeffs:
            sh_coeffs = all_sh[:, :target_coeffs, :]
        else:
            sh_coeffs = np.zeros((num_vertices, target_coeffs, 3), dtype=np.float32)
            sh_coeffs[:, :file_coeffs, :] = all_sh
    else:
        # DC-only file: convert DC to RGB, then init SH
        rgb = sh_dc * SH_C0 + 0.5
        rgb = np.clip(rgb, 0, 1)
        sh_coeffs = np.zeros((num_vertices, target_coeffs, 3), dtype=np.float32)
        sh_coeffs[:, 0, :] = (rgb - 0.5) / SH_C0

    return Gaussians(
        means=torch.from_numpy(means),
        scales=torch.from_numpy(scales),
        quats=torch.from_numpy(quats),
        opacities=torch.from_numpy(opacities),
        sh_coeffs=torch.from_numpy(sh_coeffs.astype(np.float32)),
    )


def export_ply(gaussians: Gaussians, output_path: str) -> None:
    """
    Export Gaussians to standard PLY format with full SH coefficients.

    Args:
        gaussians: Gaussians object to export
        output_path: Output file path
    """
    n = gaussians.num_gaussians
    num_sh_coeffs = gaussians.sh_coeffs.shape[1]
    num_f_rest = (num_sh_coeffs - 1) * 3  # Excluding DC

    means_np = gaussians.means.detach().cpu().numpy()
    scales_np = gaussians.scales.detach().cpu().numpy()
    quats_np = gaussians.quats.detach().cpu().numpy()
    opacities_np = gaussians.opacities.detach().cpu().numpy()
    sh_np = gaussians.sh_coeffs.detach().cpu().numpy()

    # Build header
    header_lines = [
        "ply",
        "format binary_little_endian 1.0",
        f"element vertex {n}",
        "property float x",
        "property float y",
        "property float z",
        "property float f_dc_0",
        "property float f_dc_1",
        "property float f_dc_2",
    ]

    # Add f_rest properties for higher-order SH
    for i in range(num_f_rest):
        header_lines.append(f"property float f_rest_{i}")

    header_lines.extend([
        "property float opacity",
        "property float scale_0",
        "property float scale_1",
        "property float scale_2",
        "property float rot_0",
        "property float rot_1",
        "property float rot_2",
        "property float rot_3",
        "end_header",
    ])

    with open(output_path, 'wb') as f:
        # Write header
        f.write(('\n'.join(header_lines) + '\n').encode())

        # Write binary data
        for i in range(n):
            # Position
            f.write(struct.pack('<fff', *means_np[i]))

            # SH DC (f_dc_0, f_dc_1, f_dc_2)
            f.write(struct.pack('<fff', *sh_np[i, 0]))

            # SH rest (f_rest_0, f_rest_1, ... grouped by channel)
            # Standard format: all R coeffs, then all G coeffs, then all B coeffs
            if num_sh_coeffs > 1:
                # Transpose [K-1, 3] to [3, K-1] then flatten
                sh_rest = sh_np[i, 1:].T.flatten()  # [R1,R2,...,G1,G2,...,B1,B2,...]
                f.write(struct.pack(f'<{num_f_rest}f', *sh_rest))

            # Opacity
            f.write(struct.pack('<f', opacities_np[i]))

            # Scales
            f.write(struct.pack('<fff', *scales_np[i]))

            # Quaternion (wxyz -> xyzw for file)
            q = quats_np[i]
            f.write(struct.pack('<ffff', q[1], q[2], q[3], q[0]))

    print(f"Saved {n} Gaussians ({num_sh_coeffs} SH coefficients) to {output_path}")
