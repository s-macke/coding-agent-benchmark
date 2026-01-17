"""Loss functions for Gaussian Splatting training."""

import torch
import torch.nn.functional as F


def gaussian_kernel(window_size: int, sigma: float) -> torch.Tensor:
    """Create a 1D Gaussian kernel."""
    x = torch.arange(window_size, dtype=torch.float32) - window_size // 2
    gauss = torch.exp(-x.pow(2) / (2 * sigma**2))
    return gauss / gauss.sum()


def create_window(window_size: int, channel: int) -> torch.Tensor:
    """Create a 2D Gaussian window for SSIM computation."""
    _1D_window = gaussian_kernel(window_size, 1.5).unsqueeze(1)
    _2D_window = _1D_window.mm(_1D_window.t()).unsqueeze(0).unsqueeze(0)
    return _2D_window.expand(channel, 1, window_size, window_size).contiguous()


def ssim(
    img1: torch.Tensor,
    img2: torch.Tensor,
    window_size: int = 11,
    size_average: bool = True,
) -> torch.Tensor:
    """
    Compute SSIM between two images.

    Args:
        img1: First image tensor [N, C, H, W]
        img2: Second image tensor [N, C, H, W]
        window_size: Size of the Gaussian window (default: 11)
        size_average: If True, return mean SSIM; otherwise return per-pixel SSIM

    Returns:
        SSIM value(s) in range [0, 1] where 1 means identical images
    """
    channel = img1.size(1)
    window = create_window(window_size, channel).to(img1.device).type_as(img1)

    # Compute local means
    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)
    mu1_mu2 = mu1 * mu2

    # Compute local variances and covariance
    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=channel) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=channel) - mu2_sq
    sigma12 = F.conv2d(img1 * img2, window, padding=window_size // 2, groups=channel) - mu1_mu2

    # SSIM constants for numerical stability
    C1 = 0.01**2
    C2 = 0.03**2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / (
        (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)
    )

    if size_average:
        return ssim_map.mean()
    else:
        return ssim_map.mean(dim=[1, 2, 3])
