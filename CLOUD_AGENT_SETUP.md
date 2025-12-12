# Cloud Agent Setup Guide

## Overview

The PVP-KI training system now supports **cloud/remote agents**, allowing agents to run on different machines or cloud servers instead of only on localhost. This enables distributed training and cloud-based deployments.

## Features

### 1. Remote Agent Support
- Agents can connect to Minecraft clients running on different hosts
- Each agent can have a custom host IP address
- Supports both local (127.0.0.1) and cloud/remote IPs

### 2. Configurable Command Listener
- Command listener can bind to `0.0.0.0` for remote access
- Or bind to `127.0.0.1` for local-only security
- Configurable port (default: 10001)

### 3. Configuration File
- JSON-based configuration: `agent_config.json`
- Define agent hosts and ports
- Configure command listener binding

## Configuration

### agent_config.json

```json
{
  "command_listener": {
    "port": 10001,
    "bind_host": "0.0.0.0",
    "comment": "bind_host: '0.0.0.0' for cloud/remote, '127.0.0.1' for local only"
  },
  "agents": [
    {
      "name": "Agent 1",
      "host": "127.0.0.1",
      "port": 9999
    },
    {
      "name": "Agent 2", 
      "host": "192.168.1.100",
      "port": 9999
    }
  ]
}
```

### Configuration Options

#### command_listener
- **port**: Port for receiving START/STOP/RESET commands (default: 10001)
- **bind_host**: 
  - `127.0.0.1` - Local only (more secure, default)
  - `0.0.0.0` - Accept connections from any interface (for cloud deployments)

#### agents
Each agent entry:
- **name**: Display name for the agent
- **host**: IP address where the Minecraft client is running
  - `127.0.0.1` for local
  - Cloud IP for remote agents (e.g., `34.123.45.67`)
- **port**: Port where the Minecraft client's IPC is listening (usually 9999+)

## Usage

### Local Setup (Default)
1. No configuration file needed
2. Run: `python training_loop.py`
3. Two agents will start on localhost:9999 and localhost:10000

### Cloud Setup

#### Option 1: With Configuration File
1. Create `agent_config.json` with your cloud IPs
2. Run: `python training_loop.py`
3. System loads agents from configuration

#### Option 2: Programmatic
```python
manager = AgentManager(root)
manager.add_agent(host='34.123.45.67', port=9999)  # Cloud agent
manager.add_agent(host='127.0.0.1', port=10000)     # Local agent
```

## Security Considerations

### Network Exposure
- **Local Mode (`127.0.0.1`)**: Most secure, no external access
- **Cloud Mode (`0.0.0.0`)**: Exposes ports to network
  - Use firewall rules to restrict access
  - Consider VPN for production deployments
  - Use SSH tunneling for secure connections

### Firewall Configuration
When using cloud agents, ensure these ports are open:
- Agent ports (9999, 10000, 10002, etc.)
- Command listener port (10001)

Example firewall rule (allow only specific IP):
```bash
# Allow only training server to connect
ufw allow from 34.123.45.67 to any port 9999
ufw allow from 34.123.45.67 to any port 10001
```

### SSH Tunneling (Recommended for Production)
Instead of exposing ports, use SSH tunnels:

```bash
# Forward remote port to local
ssh -L 9999:localhost:9999 user@minecraft-server
ssh -L 10001:localhost:10001 user@minecraft-server
```

Then use `127.0.0.1` in configuration (connection goes through tunnel).

## Example Deployments

### Example 1: Two Local Agents (Default)
```json
{
  "command_listener": {
    "bind_host": "127.0.0.1",
    "port": 10001
  },
  "agents": [
    {"host": "127.0.0.1", "port": 9999},
    {"host": "127.0.0.1", "port": 10000}
  ]
}
```

### Example 2: Mixed Local and Cloud
```json
{
  "command_listener": {
    "bind_host": "0.0.0.0",
    "port": 10001
  },
  "agents": [
    {"host": "127.0.0.1", "port": 9999},
    {"host": "192.168.1.100", "port": 9999},
    {"host": "192.168.1.101", "port": 9999}
  ]
}
```

### Example 3: Full Cloud Deployment
```json
{
  "command_listener": {
    "bind_host": "0.0.0.0",
    "port": 10001
  },
  "agents": [
    {"host": "34.123.45.67", "port": 9999},
    {"host": "34.123.45.68", "port": 9999},
    {"host": "34.123.45.69", "port": 9999},
    {"host": "34.123.45.70", "port": 9999}
  ]
}
```

## Troubleshooting

### Connection Refused
- Check Minecraft client is running on the target host
- Verify IPCManager is active and listening on correct port
- Check firewall rules
- Verify network connectivity: `ping <host>`

### Command Listener Fails to Bind
- Port already in use: `lsof -i :10001`
- Permission denied: May need root for ports < 1024
- Invalid bind_host: Check IP address syntax

### Agent Not Connecting
- Check host IP in configuration
- Verify port number matches Minecraft client
- Test connection: `telnet <host> <port>`
- Check Java mod IPCManager logs

## Performance Considerations

### Latency
- Local agents: ~1-5ms latency
- LAN agents: ~5-20ms latency  
- Cloud agents: ~20-100ms+ depending on distance

### Bandwidth
- Each agent streams ~10-50 MB/s (frame data)
- Ensure adequate network bandwidth for cloud deployments
- Consider frame resolution reduction for high-latency connections

## Monitoring

The GUI shows agent status:
- Agent location displayed in frame title
- Connection status in logs
- Reward updates confirm data flow

Check logs for:
- `Connecting to <host>:<port>...` - Connection attempt
- `Connected!` - Successful connection
- `Error: ...` - Connection or communication issues

## Migration from Local to Cloud

1. **Start Local**: Test with default local setup
2. **Add Config**: Create `agent_config.json` with one cloud agent
3. **Test Connection**: Verify cloud agent connects
4. **Scale Up**: Add more cloud agents as needed
5. **Secure**: Implement firewall rules and/or SSH tunneling

## Support

For issues with cloud agent setup:
1. Check configuration syntax
2. Verify network connectivity
3. Review logs for error messages
4. Test with local agents first to isolate issues

---

**Note**: Cloud agent support enables distributed training but requires proper security configuration. Always use firewalls, VPNs, or SSH tunneling in production environments.
