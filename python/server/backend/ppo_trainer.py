"""
PPO Trainer with shared model, experience buffer, GAE computation, and autosave.
Implements Proximal Policy Optimization for multi-agent training.
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from datetime import datetime
import os
from collections import deque
import threading
import logging

log = logging.getLogger(__name__)

class ExperienceBuffer:
    """
    A thread-safe, size-limited ring buffer for storing experiences.
    Ensures all tensors are on the correct device upon addition.
    """
    def __init__(self, device, max_size=2048):
        self.device = device
        self.max_size = max_size
        self.states = deque(maxlen=max_size)
        self.actions_move = deque(maxlen=max_size)
        self.actions_look = deque(maxlen=max_size)
        self.rewards = deque(maxlen=max_size)
        self.dones = deque(maxlen=max_size)
        self.log_probs_move = deque(maxlen=max_size)
        self.log_probs_look = deque(maxlen=max_size)
        self.values = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, state, action_move, action_look, reward, done, log_prob_move, log_prob_look, value):
        """Add a single experience tuple, ensuring it's on the correct device."""
        with self._lock:
            # Remove batch dimension from state if present (expecting (1, 1, 64, 64) → (1, 64, 64))
            if state.dim() == 4 and state.shape[0] == 1:
                state = state.squeeze(0)
            self.states.append(state.to(self.device, non_blocking=True))
            self.actions_move.append(action_move.to(self.device, non_blocking=True))
            self.actions_look.append(action_look.to(self.device, non_blocking=True))
            self.rewards.append(torch.tensor(reward, device=self.device, dtype=torch.float32))
            self.dones.append(torch.tensor(done, device=self.device, dtype=torch.float32))
            self.log_probs_move.append(log_prob_move.to(self.device, non_blocking=True))
            self.log_probs_look.append(log_prob_look.to(self.device, non_blocking=True))
            self.values.append(value.to(self.device, non_blocking=True))

    def get_batch(self):
        """Get all experiences and clear buffer in a thread-safe manner."""
        with self._lock:
            batch = {
                'states': torch.stack(list(self.states)),
                'actions_move': torch.stack(list(self.actions_move)),
                'actions_look': torch.stack(list(self.actions_look)),
                'rewards': torch.stack(list(self.rewards)),
                'dones': torch.stack(list(self.dones)),
                'log_probs_move': torch.stack(list(self.log_probs_move)),
                'log_probs_look': torch.stack(list(self.log_probs_look)),
                'values': torch.stack(list(self.values)).squeeze()
            }
            self.clear()
            return batch

    def clear(self):
        """Clear all stored experiences. Must be called within a lock."""
        self.states.clear()
        self.actions_move.clear()
        self.actions_look.clear()
        self.rewards.clear()
        self.dones.clear()
        self.log_probs_move.clear()
        self.log_probs_look.clear()
        self.values.clear()

    def __len__(self):
        with self._lock:
            return len(self.states)


