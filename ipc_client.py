import socket
import json
import asyncio
import numpy as np

class IPCClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False

    async def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print("Connected to Mod")
        except Exception as e:
            print(f"Connection failed: {e}")

    async def send_action(self, action):
        if self.connected:
            try:
                message = json.dumps({"type": "action", **action})
                self.socket.sendall(message.encode() + b'\n')
                print(f"Sent action: {action}")
            except Exception as e:
                print(f"Send failed: {e}")

    async def receive_state(self):
        if self.connected:
            try:
                data = self.socket.recv(1024).decode()
                if data:
                    state = json.loads(data.strip())
                    print(f"Received state: {state}")
                    # If frame_size > 0, receive binary frame
                    if state.get("frame_size", 0) > 0:
                        frame_size = state["frame_size"]
                        frame_data = b''
                        while len(frame_data) < frame_size:
                            frame_data += self.socket.recv(frame_size - len(frame_data))
                        frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((224, 224, 3))
                        print(f"Received frame: {frame.shape}")
                        return state, frame
                    return state, None
            except Exception as e:
                print(f"Receive failed: {e}")
        return None, None

    def close(self):
        if self.socket:
            self.socket.close()
            self.connected = False

# Example usage
async def main():
    client = IPCClient()
    await client.connect()
    while True:
        state, frame = await client.receive_state()
        if state:
            # Process state and frame
            action = {"move_forward": True, "attack": False, "look": [0.1, -0.2]}
            await client.send_action(action)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())