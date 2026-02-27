IPC and testing notes
---------------------

Ports:
- Command server: 127.0.0.1:9998 (Java ServerIPCClient -> Python)
- Agent frames: 127.0.0.1:9999 + agent_index (Java IPCManager -> Python)

Quick tests:

Send a command (4-byte BE length + JSON):
```python
from python.backend.test_command_client import send_command
send_command({'type':'RESET','data':'all'})
```

Send a test frame (4-byte BE header-length + header JSON + body):
```python
from python.backend.test_agent_frame_client import send_frame
header = {'events':['EVENT:HIT:Alice:Bob:enemy'], 'bodyLength':0}
send_frame(header, b'', port=9999)
```

Notes:
- The main socket implementation is in `python/backend/ipc_connector.py`.
- The command listener wrapper is `python/backend/command_connector.py`.
- `AgentController` in `python/backend/training_loop.py` uses the connector and exposes `connect()`/`disconnect()`.
