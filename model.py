import torch
import torch.nn as nn
import torch.nn.functional as F

class PVPModel(nn.Module):
    def __init__(self):
        super(PVPModel, self).__init__()
        
        # CNN for Image Processing (64x64 RGB)
        self.conv1 = nn.Conv2d(3, 32, kernel_size=8, stride=4)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=4, stride=2)
        self.conv3 = nn.Conv2d(64, 64, kernel_size=3, stride=1)
        
        # Calculate output size of CNN
        # 64x64 -> 15x15 -> 6x6 -> 4x4
        self.fc_input_dim = 64 * 4 * 4
        
        self.fc1 = nn.Linear(self.fc_input_dim, 512)
        
        # Outputs
        # Movement: W, A, S, D, Space, Attack (6 logits)
        self.actor_move = nn.Linear(512, 6)
        
        # Camera: Yaw, Pitch (Continuous)
        self.actor_look = nn.Linear(512, 2)
        
        # Critic (Value function)
        self.critic = nn.Linear(512, 1)

    def forward(self, x):
        # x: (Batch, 3, 64, 64)
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        
        move_logits = self.actor_move(x)
        look_delta = torch.tanh(self.actor_look(x)) * 10.0 # Scale look speed
        value = self.critic(x)
        
        return move_logits, look_delta, value
