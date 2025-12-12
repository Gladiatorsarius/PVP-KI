import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import os
from datetime import datetime

class PPOTrainer:
    """
    PPO (Proximal Policy Optimization) Trainer for shared model across all agents
    """
    def __init__(self, model, lr=3e-4, gamma=0.99, gae_lambda=0.95, clip_range=0.2, 
                 epochs=4, batch_size=256, checkpoint_dir='./checkpoints'):
        self.model = model
        self.optimizer = optim.Adam(model.parameters(), lr=lr)
        
        # Hyperparameters
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_range = clip_range
        self.epochs = epochs
        self.batch_size = batch_size
        
        # Experience buffer (shared across all agents)
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []
        
        # Checkpoint management
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)
        self.fight_count = 0
        self.autosave_interval = 10  # Save every 10 fights
        
    def add_experience(self, state, action, reward, value, log_prob, done):
        """
        Add experience from any agent to shared buffer
        """
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)
    
    def compute_gae(self, next_value):
        """
        Compute Generalized Advantage Estimation (GAE)
        """
        advantages = []
        gae = 0
        
        # Iterate backwards through experiences
        for i in reversed(range(len(self.rewards))):
            if i == len(self.rewards) - 1:
                next_val = next_value
            else:
                next_val = self.values[i + 1]
            
            # TD error
            delta = self.rewards[i] + self.gamma * next_val * (1 - self.dones[i]) - self.values[i]
            
            # GAE
            gae = delta + self.gamma * self.gae_lambda * (1 - self.dones[i]) * gae
            advantages.insert(0, gae)
        
        # Normalize advantages
        advantages = torch.tensor(advantages, dtype=torch.float32)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        return advantages
    
    def update(self):
        """
        Perform PPO update when batch size is reached
        """
        if len(self.states) < self.batch_size:
            return False  # Not enough data yet
        
        # Convert to tensors
        states = torch.stack(self.states)
        actions = torch.tensor(self.actions, dtype=torch.long)
        old_log_probs = torch.stack(self.log_probs)
        values = torch.stack(self.values)
        
        # Compute returns and advantages
        returns = []
        R = 0
        for r, done in zip(reversed(self.rewards), reversed(self.dones)):
            R = r + self.gamma * R * (1 - done)
            returns.insert(0, R)
        returns = torch.tensor(returns, dtype=torch.float32)
        
        advantages = returns - values.detach()
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO update for multiple epochs
        for epoch in range(self.epochs):
            # Forward pass
            logits, _, new_values = self.model(states)
            
            # Compute new log probs
            dist = torch.distributions.Categorical(logits=logits)
            new_log_probs = dist.log_prob(actions)
            
            # Compute ratio
            ratio = torch.exp(new_log_probs - old_log_probs.detach())
            
            # Clipped surrogate objective
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1.0 - self.clip_range, 1.0 + self.clip_range) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            
            # Value loss
            value_loss = 0.5 * ((new_values.squeeze() - returns) ** 2).mean()
            
            # Entropy bonus (for exploration)
            entropy = dist.entropy().mean()
            
            # Total loss
            loss = policy_loss + 0.5 * value_loss - 0.01 * entropy
            
            # Backpropagation
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
            self.optimizer.step()
        
        # Clear buffer
        self.clear_buffer()
        
        print(f"PPO Update: Policy Loss={policy_loss.item():.4f}, Value Loss={value_loss.item():.4f}, Entropy={entropy.item():.4f}")
        
        return True
    
    def clear_buffer(self):
        """Clear experience buffer after update"""
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []
    
    def on_fight_end(self):
        """
        Called when a fight ends. Handles autosaving.
        """
        self.fight_count += 1
        
        if self.fight_count % self.autosave_interval == 0:
            self.save_checkpoint()
    
    def save_checkpoint(self):
        """
        Save model checkpoint with timestamp
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"model_{timestamp}_fight_{self.fight_count}.pt"
        filepath = os.path.join(self.checkpoint_dir, filename)
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'fight_count': self.fight_count
        }, filepath)
        
        print(f"Checkpoint saved: {filename}")
    
    def load_checkpoint(self, filepath):
        """
        Load model checkpoint
        """
        checkpoint = torch.load(filepath)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.fight_count = checkpoint.get('fight_count', 0)
        print(f"Checkpoint loaded: {filepath} (Fight {self.fight_count})")
