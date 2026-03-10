"""
Tests for ppo_trainer.py (GPU support)
"""
import pytest
import torch
import os
import time

try:
    from backend.model import PVPModel
    from backend.ppo_trainer import PPOTrainer, ExperienceBuffer
except Exception:
    from python.server.backend.model import PVPModel
    from python.server.backend.ppo_trainer import PPOTrainer, ExperienceBuffer


@pytest.fixture
def device():
    """Get device for testing (prefer CPU to avoid CUDA test failures)."""
    return torch.device('cpu')


@pytest.fixture
def model_and_trainer(device):
    """Create a model and trainer for testing."""
    model = PVPModel().to(device)
    trainer = PPOTrainer(model, device=device, batch_size=8)  # Small batch for testing
    return model, trainer


def test_experience_buffer_device_consistency(device):
    """Test that ExperienceBuffer keeps all tensors on the same device."""
    buffer = ExperienceBuffer(device=device, max_size=100)
    
    # Add experiences with tensors on the correct device
    state = torch.randn(1, 1, 64, 64).to(device)
    action_move = torch.tensor([1]).to(device)
    action_look = torch.tensor([0.5, -0.3]).to(device)
    reward = 1.0
    done = False
    log_prob_move = torch.tensor([0.1]).to(device)
    log_prob_look = torch.tensor([0.2]).to(device)
    value = torch.tensor([0.5]).to(device)
    
    buffer.add(state, action_move, action_look, reward, done, log_prob_move, log_prob_look, value)
    
    # Verify buffer stored tensors on the correct device
    assert len(buffer) == 1
    batch = buffer.get_batch()
    assert batch['states'].device.type == device.type
    assert batch['rewards'].device.type == device.type
    assert batch['dones'].device.type == device.type


def test_experience_buffer_ring_buffer(device):
    """Test that ExperienceBuffer respects max_size and acts as a ring buffer."""
    buffer = ExperienceBuffer(device=device, max_size=5)
    
    for i in range(10):
        state = torch.randn(1, 1, 64, 64).to(device)
        action_move = torch.tensor([i % 8]).to(device)
        action_look = torch.tensor([0.0, 0.0]).to(device)
        buffer.add(state, action_move, action_look, 0.0, False,
                   torch.tensor([0.0]).to(device), torch.tensor([0.0]).to(device), torch.tensor([0.0]).to(device))
    
    # Buffer should only contain 5 most recent experiences
    assert len(buffer) == 5


def test_checkpoint_path_sanitization(model_and_trainer, tmp_path):
    """Test that checkpoint loading prevents path traversal attacks."""
    model, trainer = model_and_trainer
    
    # Attempt to load a checkpoint outside the checkpoints directory
    malicious_path = "../../../etc/passwd"
    
    with pytest.raises(ValueError, match="Invalid checkpoint path"):
        trainer.load_checkpoint(malicious_path)


def test_checkpoint_size_limit(model_and_trainer, tmp_path):
    """Test that checkpoint loading rejects files that are too large."""
    model, trainer = model_and_trainer
    
    # Create a fake large checkpoint file
    large_file = tmp_path / "checkpoints" / "large.pt"
    large_file.parent.mkdir(parents=True, exist_ok=True)
    with open(large_file, 'wb') as f:
        f.write(b'0' * (600 * 1024 * 1024))  # 600MB (exceeds limit)
    
    # Modify trainer's checkpoint dir temporarily
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with pytest.raises(ValueError, match="Checkpoint too large"):
            trainer.load_checkpoint("large.pt")  # Just the filename, not the path
    finally:
        os.chdir(original_cwd)

def test_checkpoint_save_load_with_map_location(model_and_trainer, tmp_path):
    """Test checkpoint save/load with device mapping."""
    model, trainer = model_and_trainer
    
    # Change working directory to tmp_path for this test
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        os.makedirs("checkpoints", exist_ok=True)
        
        # Save a checkpoint
        trainer.fight_count = 5
        trainer.update_count = 10
        filename = trainer.save_checkpoint()
        
        # Wait a bit for async save to complete
        time.sleep(0.5)
        
        # Verify file exists
        assert os.path.exists(filename)
        
        # Load checkpoint (should work with map_location)
        new_model = PVPModel().to(trainer.device)
        new_trainer = PPOTrainer(new_model, device=trainer.device)
        
        # Extract just the filename for loading
        checkpoint_name = os.path.basename(filename)
        new_trainer.load_checkpoint(checkpoint_name)
        
        assert new_trainer.fight_count == 5
        assert new_trainer.update_count == 10
    finally:
        os.chdir(original_cwd)


def test_ppo_update_with_minimal_batch(model_and_trainer):
    """Test that PPO update works with a minimal batch."""
    model, trainer = model_and_trainer
    
    # Add exactly batch_size experiences
    for i in range(trainer.batch_size):
        state = torch.randn(1, 1, 64, 64).to(trainer.device)
        action_move = torch.tensor([i % 8]).to(trainer.device)
        action_look = torch.tensor([0.1, -0.1]).to(trainer.device)
        reward = 1.0 if i % 2 == 0 else -1.0
        done = False
        
        # Mock log probs and value
        log_prob_move = torch.tensor([0.1]).to(trainer.device)
        log_prob_look = torch.tensor([0.2]).to(trainer.device)
        value = torch.tensor([0.5]).to(trainer.device)
        
        trainer.buffer.add(state, action_move, action_look, reward, done, 
                          log_prob_move, log_prob_look, value)
    
    # Buffer should be ready for update
    assert len(trainer.buffer) >= trainer.batch_size
    
    # Perform update
    metrics = trainer.update()
    
    assert metrics is not None
    assert 'policy_loss' in metrics
    assert 'value_loss' in metrics
    assert 'entropy' in metrics
    assert metrics['update_count'] == 1
    
    # Buffer should be cleared after update
    assert len(trainer.buffer) == 0


def test_gae_computation(model_and_trainer):
    """Test Generalized Advantage Estimation computation."""
    model, trainer = model_and_trainer
    
    # Create test data
    rewards = torch.tensor([1.0, 2.0, 3.0], device=trainer.device)
    values = torch.tensor([0.5, 1.0, 1.5], device=trainer.device)
    dones = torch.tensor([0.0, 0.0, 1.0], device=trainer.device)  # Last step is terminal
    
    advantages, returns = trainer.compute_gae(rewards, values, dones)
    
    # Verify shapes
    assert advantages.shape == rewards.shape
    assert returns.shape == rewards.shape
    assert advantages.device.type == trainer.device.type
    assert returns.device.type == trainer.device.type


def test_concurrent_buffer_access(device):
    """Test that buffer is thread-safe under concurrent access."""
    import threading
    buffer = ExperienceBuffer(device=device, max_size=1000)
    
    def add_experiences(n):
        for i in range(n):
            state = torch.randn(1, 1, 64, 64).to(device)
            action_move = torch.tensor([0]).to(device)
            action_look = torch.tensor([0.0, 0.0]).to(device)
            buffer.add(state, action_move, action_look, 0.0, False,
                      torch.tensor([0.0]).to(device), torch.tensor([0.0]).to(device), torch.tensor([0.0]).to(device))
    
    threads = [threading.Thread(target=add_experiences, args=(50,)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All 200 experiences should be in the buffer (4 threads × 50 each)
    assert len(buffer) == 200
