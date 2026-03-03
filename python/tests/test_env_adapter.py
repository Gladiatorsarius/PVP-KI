import sys
import os
import time
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Make a minimal package mapping so imports inside modules work
pkg = types.ModuleType('python')
pkg.__path__ = [ROOT]
sys.modules['python'] = pkg
backend_pkg = types.ModuleType('python.backend')
backend_pkg.__path__ = [os.path.join(ROOT, 'backend')]
sys.modules['python.backend'] = backend_pkg

import importlib
env_adapter_mod = importlib.import_module('python.backend.env_adapter')

import numpy as np
import torch


class DummyEnv:
    def __init__(self, steps=1, img_shape=(64, 64, 3)):
        self.steps = steps
        self._count = 0
        self.img_shape = img_shape

    def reset(self):
        self._count = 0
        img = np.zeros(self.img_shape, dtype=np.uint8)
        return {'pov': img}

    def step(self, action):
        self._count += 1
        img = np.ones(self.img_shape, dtype=np.uint8) * 128
        done = self._count >= self.steps
        reward = float(self._count)
        info = {'dummy': True}
        return {'pov': img}, reward, done, info


def test_obs_to_tensor_and_step():
    env = DummyEnv(steps=2)
    adapter = env_adapter_mod.GymEnvAdapter(env, obs_size=(64, 64))

    t = adapter.reset()
    assert isinstance(t, torch.Tensor)
    # shape (1,1,H,W)
    assert t.ndim == 4 and t.shape[0] == 1 and t.shape[1] == 1
    assert t.shape[2] == 64 and t.shape[3] == 64
    # values normalized 0..1
    assert 0.0 <= float(t.min()) and float(t.max()) <= 1.0

    # step once
    action = {'forward': 1, 'camera': [0.0, 0.0]}
    next_t, reward, done, info = adapter.step(action)
    assert isinstance(next_t, torch.Tensor)
    assert reward == 1.0
    assert done is False or done is True
    assert isinstance(info, dict)
