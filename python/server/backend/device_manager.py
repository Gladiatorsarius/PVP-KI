import torch
import logging

log = logging.getLogger(__name__)

def get_device(prefer_cuda: bool = True) -> torch.device:
    """
    Selects the best available device (CUDA, MPS, CPU) and logs the choice.
    Includes a test allocation to validate CUDA availability.

    Args:
        prefer_cuda (bool): If True, prefers CUDA if available.

    Returns:
        torch.device: The selected device.
    """
    if prefer_cuda and torch.cuda.is_available():
        try:
            # Test allocation to catch driver/initialization issues
            torch.zeros(1, device='cuda')
            log.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
            log.info(f"CUDA Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
            return torch.device('cuda')
        except RuntimeError as e:
            log.error(f"CUDA is available but initialization failed: {e}. Falling back to CPU.")
            return torch.device('cpu')
    
    # Apple Silicon (M-series chips) support
    if torch.backends.mps.is_available():
        log.info("Using Apple MPS device.")
        return torch.device('mps')

    log.warning("CUDA not available. Falling back to CPU (training will be significantly slower).")
    return torch.device('cpu')

def get_device_info(device: torch.device) -> str:
    """
    Returns a formatted string with information about the given device.
    """
    if device.type == 'cuda':
        return f"CUDA: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB)"
    elif device.type == 'mps':
        return "Apple MPS"
    else:
        return "CPU"
