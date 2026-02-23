from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QScrollArea, QGridLayout

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

        # Add/Remove agent buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Agent")
        self.remove_btn = QPushButton("- Remove Last")
        self.hide_btn = QPushButton("Hide All")
        btn_layout.addWidget(self.hide_btn)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        main_layout.addLayout(btn_layout)

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

        # Agent controllers list
        self.agent_controllers = []
        self.manager = manager
        if self.manager is None:
            try:
                from backend.manager import Manager as _Manager
            except Exception:
                from manager import Manager as _Manager
            self.manager = _Manager()

        # Connect buttons
        self.add_btn.clicked.connect(self.add_agent)
        self.remove_btn.clicked.connect(self.remove_agent)
        self.hide_btn.clicked.connect(self.toggle_agents_visibility)
        # Add two agents by default
        self.add_agent()
        self.add_agent()

    def add_agent(self):
        idx = len(self.agent_controllers)
        name = f"Agent {idx+1}"
        port = 9999 + idx
        backend = self.manager.create_agent(name, port, dummy=True)
        agent = AgentControllerQt(name, port, backend_adapter=backend)
        self.agent_controllers.append(agent)
        self.agent_panel_layout.addWidget(agent, idx//3, idx%3)  # Arrange in 3 columns

    def remove_agent(self):
        if self.agent_controllers:
            agent = self.agent_controllers.pop()
            agent.setParent(None)

    def toggle_agents_visibility(self):