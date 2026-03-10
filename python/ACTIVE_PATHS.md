# Active and Legacy Code Paths

This document clarifies which parts of the Python backend are actively maintained and which are considered legacy or deprecated.

## ✅ Active Runtime Path

The canonical, actively maintained main-machine runtime is:

**`server/main.py` → `server/backend/manager.py` → `server/backend/coordinator.py`**

- **`server/main.py`**: Application entry point, starts the UI and the `Manager`.
- **`server/backend/manager.py`**: The central orchestrator. It initializes and manages all backend services, including the model, trainer, coordinator, and command bridge.
- **`server/backend/coordinator.py`**: The WebSocket server that handles communication with VM clients. It receives screen frames, orchestrates model inference, and sends back actions. This is the primary path for data collection and agent interaction.
- **`server/backend/command_bridge.py`**: Listens for in-game events (like HIT, DEATH) from the Minecraft server and forwards them to the `Manager` for reward processing.

The actively maintained VM runtime path is:

**`client/client.py` → `client/vm_client/runtime.py`**

- **`client/client.py`**: VM entry point that parses runtime config and starts the async client loop.
- **`client/vm_client/runtime.py`**: Thin runtime that captures frames, sends them to the coordinator, and executes returned actions.

All new feature development, bug fixes, and performance optimizations should target this path.

## ⛔ Legacy / Deprecated Path

The following modules are considered deprecated and are **not** part of the active runtime. They are kept for historical reference only.

**`archive/old_root_files/training_loop.py`**

- This file represents a previous architecture that used a direct socket-based IPC connector (`ipc_connector.py`, also archived).
- It is no longer maintained, and its `AgentController` is superseded by the `WebSocketCoordinator`.
- **Do not** add new features or GPU logic to this file. It is a dead code path.
