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
- `EVENT_BRIDGE`: `tcp://<main-host>:10001`
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

⚠️ IMPORTANT: This project already has a complete training system implemented!
   You don't need to write Python code - just use the provided files.

TABLE OF CONTENTS:
1. System Architecture Overview
2. Port Configuration  
3. Training Workflow Step-by-Step
4. Understanding the Python Code (Already Implemented!)
5. Reward System Configuration (GUI-Based)
6. Event Handling
7. Multi-Agent Training
8. Troubleshooting

================================================================================
1. SYSTEM ARCHITECTURE OVERVIEW
================================================================================

The system consists of 3 main components:

┌─────────────────┐        ┌──────────────────┐        ┌─────────────────┐
│  Minecraft Mod  │───────▶│  IPC (Sockets)   │───────▶│  Python AI      │
│  (Client-Side)  │◀───────│  Frame + Events  │◀───────│  training_loop  │
└─────────────────┘        └──────────────────┘        └─────────────────┘
      │                           │                            │
      │ Captures:                 │ Sends:                     │ Processes:
      │ - Screen frames           │ - RGB frames               │ - Observations
      │ - Player state            │ - Game state               │ - Actions
      │ - Hit/Death events        │ - Events                   │ - Rewards
      │                           │ - Commands                 │ - Training


HOW IT WORKS:
-------------
1. Minecraft client captures game state every frame (60 FPS)
2. Mod sends frame data + events to Python via TCP sockets
3. Python AI receives data, calculates reward, decides action
4. Python sends action back to mod (move, attack, etc.)
5. Mod executes action in-game
6. Repeat → AI learns over time!


================================================================================
2. PORT CONFIGURATION
================================================================================

PORT LAYOUT:
------------
Port 9998:  Command Channel (START/STOP/RESET commands)
Port 9999:  Agent 1 - Frame data stream
Port 10001: Agent 2 - Frame data stream
Port 10002: Agent 3 - Frame data stream
Port 10003: Agent 4 - Frame data stream
... (and so on for more agents)


IMPORTANT:
----------
- Each Minecraft client connects to ONE port (one agent)
- Python training_loop.py must listen on ALL agent ports simultaneously
- Command port (9998) is shared across all agents


================================================================================
3. TRAINING WORKFLOW STEP-BY-STEP
================================================================================

STEP 1: START PYTHON GUI
-------------------------
1. Open terminal in the "PVP KI" folder
2. Make sure you have dependencies installed:
   pip install torch numpy tkinter
3. Run: python training_loop.py
4. A GUI window will open titled "Multi-Agent PVP Training"
5. You'll see 2 agent panels by default (Agent 1 and Agent 2)


STEP 2: CONFIGURE REWARDS (IN THE GUI)
---------------------------------------
Each agent panel has reward sliders:
  - Win: +500.0 (default)
  - Loss: -500.0 (default)
  - Dmg Dealt: +10.0 (default)
  - Dmg Taken: -10.0 (default)
  - Time: -0.1 (default - penalty per frame)
  - Team Hit: -50.0 (default)
  - Team Kill: -500.0 (default)

You can adjust these values BEFORE starting training!
Use "Apply to All" button to copy settings to all agents.


STEP 3: START MINECRAFT CLIENT(S)
----------------------------------
1. Launch Minecraft with the mod installed
2. Join a server (or singleplayer)
3. Mod automatically connects to port 9999 (Agent 1)


STEP 4: START TRAINING (CLICK IN GUI)
--------------------------------------
1. In the GUI, click the "Start" button for Agent 1
2. The agent panel will show "Status: Running"
3. When Minecraft connects, you'll see "Connected!" in the agent log
4. Training starts automatically - no /ki start command needed!


STEP 5: MONITOR TRAINING (IN THE GUI)
--------------------------------------
Each agent panel shows:
  - Status: Running/Stopped/Stopping
  - Current Reward (resets on death)
  - Event log (shows hits, deaths, wins, losses)
  
Bottom panel shows:
  - Total fights completed
  - PPO updates performed  
  - Average policy/value loss
  - Entropy (exploration metric)

In Minecraft:
  /testframe  → Check IPC connection status
  /name       → Toggle nametag overlays


STEP 6: MULTI-AGENT TRAINING (2v2 or more)
-------------------------------------------
For self-play training with 2 agents:

1. In GUI, both Agent 1 and Agent 2 panels are already created
2. Click "Start" on both agents
3. Launch first Minecraft client → Auto-connects to Agent 1 (port 9999)
4. Launch second Minecraft client → Auto-connects to Agent 2 (port 10001)
5. Both agents train against each other!

