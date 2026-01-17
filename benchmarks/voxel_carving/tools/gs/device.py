"""
Device selection utilities with automatic fallback.
"""

import torch


def get_device(requested: str) -> torch.device:
    """
    Select compute device with automatic fallback.

    Fallback order: cuda -> mps -> cpu

    Args:
        requested: Device name ('cuda', 'mps', or 'cpu')

    Returns:
        torch.device for the best available device
    """
    if requested == 'cuda':
        if torch.cuda.is_available():
            return torch.device('cuda')
        elif torch.backends.mps.is_available():
            print("  CUDA not available, using MPS (Metal)")
            return torch.device('mps')
        else:
            print("  CUDA not available, using CPU")
            return torch.device('cpu')
    elif requested == 'mps':
        if torch.backends.mps.is_available():
            return torch.device('mps')
        else:
            print("  MPS not available, using CPU")
            return torch.device('cpu')
    return torch.device(requested)
