# Team Hit/Kill Penalties Implementation Summary

## Overview
This implementation adds per-agent configurable team hit and kill penalties to the Python training system, as specified in `full-plan.txt`. This allows the AI training system to recognize and penalize agents when they hit or kill teammates, which is crucial for training agents to avoid friendly fire.

## Changes Made

### 1. Python GUI Enhancements (`training_loop.py`)

#### New Agent Configuration Fields
- **`team_hit_penalty`**: Penalty applied when agent hits a teammate (default: -50.0)
- **`team_kill_penalty`**: Penalty applied when agent kills a teammate (default: -500.0)

These fields are added to the reward configuration UI for each agent, alongside existing fields like win_reward, loss_penalty, damage_dealt, etc.

#### "Apply to All" Functionality
- Added button to copy all reward settings from one agent to all other agents
- Useful for quickly synchronizing settings across multiple agents
- Provides feedback when operation succeeds or fails

#### Agent-Player Mapping
- Added `agent_id` and `player_name` attributes to track which player controls each agent
- Automatically updated from header data when `/agent` command is used in Minecraft
- Also supported via MAP command from server (optional)

### 2. Team Penalty Logic

The implementation correctly handles team membership detection:

#### Team Hit Detection
```python
if attacker and victim both have team status == 'team':
    apply team_hit_penalty
else:
    apply normal damage_dealt reward
```

#### Team Kill Detection
```python
if killer and victim both have team status == 'team':
    apply team_kill_penalty
else:
    apply normal win_reward or loss_penalty
```

The `teams` dictionary received in headers has format:
- `{"playerName": "team"}` - Player is on this agent's team
- `{"playerName": "enemy"}` - Player is on opposing team
- `{"playerName": null}` - Unknown/neutral player

### 3. Event Handling Improvements

Enhanced HIT and DEATH event parsing to extract player names:
- `EVENT:HIT:attacker:victim` - Parses attacker and victim names
- `EVENT:DEATH:victim:killer` - Parses victim and killer names

Events are checked against team membership data to determine if penalties should apply.

### 4. Command Listener Enhancements

Added support for new command types:
- **MAP**: Maps player names to agent IDs for proper reward tracking
- **HIT**: Optional server-side HIT event forwarding
- **DEATH**: Optional server-side DEATH event forwarding

### 5. Port Allocation Fix

Fixed port allocation to properly skip port 10001 (reserved for command port):
- Agent 1: Port 9999
- Agent 2: Port 10000
- Agent 3: Port 10002 (skips 10001)
- Agent 4: Port 10003
- And so on...

## How It Works

### Flow Diagram
```
1. Player uses /agent <n> in Minecraft
   ↓
2. Client injects {player_name, agent_id} in frame header
   ↓
3. Python updates agent mapping (player_name → agent_id)
   ↓
4. Player hits/kills another player
   ↓
5. Client injects EVENT:HIT or EVENT:DEATH with names
   ↓
6. Client also sends team membership data in header
   ↓
7. Python checks if both players are on same team
   ↓
8. If yes: Apply team penalty
   If no: Apply normal reward
```

### Example Scenario

**Setup:**
- Agent 1 controls player "Alice"
- Team members: ["Alice", "Bob"]
- Enemies: ["Charlie"]

**Scenario 1: Team Hit**
- Alice hits Bob
- Result: Agent 1 receives `team_hit_penalty` (-50.0)

**Scenario 2: Normal Hit**
- Alice hits Charlie
- Result: Agent 1 receives `damage_dealt` (+10.0)

**Scenario 3: Team Kill**
- Alice kills Bob
- Result: Agent 1 receives `team_kill_penalty` (-500.0)

**Scenario 4: Normal Kill**
- Alice kills Charlie
- Result: Agent 1 receives `win_reward` (+500.0)

## Testing

### Syntax Validation
✅ All Python files compile without syntax errors

### Logic Validation
✅ Team hit detection works correctly
✅ Team kill detection works correctly
✅ Normal combat detection still works
✅ Port allocation correctly skips 10001

### Security Scan
✅ CodeQL analysis found 0 vulnerabilities

## Configuration

To use the new team penalty features:

1. **Start Python Training GUI:**
   ```bash
   python training_loop.py
   ```

2. **Configure Team Penalties:**
   - Adjust "Team Hit" and "Team Kill" values for each agent
   - Use "Apply to All" button to sync settings across agents

3. **In Minecraft:**
   - Use `/agent 1` or `/agent 2` to assign your player to an agent
   - Use `/team add <player>` to add players to your team
   - When you hit/kill teammates, penalties are automatically applied

4. **Monitor Rewards:**
   - Watch the reward display in the GUI
   - Check logs for "TEAM HIT" and "TEAM KILL" messages

## Benefits

1. **Per-Agent Customization**: Each agent can have different penalty values for fine-tuned training
2. **Easy Synchronization**: "Apply to All" button for quickly setting all agents to the same values
3. **Accurate Tracking**: Correctly identifies team hits/kills vs. normal combat
4. **Flexible Training**: Encourages agents to learn teamwork and avoid friendly fire
5. **Client-Side**: Works on any server, with or without the mod

## Notes

- Team membership is determined client-side and sent to Python via headers
- Works on any Minecraft server (mod not required for basic functionality)
- Server-side mod enhances functionality with optional features like team broadcasting
- The implementation follows the specification in `full-plan.txt`
