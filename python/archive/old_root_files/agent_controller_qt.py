# PyQt6 version of AgentController (moved to python/)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox, QTextEdit, QGroupBox, QScrollArea, QGridLayout)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
try:
    from .backend_adaptor import DummyBackendAdapter
except Exception:
    from backend_adaptor import DummyBackendAdapter

class AgentControllerQt(QWidget):
    def __init__(self, name, port, shared_model=None, ppo_trainer=None, backend_adapter=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.port = port
        self.shared_model = shared_model
        self.ppo_trainer = ppo_trainer
        self.setMinimumWidth(350)
        self.setMaximumWidth(400)
        self.setContentsMargins(5, 5, 5, 5)
        self.backend = backend_adapter or DummyBackendAdapter(name, port)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Title
        title = QLabel(f"{name} (Port {port})")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        main_layout.addWidget(title)

        # Reward Config
        reward_group = QGroupBox("Rewards")
        reward_layout = QGridLayout()
        reward_group.setLayout(reward_layout)
        self.win_reward = QLineEdit("500.0")
        self.loss_penalty = QLineEdit("-500.0")
        self.damage_dealt = QLineEdit("10.0")
        self.damage_taken = QLineEdit("-10.0")
        self.time_penalty = QLineEdit("-0.1")
        self.team_hit_penalty = QLineEdit("-50.0")
        self.team_kill_penalty = QLineEdit("-500.0")
        reward_layout.addWidget(QLabel("Win:"), 0, 0)
        reward_layout.addWidget(self.win_reward, 0, 1)
        reward_layout.addWidget(QLabel("Loss:"), 1, 0)
        reward_layout.addWidget(self.loss_penalty, 1, 1)
        reward_layout.addWidget(QLabel("Dmg Dealt:"), 2, 0)
        reward_layout.addWidget(self.damage_dealt, 2, 1)
        reward_layout.addWidget(QLabel("Dmg Taken:"), 3, 0)
        reward_layout.addWidget(self.damage_taken, 3, 1)
        reward_layout.addWidget(QLabel("Time:"), 4, 0)
        reward_layout.addWidget(self.time_penalty, 4, 1)
        reward_layout.addWidget(QLabel("Team Hit:"), 5, 0)
        reward_layout.addWidget(self.team_hit_penalty, 5, 1)
        reward_layout.addWidget(QLabel("Team Kill:"), 6, 0)
        reward_layout.addWidget(self.team_kill_penalty, 6, 1)
        main_layout.addWidget(reward_group)

        # Status and Reward Display
        self.status_label = QLabel("Status: Stopped")
        main_layout.addWidget(self.status_label)
        self.reward_label = QLabel("Reward: 0.0")
        self.reward_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        main_layout.addWidget(self.reward_label)

        # Action Toggles
        actions_group = QGroupBox("Enable Actions")
        actions_layout = QGridLayout()
        actions_group.setLayout(actions_layout)
        self.action_enabled = {}
        action_names = [
            ("Forward", 'forward'), ("Back", 'backward'), ("Left", 'left'), ("Right", 'right'),
            ("Sprint", 'sprint'), ("Sneak", 'sneak'), ("Jump", 'jump'), ("Attack", 'attack'),
            ("Use", 'use'), ("Hotkeys 1-9", 'hotkeys'), ("Mouse Look", 'mouse'),
            ("Swap Offhand (F)", 'swap_offhand'), ("Open Inventory (E)", 'open_inventory')
        ]
        for i, (label, key) in enumerate(action_names):
            cb = QCheckBox(label)
            cb.setChecked(key in ['forward','backward','left','right','attack','mouse'])
            self.action_enabled[key] = cb
            actions_layout.addWidget(cb, i//3, i%3)
        main_layout.addWidget(actions_group)

        # Log area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(80)
        main_layout.addWidget(self.log_text)

        # Control buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        main_layout.addLayout(btn_layout)

        # TODO: Add test input buttons, apply-to-all, and connect logic
        # Connect start/stop to backend adapter
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.stop_btn.clicked.connect(self._on_stop_clicked)

        # Wire backend signals to the UI
        try:
            self.backend.log.connect(self.log)
            self.backend.reward.connect(self._on_reward)
            self.backend.started.connect(self._on_started)
            self.backend.stopped.connect(self._on_stopped)
        except Exception:
            # backend may be a plain object without signals
            pass

    def _on_start_clicked(self):
        try:
            self.backend.start()
        except Exception as e:
            self.log(f"Error starting backend: {e}")

    def _on_stop_clicked(self):
        try:
            self.backend.stop()
        except Exception as e:
            self.log(f"Error stopping backend: {e}")

    def _on_started(self):
        self.status_label.setText("Status: Running")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_stopped(self):
        self.status_label.setText("Status: Stopped")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_reward(self, value):
        try:
            self.reward_label.setText(f"Reward: {value}")
        except Exception:
            pass

    def log(self, msg):
        self.log_text.append(msg)
