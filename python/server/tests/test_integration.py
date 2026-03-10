"""
Integration tests for the complete CUDA/GPU training pipeline.
Tests manager initialization, coordinator integration, and end-to-end flow.
"""
import pytest
import asyncio
import json
import base64
import numpy as np
import cv2
from unittest.mock import MagicMock, patch

try:
    from backend.manager import Manager
    MANAGER_MODULE_PATH = "backend.manager"
except Exception:
    from python.server.backend.manager import Manager
    MANAGER_MODULE_PATH = "python.server.backend.manager"


@pytest.fixture
def manager():
    """Create a manager instance for testing."""
    with patch(f'{MANAGER_MODULE_PATH}.CommandConnector'):
        mgr = Manager()
        yield mgr
        # Cleanup
        if mgr._initialized:
            mgr.stop()


def test_manager_initialization_order(manager):
    """Test that manager initializes components in the correct order."""
    # Verify initialization succeeded
    assert manager._initialized == True
    
    # Verify device was selected
    assert manager.device is not None
    
    # Verify model exists and is on the correct device
    assert manager.model is not None
    assert next(manager.model.parameters()).device.type == manager.device.type
    
    # Verify trainer exists and has the model
    assert manager.trainer is not None
    assert manager.trainer.model is manager.model
    assert manager.trainer.device == manager.device
    
    # Verify inference engine exists
    assert manager.inference_engine is not None
    assert manager.inference_engine.model is manager.model
    assert manager.inference_engine.device == manager.device
    
    # Verify coordinator exists and has references
    assert manager._coordinator is not None
    assert manager._coordinator.inference_engine is manager.inference_engine
    assert manager._coordinator.inference_executor is manager.inference_executor
    assert manager._coordinator.model_lock is manager.model_lock


def test_manager_start_requires_initialization():
    """Test that manager.start() fails if initialization failed."""
    with patch(f'{MANAGER_MODULE_PATH}.get_device', side_effect=Exception("Device init failed")):
        with patch(f'{MANAGER_MODULE_PATH}.CommandConnector'):
            mgr = Manager()
            assert mgr._initialized == False
            
            # start() should handle gracefully
            mgr.start()  # Should emit error status but not crash


def test_manager_stop_saves_checkpoint(manager):
    """Test that manager.stop() triggers a checkpoint save."""
    with patch.object(manager.trainer, 'save_checkpoint') as mock_save:
        manager.stop()
        mock_save.assert_called_once()


def test_handle_command_round_end_triggers_update(manager):
    """Test that ROUND_END command triggers trainer update if buffer is ready."""
    # Fill buffer to batch_size
    for i in range(manager.trainer.batch_size):
        state = pytest.importorskip('torch').randn(1, 1, 64, 64).to(manager.device)
        action_move = pytest.importorskip('torch').tensor([0]).to(manager.device)
        action_look = pytest.importorskip('torch').tensor([0.0, 0.0]).to(manager.device)
        manager.trainer.buffer.add(
            state, action_move, action_look, 1.0, False,
            pytest.importorskip('torch').tensor([0.0]).to(manager.device),
            pytest.importorskip('torch').tensor([0.0]).to(manager.device),
            pytest.importorskip('torch').tensor([0.0]).to(manager.device)
        )
    
    # Trigger ROUND_END
    initial_update_count = manager.trainer.update_count
    manager._handle_command({'type': 'ROUND_END'})
    
    # Verify update was called
    assert manager.trainer.update_count > initial_update_count


def test_inference_engine_integration(manager):
    """Test that inference engine correctly processes a frame."""
    # Create a test frame
    img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
    success, buffer = cv2.imencode('.jpg', img)
    assert success
    frame_b64 = base64.b64encode(buffer).decode('utf-8')
    
    # Run inference
    action = manager.inference_engine.predict(frame_b64)
    
    # Verify action structure
    assert action['type'] == 'action'
    assert 'movement' in action
    assert 'look' in action


def test_model_lock_prevents_concurrent_access(manager):
    """Test that model_lock prevents race conditions."""
    import threading
    import time
    
    results = []
    
    def inference_task():
        # Create a test frame
        img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
        success, buffer = cv2.imencode('.jpg', img)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Acquire lock and run inference
        with manager.model_lock:
            time.sleep(0.01)  # Simulate some processing time
            action = manager.inference_engine.predict(frame_b64)
            results.append(action)
    
    # Run multiple inference tasks concurrently
    threads = [threading.Thread(target=inference_task) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All tasks should complete successfully
    assert len(results) == 5


@pytest.mark.skip(reason="Requires pytest-asyncio which is not installed")
@pytest.mark.asyncio
async def test_coordinator_inference_path():
    """Test the coordinator's frame handling with inference."""
    with patch(f'{MANAGER_MODULE_PATH}.CommandConnector'):
        manager = Manager()
        
        # Mock websocket
        mock_websocket = MagicMock()
        mock_websocket.send = MagicMock(return_value=asyncio.sleep(0))
        
        # Prepare a hello message first
        hello_msg = {
            'type': 'hello',
            'agent_id': 1,
            'session_id': 'test-session',
            'episode_id': 'ep-0',
            'client_role': 'vm-runtime'
        }
        await manager._coordinator._handle_hello(mock_websocket, hello_msg)
        
        # Mark as ready
        ready_msg = {
            'type': 'ready',
            'agent_id': 1
        }
        await manager._coordinator._handle_ready(mock_websocket, ready_msg)
        
        # Create a test frame
        img = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
        success, buffer = cv2.imencode('.jpg', img)
        assert success
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Send a frame
        frame_msg = {
            'type': 'frame',
            'agent_id': 1,
            'frame_id': 1,
            'timestamp_ms': 1000,
            'session_id': 'test-session',
            'episode_id': 'ep-0',
            'width': 64,
            'height': 64,
            'format': 'jpeg',
            'payload_b64': frame_b64
        }
        
        await manager._coordinator._handle_frame(mock_websocket, frame_msg)
        
        # Verify an action was sent back
        mock_websocket.send.assert_called()
        call_args = mock_websocket.send.call_args[0][0]
        action_response = json.loads(call_args)
        
        assert action_response['type'] == 'action'
        assert action_response['agent_id'] == 1
        assert 'movement' in action_response


def test_device_detection_logs_info(caplog):
    """Test that device detection logs appropriate info."""
    import logging
    with caplog.at_level(logging.INFO):
        with patch(f'{MANAGER_MODULE_PATH}.CommandConnector'):
            manager = Manager()
        
        # Check that device info was logged
        assert any('Manager initialized' in record.message for record in caplog.records)
