from .backend_adaptor import DummyBackendAdapter, SimpleBackendAdapter
from .command_connector import CommandConnector


class Manager:
    def __init__(self):
        self.agents = {}
        # Start command listener (Java ServerIPCClient sends to 127.0.0.1:9998)
        try:
            self._cmd = CommandConnector(self._handle_command)
            self._cmd.start()
        except Exception:
            self._cmd = None

    def _handle_command(self, cmd: dict):
        # Simple dispatcher for incoming commands. Expected shape: {"type":..., "data":...}
        cmd_type = cmd.get('type') if isinstance(cmd, dict) else None
        for port, adapter in list(self.agents.items()):
            try:
                # emit a log event on adapters for visibility
                if hasattr(adapter, 'log'):
                    try:
                        adapter.log.emit(f"CMD:{cmd_type}:{cmd.get('data')}")
                    except Exception:
                        pass
                # basic reset semantics
                if cmd_type == 'RESET':
                    try:
                        if hasattr(adapter, 'stop'):
                            adapter.stop()
                        if hasattr(adapter, 'start'):
                            adapter.start()
                    except Exception:
                        pass
            except Exception:
                pass

    def create_agent(self, name, port, dummy=False, shared_model=None, ppo_trainer=None):
        """Create and return a backend adapter for an agent.
        By default returns a real AgentController wrapped in SimpleBackendAdapter.
        Set `dummy=True` to use a DummyBackendAdapter instead for testing.
        """
        if dummy:
            adapter = DummyBackendAdapter(name, port)
        else:
            # Import training_loop lazily to avoid heavy deps at module import time
            from . import training_loop
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
