Full System Design Plan (Option B)

Overview
- Goal: Unified PvP KI system with dynamic agents, client-side teams, server HIT/DEATH event streaming to Python, biome-controlled resets, and live PPO training with a shared model and autosaves.
- Environments: Works both with and without the server mod. Client-side features (teams, nametags) function on any server; server-enhanced features (events, biome filtering) activate when mod is present.

Architecture Map
- Python GUI
  - AgentManager: add/remove agents with incrementing ports (9999 + i)
  - AgentController: per-agent loop reads frame+state, computes actions, accumulates rewards
  - Command Listener: dedicated command port 10001 to receive START/STOP/RESET/HIT/DEATH/MAP
  - PPO Trainer: shared model, aggregated experience, autosave
- Java (Client)
  - PVP_KIClient: client-side commands (/team, /agent), IPCManager, frame sending
  - IPCManager: injects events, states, and pending commands into header; connects to Python agent ports
- Java (Server)
  - PVP_KI: server-side commands (/ki reset, /ki settings), biome filtering, kit application, HIT/DEATH events
  - ServerIPCClient: fire-and-forget command sender to Python (port 10001)
  - SettingsManager: settings.json persisted (nametags toggle, biome allow/block, penalties)
  - KitManager: server kits for /ki reset

Commands Overview
Client-side (works everywhere)
- /agent <n>: Assigns local player to Agent n; client sends MAP{name, agent_id} to Python
- /team add <player>, /team remove <player>, /team list, /team clear: Local team membership. If mod present, server broadcasts to all clients.
- /kit create/list/load/delete/edit: Local client kits; already implemented.

Server-side (requires mod)
- /ki start|stop: Control reward tracking via Python command port 10001
- /ki reset <p1> <p2> <kit> [shuffle]: Teleport to allowed biome, apply kits, send RESET and start match
- /ki settings ...: Manage global settings (see Settings below)
- /ki createkit <name>: Save server kit for resets

Settings (via /ki settings)
- /ki settings show: Display all settings
- /ki settings nametags <on|off>: Toggle nametag override (Team=green, Enemy=red, hide names)
- /ki settings biome allow <biome>: Add to allowed list; when present, only teleport to these biomes
- /ki settings biome block <biome>: Add to blocked list; ignored if allowed list is non-empty
- /ki settings biome clear: Clear allow + block lists
- /ki settings biome list: Show current allow/block
- Persisted: settings.json (nametags, biome lists). Teams: temporary (not persisted).
- NOTE: Team hit/kill penalties removed from server settings - now configured per-agent in Python GUI.

IPC Channels & Message Formats
- Agent Ports: 9999, 10000, 10002, 10003, ... (per agent, skip 10001 for command port)
  - Header (JSON) fields injected by IPCManager (client-side):
    - width, height, bodyLength
    - health, events["EVENT:HIT:<attacker>:<victim>", "EVENT:DEATH:<victim>:<killer>"]
    - player_name (local player), agent_id (current agent selection)
    - teams: {"<playerName>": "team"|"enemy"|null} - client-side team membership for ALL visible players
    - NOTE: Client injects HIT/DEATH events from local combat detection + team info; works on ANY server (with or without mod)
- Command Port: 10001 (ServerIPCClient -> Python, optional when mod is on server)
  - One-shot JSON messages, length-prefixed (4-byte big-endian):
    - {"type":"START","data":"Reward tracking started"}
    - {"type":"STOP","data":"Reward tracking stopped"}
    - {"type":"RESET","data":"<p1Name>,<p2Name>"}
    - {"type":"HIT","data":"<attackerName>,<victimName>"} (server-side duplicate, optional)
    - {"type":"DEATH","data":"<victimName>,<killerName>"} (server-side duplicate, optional)
    - {"type":"TEAM","data":"ADD:<player>"} or "REMOVE:<player>"} (optional server broadcast)
    - {"type":"MAP","data":"<playerName>,<agentId>"} (optional server mirror)

Agent Management
- Python AgentManager: Add Agent button creates new AgentController with port = 9999 + index; Remove Last removes
- Client /agent <n>: Maps local player to agent n; IPCManager injects {player_name, agent_id} in headers; Python tracks mapping {player_name -> agent_id}
- Server optional MAP: If client cannot inject (non-mod server), client-side still injects; if mod is present, server mirrors MAP over port 10001 when needed

Team System (Client-Side, Works Everywhere)
- Client-side /team commands manage local team membership (team add/remove/list/clear)
- Client tracks team membership for ALL visible players in match, sends via header field "teams" to Python
- Python receives: {"Technoblade": "team", "Dream": "enemy", "Notch": null}
- Works on ANY server (with or without mod):
  - Client detects HIT/DEATH locally (via AttackEntityCallback, AFTER_DEATH on client)
  - Client injects events into header with attacker/victim names
  - Python uses team data + agent mapping to apply correct rewards/penalties
- With mod on server (optional enhancement): server can broadcast TEAM changes so all clients stay synced
- Nametags:
  - Client-side setting (toggle via /ki settings nametags or local client command)
  - When enabled: overlay "Team" (green) or "Enemy" (red), hide actual names
  - When disabled: show normal names
- Teamhit/Teamkill penalties:
  - Configured per-agent in Python GUI (team_hit_penalty, team_kill_penalty)
  - Python reward logic: if attacker and victim both in agent's team list -> apply penalty

Biome-Filtered Reset
- Allowed-biomes list present -> choose location only within allowed set; repeatedly sample random chunks and read biome until matched
- If allowed-biomes empty -> avoid blocked-biomes if set; otherwise any biome
- For p1 at (x,z): compute safe y (scan from 320 downward until solid, teleport to y+1.8)
- For p2 at (x+10, z): compute independent y2 similarly
- Apply kits via KitManager; send RESET to Python

