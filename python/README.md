Python runtime overview (Protocol v1)
------------------------------------

This project now supports a distributed runtime:

- Main machine: runs coordinator + model/training + UI from `python/server/` (`python/server/main.py`)
- VM machine(s): run thin runtime client from `python/client/` (`python/client/client.py`) for frame capture and input execution
- Server event bridge: receives reset/combat events on command socket (`127.0.0.1:9998`)

Endpoints:
- WebSocket coordinator: `ws://<main-host>:8765/ws`
- Command bridge: `127.0.0.1:9998`

Run main machine:
```bash
cd python/server
pip install -r requirements.txt
python main.py
```

Run VM client:
```bash
cd python/client
pip install -r requirements.txt
python client.py --server-url ws://<main-host>:8765/ws --agent-id 1 --fps 30
```

Notes:
- Protocol schema and lifecycle are defined in `doc/TRAINING_GUIDE.md` (`2026 CONTRACT FREEZE (AGENT 0) - PROTOCOL V1`).
- VM client uses grayscale + JPEG frame transport and latest-action semantics.
- Input driver defaults to `pydirectinput` and releases held keys/buttons on stop/disconnect.
- Focused-window capture prefers active windows containing `VirtualBox` in title.
- You can copy only `python/client/` to VM machines so they do not need PyTorch or PyQt6.
