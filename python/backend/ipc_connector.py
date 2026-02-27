import socket
import struct
import threading
import json
import logging
from typing import Callable, Optional

log = logging.getLogger(__name__)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed during recv_exact")
        buf.extend(chunk)
    return bytes(buf)


class SocketConnector:
    """A small client-only framed socket connector.

    It connects to (host, port), reads frames of the form:
      4-byte BE header-length, header JSON (utf-8), then body bytes of length
      header['bodyLength'] (optional).

    Callers provide `on_message(header, body)` and optional `on_disconnect()`.
    Use `send_prefixed(payload, length_bytes=2)` to send actions to the peer.
    """

    def __init__(self, host: str, port: int,
                 on_message: Optional[Callable[[dict, bytes], None]] = None,
                 on_disconnect: Optional[Callable[[], None]] = None):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.on_disconnect = on_disconnect

        self._sock = None
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
        t = threading.Thread(target=self._client_loop, daemon=True)
        t.start()

    def stop(self):
        self._running = False
        try:
            if self._sock:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._sock.close()
                self._sock = None
        finally:
            log.debug("SocketConnector stopped")

    def _client_loop(self):
        try:
            sock = socket.create_connection((self.host, self.port))
            sock.settimeout(None)
            self._sock = sock
            log.info(f"Connected to {self.host}:{self.port}")
            while self._running:
                # Read 4-byte header length
                hdr_len_b = recv_exact(sock, 4)
                hdr_len = struct.unpack('>I', hdr_len_b)[0]
                hdr_bytes = recv_exact(sock, hdr_len)
                try:
                    header = json.loads(hdr_bytes.decode('utf-8'))
                except Exception:
                    log.exception('Failed to parse header JSON')
                    header = {}
                body_len = int(header.get('bodyLength', 0))
                body = b''
                if body_len:
                    body = recv_exact(sock, body_len)
                if self.on_message:
                    try:
                        self.on_message(header, body)
                    except Exception:
                        log.exception('on_message handler failed')
        except Exception:
            log.exception('Client loop error')
        finally:
            if self.on_disconnect:
                try:
                    self.on_disconnect()
                except Exception:
                    log.exception('on_disconnect failed')

    # --- sending helpers ---
    def send_prefixed(self, payload: bytes, length_bytes: int = 2):
        """Send payload prefixed by length_bytes (2 or 4) big-endian."""
        if length_bytes not in (2, 4):
            raise ValueError('length_bytes must be 2 or 4')
        if not self._sock:
            raise ConnectionError('No socket to send on')
        length_fmt = '>H' if length_bytes == 2 else '>I'
        header = struct.pack(length_fmt, len(payload))
        with self._lock:
            self._sock.sendall(header + payload)

    @staticmethod
    def decode_image(body_bytes: bytes):
        """Decode PNG/JPEG bytes to an image array if possible.
        Returns raw bytes if no decoder available.
        """
        try:
            import numpy as _np
            import cv2 as _cv2
            arr = _np.frombuffer(body_bytes, dtype=_np.uint8)
            img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
            return img
        except Exception:
            log.debug('cv2 decode failed, returning raw bytes')
            return body_bytes
            return body_bytes
