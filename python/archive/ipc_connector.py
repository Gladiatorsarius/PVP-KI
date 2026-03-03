import socket
import struct
import threading
import json
import logging
from typing import Callable, Optional
import os
from queue import Queue

MAX_HDR = int(os.environ.get('PVP_MAX_HDR', 64 * 1024))
MAX_BODY = int(os.environ.get('PVP_MAX_BODY', 10 * 1024 * 1024))
SOCK_TIMEOUT = float(os.environ.get('PVP_SOCK_TIMEOUT', 10.0))

log = logging.getLogger(__name__)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except socket.timeout:
            raise ConnectionError("socket timeout during recv_exact")
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
        self._lock = threading.RLock()
        # queue for decoupling IO from processing
        self._work_q = Queue(maxsize=int(os.environ.get('PVP_WORKQ_MAX', 32)))
        self._workers = []

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
        # start worker(s) to process frames off the IO queue
        w = threading.Thread(target=self._worker_loop, daemon=True)
        w.start()
        self._workers.append(w)
        thread = threading.Thread(target=self._client_loop, daemon=True)
        thread.start()

    def stop(self):
        with self._lock:
            self._running = False
            try:
                if self._sock:
                    try:
                        self._sock.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    self._sock = None
            finally:
                log.debug("SocketConnector stopped")

    def _client_loop(self):
        try:
            sock = socket.create_connection((self.host, self.port))
            sock.settimeout(SOCK_TIMEOUT)
            with self._lock:
                self._sock = sock
            log.info(f"Connected to {self.host}:{self.port}")
            while self._running:
                # Read 4-byte header length
                hdr_len_b = recv_exact(sock, 4)
                hdr_len = struct.unpack('>I', hdr_len_b)[0]
                if hdr_len <= 0 or hdr_len > MAX_HDR:
                    log.warning('Rejecting frame: header length out of bounds %s', hdr_len)
                    return
                hdr_bytes = recv_exact(sock, hdr_len)
                try:
                    header = json.loads(hdr_bytes.decode('utf-8'))
                except json.JSONDecodeError:
                    log.warning('Failed to parse header JSON')
                    header = {}
                # validate header
                if not isinstance(header, dict):
                    log.warning('Header not a dict, skipping frame')
                    continue
                try:
                    body_len = int(header.get('bodyLength', 0)) if header.get('bodyLength') is not None else 0
                except Exception:
                    body_len = 0
                if body_len < 0 or body_len > MAX_BODY:
                    log.warning('Rejecting frame: bodyLength out of bounds %s', body_len)
                    return
                body = b''
                if body_len:
                    body = recv_exact(sock, body_len)
                # push to work queue for processing
                try:
                    self._work_q.put((header, body), block=False)
                except Exception:
                    # queue full — drop incoming frame to avoid blocking reader
                    log.debug('Work queue full; dropping incoming frame')
        except ConnectionError:
            log.debug('Connection closed')
        except socket.timeout:
            log.debug('Socket timeout in client loop')
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
        length_fmt = '>H' if length_bytes == 2 else '>I'
        header = struct.pack(length_fmt, len(payload))
        with self._lock:
            if not self._sock:
                raise ConnectionError('No socket to send on')
            try:
                self._sock.sendall(header + payload)
            except (BrokenPipeError, OSError) as e:
                raise ConnectionError('send failed') from e

    @staticmethod
    def decode_image(body_bytes: bytes):
        """Decode PNG/JPEG bytes to an image array if possible.
        Returns `numpy.ndarray` on success or `None` on decode failure.
        """
        try:
            import numpy as _np
            import cv2 as _cv2
            arr = _np.frombuffer(body_bytes, dtype=_np.uint8)
            img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
            return img
        except Exception:
            log.debug('cv2 decode failed')
            return None

    def _worker_loop(self):
        # simple worker: decode and dispatch
        while self._running:
            try:
                header, body = self._work_q.get(timeout=1.0)
            except Exception:
                continue
            try:
                img = None
                if body:
                    img = self.decode_image(body)
                if self.on_message:
                    try:
                        self.on_message(header, img if img is not None else body)
                    except Exception:
                        log.exception('on_message handler failed in worker')
            except Exception:
                log.exception('Worker processing failed')
