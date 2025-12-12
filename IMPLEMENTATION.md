# PVP KI Implementation Guide

This document describes the full implementation of the PVP KI system with dynamic agents, team management, biome filtering, and PPO training.

## Architecture Overview

### Components

1. **Java Client Mod** (Fabric 1.21.10)
   - Team management (client-side)
   - Agent selection and switching
   - Event detection (HIT/DEATH)
   - IPC communication with Python agents
   - Frame capture and action application

2. **Java Server Mod** (Fabric 1.21.10)
   - Settings management (biomes, nametags)
   - Kit management
   - Reset command with biome filtering
   - Optional event broadcasting to Python

3. **Python Training System**
   - Multi-agent GUI with dynamic agent management
   - Shared PPO trainer
   - Reward calculation with team awareness
   - Checkpoint management with autosave

## Features Implemented

### Client-Side Features (Works on ANY server)

#### Team Management
- `/team add <player>` - Add player to team
- `/team remove <player>` - Remove player from team
- `/team list` - List team members and enemies
- `/team clear` - Clear all team assignments

Team data is tracked locally and injected into IPC headers for Python agents.

#### Agent Selection
- `/agent <n>` - Switch to agent N (ports: 9999, 10000, 10002, 10003, ...)
- Agent ID and player name injected into IPC headers
- Supports dynamic number of agents

#### Event Detection
- Client-side HIT event detection
- Client-side DEATH event detection
- Events injected into IPC headers for Python

### Server-Side Features (Requires mod on server)

#### Settings Commands
- `/ki settings show` - Display all settings
- `/ki settings nametags <on|off>` - Toggle team nametag overlays
- `/ki settings biome allow <biome>` - Add biome to allowed list
- `/ki settings biome block <biome>` - Add biome to blocked list
- `/ki settings biome clear` - Clear biome filters
- `/ki settings biome list` - List biome filters

#### Reset Command
- `/ki reset <p1> <p2> <kit> [shuffle]` - Reset players with biome filtering
- Finds unmodified chunks in allowed biomes
- Calculates safe spawn heights for both players
- Applies kits and sends RESET event to Python

#### Control Commands
- `/ki start` - Start reward tracking
- `/ki stop` - Stop reward tracking
- `/ki createkit <name>` - Save server kit for resets

### Python Training System

#### GUI Features
- Dynamic agent management (Add/Remove agents)
- Per-agent reward configuration:
  - Win reward
  - Loss penalty
  - Damage dealt reward
  - Damage taken penalty
  - Time penalty
  - Team hit penalty (NEW)
  - Team kill penalty (NEW)
- "Apply to All" button to sync configs
- Manual checkpoint save button
- Fight counter display

#### PPO Training
- Shared model across all agents
- Experience buffer aggregation
- GAE (Generalized Advantage Estimation)
- Clipped surrogate objective
- Autosave every 10 fights with timestamps
- Checkpoints saved to `checkpoints/` directory

#### Reward Logic
- Tracks agent-player mapping
- Team-aware reward calculation
- Applies penalties for team hits/kills
- Resets rewards on fight end

## IPC Protocol

### Agent Ports
- Agent 1: 9999
- Agent 2: 10000
- Agent 3: 10002 (skips 10001)
- Agent N: 9999 + N - 1 (+ 1 if >= 10001)

### Command Port
- Port 10001: Dedicated command channel for START/STOP/RESET/HIT/DEATH/TEAM/MAP

### Header Fields (Client -> Python)
```json
{
  "width": 64,
  "height": 64,
  "bodyLength": 12288,
  "health": 20.0,
  "player_name": "Player1",
  "agent_id": 1,
  "teams": {
    "Player1": "team",
    "Player2": "enemy",
    "Player3": null
  },
  "events": [
    "EVENT:HIT:Player1:Player2",
    "EVENT:DEATH:Player2:Player1"
  ],
  "cmd_type": "RESET",
  "cmd_data": "Player1,Player2"
}
```

