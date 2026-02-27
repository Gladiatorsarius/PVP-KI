import socket
import json
import struct
import torch
import numpy as np
import cv2
import time
import threading
from .ipc_connector import SocketConnector
try:
    from .model import PVPModel
    from .ppo_trainer import PPOTrainer, ExperienceBuffer
except Exception:
    from backend.model import PVPModel
    from backend.ppo_trainer import PPOTrainer, ExperienceBuffer

class AgentController:
    def __init__(self, name, port, shared_model=None, ppo_trainer=None):
        self.name = name
        self.port = port
        self.agent_id = port  # Use port as unique agent ID
        self.running = False
        self.stop_event = threading.Event()
        self.thread = None
        self.shared_model = shared_model
        self.ppo_trainer = ppo_trainer
        self.client_socket = None  # legacy field
        self.socket = None  # SocketConnector instance

    def start(self):
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join()

    def run_loop(self):
        # Main worker loop for agent (training, bookkeeping). Incoming frames
        # are handled by the SocketConnector _on_frame callback.
        while not self.stop_event.is_set():
            try:
                # sleep briefly to yield CPU and allow callbacks to run
                time.sleep(0.1)
            except Exception as e:
                print(f"Error in agent loop {self.name}: {e}")

    def receive_data(self):
        # legacy method kept for compatibility
        return None

    def process_data(self, data):
        # Process incoming data from the Minecraft mod
        print(f"Processing data for {self.name}: {data}")

    # --- new socket-based methods ---
    def connect(self, host: str = '127.0.0.1'):
        if self.socket:
            return
        self.socket = SocketConnector(host=host, port=self.port,
                                      on_message=self._on_frame,
                                      on_disconnect=self._on_disconnect)
        self.socket.start()

    def disconnect(self):
        if self.socket:
            try:
                self.socket.stop()
            except Exception:
                pass
            self.socket = None

    def _on_frame(self, header: dict, body: bytes):
        # Called from SocketConnector reader thread when a full frame arrives.
        try:
            # decode image if present
            img = None
            if body:
                img = SocketConnector.decode_image(body)
            # deliver header and image to processing pipeline
            self.process_data({'header': header, 'image': img})
        except Exception as e:
            print(f"Error processing frame for {self.name}: {e}")

    def _on_disconnect(self):
        print(f"Agent {self.name} disconnected from port {self.port}")

    def send_action(self, action):
        if not self.socket:
            print("No active connection to Minecraft mod")
            return
        try:
            payload = json.dumps(action).encode('utf-8')
            # Java side expects a unsigned short length prefix for actions
            self.socket.send_prefixed(payload, length_bytes=2)
        except Exception as e:
            print(f"Error sending action: {e}")
