import socket
import struct
import json

def send_command(cmd: dict, host='127.0.0.1', port=9998):
    b = json.dumps(cmd).encode('utf-8')
    hdr = struct.pack('>I', len(b))
    with socket.create_connection((host, port)) as s:
        s.sendall(hdr + b)


if __name__ == '__main__':
    send_command({'type':'RESET','data':'all'})
    print('Sent RESET')
