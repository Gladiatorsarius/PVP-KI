import time
import numpy as np
import torch
from PIL import Image

class GymEnvAdapter:
    """Adapter to run MineRL/Gym envs and convert observations/actions

    - Exposes `reset()` returning a torch.FloatTensor shaped (1,1,64,64)
    - Exposes `step(action_dict)` where action_dict is a MineRL-style action
    - Provides `action_from_policy(move_logits, look_delta)` helper
    """
    def __init__(self, env, obs_size=(64, 64)):
        # `env` may be a gym.Env instance or a callable that returns one
        if callable(env):
            self.env = env()
        else:
            self.env = env
        self.obs_size = obs_size

    def reset(self):
        obs = self.env.reset()
        return self.obs_to_tensor(obs)

    def step(self, action_dict):
        next_obs, reward, done, info = self.env.step(action_dict)
        return self.obs_to_tensor(next_obs), float(reward), bool(done), info

    def close(self):
        try:
            self.env.close()
        except Exception:
            pass

    def obs_to_tensor(self, obs):
        """Convert env observation to a torch tensor (1,1,H,W) float32 normalized 0..1

        Expects `obs` to contain a 'pov' image (H,W,3) or be an image-like array.
        """
        img = None
        if isinstance(obs, dict) and 'pov' in obs:
            img = obs['pov']
        else:
            img = obs

        # Ensure numpy array
        if not isinstance(img, np.ndarray):
            img = np.array(img)

        # Convert RGB -> Grayscale
        if img.ndim == 3 and img.shape[2] == 3:
            # Use ITU-R 601-2 luma transform
            img = (0.2989 * img[..., 0] + 0.5870 * img[..., 1] + 0.1140 * img[..., 2]).astype(np.float32)
        elif img.ndim == 2:
            img = img.astype(np.float32)
        else:
            img = img.astype(np.float32)

        # Resize using PIL for simplicity
        im = Image.fromarray(img)
        im = im.resize(self.obs_size, resample=Image.BILINEAR)
        arr = np.array(im, dtype=np.float32)

        # Normalize to [0,1] and shape to (1,1,H,W)
        arr = arr / 255.0
        tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)
        return tensor

    def action_from_policy(self, move_logits, look_delta):
        """Map model outputs to a MineRL/Gym action dict.

        - `move_logits`: torch.Tensor shape (1, 8) corresponding to move logits
        - `look_delta`: torch.Tensor shape (1, 2) continuous camera delta
        """
        # Define mapping order matching PVPModel actor_move comment
        move_names = ['forward', 'left', 'back', 'right', 'jump', 'attack', 'swap_offhand', 'open_inventory']

        # Convert move logits -> discrete action index
        try:
            idx = int(torch.argmax(move_logits, dim=-1).item())
        except Exception:
            idx = 0

        action = {k: 0 for k in move_names}
        action[move_names[idx]] = 1

        # Camera: convert look_delta to python list
        try:
            cam = look_delta.squeeze(0).cpu().numpy().tolist()
        except Exception:
            cam = [0.0, 0.0]

        # MineRL expects camera as [yaw, pitch] or similar; put as 'camera'
        action['camera'] = cam

        return action
