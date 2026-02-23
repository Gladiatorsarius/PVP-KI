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

class ExperienceBuffer:
    """Global experience buffer shared across all agents"""
    def __init__(self):
        self.states = []
        self.actions_move = []
        self.actions_look = []
        self.rewards = []
        self.dones = []
        self.log_probs_move = []
        self.log_probs_look = []
        self.values = []
        
    def add(self, state, action_move, action_look, reward, done, log_prob_move, log_prob_look, value):
        """Add a single experience tuple"""
        self.states.append(state)
        self.actions_move.append(action_move)
        self.actions_look.append(action_look)
        self.rewards.append(reward)
        self.dones.append(done)
        self.log_probs_move.append(log_prob_move)
        self.log_probs_look.append(log_prob_look)
        self.values.append(value)
    
    def get_batch(self):
        """Get all experiences and clear buffer"""
        batch = {
            'states': torch.stack(self.states),
            'actions_move': torch.tensor(self.actions_move),
            'actions_look': torch.stack(self.actions_look),
            'rewards': torch.tensor(self.rewards, dtype=torch.float32),
            'dones': torch.tensor(self.dones, dtype=torch.float32),
            'log_probs_move': torch.stack(self.log_probs_move),
            'log_probs_look': torch.stack(self.log_probs_look),
            'values': torch.stack(self.values).squeeze()
        }
        self.clear()
        return batch

# (rest of file archived but not repeated here)