To add more agents:
  - Click "+ Add Agent" in the GUI
  - Launch more Minecraft clients
  - Each client auto-connects to the next available port


STEP 7: SAVING THE MODEL
-------------------------
The model auto-saves after every fight ends (on death)!
Manual save: Click "Save Model" button in GUI

Checkpoints are saved to: checkpoints/pvp_model_YYYYMMDD_HHMMSS.pth


================================================================================
4. UNDERSTANDING THE PYTHON CODE (Already Implemented!)
================================================================================

YOU DON'T NEED TO WRITE CODE! The system is already complete.

FILES PROVIDED:
---------------
1. training_loop.py    - Main GUI and agent coordination
2. model.py            - Neural network (CNN + Actor-Critic)
3. ppo_trainer.py      - PPO algorithm implementation
4. ipc_client.py       - Socket communication utilities
5. drl_agent.py        - Additional agent utilities

HOW IT WORKS:
-------------
A) training_loop.py creates a GUI with:
   - Agent panels for each Minecraft client
   - Reward configuration sliders
   - Real-time status and metrics display
   - Start/Stop controls for each agent

B) Each agent connects to Minecraft via TCP socket:
   - Minecraft MOD → connects to → Python on ports 9999, 10001, etc.
   - Python receives: Frame data + Events + Game state
   - Python sends: Actions (movement, attack, look direction)

C) Neural Network (model.py):
   - Input: 64x64 RGB game frames
   - CNN extracts visual features
   - Actor outputs: Movement (W/A/S/D/Space/Attack) + Look (Yaw/Pitch)
   - Critic outputs: State value (for PPO training)

D) PPO Training (ppo_trainer.py):
   - Collects experiences in a shared buffer
   - Computes advantages using GAE (Generalized Advantage Estimation)
   - Updates policy with clipped objective
   - Auto-saves checkpoints after each fight

E) Reward Calculation:
   - Configured via GUI sliders (see Step 2 above)
   - Applied automatically based on events from Minecraft
   - Example: Hit enemy → +10.0, Got hit → -10.0, Win → +500.0
   - Per-Damage Relation-Based Rewards (NEW):
     * Enemy Hit/♥: reward per 0.5 heart dealt to enemies (default: +5.0)
     * Neutral Hit/♥: penalty per 0.5 heart dealt to neutrals (default: -10.0)
     * Team Hit/♥: penalty per 0.5 heart dealt to teammates (default: -25.0)
   - Encourages precise targeting and discourages friendly fire
   - Fine-tune per half-heart to train agents on damage optimization

THE SYSTEM IS FULLY AUTOMATED!
-------------------------------
Once you:
1. Start the GUI (python training_loop.py)
2. Click "Start" on an agent
3. Launch Minecraft

Everything else happens automatically:
  ✅ Frame capture and sending
  ✅ Event detection (hits, deaths)
  ✅ Reward calculation
  ✅ Neural network inference
  ✅ Action execution in-game
  ✅ PPO training updates
  ✅ Model checkpointing


================================================================================
5. REWARD SYSTEM CONFIGURATION (GUI-Based - No Code Needed!)
================================================================================

REWARD CONFIGURATION IN THE GUI:
---------------------------------
Each agent panel has 7 reward sliders you can adjust IN REAL-TIME:

1. WIN REWARD (+500.0 default)
   - Given when the agent wins a fight (enemy dies, agent survives)
   - Higher = More motivation to win
   - Resets agent's cumulative reward to 0 after win

2. LOSS PENALTY (-500.0 default)  
   - Given when the agent loses (agent dies)
   - More negative = More punishment for dying
   - Resets agent's cumulative reward to 0 after loss

3. DAMAGE DEALT (+10.0 default)
   - Given for each hit the agent lands on enemy
   - Detected via EVENT:HIT events from mod
   - Encourages aggressive play

4. DAMAGE TAKEN (-10.0 default)
   - Given when agent loses health
   - Calculated from health delta in frame header
   - Encourages defensive play and dodging

5. TIME PENALTY (-0.1 default)
   - Applied EVERY FRAME
   - Encourages fast, decisive combat
   - Prevents passive/camping strategies
   - Total penalty = -0.1 × frames_per_fight

6. TEAM HIT PENALTY (-50.0 default)
   - Given when agent hits a teammate
   - Only applies in team modes
   - Discourages friendly fire

7. TEAM KILL PENALTY (-500.0 default)
   - Given when agent kills a teammate
   - Severe punishment for team kills
   - Only applies in team modes


