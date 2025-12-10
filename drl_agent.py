import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

class CNNPolicy(nn.Module):
    def __init__(self, input_channels=3, num_actions=5):  # Example: forward, attack, look_dx, look_dy
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
            nn.Linear(64 * 7 * 7, 512),
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
    def __init__(self, num_actions=5):
        self.model = CNNPolicy(num_actions=num_actions)
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-4)
        self.num_actions = num_actions

    def preprocess_frame(self, frame):
        # frame: (224, 224, 3) uint8
        frame = frame.transpose(2, 0, 1)  # (3, 224, 224)
        frame = frame / 255.0
        return torch.tensor(frame, dtype=torch.float32).unsqueeze(0)

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
    dummy_frame = np.random.randint(0, 256, (224, 224, 3), dtype=np.uint8)
    action = agent.get_action(dummy_frame, {})
    print(f"Action: {action}")