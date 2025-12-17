import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np

class CNNPolicy(nn.Module):
    def __init__(self, input_channels=1, num_actions=8):  # forward, back, left, right, jump, attack, swap_offhand, open_inventory
        super(CNNPolicy, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(input_channels, 32, kernel_size=8, stride=4),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),
            nn.ReLU(),
            nn.Flatten()
        )
        self.fc = nn.Sequential(
            nn.Linear(64 * 4 * 4, 512),
            nn.ReLU(),
            nn.Linear(512, num_actions)
        )
        self.value_head = nn.Linear(512, 1)

    def forward(self, x):
        x = self.conv(x)
        x = self.fc[:-1](x)  # Before last layer
        policy_logits = self.fc[-1](x)
        value = self.value_head(x)
        return policy_logits, value

class DRLAgent:
    def __init__(self, num_actions=8):
        self.model = CNNPolicy(num_actions=num_actions)
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-4)
        self.num_actions = num_actions

    def preprocess_frame(self, frame):
        # frame: (H, W, 3) or (H, W) uint8 -> grayscale 64x64
        if frame.ndim == 3 and frame.shape[2] == 3:
            frame = (0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1] + 0.114 * frame[:, :, 2]).astype(np.uint8)
        # Resize to 64x64
        frame = torch.tensor(frame, dtype=torch.float32)
        frame = F.interpolate(frame.unsqueeze(0).unsqueeze(0), size=(64, 64), mode='bilinear', align_corners=False).squeeze(0)
        frame = frame / 255.0
        return frame.unsqueeze(0)  # (1, 1, 64, 64)

    def get_action(self, frame, state):
        self.model.eval()
        with torch.no_grad():
            obs = self.preprocess_frame(frame)
            policy_logits, value = self.model(obs)
            action_probs = torch.softmax(policy_logits, dim=-1)
            action = torch.multinomial(action_probs, 1).item()
        return action

    def train_step(self, obs, actions, rewards, next_obs):
        # Placeholder for PPO training
        pass

# Example
if __name__ == "__main__":
    agent = DRLAgent()
    dummy_frame = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
    action = agent.get_action(dummy_frame, {})
    print(f"Action: {action}")