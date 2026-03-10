# PVP AI TRAINING GUIDE - COMPLETE WALKTHROUGH

## 2026 CONTRACT FREEZE (AGENT 0) - PROTOCOL V1

This section is the canonical interface contract for the distributed architecture.
All implementation streams (Agent 1-4) must follow this contract.

### A. Scope and authority

- Main machine runs model, trainer, and coordinator.
- VM nodes run thin clients: capture + preprocess + input injection only.
- Minecraft server-side mod is the authoritative source for reset/combat events.
- Client-side Minecraft mod is not required for capture/input in the new flow.

### B. Network endpoints (canonical)

- `WS_COORDINATOR`: `ws://<main-host>:8765/ws`
- `EVENT_BRIDGE`: `tcp://<main-host>:9998`
- `HEALTH`: `http://<main-host>:8765/health`

If older docs mention different ports, this table wins.

### C. Session lifecycle state machine

Client session transitions:

1. `connected`
2. `registered` (after `hello` accepted)
3. `ready` (after manual ready)
4. `started` (after global start)
5. `running`
6. `ended` (normal stop/reset boundary)
7. `disconnected`

Invalid transitions are rejected with `error`.

### D. Message catalog (Protocol v1)

Control messages:

- `hello`
- `ready`
- `start`
- `stop`
- `heartbeat`
- `disconnect`
- `error`

Data-plane messages:

- `frame`
- `action`
- `event`
- `reset`

### E. Common required fields

Every `frame`, `action`, `event`, and `reset` message must include:

- `protocol_version` (string, must be `"v1"`)
- `session_id` (string)
- `agent_id` (integer >= 1)
- `episode_id` (string)
- `timestamp_ms` (integer, epoch ms)

Sequencing fields:

- `frame_id` required on `frame`
- `action_id` required on `action`

### F. Frame schema (VM -> main)

`frame` payload fields:

- `frame_id` (monotonic per session)
- `capture_ts_ms`
- `width`, `height`
- `channels` (must be `1` for grayscale)
- `dtype` (e.g. `uint8`)
- `encoding` (`jpeg` for v1)
- `payload_b64` (base64 bytes)
- `dropped_frame_count` (integer)

Target ingest profile:

- 30 FPS capture target per VM
- Latest-frame preference under load (stale frames may be dropped)

### G. Action schema (main -> VM)

`action` payload fields:

- `action_id` (monotonic per session)
- `movement` object: `forward`, `back`, `left`, `right`, `jump`, `sprint`, `sneak`, `attack`, `use`
- `look` object: `dx`, `dy` (relative deltas)
- `mouse` object: `left_click`, `right_click`, `hold_ms`

Execution mode for v1:

- Asynchronous latest-action semantics
- VM applies newest received action and may skip older action IDs
- VM must release all held keys/buttons on `stop` or disconnect

### H. Event/reset schema (server bridge -> main)

`event` payload fields:

- `event_type` in `{HIT, DEATH, ROUND_START, ROUND_END}`
- `actor_player` (nullable)
- `target_player` (nullable)
- `value` (optional numeric)
- `metadata` (optional object)

`reset` payload fields:

- `reason` (e.g. `manual`, `death`, `timeout`)
- `next_episode_id`
- `participants` (array of player names)

### I. Minimal JSON examples

`hello`

```json
{
  "type": "hello",
  "protocol_version": "v1",
  "agent_id": 2,
  "client_role": "vm-runtime",
  "capabilities": { "grayscale": true, "input_driver": "pydirectinput" }
}
```

`frame`

```json
{
  "type": "frame",
  "protocol_version": "v1",
  "session_id": "s-9f2",
  "agent_id": 2,
  "episode_id": "ep-104",
  "frame_id": 1188,
  "timestamp_ms": 1772520000000,
  "capture_ts_ms": 1772520000000,
  "width": 320,
  "height": 180,
  "channels": 1,
  "dtype": "uint8",
  "encoding": "jpeg",
  "payload_b64": "...",
  "dropped_frame_count": 0
}
```

