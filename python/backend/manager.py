from .backend_adapter import DummyBackendAdapter, SimpleBackendAdapter


class Manager:
    def __init__(self):
        self.agents = {}
        self._status_listeners = []

        try:
            from .command_bridge import CommandConnector
            try:
                self._cmd = CommandConnector(self._handle_command)
            except Exception:
                self._cmd = None
        except Exception:
            self._cmd = None

        try:
            from .coordinator import WebSocketCoordinator
            self._coordinator = WebSocketCoordinator(status_hook=self._on_coordinator_status)
        except Exception:
            self._coordinator = None

    def start(self):
        """Start optional services (command listener + coordinator)."""
        if getattr(self, '_cmd', None):
            try:
                self._cmd.start()
                self._emit_status({'type': 'command_connector_started'})
            except Exception as exc:
                self._emit_status({'type': 'command_connector_error', 'error': str(exc)})

        self.start_coordinator()

    def stop(self):
        """Stop services cleanly."""
        if getattr(self, '_cmd', None):
            try:
                self._cmd.stop()
                self._emit_status({'type': 'command_connector_stopped'})
            except Exception:
                pass

        self.stop_coordinator()

    def start_coordinator(self):
        if not getattr(self, '_coordinator', None):
            self._emit_status({'type': 'coordinator_unavailable'})
            return False
        try:
            started = self._coordinator.start()
            if started:
                self._emit_status({'type': 'coordinator_start_requested'})
            return bool(started)
        except Exception as exc:
            self._emit_status({'type': 'coordinator_error', 'error': str(exc)})
            return False

    def stop_coordinator(self):
        if not getattr(self, '_coordinator', None):
            return
        try:
            self._coordinator.stop()
            self._emit_status({'type': 'coordinator_stop_requested'})
        except Exception:
            pass

    def start_all(self):
        """Global Start-All path for VM sessions that are currently ready."""
        if not getattr(self, '_coordinator', None):
            self._emit_status({'type': 'start_all_skipped', 'reason': 'coordinator_unavailable'})
            return
        self._coordinator.start_all()

    def get_coordinator_status(self):
        if not getattr(self, '_coordinator', None):
            return {}
        try:
            return self._coordinator.status_snapshot()
        except Exception:
            return {}

    def register_status_listener(self, listener):
        if listener and listener not in self._status_listeners:
            self._status_listeners.append(listener)

    def _emit_status(self, payload: dict):
        for listener in list(self._status_listeners):
            try:
                listener(payload)
            except Exception:
                pass

    def _on_coordinator_status(self, payload: dict):
        self._emit_status(payload)

    def _handle_command(self, cmd: dict):
        cmd_type = cmd.get('type') if isinstance(cmd, dict) else None
        if cmd_type == 'START_ALL':
            self.start_all()

        for _, adapter in list(self.agents.items()):
            try:
                if hasattr(adapter, 'log'):
                    try:
                        adapter.log.emit(f"CMD:{cmd_type}:{cmd.get('data')}")
                    except Exception:
                        pass
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