Event Streaming (Client-Side, Works on Any Server)
- Client-side event detection (AttackEntityCallback, ServerLivingEntityEvents on client):
  - On local player hit or is hit: record HIT event with attacker/victim names
  - On death: record DEATH event with victim/killer names
- Client IPCManager injects events into header "events" array (already implemented)
- Client also injects "teams" object with current team membership for all visible players
- Python AgentController receives events in header, applies rewards:
  - HIT dealt by agent: +damage_dealt (per-agent configurable)
  - HIT taken by agent: +damage_taken (per-agent configurable, typically negative)
  - DEATH (agent killed): +loss_penalty
  - DEATH (agent got kill): +win_reward
  - Teamhit (agent hit teammate): +team_hit_penalty (per-agent configurable, typically negative)
  - Teamkill (agent killed teammate): +team_kill_penalty (per-agent configurable, typically large negative)
- Optional server-side duplicate (if mod present): Server can also send HIT/DEATH via port 10001 for redundancy/logging

Python: Agent-Player Mapping
- When /agent <n> used, client injects header fields {player_name, agent_id}; Python persists mapping in memory
- On HIT/DEATH commands, Python looks up agent ids for attacker/victim to correctly assign rewards/penalties
- If no mapping found, event logged but ignored for reward changes

Training: PPO (Shared Model)
- Model: Shared Actor-Critic across all agents (CNN trunk -> policy head (logits) + value head)
- Experience: Each AgentController adds (state, action, reward, done) to a global buffer
- Update cadence (defaults):
  - Batch size: 256 frames
  - LR: 3e-4 (Adam)
  - Epochs: 4 per batch
  - Gamma: 0.99, GAE-lambda: 0.95
  - Clip range: 0.2
- Autosave: Every 10 fights -> checkpoints/model_YYYY-MM-DD_HH-mm_fight_<N>.pt
- Per-agent reward config in GUI (all configurable):
  - Win reward
  - Loss penalty
  - Damage dealt
  - Damage taken
  - Time penalty (per frame)
  - Team hit penalty (NEW)
  - Team kill penalty (NEW)
- "Apply to all" button copies the current agent's values to all other agents

Data & Persistence
- settings.json (server): {showTeamNametags, allowedBiomes[], blockedBiomes[], team penalties}
- kits.json (server): server kit storage for /ki reset
- client_kits.json (client): local kit storage
- Agent-player mapping: Python in-memory; optional save file agent_mapping.json if you want persistence later
- Checkpoints: ./checkpoints/ shared directory for autosaves

Client vs Server Behavior
- Without mod: Client-only /team applies local overlays + Python reward logic; /agent injects mapping via headers; HIT/DEATH are not available from server, so Python relies on local health trend and time penalties
- With mod: Full pipeline active (events, biome filter, team broadcast), better training signal

Implementation Plan (Phased)
Phase 1: IPC + Events
- ServerIPCClient: send HIT/DEATH/RESET over 10001 (already implemented RESET)
- Python command_listener: parse new HIT/DEATH types, apply mapping/rewards
- Client /agent: inject {player_name, agent_id} in headers

Phase 2: Teams + Nametags
- Client /team commands; local lists and overlays (green Team, red Enemy, names hidden)
- Settings toggle: /ki settings nametags on/off controls overlays
- With mod: server relays TEAM changes to all clients (optional), or each client maintains own view

Phase 3: Biome Filtering
- SettingsManager with allowed/blocked lists; /ki settings biome commands
- /ki reset samples only allowed biomes; computed y for both p1/p2

Phase 4: PPO Training
- Shared model, buffer, optimizer, update step after batch size reached
- Autosave every 10 fights with timestamped filenames
- "Apply to all" GUI hook for reward configs

Testing Plan
- Unit: Verify SettingsManager load/save; biome filtering logic
- Integration: Run Python GUI; issue /ki start, /ki reset, /team add; observe logs and reward updates
- Events: Hit a player on server; verify Python logs HIT and adjusts reward for mapped agent
- PPO: Simulate small fights; verify buffer growth, update calls, checkpoint files created

Edge Cases & Safeguards
- Mapping missing: log and skip reward adjustment
- Command port unavailable: log warning; continue frame loop
- Biomes rare: If allowed set very small, warn after N attempts; keep trying or fall back to next allowed biome
- Nametags off: original names remain; no overlays; penalties still applied if teams exist

File Changes Summary (to be implemented)
- Java (server): PVP_KI.java (commands, events, reset), SettingsManager.java (new), ServerIPCClient.java (already using 10001)
- Java (client): PVP_KIClient.java (/team, /agent injection), IPCManager.java (header field injection)
- Python: training_loop.py (AgentManager, command_listener: HIT/DEATH/MAP, PPO trainer, autosave)

Try-It Instructions
- Build mod:
  - Windows: gradlew.bat build
- Run Python GUI:
  - python training_loop.py
- In-game:
  - /agent 1, /agent 2, ...
  - /team add <name>; /ki settings nametags on
  - /ki settings biome allow plains; /ki reset <p1> <p2> <kit>
  - Watch Python logs: HIT/DEATH, RESET, reward updates, checkpoint saves

Notes
- All colors fixed: Team=green, Enemy=red; overridable via /ki settings nametags on/off only (no custom colors for now)
- Team penalties adjustable via /ki settings; individual rewards adjustable per agent in GUI; "Apply to all" button syncs values.
