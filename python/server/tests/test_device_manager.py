"""
Tests for device_manager.py
"""
import pytest
import torch
from unittest.mock import patch, MagicMock

try:
    from backend.device_manager import get_device, get_device_info
except Exception:
    from python.server.backend.device_manager import get_device, get_device_info


def test_get_device_cuda_available():
    """Test that CUDA device is selected when available."""
    with patch('torch.cuda.is_available', return_value=True):
        with patch('torch.zeros') as mock_zeros:
            device = get_device(prefer_cuda=True)
            assert device.type == 'cuda'
            # Verify a test allocation was attempted
            mock_zeros.assert_called_once()


def test_get_device_cuda_unavailable():
    """Test that CPU device is selected when CUDA is unavailable."""
    with patch('torch.cuda.is_available', return_value=False):
        device = get_device(prefer_cuda=True)
        assert device.type == 'cpu'


def test_get_device_cuda_init_fails():
    """Test CPU fallback when CUDA initialization fails."""
    with patch('torch.cuda.is_available', return_value=True):
        with patch('torch.zeros', side_effect=RuntimeError("CUDA initialization failed")):
            device = get_device(prefer_cuda=True)
            assert device.type == 'cpu'


def test_get_device_force_cpu():
    """Test that CPU is selected when prefer_cuda is False."""
    device = get_device(prefer_cuda=False)
    assert device.type == 'cpu'


def test_get_device_info_cuda():
    """Test device info string for CUDA."""
    with patch('torch.cuda.get_device_name', return_value='NVIDIA GeForce RTX 3060'):
        with patch('torch.cuda.get_device_properties') as mock_props:
            mock_props.return_value = MagicMock(total_memory=12884901888)  # 12GB
            device = torch.device('cuda')
            info = get_device_info(device)
            assert 'NVIDIA GeForce RTX 3060' in info
            assert '12.88 GB' in info


def test_get_device_info_cpu():
    """Test device info string for CPU."""
    device = torch.device('cpu')
    info = get_device_info(device)
    assert info == 'CPU'


def test_get_device_info_mps():
    """Test device info string for Apple MPS."""
    device = torch.device('mps')
    info = get_device_info(device)
    assert info == 'Apple MPS'