`action`

```json
{
  "type": "action",
  "protocol_version": "v1",
  "session_id": "s-9f2",
  "agent_id": 2,
  "episode_id": "ep-104",
  "action_id": 412,
  "timestamp_ms": 1772520000100,
  "movement": { "forward": true, "back": false, "left": false, "right": true, "jump": false, "sprint": true, "sneak": false, "attack": false, "use": false },
  "look": { "dx": 3.0, "dy": -1.5 },
  "mouse": { "left_click": false, "right_click": false, "hold_ms": 0 }
}
```

### J. Acceptance checklist (contract conformance)

All streams must satisfy:

- No conflicting port declarations outside this section
- All messages contain required fields for their type
- Ready + global Start All flow is implemented exactly once in coordinator
- VM runtime performs full key/button release on stop/disconnect
- Event bridge payloads match `event`/`reset` schemas

### K. Deprecation note

- MineRL/Gym runtime path is legacy and not the active distributed runtime.
- Legacy TCP framing variants from old docs remain historical only.

---

## TRAINING METHODOLOGY

This section describes the Deep Reinforcement Learning (DRL) training phases and reward schema evolution for developing PvP combat agents from basic skills to advanced strategies.

### Phase 1: Bootstrapping (Initial Learning)

**Purpose**: Teach the untrained agent fundamental game mechanics (movement, attacking, aiming) as quickly as possible through training against a human opponent.

**Goals**:
- Acquire basic skills (attacking, dodging)
- Establish stable behavior before exposing the agent to complex self-play strategies

**Reward Schema (Active During Bootstrapping)**

| Component | Reward Value | Purpose |
|-----------|--------------|---------|
| Terminal Victory | **+500 points (Moderate)** | Establishes victory as the main goal without creating excessive risk aversion |
| Terminal Defeat | **-500 points (Moderate)** | Minimizes punishment so the agent is willing to take risky actions to learn |
| Continuous HP Delta (Enemy loses HP) | **+10 points per 0.5 heart** | Dense positive feedback for successful hits |
| Continuous HP Delta (Agent loses HP) | **-10 points per 0.5 heart** | Dense negative feedback promoting survival and dodging |
| Time Penalty | **0 (Removed)** | Inefficiency punishment is handled by the human opponent who defeats hesitant agents |

**Key Insight**: Moderate terminal rewards during bootstrapping encourage exploration and risk-taking, which is essential for learning basic combat mechanics.

### Phase 2: Self-Play (Advanced Strategy Development)

**Purpose**: After the agent masters the basics, switch to self-play (agent vs agent) training. Sharpen the reward schema and penalties to enforce highly optimized and efficient behaviors.

**Goals**:
- Develop complex strategies (e.g., optimal timing, block usage, positioning)
- Maximize efficiency and aggression

**Reward Schema (Active During Self-Play)**

| Component | Reward Value | Purpose |
|-----------|--------------|---------|
| Terminal Victory | **+1000 points (High)** | Maximally prioritizes victory as the only true objective |
| Terminal Defeat | **-1000 points (High)** | Strong penalty to eliminate poor overall strategies |
| Continuous HP Delta (Enemy loses HP) | **+10 points per 0.5 heart** | Remains the primary source of dense feedback |
| Continuous HP Delta (Agent loses HP) | **-10 points per 0.5 heart** | Remains the primary source of dense feedback |
| Time Penalty | **-1 point per frame (Added)** | Punishes slow/inefficient play, forcing aggressive optimization |

**Key Insight**: High terminal rewards during self-play create strong selection pressure for winning strategies, while the time penalty prevents passive play and encourages decisive action.

### Training Progression

1. **Start with Bootstrapping**: Train against human opponents until the agent demonstrates consistent basic combat behavior (can hit, dodge, survive reasonable duration)

2. **Transition to Self-Play**: Once bootstrapping is complete, switch to agent-vs-agent training with the intensified reward schema

