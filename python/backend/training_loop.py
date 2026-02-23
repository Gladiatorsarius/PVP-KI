import socket
import json
import struct
import torch
import numpy as np
import cv2
import time
import threading
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
        self.client_socket = None  # Socket connection to Minecraft mod (set during loop)

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
        while not self.stop_event.is_set():
            try:
                # Example: Receive data from the socket
                data = self.receive_data()
                if data:
                    self.process_data(data)
            except Exception as e:
                print(f"Error in agent loop {self.name}: {e}")

    def receive_data(self):
        if not self.client_socket:
            return None
        try:
            data = self.client_socket.recv(1024)
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Error receiving data: {e}")
            return None

    def process_data(self, data):
        # Process incoming data from the Minecraft mod
        print(f"Processing data for {self.name}: {data}")

    def send_action(self, action):
        if not self.client_socket:
            print("No active connection to Minecraft mod")
            return
        try:
            self.client_socket.send(json.dumps(action).encode('utf-8'))
        except Exception as e:
            print(f"Error sending action: {e}")
