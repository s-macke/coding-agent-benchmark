"""Command-line argument handling for sprite_to_3dgs."""

import argparse
from dataclasses import dataclass


@dataclass
class TrainConfig:
    """Configuration for train_gaussians()."""
    num_iterations: int = 5000
    lr: float = 0.01
    device: str = 'cuda'
    pose_opt: bool = False
    fix_positions: bool = False


@dataclass
class TrainingArgs:
    """Command-line arguments for training."""
    output: str
    resolution: int
    num_gaussians: int
    camera_type: str
    ortho_scale: float
    fov: float
    train: TrainConfig


def parse_args() -> TrainingArgs:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Convert sprites to 3D Gaussian Splatting')
    parser.add_argument('--output', default='ship_gaussians.ply', help='Output PLY file')
    parser.add_argument('--iterations', type=int, default=5000, help='Training iterations')
    parser.add_argument('--num-gaussians', type=int, default=5000, help='Max Gaussian count')
    parser.add_argument('--lr', type=float, default=0.01, help='Learning rate')
    parser.add_argument('--resolution', type=int, default=64, help='Voxel grid resolution')
    parser.add_argument('--device', default='cuda', help='Device (cuda or cpu)')
    parser.add_argument('--camera-type', choices=['orthographic', 'perspective'],
                        default='orthographic', help='Camera projection type')
    parser.add_argument('--ortho-scale', type=float, default=2.0,
                        help='Orthographic scale (only for orthographic camera)')
    parser.add_argument('--fov', type=float, default=60.0,
                        help='Field of view in degrees (only for perspective camera)')
    parser.add_argument('--pose-opt', action='store_true',
                        help='Enable camera pose optimization during training')
    parser.add_argument('--fix-positions', action='store_true',
                        help='Keep Gaussian positions fixed during training')
    args = parser.parse_args()

    return TrainingArgs(
        output=args.output,
        resolution=args.resolution,
        num_gaussians=args.num_gaussians,
        camera_type=args.camera_type,
        ortho_scale=args.ortho_scale,
        fov=args.fov,
        train=TrainConfig(
            num_iterations=args.iterations,
            lr=args.lr,
            device=args.device,
            pose_opt=args.pose_opt,
            fix_positions=args.fix_positions,
        ),
    )
