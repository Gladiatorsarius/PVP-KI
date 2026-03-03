from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import random

# Archived copy of backend_adaptor.py for reference. The active version has
# been moved to `python/backend/backend_adaptor.py` previously; this file
# preserves the original behavior in the archive folder.

class DummyBackendAdapter(QObject):
    started = pyqtSignal()
    stopped = pyqtSignal()
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    log = pyqtSignal(str)
    reward = pyqtSignal(float)

    def __init__(self, name, port, parent=None):
        super().__init__(parent)
        self.name = name
        self.port = port
        self._running = False
        self._connected = False
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._emit_metrics)

    def start(self):
        if self._running:
            return
        if not self._connected:
            self.log.emit(f"{self.name}: cannot start, not connected")
            return
        self._running = True
        self.log.emit(f"{self.name}: started (dummy)")
        self.started.emit()
        self._timer.start()

    def stop(self):
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        self.log.emit(f"{self.name}: stopped (dummy)")
        self.stopped.emit()

    def connect(self):
        if self._connected:
            return
        self._connected = True
        self.log.emit(f"{self.name}: connected (dummy)")
        self.connected.emit()

    def disconnect(self):
        if self._running:
            self.stop()
        if not self._connected:
            return
        self._connected = False
        self.log.emit(f"{self.name}: disconnected (dummy)")
        self.disconnected.emit()

    def _emit_metrics(self):
        r = round(random.uniform(-1.0, 1.0) * 100.0, 2)
        self.reward.emit(r)
        self.log.emit(f"{self.name}: reward={r}")

    def on_frame(self, header: dict, image):
        events = header.get('events', []) if isinstance(header, dict) else []
        for e in events:
            try:
                self.log.emit(f"{self.name}: event={e}")
            except Exception:
                pass

    def on_command(self, cmd: dict):
        try:
            self.log.emit(f"{self.name}: command={cmd}")
        except Exception:
            pass


class SimpleBackendAdapter(QObject):
    started = pyqtSignal()
    stopped = pyqtSignal()
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    log = pyqtSignal(str)
    reward = pyqtSignal(float)

    def __init__(self, agent_controller, parent=None):
        super().__init__(parent)
        self._ctrl = agent_controller
        self._connected = False

    def start(self):
        try:
            self._ctrl.start()
            self.log.emit(f"{self._ctrl.name}: started")
            self.started.emit()
        except Exception as e:
            self.log.emit(f"Error starting {self._ctrl.name}: {e}")

    def stop(self):
        try:
            self._ctrl.stop()
            self.log.emit(f"{self._ctrl.name}: stopped")
            self.stopped.emit()
        except Exception as e:
            self.log.emit(f"Error stopping {self._ctrl.name}: {e}")

    def connect(self):
        try:
            if hasattr(self._ctrl, 'connect'):
                self._ctrl.connect()
            self._connected = True
            self.log.emit(f"{self._ctrl.name}: connected")
            self.connected.emit()
        except Exception as e:
            self.log.emit(f"Error connecting {getattr(self._ctrl, 'name', '')}: {e}")

    def on_frame(self, header: dict, image):
        events = header.get('events', []) if isinstance(header, dict) else []
        for ev in events:
            if not isinstance(ev, str):
                continue
            if ev.startswith('EVENT:HIT:'):
                parts = ev.split(':')
                attacker = parts[2] if len(parts) > 2 else None
                target = parts[3] if len(parts) > 3 else None
                relation = parts[4] if len(parts) > 4 else None
                if relation == 'team':
                    self.log.emit(f"{self._ctrl.name}: teammate hit ignored ({attacker}->{target})")
                else:
                    try:
                        self.reward.emit(-1.0)
                        self.log.emit(f"{self._ctrl.name}: penalty applied for {attacker}->{target} (relation={relation})")
                    except Exception:
                        pass

    def on_command(self, cmd: dict):
        try:
            self.log.emit(f"{getattr(self._ctrl, 'name', '')}: command={cmd}")
            if isinstance(cmd, dict) and cmd.get('type') == 'RESET':
                try:
                    self.stop()
                    self.start()
                except Exception:
                    pass
        except Exception:
            pass

    def disconnect(self):
        try:
            if hasattr(self._ctrl, 'disconnect'):
                self._ctrl.disconnect()
            self._connected = False
            self.log.emit(f"{getattr(self._ctrl, 'name', '')}: disconnected")
            self.disconnected.emit()
        except Exception as e:
            self.log.emit(f"Error disconnecting {getattr(self._ctrl, 'name', '')}: {e}")

    def send_action(self, action):
        try:
            self._ctrl.send_action(action)
        except Exception as e:
            self.log.emit(f"Error sending action: {e}")
