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
- Visual team/enemy/neutral identification
- `[Team]` (green) for teammates
- `[Enemy]` (red) for opponents
- `[Neutral]` (gray) for neutrals
- Labels-only display (no player names)
- `/nametags` - Toggle overlay (default ON, session-only)
- `/clientteam team add/remove` - Client fallback teams (when not OP)
- `/clientteam neutral add/remove` - Client neutral list
- `/ki neutral <teamName>` - Server-side neutral team marking (OP-only)

#### **Phase 6: PPO Training Infrastructure**
- Shared Actor-Critic model across all agents
- Experience buffer with automatic batching
- GAE (λ=0.95) + PPO clipping (ε=0.2)
- Autosave every 10 fights to `checkpoints/`
- Real-time metrics display (policy loss, value loss, entropy)
- Per-damage relation-based rewards:
  - Enemy Hit/♥: reward per 0.5 heart dealt to enemies
  - Neutral Hit/♥: penalty per 0.5 heart dealt to neutrals
