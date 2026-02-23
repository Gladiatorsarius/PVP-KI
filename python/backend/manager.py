from .backend_adaptor import DummyBackendAdapter, SimpleBackendAdapter
from . import training_loop

class Manager:
    def __init__(self):
        self.agents = {}

    def create_agent(self, name, port, dummy=True, shared_model=None, ppo_trainer=None):
        """Create and return a backend adapter for an agent.
        By default returns a DummyBackendAdapter for quick testing. If dummy=False
        a real training_loop.AgentController is created and wrapped in a
        SimpleBackendAdapter.
        """
        if dummy:
            adapter = DummyBackendAdapter(name, port)
        else:
            ctrl = training_loop.AgentController(name, port, shared_model=shared_model, ppo_trainer=ppo_trainer)
            adapter = SimpleBackendAdapter(ctrl)
        self.agents[port] = adapter
        return adapter

    def remove_agent(self, port):
        adapter = self.agents.pop(port, None)
        if adapter:
            try:
                adapter.stop()
            except Exception:
                pass
