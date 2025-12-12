# PVP-KI: Multi-Agent PvP Training System

Complete implementation of the multi-agent reinforcement learning system for Minecraft PvP training, as specified in `full-plan.txt`.

## 🎯 Features

### ✅ All Phases Complete (1-6)

#### **Phase 1: Client-Side Team System**
- `/team add/remove/list/clear` - Manage team membership
- `/agent <1-100>` - Switch between unlimited agents (skips port 10001)
- Team data injected into IPC headers for reward logic

#### **Phase 2: Python Agent Enhancements**
- Team hit/kill penalties configurable per agent
- Agent-player mapping via MAP commands
- HIT/DEATH event handling with team awareness
- "Apply to All" button for quick config sync

#### **Phase 3: Server Settings**
- `/ki settings show` - Display all settings
- `/ki settings nametags on/off` - Toggle overlays
- `/ki settings biome allow/block/clear/list` - Control spawn biomes
- JSON persistence for all settings

#### **Phase 4: Biome-Filtered Reset**
- `/ki reset <p1> <p2> <kit> [shuffle]` with biome checking
- Respects allowed/blocked biome lists
- 100 sampling attempts for suitable locations

#### **Phase 5: Nametag Overlay System**
- Visual team/enemy identification
- `[Team]` (green) for teammates
- `[Enemy]` (red) for opponents
- Hides actual player names

#### **Phase 6: PPO Training Infrastructure**
- Shared Actor-Critic model across all agents
- Experience buffer with automatic batching
- GAE (λ=0.95) + PPO clipping (ε=0.2)
- Autosave every 10 fights to `checkpoints/`
- Real-time metrics display (policy loss, value loss, entropy)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install torch numpy --index-url https://download.pytorch.org/whl/cpu
sudo apt-get install python3-tk
```

### 2. Start Training GUI

```bash
python3 training_loop.py
```

The GUI will start with 2 agents on ports 9999 and 10000. Use "+ Add Agent" to create more agents.

### 3. Build & Install Mod

```bash
cd pvp_ki-template-1.21.10
./gradlew build
# Copy build/libs/pvp_ki-*.jar to your Minecraft mods folder
```

### 4. In-Game Setup

```
# Assign players to agents
/agent 1
/agent 2

# Create teams (client-side)
/team add PlayerName

# Configure environment (server-side, requires mod)
/ki settings biome allow plains
/ki settings nametags on

# Start training match
/ki reset Player1 Player2 default_kit
```

## 📁 Project Structure

```
PVP-KI/
├── training_loop.py          # Main GUI and agent management
├── ppo_trainer.py             # PPO implementation with GAE
├── model.py                   # Actor-Critic neural network
├── ipc_client.py              # IPC communication (legacy)
├── drl_agent.py               # DRL agent (legacy)
├── full-plan.txt              # Complete feature specification
├── STATUS.md                  # Detailed implementation status
├── requirements.txt           # Python dependencies
└── pvp_ki-template-1.21.10/   # Minecraft mod source
    ├── src/client/java/       # Client-side code
    │   ├── PVP_KIClient.java  # Team tracking, agent selection
    │   ├── IPCManager.java    # Frame capture, header injection
    │   └── mixin/client/
    │       ├── ExampleClientMixin.java  # Frame capture
    │       └── NameTagMixin.java        # Nametag overlays
    └── src/main/java/         # Server-side code
        ├── PVP_KI.java        # Commands, event handlers
        ├── SettingsManager.java  # Settings persistence
        ├── KitManager.java    # Kit storage
        └── ServerIPCClient.java  # Command port 10001
