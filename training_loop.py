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

class AgentController:
    def __init__(self, parent, name, port):
        self.name = name
        self.port = port
        self.running = False
        self.stop_event = threading.Event()
        self.thread = None

        # UI Frame
        self.frame = ttk.LabelFrame(parent, text=f"{name} (Port {port})")
        self.frame.pack(side="left", padx=10, pady=10, fill="both", expand=True)

        # Reward Config
        config_frame = ttk.LabelFrame(self.frame, text="Rewards")
        config_frame.pack(padx=5, pady=5, fill="x")

        self.win_reward = self.create_input(config_frame, "Win:", "500.0")
        self.loss_penalty = self.create_input(config_frame, "Loss:", "-500.0")
        self.damage_dealt = self.create_input(config_frame, "Dmg Dealt:", "10.0")
        self.damage_taken = self.create_input(config_frame, "Dmg Taken:", "-10.0")
        self.time_penalty = self.create_input(config_frame, "Time:", "-0.1")
        self.team_hit_penalty = self.create_input(config_frame, "Team Hit:", "-50.0")
        self.team_kill_penalty = self.create_input(config_frame, "Team Kill:", "-500.0")

        # Controls
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=10)
        
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        self.apply_all_btn = ttk.Button(btn_frame, text="Apply to All", command=lambda: self.apply_to_all())
        self.apply_all_btn.pack(side="left", padx=5)

        # Status
        self.status_var = tk.StringVar(value="Status: Stopped")
        ttk.Label(self.frame, textvariable=self.status_var).pack(pady=5)

        # Reward Display
        self.reward_var = tk.StringVar(value="Reward: 0.0")
        ttk.Label(self.frame, textvariable=self.reward_var, font=("Arial", 12, "bold")).pack(pady=5)
        self.total_reward = 0.0

        self.log_text = tk.Text(self.frame, height=15, width=30, state="disabled")
        self.log_text.pack(padx=5, pady=5, fill="both", expand=True)

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

    def start(self):
        if self.running: return
        self.running = True
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Status: Running")
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running: return
        self.running = False
        self.stop_event.set()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Status: Stopping...")

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

        model = PVPModel()
        model.eval()
        last_health = 20.0
        self.total_reward = 0.0  # Reset reward at start

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

                # Inference
                w, h = header['width'], header['height']
                img = np.frombuffer(img_data, dtype=np.uint8).reshape((h, w, 3))
                t = torch.from_numpy(img).permute(2, 0, 1).float().unsqueeze(0) / 255.0
                
                with torch.no_grad():
                    logits, look, val = model(t)
                
                probs = torch.sigmoid(logits[0])
                acts = (probs > 0.5).int().tolist()
                look = look[0].tolist()

                resp = {
                    'forward': bool(acts[0]), 'left': bool(acts[1]),
                    'back': bool(acts[2]), 'right': bool(acts[3]),
                    'jump': bool(acts[4]), 'attack': bool(acts[5]),
                    'yaw': float(look[0]), 'pitch': float(look[1])
                }
                
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
        
        # Scrollable frame for agents
        canvas = tk.Canvas(root)
        scrollbar = ttk.Scrollbar(root, orient="horizontal", command=canvas.xview)
        self.agent_frame = ttk.Frame(canvas)
        
        canvas.configure(xscrollcommand=scrollbar.set)
        scrollbar.pack(side="bottom", fill="x")
        canvas.pack(side="top", fill="both", expand=True)
        canvas.create_window((0, 0), window=self.agent_frame, anchor="nw")
        
        self.agent_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        # Control panel
        control = ttk.Frame(root)
        control.pack(side="bottom", pady=5)
        ttk.Button(control, text="+ Add Agent", command=self.add_agent).pack(side="left", padx=5)
        ttk.Button(control, text="- Remove Last", command=self.remove_agent).pack(side="left", padx=5)
        
        # Start with 2 agents
        self.add_agent()
        self.add_agent()
    
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
    
    def add_agent(self):
        agent_num = len(self.agents) + 1
        port = 9999 + len(self.agents)
        if port == 10001:  # Skip command port
            port = 10002
        name = f"Agent {agent_num}"
        agent = AgentController(self.agent_frame, name, port)
        agent.manager = self  # Set reference to manager
        self.agents.append(agent)
        print(f"Added {name} on port {port}")
    
    def remove_agent(self):
        if len(self.agents) > 1:
            agent = self.agents.pop()
            agent.stop()
            agent.frame.destroy()
            print(f"Removed {agent.name}")

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Multi-Agent PVP Training")
    root.geometry("1200x700")
    
    manager = AgentManager(root)
    
    # Start command listener thread
    threading.Thread(target=command_listener, args=(manager.agents,), daemon=True).start()
    
    root.mainloop()