### Command Messages (Server -> Python)
```json
{"type": "START", "data": "Reward tracking started"}
{"type": "STOP", "data": "Reward tracking stopped"}
{"type": "RESET", "data": "Player1,Player2"}
{"type": "HIT", "data": "attacker,victim"}
{"type": "DEATH", "data": "victim,killer"}
{"type": "TEAM", "data": "ADD:player"}
{"type": "MAP", "data": "playerName,agentId"}
```

## Usage Instructions

### Building the Mod

**Note**: There is currently a Fabric Loom version issue in the build system. The implementation is complete but building may require updating the Gradle dependencies.

```bash
cd pvp_ki-template-1.21.10
chmod +x gradlew
./gradlew build
```

### Running the Python Training System

```bash
# Install dependencies
pip install torch numpy tkinter

# Run the GUI
python training_loop.py
```

### In-Game Usage

1. **Set up agents**:
   ```
   /agent 1  (Client-side, switch to Agent 1)
   /agent 2  (Client-side, switch to Agent 2)
   ```

2. **Configure teams**:
   ```
   /team add Player1
   /team add Player2
   /team list
   ```

3. **Configure biome filtering** (server-side):
   ```
   /ki settings biome allow minecraft:plains
   /ki settings biome allow minecraft:forest
   /ki settings show
   ```

4. **Start training**:
   ```
   /ki start
   /ki reset Player1 Player2 pvp_kit
   ```

5. **Manage nametags**:
   ```
   /ki settings nametags on
   ```

## File Structure

```
PVP-KI/
├── pvp_ki-template-1.21.10/          # Minecraft mod
│   ├── src/
│   │   ├── client/java/com/example/
│   │   │   ├── PVP_KIClient.java      # Client entry point
│   │   │   ├── IPCManager.java        # IPC communication
│   │   │   ├── TeamManager.java       # Team tracking
│   │   │   └── ClientKitManager.java  # Client kits
│   │   └── main/java/com/example/
│   │       ├── PVP_KI.java            # Server entry point
│   │       ├── SettingsManager.java   # Settings persistence
│   │       ├── KitManager.java        # Server kits
│   │       └── ServerIPCClient.java   # Command port sender
│   └── build.gradle
├── training_loop.py                   # Python GUI and training
├── ppo_trainer.py                     # PPO implementation
├── model.py                           # Neural network model
├── requirements.txt                   # Python dependencies
└── checkpoints/                       # Model checkpoints (created at runtime)
```

## Implementation Status

### ✅ Completed
- Client-side team management
- Dynamic agent selection
- Agent-player mapping
- Team data injection into headers
- Biome filtering for resets
- Settings management and persistence
- Event detection (HIT/DEATH) on client
- Server-side event broadcasting
- PPO trainer with shared model
- Autosave every 10 fights
- Per-agent reward configuration
- Team hit/kill penalties
- "Apply to All" config sync

### ⚠️ Partial
- Nametag rendering (mixin structure in place, needs full rendering code)
- Server team broadcast (optional, client-side works without it)

### 🔧 Known Issues
- Fabric Loom version in build.gradle needs update
- Death event on client doesn't capture killer (uses server event for accurate data)

## Configuration

### Reward Configuration
All reward values are configurable per agent in the GUI:
- Win reward: Default 500.0
- Loss penalty: Default -500.0
- Damage dealt: Default 10.0
- Damage taken: Default -10.0
- Time penalty: Default -0.1
- Team hit penalty: Default -50.0
- Team kill penalty: Default -1000.0

### PPO Hyperparameters
Edit `ppo_trainer.py` to adjust:
- Learning rate: 3e-4
- Gamma: 0.99
- GAE Lambda: 0.95
- Clip range: 0.2
- Batch size: 256
- Epochs per update: 4

### Settings Persistence
Settings are saved to `config/pvp_ki/settings.json`:
- Nametag toggle
- Allowed biomes list
- Blocked biomes list

## Future Enhancements

1. **Complete nametag rendering** - Full custom rendering with colored text
2. **Experience replay** - Priority experience replay for better training
3. **Multi-modal input** - Add game state beyond vision (inventory, nearby entities)
4. **Curriculum learning** - Progressive difficulty increase
5. **Self-play** - Train agents against each other
6. **Tensorboard logging** - Training metrics visualization

## Support

For issues or questions, please refer to the repository issues page.
