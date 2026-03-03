"""Optional dataset utilities for MineRL imitation pretraining.

This module guards the `minerl` import so the code can run even if `minerl`
is not installed. Use `DatasetLoader` to access `minerl.data.make` when
available.
"""
from typing import Optional

try:
    import minerl
except Exception:
    minerl = None

class DatasetLoader:
    def __init__(self, env_name: str, data_dir: Optional[str] = None):
        if minerl is None:
            raise RuntimeError("minerl is not installed; install it to use DatasetLoader")
        self.env_name = env_name
        self.data_dir = data_dir

    def make(self):
        if minerl is None:
            raise RuntimeError("minerl is not installed")
        return minerl.data.make(self.env_name, data_dir=self.data_dir)

    def batch_iter(self, batch_size=32, epochs=1, **kwargs):
        data = self.make()
        # generator wrapper; minesrl's API provides `batch_iter` on data
        for _ in range(epochs):
            for item in data.batch_iter(batch_size=batch_size, **kwargs):
                yield item