HOW TO ADJUST REWARDS:
-----------------------
1. Type new values in the text boxes next to each reward
2. Press Enter to apply
3. Changes take effect IMMEDIATELY (even during active training!)
4. Use "Apply to All" button to copy settings to all agents


RECOMMENDED CONFIGURATIONS:
---------------------------

AGGRESSIVE FIGHTER:
  Win: +500, Loss: -300, Dmg Dealt: +20, Dmg Taken: -5, Time: -0.2

DEFENSIVE FIGHTER:
  Win: +800, Loss: -100, Dmg Dealt: +5, Dmg Taken: -30, Time: -0.05

BALANCED:
  Win: +500, Loss: -500, Dmg Dealt: +10, Dmg Taken: -10, Time: -0.1

SPEEDRUNNER (Fast kills):
  Win: +1000, Loss: -200, Dmg Dealt: +15, Dmg Taken: -5, Time: -1.0


HOW REWARDS ARE CALCULATED:
----------------------------
The training_loop.py automatically:

1. Monitors health changes → applies Damage Taken penalty
2. Detects EVENT:HIT events → applies Damage Dealt reward
3. Detects EVENT:DEATH events → applies Win/Loss rewards
4. Applies Time Penalty every frame
5. Accumulates total reward and displays in GUI
6. Resets to 0 after each fight ends


================================================================================
6. EVENT HANDLING
================================================================================

EVENTS SENT FROM MOD TO PYTHON:
--------------------------------

1. EVENT:HIT:attacker:target
   - Triggered when attacker hits target
   - Works on any server (client-side detection)
   - Example: "EVENT:HIT:Player1:Player2"

2. EVENT:DEATH:victim:killer
   - Triggered when victim dies
   - killer = player name OR "Environment"
   - Works on any server (chat message parsing)
   - Example: "EVENT:DEATH:Player2:Player1"
   - Example: "EVENT:DEATH:Player1:Environment"


FRAME HEADER FORMAT:
--------------------
{
  "events": ["EVENT:HIT:...", "EVENT:DEATH:..."],
  "player_name": "YourPlayerName",
  "agent_id": 1,
  "health": 20.0,
  "position": {"x": 100, "y": 64, "z": 200},
  "yaw": 90.0,
  "pitch": 0.0,
  "bodyLength": 691200,  // Frame size in bytes
  "cmd_type": "START",   // Optional command
  "cmd_data": "..."      // Optional command data
}


================================================================================
7. MULTI-AGENT TRAINING (Self-Play)
================================================================================

WHAT IS SELF-PLAY?
------------------
Training multiple copies of the same agent against each other.
All agents share the SAME neural network weights.
This creates a "curriculum" where agents continuously adapt to their own strategies.

BENEFITS:
- Agents never plateau - always facing equally skilled opponents
- Discovers creative strategies and counter-strategies
- Much faster than training against fixed opponents
- No need for human players!


SETUP FOR 2-AGENT SELF-PLAY:
-----------------------------
1. Start training_loop.py GUI
2. You'll see Agent 1 and Agent 2 panels (already created by default)
3. Click "Start" on BOTH agents
4. Launch Minecraft client 1 → Auto-connects to port 9999 (Agent 1)
5. Launch Minecraft client 2 → Auto-connects to port 10001 (Agent 2)
6. Put them in the same Minecraft world
7. Let them fight!

IMPORTANT:
- Both agents share the same model (controlled by shared_model flag)
- Each fight improves BOTH agents simultaneously
- Model auto-saves after every fight ends


ADDING MORE AGENTS (3+ Players):
---------------------------------
1. In GUI, click "+ Add Agent" button
2. Agent 3 appears on port 10002
3. Launch Minecraft client 3 → Auto-connects to 10002
4. Repeat for Agent 4, 5, etc.

TEAM VS TEAM (2v2, 3v3):
------------------------
1. Create 4 agents in GUI
2. Launch 4 Minecraft clients
3. In Minecraft, use team commands:
   /team create red
   /team create blue
   /team add red Agent1Name
   /team add red Agent2Name
   /team add blue Agent3Name
   /team add blue Agent4Name
4. Agents will avoid hitting teammates (Team Hit/Kill penalties apply)


PORT ALLOCATION:
----------------
Agent 1: Port 9999
Agent 2: Port 10001 (skips 10000)
Agent 3: Port 10002
Agent 4: Port 10003
... and so on

Each Minecraft client auto-connects to the next available port.


================================================================================
8. TROUBLESHOOTING
================================================================================