3. **Monitor for Overfitting**: Watch for degenerate strategies (e.g., excessive blocking, running away). Adjust rewards or introduce curriculum variations if needed

4. **Iterate**: Continue self-play training for convergence, periodically validating against human opponents to ensure strategies generalize

## PROTOCOL V1 TRAINING WALKTHROUGH

### System Architecture Overview

The Protocol v1 distributed architecture separates concerns across three components:

```
┌─────────────────────────────────────────────┐
│           MAIN MACHINE                      │
│  ┌──────────────────────────────────────┐  │
│  │ Coordinator (WebSocket :8765)        │  │
│  │ - Session management                 │  │
│  │ - Frame routing                      │  │
│  │ - Action distribution                │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ Model + PPO Trainer                  │  │
│  │ - CNN Actor-Critic                   │  │
│  │ - Experience buffer                  │  │
│  │ - Gradient updates                   │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ Command Bridge (TCP :9998)           │  │
│  │ - Receives server events             │  │
│  │ - HMAC-SHA256 auth                   │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ PyQt6 UI                             │  │
│  │ - Agent panels                       │  │
│  │ - Start/Stop controls                │  │
│  │ - Real-time metrics                  │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                    ↕ WebSocket
┌─────────────────────────────────────────────┐
│           VM MACHINES (1 per agent)         │
│  ┌──────────────────────────────────────┐  │
│  │ Runtime Client (client.py)           │  │
│  │ - Screen capture (mss)               │  │
│  │ - Grayscale + JPEG preprocessing     │  │
│  │ - Action execution (pydirectinput)   │  │
│  │ - WebSocket client                   │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ Minecraft Client                     │  │
│  │ - Renders game                       │  │
│  │ - Receives input from runtime        │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                    ↕ TCP
┌─────────────────────────────────────────────┐
│           MINECRAFT SERVER                  │
│  - Server-side mod                          │
│  - Authoritative events: HIT, DEATH, RESET  │
│  - Sends to command bridge :9998            │
└─────────────────────────────────────────────┘
```

**Key Design Principles**:
- **Separation of concerns**: Main machine handles AI computation, VMs handle I/O
- **Server-authoritative events**: Combat events come from server, not client
- **Thin VM clients**: Minimal processing on VM, keeps latency low
- **WebSocket coordinator**: Single connection point for all agents

---

### Quick Start Guide

#### Prerequisites

1. **Python 3.10+** with pip installed
2. **CUDA-compatible GPU** (optional but recommended for training)
3. **Minecraft 1.21.11** with Fabric Loader
4. **Network access** between main machine and VMs (if distributed)

#### Installation

1. **Install Python dependencies** on main machine:
   ```bash
   cd python/server
   pip install -r requirements.txt
   ```

2. **Install Python dependencies** on each VM:
   ```bash
   cd python/client
   pip install -r requirements.txt
   ```

3. **Build and install the Fabric mod**:
   ```bash
   cd pvp_ki-template-1.21.10
   ./gradlew build
   # Copy build/libs/*.jar to Minecraft mods folder
   ```

4. **Configure the server-side mod**:
   - Install mod on Minecraft server
   - Set command bridge endpoint in mod config (default: localhost:9998)
   - (Optional) Configure HMAC authentication via `PVP_CMD_SECRET` environment variable for production
     - Note: Current server mod implementation doesn't send HMAC tokens, so authentication is typically disabled for development

---

### Step-by-Step Training Workflow

#### Step 1: Start Main Machine Runtime

On the main machine (where AI computation happens):

```bash
cd python/server
python main.py
```

**What this does**:
- Starts WebSocket coordinator on port 8765
- Starts command bridge listener on port 9998
- Initializes PPO trainer and model (CPU/CUDA/MPS auto-detected)
- Opens PyQt6 UI for agent management

**Expected output**:
```
[INFO] Device: cuda (NVIDIA GeForce RTX 3080)
[INFO] Coordinator listening on ws://0.0.0.0:8765/ws
[INFO] Command bridge listening on tcp://0.0.0.0:9998
[INFO] UI started
```

