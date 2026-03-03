from .backend_adaptor import DummyBackendAdapter, SimpleBackendAdapter


class Manager:
    def __init__(self):
        self.agents = {}
        # Prepare command listener but do not start it automatically.
        try:
            # try to import the optional CommandConnector (may be archived)
            from .command_connector import CommandConnector
            try:
                self._cmd = CommandConnector(self._handle_command)
            except Exception:
                self._cmd = None
        except Exception:
            self._cmd = None

    def start(self):
        """Start optional services (command listener)."""
        if getattr(self, '_cmd', None):
            try:
                self._cmd.start()
            except Exception:
                pass

    def stop(self):
        """Stop services cleanly."""
        if getattr(self, '_cmd', None):
            try:
                self._cmd.stop()
            except Exception:
                pass

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

    def create_agent(self, name, port, dummy=False, shared_model=None, ppo_trainer=None, use_gym: bool = False, env_name: str = None):
        """Create and return a backend adapter for an agent.
        By default returns a real AgentController wrapped in SimpleBackendAdapter.
        Set `dummy=True` to use a DummyBackendAdapter instead for testing.
        """
        if dummy:
            adapter = DummyBackendAdapter(name, port)
        else:
            # Import training_loop lazily to avoid heavy deps at module import time
            from . import training_loop
            env_adapter = None
            if use_gym and env_name:
                try:
                    # Lazy import to avoid requiring gym/minerl at module import time
                    from .env_adapter import GymEnvAdapter
                    import gym
                    env = lambda: gym.make(env_name)
                    env_adapter = GymEnvAdapter(env)
                except Exception:
                    env_adapter = None

            ctrl = training_loop.AgentController(name, port, shared_model=shared_model, ppo_trainer=ppo_trainer, use_gym=use_gym, env_adapter=env_adapter)
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
