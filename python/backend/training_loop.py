import socket
import json
import struct
import torch
import numpy as np
import cv2
import time
import threading
try:
    from .ipc_connector import SocketConnector
except Exception:
    SocketConnector = None
try:
    from .model import PVPModel
    from .ppo_trainer import PPOTrainer, ExperienceBuffer
except Exception:
    from backend.model import PVPModel
    from backend.ppo_trainer import PPOTrainer, ExperienceBuffer

class AgentController:
    def __init__(self, name, port, shared_model=None, ppo_trainer=None, use_gym: bool = False, env_adapter=None):
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
        # Gym integration
        self.use_gym = use_gym
        self.env_adapter = env_adapter

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
        # Main worker loop for agent (training, bookkeeping). Supports two modes:
        #  - Gym mode: run env loop via `env_adapter`
        #  - Legacy mode: keep sleeping and let SocketConnector callbacks deliver frames
        if self.use_gym and self.env_adapter is not None:
            try:
                obs = self.env_adapter.reset()
                done = False
                while not self.stop_event.is_set():
                    # obs: torch.Tensor shaped (1,1,64,64)
                    state = obs
                    # Determine model to use
                    model = None
                    if self.ppo_trainer is not None and hasattr(self.ppo_trainer, 'model'):
                        model = self.ppo_trainer.model
                    elif self.shared_model is not None:
                        model = self.shared_model

                    if model is None:
                        # No model available yet; wait a bit
                        time.sleep(0.1)
                        continue

                    with torch.no_grad():
                        # Ensure batch dimension
                        if state.dim() == 3:
                            inp = state.unsqueeze(0)
                        else:
                            inp = state
                        move_logits, look_delta, value = model(inp)

                        # Map to action dict
                        try:
                            action = self.env_adapter.action_from_policy(move_logits, look_delta)
                        except Exception:
                            action = self.env_adapter.action_from_policy(move_logits, look_delta)

                        # Step environment
                        next_obs, reward, done, info = self.env_adapter.step(action)

                        # Optionally add experience to trainer buffer
                        if self.ppo_trainer is not None:
                            try:
                                # compute log probs for move and look
                                move_dist = torch.distributions.Categorical(logits=move_logits)
                                move_idx = int(torch.argmax(move_logits, dim=-1).item())
                                log_prob_move = move_dist.log_prob(torch.tensor(move_idx))
                                look_dist = torch.distributions.Normal(look_delta, 1.0)
                                # compute a scalar log_prob for the chosen look (sum over dims)
                                look_val = torch.tensor(look_delta.squeeze(0))
                                log_prob_look = look_dist.log_prob(look_val).sum()
                                # store state without batch dim
                                store_state = inp.squeeze(0)
                                self.ppo_trainer.buffer.add(store_state, move_idx, look_val, reward, done, log_prob_move, log_prob_look, value)
                            except Exception:
                                pass

                        obs = next_obs
                        if done:
                            obs = self.env_adapter.reset()
                    # yield briefly
                    time.sleep(0.01)
            except Exception as e:
                print(f"Error in agent Gym loop {self.name}: {e}")
            return

        # Legacy: wait and let SocketConnector callbacks drive processing
        while not self.stop_event.is_set():
            try:
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
