# IPC Test Input Fix - Summary

## Problem
When clicking test input buttons in the training GUI, it showed:
- "Connected!" when the agent first started
- "IPC not connected" when trying to send test inputs

## Root Cause
The Python code in `training_loop.py` was trying to access Java's `IPCManager` object, which is **impossible from Python**. The code had:

```python
self.ipcManager = None  # Tried to reference Java IPCManager
# Later...
self.ipcManager.currentOut.write(...)  # This could never work!
```

This is a fundamental architecture issue:
- Python runs as a separate process on one end of a socket
- Java/Minecraft runs on the other end
- They cannot directly access each other's objects

## Solution
Implemented proper bidirectional socket communication:

1. **Store the client socket in AgentController** (line 24)
   - When the agent connects to the Minecraft mod, save the socket reference
   - `self.client_socket = None` initialized in `__init__`
   - `self.client_socket = client` set in `loop()` after connection (line 278)
   - `self.client_socket = None` cleared on disconnect (line 462)

2. **Send test inputs over the same socket** (lines 182-211)
   - Use the stored `client_socket` to send actions
   - Proper protocol: 2-byte length prefix + JSON action bytes
   ```python
   self.client_socket.send(struct.pack('>H', len(action_bytes)))
   self.client_socket.send(action_bytes)
   ```

3. **Removed broken references**
   - Deleted `agent.ipcManager = self.ipc_manager` from AgentManager.add_agent()
   - Removed unused `self.ipc_manager = None` initialization

## How It Works Now

```
GUI (Python)
  ├─ Agent clicks test button
  └─ send_test_input() calls
      └─ self.client_socket.send(action_json)
            ↓
Minecraft Mod (Java)
  ├─ IPCManager receives on port 9999/10001/etc
  └─ Mod parses action and applies to player
```

## Testing
- Syntax verified: `python -m py_compile training_loop.py` ✓
- Ready for live testing with Minecraft client

## Files Changed
- `training_loop.py`: AgentController class, send_test_input method, loop method, add_agent method
