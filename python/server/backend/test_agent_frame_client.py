import socket
import struct
import json

def send_frame(header: dict, body: bytes = b'', host='127.0.0.1', port=9999):
    hb = json.dumps(header).encode('utf-8')
    hdr = struct.pack('>I', len(hb))
    with socket.create_connection((host, port)) as s:
        s.sendall(hdr + hb)
        if body:
            s.sendall(body)


if __name__ == '__main__':
    header = {'events':['EVENT:HIT:Alice:Bob:enemy'], 'bodyLength':0}
    send_frame(header)
    print('Sent test frame')
