from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QScrollArea, QGridLayout
from PyQt6.QtCore import QTimer, pyqtSignal

try:
    from .agent_controller import AgentControllerQt
except Exception:
    from frontend.agent_controller import AgentControllerQt

class MainWindow(QMainWindow):
    manager_status_signal = pyqtSignal(dict)

    def __init__(self, manager=None):
        super().__init__()
        self.setWindowTitle("Multi-Agent PVP Training")
        self.setGeometry(100, 100, 1200, 700)

        # Main layout widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        # Global control buttons
        btn_layout = QHBoxLayout()
        self.hide_btn = QPushButton("Hide All")
        self.show_btn = QPushButton("Show All")
        self.start_all_btn = QPushButton("Start All")
        btn_layout.addWidget(self.hide_btn)
        btn_layout.addWidget(self.show_btn)
        btn_layout.addWidget(self.start_all_btn)
        main_layout.addLayout(btn_layout)
        
        # Connect buttons
        self.hide_btn.clicked.connect(self.hide_all_agents)
        self.show_btn.clicked.connect(self.show_all_agents)
        self.start_all_btn.clicked.connect(self.start_all)
        
        # Scroll area for agents
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.agent_panel = QWidget()
        self.agent_panel_layout = QGridLayout()
        self.agent_panel.setLayout(self.agent_panel_layout)
        self.scroll.setWidget(self.agent_panel)
        main_layout.addWidget(self.scroll)

        # Metrics label
        self.metrics_label = QLabel("No training data yet")
        main_layout.addWidget(self.metrics_label)
        self.coordinator_label = QLabel("Coordinator: unknown")
        main_layout.addWidget(self.coordinator_label)

        # Agent controllers list + lookup
        self.agent_controllers = []
        self.agent_controllers_by_id = {}
        self.manager = manager
        if self.manager is None:
            try:
                from backend.manager import Manager as _Manager
            except Exception:
                from manager import Manager as _Manager
            self.manager = _Manager()

        # Route backend thread status updates safely onto the Qt UI thread.
        self.manager_status_signal.connect(self._handle_manager_status)

        # Manager status hooks for coordinator/log events
        try:
            self.manager.register_status_listener(self._on_manager_status)
        except Exception:
            pass

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._refresh_coordinator_status)
        self._status_timer.start()

    def add_agent(self, agent_id, session_id=None, episode_id=None):
        try:
            agent_id = int(agent_id)
        except Exception:
            return

        if agent_id in self.agent_controllers_by_id:
            return

        idx = len(self.agent_controllers)
        name = f"Agent {agent_id}"
        # VM clients connect over the coordinator socket, not a per-agent local port.
        coordinator_port = getattr(getattr(self.manager, '_coordinator', None), 'port', 0)
        agent = AgentControllerQt(name, coordinator_port, backend_adapter=None)

        # Keep widget read-only for coordinator-managed sessions.
        try:
            agent.start_btn.setEnabled(False)
            agent.stop_btn.setEnabled(False)
            agent.status_label.setText("Status: Connected")
            if session_id or episode_id:
                agent.log(f"Auto-registered: session={session_id} episode={episode_id}")
            else:
                agent.log("Auto-registered from VM client")
        except Exception:
            pass

        self.agent_controllers.append(agent)
        self.agent_controllers_by_id[agent_id] = agent
        self.agent_panel_layout.addWidget(agent, idx // 3, idx % 3)

    def remove_agent(self, agent_id):
        try:
            agent_id = int(agent_id)
        except Exception:
            return

        agent = self.agent_controllers_by_id.pop(agent_id, None)
        if not agent:
            return

        try:
            self.agent_panel_layout.removeWidget(agent)
        except Exception:
            pass
        if agent in self.agent_controllers:
            self.agent_controllers.remove(agent)
        agent.setParent(None)
        agent.deleteLater()
        self._reflow_agent_grid()

    def _reflow_agent_grid(self):
        for idx, agent in enumerate(self.agent_controllers):
            self.agent_panel_layout.addWidget(agent, idx // 3, idx % 3)

    def _set_agent_status(self, agent_id, text):
        try:
            agent_id = int(agent_id)
        except Exception:
            return
        agent = self.agent_controllers_by_id.get(agent_id)
        if not agent:
            return
        try:
            agent.status_label.setText(text)
            agent.log(text)
        except Exception:
            pass
        
    def hide_all_agents(self):
        for agent in self.agent_controllers:
            agent._set_visible(False)

    def show_all_agents(self):
        for agent in self.agent_controllers:
            agent._set_visible(True)

    def start_all(self):
        try:
            self.manager.start_all()
            self.metrics_label.setText("Start-All requested")
        except Exception as exc:
            self.metrics_label.setText(f"Start-All failed: {exc}")

    def _on_manager_status(self, payload: dict):
        # Called by manager/coordinator worker threads.
        try:
            self.manager_status_signal.emit(payload if isinstance(payload, dict) else {})
        except Exception:
            pass

    def _handle_manager_status(self, payload: dict):
        event_type = payload.get('type', 'unknown') if isinstance(payload, dict) else 'unknown'
        self.coordinator_label.setText(f"Coordinator event: {event_type}")

        if event_type == 'agent_registered':
            self.add_agent(
                agent_id=payload.get('agent_id'),
                session_id=payload.get('session_id'),
                episode_id=payload.get('episode_id'),
            )
        elif event_type == 'agent_disconnected':
            self.remove_agent(payload.get('agent_id'))
        elif event_type == 'agent_ready':
            self._set_agent_status(payload.get('agent_id'), 'Status: Ready')
        elif event_type == 'start_sent':
            self._set_agent_status(payload.get('agent_id'), 'Status: Running')

    def _refresh_coordinator_status(self):
        try:
            snapshot = self.manager.get_coordinator_status()
            if not snapshot:
                self.coordinator_label.setText("Coordinator: no agent sessions")
                return

            # Backfill UI widgets in case events were missed before UI listener binding.
            for agent_id, item in snapshot.items():
                self.add_agent(agent_id=agent_id, session_id=item.get('session_id'), episode_id=item.get('episode_id'))

            ready = sum(1 for item in snapshot.values() if item.get('state') == 'ready')
            running = sum(1 for item in snapshot.values() if item.get('state') == 'running')
            self.coordinator_label.setText(f"Coordinator: sessions={len(snapshot)} ready={ready} running={running}")
        except Exception:
            pass