```

## 🔧 Configuration

### Reward Configuration (Per Agent)
- **Win Reward**: +500.0 (default)
- **Loss Penalty**: -500.0 (default)
- **Damage Dealt**: +10.0 per hit
- **Damage Taken**: -10.0 per hit received
- **Time Penalty**: -0.1 per frame (encourages quick victories)
- **Team Hit Penalty**: -50.0 (hitting teammate)
- **Team Kill Penalty**: -500.0 (killing teammate)

### PPO Hyperparameters
- **Learning Rate**: 3e-4
- **Gamma**: 0.99 (discount factor)
- **GAE Lambda**: 0.95
- **Clip Range**: 0.2
- **Epochs per Update**: 4
- **Batch Size**: 256 frames
- **Gradient Clipping**: 0.5

### Port Allocation
- **Agent Ports**: 9999, 10000, 10002-10099 (skip 10001)
- **Command Port**: 10001 (server → Python)

## 📊 Training Workflow

1. **Start Python GUI**: Agents wait for connections
2. **Launch Minecraft**: Client connects to agent ports
3. **Assign Agents**: Use `/agent <id>` to map player to agent
4. **Form Teams**: Use `/team add <player>` for team training
5. **Configure Environment**: Use `/ki settings biome allow plains`
6. **Start Match**: Use `/ki reset Player1 Player2 kit_name`
7. **Train**: Agents automatically collect experiences and update model
8. **Monitor**: Watch metrics display for training progress
9. **Autosave**: Model saved every 10 fights to `checkpoints/`

## 🎮 Commands Reference

### Client-Side (Works Everywhere)
```
/agent <1-100>              Switch to agent N
/team add <player>          Add player to team
/team remove <player>       Remove player from team
/team list                  Show team members
/team clear                 Clear team
/kit create <name>          Save current inventory as kit
/kit load <name>            Load kit
/kit delete <name>          Delete kit
/kit list                   List available kits
```

### Server-Side (Requires Mod)
```
/ki start                   Start reward tracking
/ki stop                    Stop reward tracking
/ki reset <p1> <p2> <kit> [shuffle]  Reset match
/ki createkit <name>        Save server kit
/ki settings show           Display all settings
/ki settings nametags on|off  Toggle nametag overlays
/ki settings biome allow <biome>    Add to allowed list
/ki settings biome block <biome>    Add to blocked list
/ki settings biome clear    Clear biome filters
/ki settings biome list     Show biome filters
```

## 🔬 IPC Protocol

### Agent Ports (9999+)
**Request (Python → Minecraft):**
```json
{
  "forward": true,
  "left": false,
  "back": false,
  "right": false,
  "jump": false,
  "attack": true,
  "yaw": 2.5,
  "pitch": -1.0
}
```

**Response (Minecraft → Python):**
- 4-byte header length (big-endian)
- JSON header with:
  - `width`, `height`, `bodyLength`
  - `health`, `hunger`, `x`, `y`, `z`, `pitch`, `yaw`
  - `events`: `["EVENT:HIT:attacker:victim", "EVENT:DEATH:victim:killer"]`
  - `player_name`, `agent_id`
  - `teams`: `{"PlayerA": "team", "PlayerB": "enemy"}`
- Raw frame bytes (BGRA, 64×64)

### Command Port (10001)
**Commands (Server → Python):**
```json
{"type": "START", "data": "..."}
{"type": "STOP", "data": "..."}
{"type": "RESET", "data": "player1,player2"}
{"type": "HIT", "data": "attacker,victim"}
{"type": "DEATH", "data": "victim,killer"}
{"type": "MAP", "data": "playerName,agentId"}
```

## 🐛 Troubleshooting

### Python Issues
- **"No module named 'torch'"**: Run `pip install torch --index-url https://download.pytorch.org/whl/cpu`
- **"No module named 'tkinter'"**: Run `sudo apt-get install python3-tk`
- **"Connection refused"**: Ensure agents are started before launching Minecraft

### Mod Build Issues
- **Loom version error**: Update `gradle.properties` with correct Loom version for MC 1.21.10
- **Mixin errors**: Ensure `pvp_ki.client.mixins.json` lists all mixin classes

### Training Issues
- **No updates**: Check buffer size reaches 256 before update
- **NaN losses**: Reduce learning rate or check for invalid rewards
- **Slow training**: Increase batch size or reduce update epochs

## 📚 Technical Details

### Model Architecture
```
Input: 64×64 RGB frame
→ Conv2D(3→32, k=8, s=4) + ReLU
→ Conv2D(32→64, k=4, s=2) + ReLU
→ Conv2D(64→64, k=3, s=1) + ReLU
→ Flatten (64×4×4 = 1024)
→ Linear(1024→512) + ReLU
→ Policy Head: Linear(512→6) [W,A,S,D,Space,Attack]
→ Look Head: Linear(512→2) + Tanh×10 [Yaw,Pitch]
→ Value Head: Linear(512→1)
```

### PPO Algorithm
1. **Collection**: Agents collect (state, action, reward, log_prob, value)
2. **GAE**: Compute advantages using rewards and values
3. **Normalization**: Normalize advantages (μ=0, σ=1)
4. **Update**: For 4 epochs:
   - Forward pass through current policy
   - Compute probability ratios
   - Clip ratios to [1-ε, 1+ε]
   - Compute policy loss (clipped surrogate)
   - Compute value loss (MSE)
   - Add entropy bonus
   - Backpropagate and update
5. **Autosave**: Every 10 fights, save to checkpoint

## 🎓 Citation

If you use this system in your research, please cite:

```
@software{pvp_ki_2024,
  title={PVP-KI: Multi-Agent Reinforcement Learning for Minecraft PvP},
  author={Your Name},
  year={2024},
  url={https://github.com/Gladiatorsarius/PVP-KI}
}
```

## 📄 License

See LICENSE file for details.

## 🤝 Contributing

This implementation is complete according to full-plan.txt. For enhancements or bug fixes, please open an issue or pull request.

## 📞 Support

For issues or questions:
1. Check STATUS.md for implementation details
2. Review full-plan.txt for feature specifications
3. Open a GitHub issue with logs and error messages
