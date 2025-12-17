import socket
import json
import struct
import torch
import numpy as np
import time
import threading
import tkinter as tk
from tkinter import ttk
from model import PVPModel
from ppo_trainer import PPOTrainer, ExperienceBuffer

class AgentController:
    def __init__(self, parent, name, port, shared_model=None, ppo_trainer=None):
        self.name = name
        self.port = port
        self.running = False
        self.stop_event = threading.Event()
        self.thread = None
        self.shared_model = shared_model
        self.ppo_trainer = ppo_trainer
        self.ipcManager = None  # Reference to IPC manager for test inputs

        # UI Frame with scroll
        self.frame = ttk.LabelFrame(parent, text=f"{name} (Port {port})")
        self.frame.pack(side="left", padx=10, pady=10, fill="both", expand=True)
        
        # Create scrollable inner frame
        canvas = tk.Canvas(self.frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mousewheel scrolling (per-agent canvas to avoid stale bindings)
        self.canvas = canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Use scrollable_frame for all content
        content_frame = self.scrollable_frame

        # Reward Config
        config_frame = ttk.LabelFrame(content_frame, text="Rewards")
        config_frame.pack(padx=5, pady=5, fill="x")

        self.win_reward = self.create_input(config_frame, "Win:", "500.0")
        self.loss_penalty = self.create_input(config_frame, "Loss:", "-500.0")
        self.damage_dealt = self.create_input(config_frame, "Dmg Dealt:", "10.0")
        self.damage_taken = self.create_input(config_frame, "Dmg Taken:", "-10.0")
        self.time_penalty = self.create_input(config_frame, "Time:", "-0.1")
        self.team_hit_penalty = self.create_input(config_frame, "Team Hit:", "-50.0")
        self.team_kill_penalty = self.create_input(config_frame, "Team Kill:", "-500.0")

        # Controls
        btn_frame = ttk.Frame(content_frame)
        btn_frame.pack(pady=10)
        
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        self.apply_all_btn = ttk.Button(btn_frame, text="Apply to All", command=lambda: self.apply_to_all())
        self.apply_all_btn.pack(side="left", padx=5)

        # Status
        self.status_var = tk.StringVar(value="Status: Stopped")
        ttk.Label(content_frame, textvariable=self.status_var).pack(pady=5)

        # Reward Display
        self.reward_var = tk.StringVar(value="Reward: 0.0")
        ttk.Label(content_frame, textvariable=self.reward_var, font=("Arial", 12, "bold")).pack(pady=5)
        self.total_reward = 0.0

        self.log_text = tk.Text(content_frame, height=15, width=30, state="disabled")
        self.log_text.pack(padx=5, pady=5, fill="both", expand=True)

        # Available Actions Panel
        actions_frame = ttk.LabelFrame(content_frame, text="Available Actions")
        actions_frame.pack(padx=5, pady=5, fill="x")
        
        ttk.Label(actions_frame, text="TOGGLE (hold):", font=("Arial", 8, "bold")).pack(anchor="w", padx=5)
        ttk.Label(actions_frame, text="• forward, backward, left, right", font=("Arial", 8)).pack(anchor="w", padx=15)
        ttk.Label(actions_frame, text="• sprint, sneak", font=("Arial", 8)).pack(anchor="w", padx=15)
        
        ttk.Label(actions_frame, text="ONCE (single frame):", font=("Arial", 8, "bold")).pack(anchor="w", padx=5, pady=(5,0))
        ttk.Label(actions_frame, text="• jump, attack, use", font=("Arial", 8)).pack(anchor="w", padx=15)
        ttk.Label(actions_frame, text="• swap_offhand (F), open_inventory (E)", font=("Arial", 8)).pack(anchor="w", padx=15)
        ttk.Label(actions_frame, text="• hotkey1-9 (slots)", font=("Arial", 8)).pack(anchor="w", padx=15)
        ttk.Label(actions_frame, text="• mouse_dx, mouse_dy (look)", font=("Arial", 8)).pack(anchor="w", padx=15)

        # Action Configuration (Enable/Disable)
        config_actions_frame = ttk.LabelFrame(content_frame, text="Enable Actions")
        config_actions_frame.pack(padx=5, pady=5, fill="x")
        
        # Store action enable states (default: basic PVP only)
        self.action_enabled = {
            'forward': tk.BooleanVar(value=True),
            'backward': tk.BooleanVar(value=True),
            'left': tk.BooleanVar(value=True),
            'right': tk.BooleanVar(value=True),
            'sprint': tk.BooleanVar(value=False),
            'sneak': tk.BooleanVar(value=False),
            'jump': tk.BooleanVar(value=False),
            'attack': tk.BooleanVar(value=True),
            'use': tk.BooleanVar(value=False),
            'swap_offhand': tk.BooleanVar(value=False),
            'open_inventory': tk.BooleanVar(value=False),
            'hotkeys': tk.BooleanVar(value=False),  # All hotkeys 1-9
            'mouse': tk.BooleanVar(value=True)  # Look (yaw/pitch)
        }
        
        # Create checkboxes in compact grid
        row1 = ttk.Frame(config_actions_frame)
        row1.pack(fill="x", padx=5, pady=2)
        ttk.Checkbutton(row1, text="Forward", variable=self.action_enabled['forward']).pack(side="left", padx=3)
        ttk.Checkbutton(row1, text="Back", variable=self.action_enabled['backward']).pack(side="left", padx=3)
        ttk.Checkbutton(row1, text="Left", variable=self.action_enabled['left']).pack(side="left", padx=3)
        ttk.Checkbutton(row1, text="Right", variable=self.action_enabled['right']).pack(side="left", padx=3)
        
        row2 = ttk.Frame(config_actions_frame)
        row2.pack(fill="x", padx=5, pady=2)
        ttk.Checkbutton(row2, text="Sprint", variable=self.action_enabled['sprint']).pack(side="left", padx=3)
        ttk.Checkbutton(row2, text="Sneak", variable=self.action_enabled['sneak']).pack(side="left", padx=3)
        ttk.Checkbutton(row2, text="Jump", variable=self.action_enabled['jump']).pack(side="left", padx=3)
        ttk.Checkbutton(row2, text="Attack", variable=self.action_enabled['attack']).pack(side="left", padx=3)
        
        row3 = ttk.Frame(config_actions_frame)
        row3.pack(fill="x", padx=5, pady=2)
        ttk.Checkbutton(row3, text="Use", variable=self.action_enabled['use']).pack(side="left", padx=3)
        ttk.Checkbutton(row3, text="Hotkeys 1-9", variable=self.action_enabled['hotkeys']).pack(side="left", padx=3)
        ttk.Checkbutton(row3, text="Mouse Look", variable=self.action_enabled['mouse']).pack(side="left", padx=3)
        
        row4 = ttk.Frame(config_actions_frame)
        row4.pack(fill="x", padx=5, pady=2)
        ttk.Checkbutton(row4, text="Swap Offhand (F)", variable=self.action_enabled['swap_offhand']).pack(side="left", padx=3)
        ttk.Checkbutton(row4, text="Open Inventory (E)", variable=self.action_enabled['open_inventory']).pack(side="left", padx=3)
        
        # Apply actions to all button
        ttk.Button(config_actions_frame, text="Apply to All Agents", 
                  command=lambda: self.apply_actions_to_all()).pack(pady=5)

        # Test Input Buttons (19 total inputs)
        test_frame = ttk.LabelFrame(content_frame, text="Test Inputs (Click to Inject)")
        test_frame.pack(padx=5, pady=5, fill="x")
        
        # Input mapping: 1-9=hotkeys, 10-13=WASD, 14=sneak, 15=sprint, 16=left_click, 17=jump, 18=right_click, 19=offhand
        self.input_names = [
            "1:Hotkey1", "2:Hotkey2", "3:Hotkey3", "4:Hotkey4", "5:Hotkey5",
            "6:Hotkey6", "7:Hotkey7", "8:Hotkey8", "9:Hotkey9",
            "10:W", "11:A", "12:S", "13:D",
            "14:Sneak", "15:Sprint", "16:LClick", "17:Jump", "18:RClick", "19:Offhand"
        ]
        
        # Create test buttons in rows
        for i in range(0, 19, 5):
            btn_row = ttk.Frame(test_frame)
            btn_row.pack(fill="x", padx=5, pady=2)
            for j in range(i, min(i + 5, 19)):
                label = self.input_names[j].split(":")[1]
                ttk.Button(btn_row, text=label, width=8, 
                          command=lambda idx=j: self.send_test_input(idx)).pack(side="left", padx=2)

    def send_test_input(self, input_idx):
        """Send a single test input to the mod"""
        if not self.ipcManager:
            self.log("IPC not connected")
            return
        
        # Map input index to action
        action = {
            0: {'hotkey1': True}, 1: {'hotkey2': True}, 2: {'hotkey3': True}, 3: {'hotkey4': True}, 4: {'hotkey5': True},
            5: {'hotkey6': True}, 6: {'hotkey7': True}, 7: {'hotkey8': True}, 8: {'hotkey9': True},
            9: {'forward': True}, 10: {'left': True}, 11: {'back': True}, 12: {'right': True},
            13: {'sneak': True}, 14: {'sprint': True}, 15: {'attack': True}, 16: {'jump': True},
            17: {'use': True}, 18: {'swap_offhand': True}
        }
        
        if input_idx in action:
            try:
                self.log(f"Test button clicked: {self.input_names[input_idx]}")
                rb = json.dumps(action[input_idx]).encode('utf-8')
                if self.ipcManager and getattr(self.ipcManager, 'currentOut', None):
                    self.ipcManager.currentOut.write(struct.pack('>H', len(rb)))
                    self.ipcManager.currentOut.write(rb)
                    self.ipcManager.currentOut.flush()
                    self.log(f"Sent test input {self.input_names[input_idx]}")
                else:
                    self.log("IPC not connected for test input")
            except Exception as e:
                self.log(f"Error sending test input: {e}")

    def create_input(self, parent, label, default):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=1)
        ttk.Label(f, text=label, width=15).pack(side="left")
        var = tk.DoubleVar(value=float(default))
        ttk.Entry(f, textvariable=var).pack(side="right", expand=True, fill="x")
        return var

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _on_mousewheel(self, event):
        # Safe scroll handler that ignores destroyed canvases
        if not hasattr(self, 'canvas') or self.canvas is None:
            return
        if not self.canvas.winfo_exists():
            return
        try:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except tk.TclError:
            pass

    def start(self):
        if self.running: return
        self.running = True
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Status: Running")
        self.log("Start clicked")
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running: return
        self.running = False
        self.stop_event.set()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Status: Stopping...")
        self.log("Stop clicked")

    def recv_exact(self, sock, n):
        data = b''
        while len(data) < n:
            if self.stop_event.is_set(): return None
            try:
                sock.settimeout(1.0)
                packet = sock.recv(n - len(data))
                if not packet: return None
                data += packet
            except socket.timeout: continue
            except: return None
        return data


    def loop(self):
        self.log(f"Listening on {self.port}...")
        client = None
        
        while not self.stop_event.is_set():
            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.connect(('127.0.0.1', self.port))
                self.log("Connected!")
                break
            except ConnectionRefusedError:
                if self.stop_event.is_set(): return
                time.sleep(1)

        if self.stop_event.is_set(): return

        # Use shared model if available, otherwise create local
        if self.shared_model is not None:
            model = self.shared_model
            model.train()  # Training mode for PPO
        else:
            model = PVPModel()
            model.eval()
        
        last_health = 20.0
        self.total_reward = 0.0  # Reset reward at start
        last_state = None

        try:
            while not self.stop_event.is_set():
                # Header Length
                lb = self.recv_exact(client, 4)
                if not lb: break
                hlen = struct.unpack('>I', lb)[0]

                # Header
                hdata = self.recv_exact(client, hlen)
                if not hdata: break
                header = json.loads(hdata.decode('utf-8'))

                # Check for server commands in header
                if 'cmd_type' in header:
                    self.handle_server_command(header)

                # Body
                blen = header['bodyLength']
                img_data = self.recv_exact(client, blen)
                if not img_data: break

                # Rewards
                reward = self.time_penalty.get()
                curr_health = header.get('health', 20.0)
                
                if curr_health < last_health:
                    reward += (last_health - curr_health) * self.damage_taken.get()
                last_health = curr_health

                for evt in header.get('events', []):
                    parts = evt.split(':')
                    if len(parts) >= 3:
                        etype = parts[1]
                        if etype == 'HIT':
                            reward += self.damage_dealt.get()
                        elif etype == 'DEATH':
                            if curr_health <= 0:
                                reward += self.loss_penalty.get()
                                self.log("LOSS")
                                self.total_reward += reward  # Add final reward and reset
                                self.frame.after(0, lambda: self.reward_var.set(f"Reward: 0.0"))
                                self.total_reward = 0.0
                            else:
                                reward += self.win_reward.get()
                                self.log("WIN")
                                self.total_reward += reward  # Add final reward and reset
                                self.frame.after(0, lambda: self.reward_var.set(f"Reward: 0.0"))
                                self.total_reward = 0.0

                # Accumulate reward
                self.total_reward += reward
                # Update display
                self.frame.after(0, lambda r=self.total_reward: self.reward_var.set(f"Reward: {r:.1f}"))

                # Inference - Convert to grayscale (3x faster than RGB)
                w, h = header['width'], header['height']
                img_rgb = np.frombuffer(img_data, dtype=np.uint8).reshape((h, w, 3))
                # Convert RGB to grayscale: 0.299*R + 0.587*G + 0.114*B
                img_gray = (0.299 * img_rgb[:,:,0] + 0.587 * img_rgb[:,:,1] + 0.114 * img_rgb[:,:,2]).astype(np.uint8)
                state_tensor = torch.from_numpy(img_gray).float().unsqueeze(0).unsqueeze(0) / 255.0  # (1, 1, H, W)
                
                # Forward pass through model
                with torch.no_grad():
                    move_logits, look_delta, value = model(state_tensor)
                
                # Sample actions from distributions
                move_dist = torch.distributions.Categorical(logits=move_logits)
                look_dist = torch.distributions.Normal(look_delta, 1.0)
                
                action_move = move_dist.sample()
                action_look = look_dist.sample()
                
                log_prob_move = move_dist.log_prob(action_move)
                log_prob_look = look_dist.log_prob(action_look).sum()
                
                # Convert to boolean actions
                acts = [False] * 8
                move_idx = action_move.item()
                if move_idx < len(acts):
                    acts[move_idx] = True
                
                look = action_look[0].tolist()

                # Actions are LOGICAL not PHYSICAL KEYS
                # Mod uses these to inject movement regardless of user's keybinds
                # TOGGLE actions: forward, left, back, right, sprint, sneak
                # ONCE actions: jump, attack, use, swap_offhand (F), open_inventory (E), hotkey switches
                
                # Build response with only enabled actions
                resp = {}
                if self.action_enabled['forward'].get():
                    resp['forward'] = acts[0]
                if self.action_enabled['backward'].get():
                    resp['back'] = acts[2]
                if self.action_enabled['left'].get():
                    resp['left'] = acts[1]
                if self.action_enabled['right'].get():
                    resp['right'] = acts[3]
                if self.action_enabled['sprint'].get():
                    resp['sprint'] = False  # Not in current model output
                if self.action_enabled['sneak'].get():
                    resp['sneak'] = False  # Not in current model output
                if self.action_enabled['jump'].get():
                    resp['jump'] = acts[4]
                if self.action_enabled['attack'].get():
                    resp['attack'] = acts[5]
                if self.action_enabled['use'].get():
                    resp['use'] = False  # Not in current model output
                if self.action_enabled['swap_offhand'].get():
                    resp['swap_offhand'] = acts[6]
                if self.action_enabled['open_inventory'].get():
                    resp['open_inventory'] = acts[7]
                # Hotkeys would go here if enabled
                # Mouse look (always send if enabled)
                if self.action_enabled['mouse'].get():
                    resp['yaw'] = float(look[0])
                    resp['pitch'] = float(look[1])
                
                # Collect experience for PPO training
                done = (curr_health <= 0)  # Episode ends on death
                if self.ppo_trainer is not None and last_state is not None:
                    self.ppo_trainer.buffer.add(
                        last_state, action_move.item(), action_look[0], 
                        reward, done, log_prob_move, log_prob_look, value
                    )
                    
                    # Trigger PPO update if buffer is full
                    if len(self.ppo_trainer.buffer) >= self.ppo_trainer.batch_size:
                        metrics = self.ppo_trainer.update()
                        if metrics:
                            self.log(f"PPO Update: Loss={metrics['total_loss']:.4f}")
                    
                    # On fight end, trigger autosave
                    if done:
                        self.ppo_trainer.on_fight_end()
                
                last_state = state_tensor
                
                rb = json.dumps(resp).encode('utf-8')
                client.sendall(struct.pack('>H', len(rb)) + rb)

        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            if client: client.close()
            self.running = False
            # Use frame.after() to update GUI from thread safely
            self.frame.after(0, lambda: self.start_btn.config(state="normal"))
            self.frame.after(0, lambda: self.stop_btn.config(state="disabled"))
            self.frame.after(0, lambda: self.status_var.set("Status: Stopped"))
            self.log("Disconnected")

    def handle_server_command(self, header):
        """Handle commands from server (START, STOP, RESET) in header"""
        try:
            cmd_type = header.get('cmd_type', '')
            cmd_data = header.get('cmd_data', '')
            
            if cmd_type == 'START':
                self.log(">>> Reward tracking STARTED")
                # Reward tracking starts automatically
            elif cmd_type == 'STOP':
                self.log(">>> Reward tracking STOPPED")
                # Could pause reward accumulation here if needed
            elif cmd_type == 'RESET':
                self.log(f">>> RESET: {cmd_data}")
                # Reset total reward on new match
                self.total_reward = 0.0
                self.frame.after(0, lambda: self.reward_var.set(f"Reward: 0.0"))
        except Exception as e:
            self.log(f"Command error: {e}")
    
    def apply_to_all(self):
        """Copy this agent's reward config to all other agents"""
        # The manager reference will be set by AgentManager during agent creation
        if hasattr(self, 'manager'):
            self.manager.apply_rewards_to_all(self)
            self.log("Applied config to all agents")
    
    def apply_actions_to_all(self):
        """Copy this agent's action configuration to all other agents"""
        if hasattr(self, 'manager'):
            self.manager.apply_actions_to_all(self)
            self.log("Applied actions to all agents")


