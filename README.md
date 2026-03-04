
# PVP-KI

PVP-KI is a hybrid project combining Java and Python components to create an advanced AI agent for Minecraft PvP scenarios. It enables automated player-versus-player actions, reinforcement learning, and agent control, supporting both client and server-side modifications.

## Features
- **Main-machine coordinator runtime (Protocol v1):** Central WebSocket coordinator, model/training, and Start-All session control.
- **VM thin client runtime:** Screen capture (grayscale/JPEG), frame streaming, and action execution via `pydirectinput`.
- **Server-authoritative event/reset bridge:** Minecraft server-side events and reset signals flow into Python command bridge.
- **Modular Design:** Easily extendable for new features, kits, and AI strategies.
- **Documentation:** Training guides, plans, and summaries for AI development and mod integration.

## Protocol v1 Quick Start
1. Install Python dependencies from [python/requirements.txt](python/requirements.txt).
2. Start main machine runtime:
   - `cd python`
   - `python main.py`
3. Start each VM runtime client:
   - `cd python`
   - `python client.py --server-url ws://<main-host>:8765/ws --agent-id <N> --fps 30`
4. In the UI, wait for clients to become ready and use **Start All**.

Canonical contract and schemas are documented in [doc/TRAINING_GUIDE.md](doc/TRAINING_GUIDE.md) under `2026 CONTRACT FREEZE (AGENT 0) - PROTOCOL V1`.

## Java/Python Integration
The Java mod communicates with the Python backend via IPC, allowing real-time control and training of AI agents. The Python backend can send commands, receive game state, and manage agent behavior, while the Java mod executes actions in Minecraft.

## Project Structure
- `pvp_ki-template-1.21.10/`: Java Fabric mod source
  - `src/client/java/com/example/`: Client-side logic, overlays, mixins
  - `src/main/java/com/example/`: Server-side logic, team/kit management, IPC
  - `src/main/resources/`: Mod configuration and assets
- `python/`: Python AI agent, backend, and frontend
  - `backend/`: Reinforcement learning, agent training, model management
  - `frontend/`: Agent controller UI
  - `archive/`: Legacy and experimental scripts
- `doc/`: Documentation and training guides

## Setup
### Java (Fabric Mod)
1. Install Minecraft and Fabric Loader (compatible version)
2. Build the mod:
   ```bash
   cd pvp_ki-template-1.21.10
   ./gradlew build
   ```
3. Place the generated `.jar` in your Minecraft mods folder
4. Configure mod settings as needed in `src/main/resources/`

### Python (AI Agent)
1. Install Python 3.10+ and pip
2. Create and activate a virtual environment:
   ```bash
   cd python
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies inside the virtual environment:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the main agent:
   ```bash
   python main.py
   ```
5. For training, refer to `doc/TRAINING_GUIDE.md` and use scripts in `python/backend/`

## Usage
- Launch Minecraft with the mod installed
- Start the Python backend for agent control and training
- Use the UI in `python/frontend/UI.py` for agent management
- For reinforcement learning, follow the steps in `doc/TRAINING_GUID.md`
- Example: To start training, run `python/backend/ppo_trainer.py`

## Documentation
- Guides and plans: `doc/`
- Java source: `pvp_ki-template-1.21.10/src/`
- Python backend: `python/backend/`
- Python frontend: `python/frontend/`

## Contributing
Pull requests and issues are welcome. Please review the documentation, follow the project structure, and ensure code quality.

## License
See `pvp_ki-template-1.21.10/LICENSE` for license details.

## Contact
For questions or support, open an issue in the repository or consult the documentation in `doc/`.