#### Step 2: Start VM Runtime Clients

On each VM machine (one per agent):

```bash
cd python/client
python client.py --server-url ws://<main-machine-ip>:8765/ws --agent-id 1 --fps 30
```

**Parameters**:
- `--server-url`: WebSocket coordinator endpoint (default: ws://127.0.0.1:8765/ws)
- `--agent-id`: Unique agent identifier (1, 2, 3, ...)
- `--fps`: Frame capture rate (default: 30)
- `--jpeg-quality`: JPEG compression quality 1-100 (default: 70)
- `--width`: Frame resize width in pixels (default: 320)
- `--height`: Frame resize height in pixels (default: 180)
- `--window-title-contains`: Preferred window title substring for capture (default: "VirtualBox")

**What this does**:
- Connects to main machine coordinator via WebSocket
- Begins screen capture at specified FPS
- Preprocesses frames (grayscale conversion, JPEG encoding)
- Streams frames to coordinator
- Waits for action commands

**Expected output**:
```
[INFO] Connecting to ws://192.168.1.100:8765/ws as agent_1
[INFO] Connected! Session state: registered
[INFO] Capture initialized: 1920x1080 @ 30fps
[INFO] Ready to start
```

#### Step 3: Configure Agents in UI

In the PyQt6 UI on the main machine:

1. **Agent panels** will appear as VM clients connect
2. **Wait for "Ready" status** on all agents
3. **Click "Start All"** to begin coordinated training session

**Agent Panel UI Elements**:
- **Status indicator**: Connected → Registered → Ready → Running
- **Metrics display**: Current reward, episode length, last action
- **Control buttons**: Start, Stop, Reset
- **Reward configuration**: Win/Loss rewards, HP delta rewards

#### Step 4: Launch Minecraft Clients

On each VM machine:

1. Launch Minecraft with the client mod installed
2. Join your Minecraft server (where server-side mod is running)
3. The runtime client will automatically detect the game window and begin capture

**No in-game commands needed!** The VM runtime handles everything automatically.

#### Step 5: Start Training Session

In the UI, click **"Start All"** to begin training:

1. Coordinator broadcasts `start` message to all VM clients
2. VM clients begin sending frames at configured FPS
3. Main machine:
   - Receives frames from all agents
   - Runs model inference (batched for efficiency)
   - Sends actions back to each agent
   - Accumulates experiences in PPO buffer
4. VM clients:
   - Receive actions from coordinator
   - Execute actions via pydirectinput (keyboard/mouse simulation)
   - Continue frame capture loop

**Server mod sends events**:
- `HIT` events when player hits enemy
- `DEATH` events when player dies
- `RESET` signals to start new episode

**Training updates**:
- PPO updates run automatically when buffer fills
- Model checkpoints saved after each episode
- Metrics displayed in UI (policy loss, value loss, entropy)

#### Step 6: Monitor Training Progress

**UI Metrics** (real-time):
- **Episode Reward**: Cumulative reward for current episode
- **Win Rate**: Percentage of episodes won (last 100)
- **Average Episode Length**: Mean frames per episode
- **PPO Stats**: Policy loss, value loss, entropy, KL divergence

**Checkpoint Files** (saved to `checkpoints/`):
- Format: `model_YYYY-MM-DD_HH-MM_fight_N.pt`
- Contains: Model weights, optimizer state, training config
- Auto-saved after each episode completion

**Logs** (`python/logs/`):
- Coordinator logs: Session events, errors
- Training logs: Reward curves, loss curves
- Event logs: Combat events from server

#### Step 7: Stop Training

To stop gracefully:

1. **In UI**: Click "Stop All"
2. **Coordinator**: Broadcasts `stop` message to all agents
3. **VM clients**: Complete current frame, release inputs, disconnect
4. **Main machine**: Saves final checkpoint, closes sessions

To resume later:

1. Restart `main.py` (will load latest checkpoint automatically)
2. Restart VM clients
3. Click "Start All" in UI

---

### Multi-Agent Training (Self-Play)

For agent-vs-agent self-play:

1. **Start 2+ VM clients** with different agent IDs:
   ```bash
   # VM 1
   cd python/client
   python client.py --agent-id 1 --fps 30
   
   # VM 2
   cd python/client
   python client.py --agent-id 2 --fps 30
   ```

2. **Launch Minecraft on each VM** and join the same server

3. **In UI**: All agent panels appear, click "Start All"

4. **Server mod**: Manages team assignments, combat events for all players

**Self-Play Benefits**:
- Agents learn to counter each other's strategies
- Emergent complexity from co-evolution
- No human opponent needed after bootstrapping

---

### Reward Configuration

Rewards are configured in the UI and applied automatically based on server events.

**Default Reward Schema** (Bootstrapping Phase):

| Event | Reward | Notes |
|-------|--------|-------|
| Victory | +500 | Agent wins fight |
| Defeat | -500 | Agent dies |
| HP Loss (Agent) | -10 per 0.5 heart | Encourages survival |
| HP Loss (Enemy) | +10 per 0.5 heart | Encourages aggression |
| Time Penalty | 0 | No time penalty during bootstrapping |

**Self-Play Reward Schema**:

| Event | Reward | Notes |
|-------|--------|-------|
| Victory | +1000 | Higher stakes |
| Defeat | -1000 | Higher stakes |
| HP Loss (Agent) | -10 per 0.5 heart | Same as bootstrapping |
| HP Loss (Enemy) | +10 per 0.5 heart | Same as bootstrapping |
| Time Penalty | -1 per frame | Punishes slow play |

**To modify rewards**:
1. Edit values in agent panel UI
2. Click "Apply" or "Apply to All"
3. Changes take effect immediately (even during training)

---

### Troubleshooting

#### VM Client Won't Connect

**Symptom**: "Connection refused" or timeout errors

**Solution**:
- Check main machine IP address is correct
- Verify port 8765 is not blocked by firewall
- Test with `telnet <main-ip> 8765`
- Check coordinator logs for connection attempts

#### No Frames Received

**Symptom**: UI shows agent as "Connected" but no frame count increasing

**Solution**:
- Verify Minecraft is running on VM
- Check screen capture region matches game window
- Look for errors in VM client logs
- Try lowering FPS (--fps 15)

#### Actions Not Executing in Game

**Symptom**: Model sends actions but character doesn't move

**Solution**:
- Verify pydirectinput is installed correctly
- Check Minecraft window has focus
- Disable "Raw Input" in Minecraft settings
- Run VM client as administrator (Windows)

#### Server Events Not Received

**Symptom**: No HIT/DEATH events in logs

**Solution**:
- Verify server-side mod is installed
- Check command bridge endpoint in mod config (should be localhost:9998 or main machine IP:9998)
- Check server-side mod logs for errors
- Test command bridge connectivity with `telnet <main-ip> 9998`
- If using HMAC authentication (optional), verify `PVP_CMD_SECRET` environment variable matches on both sides

#### Training Not Improving

**Symptom**: Win rate stays at 50% or model doesn't learn

**Solution**:
- Increase training iterations (let it run longer)
- Adjust reward schema (try higher terminal rewards)
- Check for reward shaping issues (sum of rewards should correlate with wins)
- Verify model is actually updating (check loss curves)
- Try different learning rate or hyperparameters

#### Out of Memory Errors

**Symptom**: CUDA out of memory or system RAM exhausted

**Solution**:
- Reduce batch size in PPO trainer config
- Lower FPS to reduce buffer fill rate
- Enable gradient checkpointing
- Use smaller model architecture
- Train on CPU if GPU memory insufficient

---

### Advanced Configuration

#### Hyperparameter Tuning

Edit `python/server/backend/ppo_trainer.py`:

```python
# Learning rate
lr = 3e-4  # Default, try 1e-4 for more stable training

# PPO clip epsilon
clip_epsilon = 0.2  # Default, try 0.1 for more conservative updates

# GAE lambda
gae_lambda = 0.95  # Default, try 0.99 for longer-term credit assignment

# Entropy coefficient
entropy_coef = 0.01  # Default, try 0.02 for more exploration
```

#### Custom Architectures

Edit `python/server/backend/model.py` to modify the CNN architecture:

```python
# Default: 64x64 grayscale input, 3 conv layers
# Customize layers, filters, activation functions
```

#### Distributed Training

Run multiple main machines with different model instances, then merge checkpoints periodically for ensemble training.

---

### Command Reference

**Main Machine**:
```bash
cd python/server
python main.py                    # Start coordinator + trainer + UI (uses defaults)
# Note: Configuration is currently hardcoded in manager.py
# - Coordinator: 0.0.0.0:8765
# - Command bridge: 127.0.0.1:9998
# - Device: auto-detected (CUDA > MPS > CPU)
```

**VM Client**:
```bash
cd python/client
python client.py --agent-id 1                              # Basic usage
python client.py --server-url ws://192.168.1.100:8765/ws   # Remote server
python client.py --fps 60 --width 640 --height 360        # High FPS + higher resolution
python client.py --jpeg-quality 85                         # Higher quality frames
python client.py --window-title-contains "Minecraft"       # Custom window detection
```

---

### File Structure Reference

```
python/
├── server/
│   ├── main.py                 # Main machine entry point
│   ├── requirements.txt        # Main machine dependencies
│   ├── backend/
│   │   ├── manager.py          # Service orchestrator
│   │   ├── coordinator.py      # WebSocket coordinator
│   │   ├── model.py            # CNN Actor-Critic
│   │   ├── ppo_trainer.py      # PPO algorithm
│   │   ├── command_bridge.py   # Event receiver (port 9998)
│   │   ├── inference_engine.py # Model inference
│   │   ├── session_registry.py # Agent session state
│   │   └── device_manager.py   # GPU/CPU detection
│   ├── frontend/
│   │   ├── UI.py               # PyQt6 main window
│   │   └── agent_controller.py # Agent panel widgets
│   └── tests/
│       └── ...                 # Server-side tests
├── client/
│   ├── client.py               # VM client entry point
│   ├── requirements.txt        # VM client dependencies
│   └── vm_client/
│       ├── runtime.py          # Main event loop
│       ├── capture.py          # Screen capture (mss)
│       ├── preprocess.py       # Grayscale + JPEG
│       ├── input_driver.py     # pydirectinput wrapper
│       └── ws_client.py        # WebSocket client
└── ACTIVE_PATHS.md             # Active vs legacy code guide
```

**Key Files**:
- `server/backend/manager.py`: Initializes all services, entry point from `server/main.py`
- `server/backend/coordinator.py`: Handles WebSocket sessions, frame/action routing
- `server/backend/ppo_trainer.py`: PPO algorithm, experience buffer, model updates
- `client/vm_client/runtime.py`: VM client main loop (capture → send → receive → execute)

**Legacy Files** (in `archive/`):
- `training_loop.py`: Old direct IPC approach (deprecated)
- Do not modify! See `ACTIVE_PATHS.md` for guidance

---

### Next Steps

1. **Complete Bootstrapping**: Train against human opponents until agents show basic combat competence
2. **Switch to Self-Play**: Update reward schema to Phase 2 values (high terminal rewards + time penalty)
3. **Monitor for Convergence**: Watch win rate, episode length, reward curves
4. **Validate Against Humans**: Periodically test agents against human players to ensure strategies generalize
5. **Iterate**: Adjust rewards, architectures, hyperparameters based on observed behavior

For detailed protocol specifications, see the **Protocol v1 Contract** at the top of this document.

For code structure clarification, see `python/ACTIVE_PATHS.md`.

For additional context, see the root [README.md](../README.md).

---

**End of Training Guide**