def command_listener(agents, port=10001):
    """Listen for START/STOP/RESET/HIT/DEATH/MAP commands from the Minecraft mod on a dedicated port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Global agent-player mapping: {player_name: agent_index}
    player_to_agent = {}
    
    try:
        sock.bind(('127.0.0.1', port))
        sock.listen(5)
        print(f"Command listener on port {port}...")
    except Exception as e:
        print(f"Command listener failed to bind on port {port}: {e}")
        return

    while True:
        try:
            conn, _ = sock.accept()
            with conn:
                # Length-prefixed JSON (4 bytes big-endian)
                len_bytes = conn.recv(4)
                if len(len_bytes) < 4:
                    continue
                msg_len = struct.unpack('>I', len_bytes)[0]
                msg_bytes = b''
                while len(msg_bytes) < msg_len:
                    chunk = conn.recv(msg_len - len(msg_bytes))
                    if not chunk:
                        break
                    msg_bytes += chunk
                if len(msg_bytes) != msg_len:
                    continue

                try:
                    msg = json.loads(msg_bytes.decode('utf-8'))
                    cmd_type = msg.get('type', '')
                    cmd_data = msg.get('data', '')

                    if cmd_type == 'START':
                        for ag in agents:
                            ag.log('>>> Reward tracking STARTED')
                    elif cmd_type == 'STOP':
                        for ag in agents:
                            ag.log('>>> Reward tracking STOPPED')
                    elif cmd_type == 'RESET':
                        for ag in agents:
                            ag.log(f'>>> RESET: {cmd_data}')
                            ag.total_reward = 0.0
                            ag.frame.after(0, lambda a=ag: a.reward_var.set("Reward: 0.0"))
                    elif cmd_type == 'MAP':
                        # MAP command: "playerName,agentId"
                        parts = cmd_data.split(',')
                        if len(parts) == 2:
                            player_name = parts[0]
                            agent_id = int(parts[1])
                            player_to_agent[player_name] = agent_id - 1  # Convert to 0-based index
                            print(f"Mapped {player_name} -> Agent {agent_id}")
                    elif cmd_type == 'HIT':
                        # HIT command: "attackerName,victimName"
                        parts = cmd_data.split(',')
                        if len(parts) == 2:
                            attacker = parts[0]
                            victim = parts[1]
                            # Apply rewards to corresponding agents
                            if attacker in player_to_agent:
                                ag_idx = player_to_agent[attacker]
                                if 0 <= ag_idx < len(agents):
                                    # Attacker gets damage dealt reward
                                    agents[ag_idx].log(f"HIT dealt to {victim}")
                            if victim in player_to_agent:
                                ag_idx = player_to_agent[victim]
                                if 0 <= ag_idx < len(agents):
                                    # Victim gets damage taken penalty
                                    agents[ag_idx].log(f"HIT taken from {attacker}")
                    elif cmd_type == 'DEATH':
                        # DEATH command: "victimName,killerName"
                        parts = cmd_data.split(',')
                        if len(parts) == 2:
                            victim = parts[0]
                            killer = parts[1]
                            if victim in player_to_agent:
                                ag_idx = player_to_agent[victim]
                                if 0 <= ag_idx < len(agents):
                                    agents[ag_idx].log(f"DEATH by {killer}")
                            if killer in player_to_agent and killer != "Environment":
                                ag_idx = player_to_agent[killer]
                                if 0 <= ag_idx < len(agents):
                                    agents[ag_idx].log(f"KILL of {victim}")
                except Exception as e:
                    print(f"Command parse error: {e}")
        except Exception:
            # Ignore transient errors and continue listening
            continue


class AgentManager:
    def __init__(self, root):
        self.root = root
        self.agents = []
        
        # Shared model and PPO trainer
        self.shared_model = PVPModel()
        self.ppo_trainer = PPOTrainer(self.shared_model)
        print(f"Initialized shared model and PPO trainer")
        
        # Scrollable frame for agents
        canvas = tk.Canvas(root)
        scrollbar = ttk.Scrollbar(root, orient="horizontal", command=canvas.xview)
        self.agent_frame = ttk.Frame(canvas)
        
        canvas.configure(xscrollcommand=scrollbar.set)
        scrollbar.pack(side="bottom", fill="x")
        canvas.pack(side="top", fill="both", expand=True)
        canvas.create_window((0, 0), window=self.agent_frame, anchor="nw")
        
        self.agent_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        # Create a mock IPC manager for test inputs (will be updated by agents)
        self.ipc_manager = None
        
        # Training metrics frame
        metrics_frame = ttk.LabelFrame(root, text="Training Metrics")
        metrics_frame.pack(side="bottom", fill="x", padx=10, pady=5)
        
        self.metrics_var = tk.StringVar(value="No training data yet")
        ttk.Label(metrics_frame, textvariable=self.metrics_var, font=("Arial", 10)).pack(padx=5, pady=5)
        
        # Control panel
        control = ttk.Frame(root)
        control.pack(side="bottom", pady=5)
        ttk.Button(control, text="+ Add Agent", command=self.add_agent).pack(side="left", padx=5)
        ttk.Button(control, text="- Remove Last", command=self.remove_agent).pack(side="left", padx=5)
        ttk.Button(control, text="Save Model", command=self.save_model).pack(side="left", padx=5)
        
        # Start with 2 agents
        self.add_agent()
        self.add_agent()
        
        # Start metrics update thread
        self.update_metrics_display()
    
    def apply_rewards_to_all(self, source_agent):
        """Copy reward config from source agent to all other agents"""
        for agent in self.agents:
            if agent != source_agent:
                agent.win_reward.set(source_agent.win_reward.get())
                agent.loss_penalty.set(source_agent.loss_penalty.get())
                agent.damage_dealt.set(source_agent.damage_dealt.get())
                agent.damage_taken.set(source_agent.damage_taken.get())
                agent.time_penalty.set(source_agent.time_penalty.get())
                agent.team_hit_penalty.set(source_agent.team_hit_penalty.get())
                agent.team_kill_penalty.set(source_agent.team_kill_penalty.get())
                agent.log("Reward config updated from " + source_agent.name)
    
    def apply_actions_to_all(self, source_agent):
        """Copy action configuration from source agent to all other agents"""
        for agent in self.agents:
            if agent != source_agent:
                for action_name, var in source_agent.action_enabled.items():
                    agent.action_enabled[action_name].set(var.get())
                agent.log("Action config updated from " + source_agent.name)
    
    def add_agent(self):
        agent_num = len(self.agents) + 1
        port = 9999 + len(self.agents)
        if port == 10001:  # Skip command port
            port = 10002
        name = f"Agent {agent_num}"
        agent = AgentController(self.agent_frame, name, port, self.shared_model, self.ppo_trainer)
        agent.manager = self  # Set reference to manager
        agent.ipcManager = self.ipc_manager  # Share IPC manager for test inputs
        self.agents.append(agent)
        print(f"Added {name} on port {port}")
    
    def remove_agent(self):
        if len(self.agents) > 1:
            agent = self.agents.pop()
            agent.stop()
            agent.frame.destroy()
            print(f"Removed {agent.name}")
    
    def save_model(self):
        """Manually save the model checkpoint"""
        filename = self.ppo_trainer.save_checkpoint()
        print(f"Model saved to {filename}")
    
    def update_metrics_display(self):
        """Update the metrics display periodically"""
        summary = self.ppo_trainer.get_metrics_summary()
        if isinstance(summary, dict):
            metrics_text = (f"Fights: {summary['fights']} | Updates: {summary['updates']} | "
                          f"Policy Loss: {summary['avg_policy_loss']:.4f} | "
                          f"Value Loss: {summary['avg_value_loss']:.4f} | "
                          f"Entropy: {summary['avg_entropy']:.4f}")
            self.metrics_var.set(metrics_text)
        else:
            self.metrics_var.set(summary)
        
        # Schedule next update
        self.root.after(1000, self.update_metrics_display)

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Multi-Agent PVP Training")
    root.geometry("1200x700")
    
    manager = AgentManager(root)
    
    # Start command listener thread
    threading.Thread(target=command_listener, args=(manager.agents,), daemon=True).start()
    
    root.mainloop()
