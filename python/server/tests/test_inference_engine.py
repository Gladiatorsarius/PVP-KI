"""
Tests for inference_engine.py
"""
import pytest
import torch
import base64
import numpy as np
from unittest.mock import patch, MagicMock

try:
    from backend.inference_engine import InferenceEngine
    from backend.model import PVPModel
except Exception:
    from python.server.backend.inference_engine import InferenceEngine
    from python.server.backend.model import PVPModel


@pytest.fixture
def model_and_device():
    """Create a test model and device."""
    device = torch.device('cpu')
    model = PVPModel().to(device)
    model.eval()
    return model, device


@pytest.fixture
def inference_engine(model_and_device):
    """Create an inference engine for testing."""
    model, device = model_and_device
    return InferenceEngine(model, device)


@pytest.fixture
def sample_frame_b64():
    """Create a valid 64x64 grayscale JPEG base64 encoded string."""
    import cv2
    import io
    # Create a random 64x64 grayscale image
    img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    # Encode as JPEG
    success, buffer = cv2.imencode('.jpg', img)
    if not success:
        pytest.fail("Failed to encode test image")
    # Convert to base64
    return base64.b64encode(buffer).decode('utf-8')


def test_inference_engine_initialization(model_and_device):
    """Test that InferenceEngine initializes correctly."""
    model, device = model_and_device
    engine = InferenceEngine(model, device)
    assert engine.model is model
    assert engine.device == device


def test_predict_valid_frame(inference_engine, sample_frame_b64):
    """Test prediction with a valid frame."""
    action = inference_engine.predict(sample_frame_b64)
    
    # Verify action structure
    assert 'type' in action
    assert action['type'] == 'action'
    assert 'movement' in action
    assert 'mouse' in action
    assert 'look' in action
    assert 'hotbar' in action
    assert 'inventory' in action
    
    # Verify movement keys
    movement = action['movement']
    assert isinstance(movement['w'], bool)
    assert isinstance(movement['a'], bool)
    assert isinstance(movement['s'], bool)
    assert isinstance(movement['d'], bool)
    assert isinstance(movement['jump'], bool)
    
    # Verify look deltas
    look = action['look']
    assert isinstance(look['dx'], float)
    assert isinstance(look['dy'], float)


def test_predict_invalid_base64(inference_engine):
    """Test that invalid base64 raises an error."""
    with pytest.raises(Exception):  # Should raise base64 decoding error
        inference_engine.predict("not-valid-base64!!!")


def test_predict_wrong_dimensions(inference_engine):
    """Test frame with wrong dimensions gets resized."""
    import cv2
    # Create a 128x128 image (wrong size)
    img = np.random.randint(0, 256, (128, 128), dtype=np.uint8)
    success, buffer = cv2.imencode('.jpg', img)
    assert success
    frame_b64 = base64.b64encode(buffer).decode('utf-8')
    
    # Should still work due to automatic resizing
    action = inference_engine.predict(frame_b64)
    assert action['type'] == 'action'


def test_preprocess_cv2(inference_engine, sample_frame_b64):
    """Test CV2 preprocessing path."""
    jpeg_bytes = base64.b64decode(sample_frame_b64)
    tensor = inference_engine._preprocess_cv2(jpeg_bytes)
    
    # Verify tensor shape and type
    assert tensor.shape == (1, 1, 64, 64)
    assert tensor.dtype == torch.float32
    # Values should be normalized to [0, 1]
    assert tensor.min() >= 0.0
    assert tensor.max() <= 1.0


def test_map_to_protocol(inference_engine):
    """Test action protocol mapping."""
    # Create mock model outputs
    move_logits = torch.tensor([[1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]])
    look_delta = torch.tensor([[5.0, -3.0]])
    
    action = inference_engine._map_to_protocol(move_logits, look_delta)
    
    # Verify structure
    assert action['movement']['w'] == True  # sigmoid(1.0) > 0.5
    assert action['movement']['a'] == False  # sigmoid(-1.0) < 0.5
    assert action['look']['dx'] == 5.0
    assert action['look']['dy'] == -3.0


def test_predict_with_torch_no_grad(inference_engine, sample_frame_b64):
    """Verify that predictions don't track gradients."""
    with torch.set_grad_enabled(True):
        # Even if gradients are enabled globally, predict should use no_grad
        action = inference_engine.predict(sample_frame_b64)
        assert action is not None
        # Verify no gradients were accumulated
        for param in inference_engine.model.parameters():
            assert param.grad is None or torch.all(param.grad == 0)