PROBLEM: "IPC not active - Python not connected"
SOLUTION:
  - Make sure training_loop.py is running FIRST
  - Check Python is listening on the correct port
  - Verify firewall isn't blocking connections
  - Use /testframe command to check status

PROBLEM: "Frames not being sent"
SOLUTION:
  - Check console output for "[IPC Port 9999] Frame sent"
  - Verify Python is reading frames correctly
  - Check socket connection isn't timing out

PROBLEM: "Events not detected"
SOLUTION:
  - Hit events: Check AttackEntityCallback is registered
  - Death events: Check chat messages are being parsed
  - Use /testframe to verify IPC is active

PROBLEM: "Port 10001 gets skipped"
SOLUTION:
  - Already fixed! Command port moved to 9998
  - Agent 1 = 9999, Agent 2 = 10001, Agent 3 = 10002

PROBLEM: "Nametags not rendering"
SOLUTION:
  - Create team: /team create myteam
  - Add player: /team add myteam PlayerName
  - Teams are now synced to clients automatically!
  - Toggle nametags: /name

PROBLEM: "Rewards not tracking"
SOLUTION:
  - Make sure /ki start was called
  - Check Python is processing events correctly
  - Verify event format matches expected pattern
  - Check cumulative_reward is being updated


================================================================================
QUICK REFERENCE - COMMANDS
================================================================================

CLIENT-SIDE COMMANDS (work on any server):
  /ki start          → Start reward tracking
  /ki stop           → Stop reward tracking
  /ki reset          → Reset rewards (no teleport)
  /testframe         → Check IPC connection status
  /name              → Toggle nametag overlays
  /agent <id>        → Switch to agent ID (changes port)
  /kit create <name> → Save current inventory as kit
  /kit load <name>   → Load kit
  /kit list          → List all kits
  /kit sync          → Sync client kits to server

SERVER-SIDE COMMANDS (require mod on server):
  /ki start          → Start tracking (sends to port 9998)
  /ki stop           → Stop tracking
  /ki reset <p1> <p2> <kit> [shuffle] → Reset players with kit
  /team create <name>      → Create team
  /team add <team> <player> → Add player to team
  /team remove team <name>  → Remove team
  /team remove player <name> → Remove player from team
  /team list         → List all teams
  /team clear        → Clear all teams


================================================================================
IMPORTANT NOTES
================================================================================

✅ THE SYSTEM IS COMPLETE - NO CODING REQUIRED!
------------------------------------------------
Everything is already implemented:
  - Neural network model (CNN + Actor-Critic)
  - PPO training algorithm
  - Experience replay buffer
  - GUI for monitoring and configuration
  - Auto-save checkpoints
  - Multi-agent support

All you need to do:
  1. Run: python training_loop.py
  2. Click "Start" in GUI
  3. Launch Minecraft
  4. Watch it train!


✅ REWARD TUNING IS KEY
-----------------------
The default rewards work well, but experiment with:
  - Higher win rewards for more aggressive play
  - Higher time penalties for faster fights
  - Lower damage taken penalties if agent is too passive


✅ TRAINING TAKES TIME
----------------------
- Expect 100-1000 fights before agent shows skill
- Early fights will be random/chaotic
- Gradually agent learns to aim, dodge, combo attacks
- Save checkpoints frequently!


✅ WORKS ON ANY SERVER
----------------------
- Client-side only - no server mod needed
- Hit detection works via client
- Death detection via chat parsing
- Train on vanilla servers, PvP servers, anywhere!


✅ MODEL SAVES AUTOMATICALLY
----------------------------
- Auto-saves after every fight (on death)
- Manual save: Click "Save Model" button
- Checkpoints saved to: checkpoints/pvp_model_YYYYMMDD_HHMMSS.pth
- Load previous checkpoint by modifying training_loop.py


✅ MONITOR METRICS
------------------
Bottom panel shows real-time training metrics:
  - Fights: Total fights completed
  - Updates: PPO optimization steps
  - Policy Loss: How well agent follows policy
  - Value Loss: How accurate value predictions are
  - Entropy: How much exploration is happening


✅ TROUBLESHOOTING TIPS
-----------------------
- If reward stays at 0: Check agent is hitting/being hit
- If agent doesn't move: Check action sending (2 bytes + JSON)
- If model doesn't learn: Try increasing batch_size or epochs in ppo_trainer.py
- If training is slow: Lower frame resolution in FrameCaptureMixin


Good luck with your training! 🚀
The agent will surprise you with emergent strategies!
================================================================================
