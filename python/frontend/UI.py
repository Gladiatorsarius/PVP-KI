from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QScrollArea, QGridLayout, QCheckBox, QLineEdit
from PyQt6.QtCore import QTimer

try:
    from .agent_controller import AgentControllerQt
except Exception:
    from python.frontend.agent_controller import AgentControllerQt

class MainWindow(QMainWindow):
    def __init__(self, manager=None):
        super().__init__()
        self.setWindowTitle("Multi-Agent PVP Training")
        self.setGeometry(100, 100, 1200, 700)

        # Main layout widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        # Add agent control buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Agent")
        self.remove_btn = QPushButton("- Remove Last")
        self.hide_btn = QPushButton("Hide All")
        self.show_btn = QPushButton("Show All")
        self.start_all_btn = QPushButton("Start All")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.hide_btn)
        btn_layout.addWidget(self.show_btn)
        btn_layout.addWidget(self.start_all_btn)
        main_layout.addLayout(btn_layout)
        
        # Connect buttons
        self.add_btn.clicked.connect(self.add_agent)
        self.remove_btn.clicked.connect(self.remove_agent)
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

        # Agent controllers list
        self.agent_controllers = []
        self.manager = manager
        if self.manager is None:
            try:
                from backend.manager import Manager as _Manager
            except Exception:
                from manager import Manager as _Manager
            self.manager = _Manager()

        # Manager status hooks for coordinator/log events
        try:
            self.manager.register_status_listener(self._on_manager_status)
        except Exception:
            pass

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._refresh_coordinator_status)
        self._status_timer.start()

        # Add two agents by default
        self.add_agent()
        self.add_agent()

    def add_agent(self):
        idx = len(self.agent_controllers)
        name = f"Agent {idx+1}"
        port = 9999 + idx
        backend = self.manager.create_agent(name, port, dummy=False)
        agent = AgentControllerQt(name, port, backend_adapter=backend)
        self.agent_controllers.append(agent)
        self.agent_panel_layout.addWidget(agent, idx//3, idx%3)  # Arrange in 3 columns

    def remove_agent(self):
        if self.agent_controllers:
            agent = self.agent_controllers.pop()
            agent.setParent(None)

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
        event_type = payload.get('type', 'unknown') if isinstance(payload, dict) else 'unknown'
        self.coordinator_label.setText(f"Coordinator event: {event_type}")

    def _refresh_coordinator_status(self):
        try:
            snapshot = self.manager.get_coordinator_status()
            if not snapshot:
                self.coordinator_label.setText("Coordinator: no agent sessions")
                return
            ready = sum(1 for item in snapshot.values() if item.get('state') == 'ready')
            running = sum(1 for item in snapshot.values() if item.get('state') == 'running')
            self.coordinator_label.setText(f"Coordinator: sessions={len(snapshot)} ready={ready} running={running}")
        except Exception:
            pass