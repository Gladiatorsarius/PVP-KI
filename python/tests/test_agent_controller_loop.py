import sys
import os
import time
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Minimal package mapping for module imports
pkg = types.ModuleType('python')
pkg.__path__ = [ROOT]
sys.modules['python'] = pkg
backend_pkg = types.ModuleType('python.backend')
backend_pkg.__path__ = [os.path.join(ROOT, 'backend')]
sys.modules['python.backend'] = backend_pkg

import importlib
training_loop = importlib.import_module('python.backend.training_loop')
env_adapter_mod = importlib.import_module('python.backend.env_adapter')
model_mod = importlib.import_module('python.backend.model')
ppo_mod = importlib.import_module('python.backend.ppo_trainer')

import torch
import numpy as np


class FastEnv:
    """Simple deterministic environment that runs for a few steps."""
    def __init__(self, max_steps=3, img_shape=(64, 64, 3)):
        self.max_steps = max_steps
        self._step = 0
        self.img_shape = img_shape

    def reset(self):
        self._step = 0
        return {'pov': np.zeros(self.img_shape, dtype=np.uint8)}

    def step(self, action):
        self._step += 1
        img = np.full(self.img_shape, fill_value=50 + self._step, dtype=np.uint8)
        reward = 1.0
        done = self._step >= self.max_steps
        return {'pov': img}, reward, done, {}


def test_agentcontroller_collects_experience():
    # create model and trainer
    model = model_mod.PVPModel()
    trainer = ppo_mod.PPOTrainer(model, batch_size=1024)

    # create env adapter using FastEnv
    env = FastEnv(max_steps=2)
    adapter = env_adapter_mod.GymEnvAdapter(env, obs_size=(64, 64))

    # create agent controller in gym mode
    agent = training_loop.AgentController('test', port=10000, shared_model=None, ppo_trainer=trainer, use_gym=True, env_adapter=adapter)

    # start agent and let it run briefly
    agent.start()
    deadline = time.time() + 2.0
    # wait until buffer has entries or timeout
    while time.time() < deadline:
        if len(trainer.buffer) > 0:
            break
        time.sleep(0.05)

    agent.stop()

    assert len(trainer.buffer) > 0, "Trainer buffer should have recorded experiences"