class PPOTrainer:
    """PPO Trainer with GAE and policy clipping"""
    def __init__(self, model, device, lr=3e-4, gamma=0.99, gae_lambda=0.95,
                 clip_range=0.2, epochs=4, batch_size=256):
        self.model = model
        self.device = device
        self.optimizer = optim.Adam(model.parameters(), lr=lr)
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_range = clip_range
        self.epochs = epochs
        self.batch_size = batch_size
        
        self.buffer = ExperienceBuffer(device=self.device)
        self.fight_count = 0
        self.update_count = 0
        
        # Create checkpoints directory
        os.makedirs('checkpoints', exist_ok=True)
        
        # Training metrics
        self.metrics = {
            'policy_loss': deque(maxlen=100),
            'value_loss': deque(maxlen=100),
            'entropy': deque(maxlen=100),
            'total_loss': deque(maxlen=100)
        }
    
    def compute_gae(self, rewards, values, dones, next_value=0):
        """Compute Generalized Advantage Estimation. Assumes all tensors are on the same device."""
        advantages = torch.zeros_like(rewards)
        gae = 0.0
        
        # Bootstrap from the last value if the episode is not done
        next_val_tensor = values[-1] if not dones[-1] else torch.tensor(0.0, device=self.device)

        for t in reversed(range(len(rewards))):
            delta = rewards[t] + self.gamma * next_val_tensor * (1 - dones[t]) - values[t]
            gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * gae
            advantages[t] = gae
            next_val_tensor = values[t]

        returns = advantages + values
        return advantages, returns
    
    def update(self):
        """Perform PPO update using buffered experiences"""
        if len(self.buffer) < self.batch_size:
            return None
        
        # Get batch from buffer
        batch = self.buffer.get_batch()
        
        # Compute advantages using GAE
        advantages, returns = self.compute_gae(
            batch['rewards'], 
            batch['values'], 
            batch['dones']
        )
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO update for multiple epochs
        total_policy_loss = 0
        total_value_loss = 0
        total_entropy = 0
        
        for epoch in range(self.epochs):
            # Forward pass through model
            states = batch['states']
            move_logits, look_delta, values = self.model(states)
            
            # Compute distributions
            move_dist = torch.distributions.Categorical(logits=move_logits)
            look_dist = torch.distributions.Normal(look_delta, 1.0)
            
            # Compute new log probabilities
            new_log_probs_move = move_dist.log_prob(batch['actions_move'])
            new_log_probs_look = look_dist.log_prob(batch['actions_look']).sum(dim=-1)
            
            # Compute entropy for exploration
            entropy_move = move_dist.entropy().mean()
            entropy_look = look_dist.entropy().mean()
            entropy = entropy_move + entropy_look
            
            # Compute ratios for PPO clipping
            ratio_move = torch.exp(new_log_probs_move - batch['log_probs_move'])
            ratio_look = torch.exp(new_log_probs_look - batch['log_probs_look'])
            ratio = ratio_move * ratio_look
            
            # PPO clipped objective
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.clip_range, 1 + self.clip_range) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            
            # Value loss (MSE)
            value_loss = nn.MSELoss()(values.squeeze(), returns)
            
            # Total loss
            loss = policy_loss + 0.5 * value_loss - 0.01 * entropy
            
            # Backward pass and optimization
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
            self.optimizer.step()
            
            # Track metrics
            total_policy_loss += policy_loss.item()
            total_value_loss += value_loss.item()
            total_entropy += entropy.item()
        
        # Average metrics over epochs
        avg_policy_loss = total_policy_loss / self.epochs
        avg_value_loss = total_value_loss / self.epochs
        avg_entropy = total_entropy / self.epochs
        avg_total_loss = avg_policy_loss + 0.5 * avg_value_loss - 0.01 * avg_entropy
        
        # Update metrics
        self.metrics['policy_loss'].append(avg_policy_loss)
        self.metrics['value_loss'].append(avg_value_loss)
        self.metrics['entropy'].append(avg_entropy)
        self.metrics['total_loss'].append(avg_total_loss)
        
        self.update_count += 1
        
        return {
            'policy_loss': avg_policy_loss,
            'value_loss': avg_value_loss,
            'entropy': avg_entropy,
            'total_loss': avg_total_loss,
            'update_count': self.update_count
        }
    
    def on_fight_end(self):
        """Called when a fight ends. Handles autosave every 10 fights."""
        self.fight_count += 1
        
        # Autosave every 10 fights
        if self.fight_count % 10 == 0:
            self.save_checkpoint()
    
    def _async_save(self, checkpoint, filename):
        try:
            torch.save(checkpoint, filename)
            log.info(f"✓ Saved checkpoint: {filename}")
        except Exception as e:
            log.error(f"Failed to save checkpoint {filename}: {e}")

    def save_checkpoint(self):
        """Save model checkpoint with timestamp in a background thread."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"checkpoints/model_{timestamp}_fight_{self.fight_count}.pt"
        
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'fight_count': self.fight_count,
            'update_count': self.update_count,
            'metrics': dict(self.metrics)
        }
        
        threading.Thread(target=self._async_save, args=(checkpoint, filename), daemon=True).start()
        return filename
    
    def load_checkpoint(self, filename):
        """Load model checkpoint with security and path validation."""
        checkpoint_dir = os.path.abspath('checkpoints')
        requested_path = os.path.abspath(os.path.join(checkpoint_dir, filename))

        if not requested_path.startswith(checkpoint_dir):
            raise ValueError(f"Invalid checkpoint path: must be in {checkpoint_dir}")

        if not os.path.isfile(requested_path):
            raise FileNotFoundError(f"Checkpoint not found: {filename}")

        MAX_CHECKPOINT_SIZE = 500 * 1024 * 1024  # 500MB
        if os.path.getsize(requested_path) > MAX_CHECKPOINT_SIZE:
            raise ValueError(f"Checkpoint too large: {requested_path}")

        try:
            # Register safe globals for collections.deque used in metrics
            torch.serialization.add_safe_globals([deque])
            checkpoint = torch.load(requested_path, map_location=self.device, weights_only=True)
            
            required_keys = ['model_state_dict', 'optimizer_state_dict']
            if not all(key in checkpoint for key in required_keys):
                raise ValueError("Invalid checkpoint: missing required keys.")

            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            self.fight_count = checkpoint.get('fight_count', 0)
            self.update_count = checkpoint.get('update_count', 0)
            log.info(f"Loaded checkpoint: {filename} (Fight {self.fight_count}, Update {self.update_count})")
        except Exception as e:
            raise RuntimeError(f"Failed to load checkpoint {filename}: {str(e)}") from e
    
    def get_metrics_summary(self):
        """Get summary of recent training metrics"""
        if not self.metrics['total_loss']:
            return "No training data yet"
        
        summary = {
            'avg_policy_loss': np.mean(self.metrics['policy_loss']),
            'avg_value_loss': np.mean(self.metrics['value_loss']),
            'avg_entropy': np.mean(self.metrics['entropy']),
            'avg_total_loss': np.mean(self.metrics['total_loss']),
            'fights': self.fight_count,
            'updates': self.update_count
        }
        return summary
