from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import random

class DummyBackendAdapter(QObject):
    started = pyqtSignal()
    stopped = pyqtSignal()
    log = pyqtSignal(str)
    reward = pyqtSignal(float)

    def __init__(self, name, port, parent=None):
        super().__init__(parent)
        self.name = name
        self.port = port
        self._running = False
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._emit_metrics)

    def start(self):
        if self._running:
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

    def _emit_metrics(self):
        # Emit a random reward and a small log message
        r = round(random.uniform(-1.0, 1.0) * 100.0, 2)
        self.reward.emit(r)
        self.log.emit(f"{self.name}: reward={r}")


class SimpleBackendAdapter(QObject):
    """Simple adapter that wraps a real AgentController instance.
    It exposes the same signals but does not fabricate metrics. Useful to call
    start/stop on the controller and emit started/stopped/log events.
    """
    started = pyqtSignal()
    stopped = pyqtSignal()
    log = pyqtSignal(str)
    reward = pyqtSignal(float)

    def __init__(self, agent_controller, parent=None):
        super().__init__(parent)
        self._ctrl = agent_controller

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

    def send_action(self, action):
        try:
            self._ctrl.send_action(action)
        except Exception as e:
            self.log.emit(f"Error sending action: {e}")
