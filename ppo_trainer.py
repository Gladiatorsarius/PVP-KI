import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import os
from datetime import datetime

class PPOTrainer:
    """
    Shared PPO trainer for all agents.
    Implements Proximal Policy Optimization with shared model.
    """
    
    def __init__(self, model, lr=3e-4, gamma=0.99, gae_lambda=0.95, 
                 clip_range=0.2, batch_size=256, epochs=4):
        self.model = model
        self.optimizer = optim.Adam(model.parameters(), lr=lr)
        
        # PPO hyperparameters
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_range = clip_range
        self.batch_size = batch_size
        self.epochs = epochs
        
        # Experience buffer (shared across all agents)
        self.states = deque(maxlen=10000)
        self.actions = deque(maxlen=10000)
        self.rewards = deque(maxlen=10000)
        self.values = deque(maxlen=10000)
        self.log_probs = deque(maxlen=10000)
        self.dones = deque(maxlen=10000)
        
        # Training stats
        self.fight_count = 0
        self.update_count = 0
        
        # Checkpoint directory
        self.checkpoint_dir = "checkpoints"
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def add_experience(self, state, action, reward, value, log_prob, done):
        """Add experience from any agent to shared buffer"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)
        
        # Check if we should update
        if len(self.states) >= self.batch_size:
            self.update()
    
    def compute_gae(self, rewards, values, dones):
        """Compute Generalized Advantage Estimation"""
        advantages = []
        gae = 0
        
        for i in reversed(range(len(rewards))):
            if i == len(rewards) - 1:
                next_value = 0
            else:
                next_value = values[i + 1]
            
            delta = rewards[i] + self.gamma * next_value * (1 - dones[i]) - values[i]
            gae = delta + self.gamma * self.gae_lambda * (1 - dones[i]) * gae
            advantages.insert(0, gae)
        
        return advantages
    
    def update(self):
        """Perform PPO update on accumulated experience"""
        if len(self.states) < self.batch_size:
            return
        
        # Convert to tensors
        states = torch.stack([torch.tensor(s, dtype=torch.float32) for s in self.states])
        actions = torch.stack([torch.tensor(a, dtype=torch.float32) for a in self.actions])
        old_log_probs = torch.stack([torch.tensor(lp, dtype=torch.float32) for lp in self.log_probs])
        rewards = [r for r in self.rewards]
        values = [v for v in self.values]
        dones = [d for d in self.dones]
        
        # Compute advantages
        advantages = self.compute_gae(rewards, values, dones)
        advantages = torch.tensor(advantages, dtype=torch.float32)
        returns = advantages + torch.tensor(values, dtype=torch.float32)
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO update for multiple epochs
        for epoch in range(self.epochs):
            # Get new predictions
            move_logits, look_delta, new_values = self.model(states)
            
            # Compute new log probs (simplified, assumes independent binary actions)
            # In practice, you'd need proper action distribution
            new_log_probs = torch.distributions.Bernoulli(logits=move_logits).log_prob(actions).sum(dim=1)
            
            # PPO clipped objective
            ratio = torch.exp(new_log_probs - old_log_probs)
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.clip_range, 1 + self.clip_range) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            
            # Value loss
            value_loss = ((new_values.squeeze() - returns) ** 2).mean()
            
            # Total loss
            loss = policy_loss + 0.5 * value_loss
            
            # Update
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
            self.optimizer.step()
        
        # Clear buffer after update
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.values.clear()
        self.log_probs.clear()
        self.dones.clear()
        
        self.update_count += 1
        print(f"[PPO] Update {self.update_count} completed")
    
    def on_fight_end(self):
        """Called when a fight ends, handles autosave"""
        self.fight_count += 1
        print(f"[PPO] Fight {self.fight_count} completed")
        
        # Autosave every 10 fights
        if self.fight_count % 10 == 0:
            self.save_checkpoint()
    
    def save_checkpoint(self):
        """Save model checkpoint with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"model_{timestamp}_fight_{self.fight_count}.pt"
        filepath = os.path.join(self.checkpoint_dir, filename)
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'fight_count': self.fight_count,
            'update_count': self.update_count,
        }, filepath)
        
        print(f"[PPO] Saved checkpoint: {filename}")
    
    def load_checkpoint(self, filepath):
        """Load model checkpoint"""
        checkpoint = torch.load(filepath)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.fight_count = checkpoint['fight_count']
        self.update_count = checkpoint['update_count']
        print(f"[PPO] Loaded checkpoint from fight {self.fight_count}")
