import logging
import socket
import struct
import threading
import json
from .ipc_connector import recv_exact

log = logging.getLogger(__name__)


class CommandConnector:
    """Server wrapper that accepts 4-byte-length-prefixed JSON commands and
    dispatches them to `dispatcher_callback`.
    """

    def __init__(self, dispatcher_callback, host: str = '127.0.0.1', port: int = 9998):
        self.dispatcher = dispatcher_callback
        self.host = host
        self.port = port
        self._server_sock = None
        self._accept_thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(4)
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        log.info(f"CommandConnector started on {self.host}:{self.port}")

    def stop(self):
        self._running = False
        try:
            if self._server_sock:
                try:
                    self._server_sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._server_sock.close()
        except Exception:
            log.exception('Error stopping CommandConnector')

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server_sock.accept()
                t = threading.Thread(target=self._handle_client_conn, args=(conn, addr), daemon=True)
                t.start()
            except Exception:
                log.exception('Accept loop error')

    def _handle_client_conn(self, conn: socket.socket, addr):
        try:
            hdr_len_b = recv_exact(conn, 4)
            hdr_len = struct.unpack('>I', hdr_len_b)[0]
            hdr_bytes = recv_exact(conn, hdr_len)
            try:
                header = json.loads(hdr_bytes.decode('utf-8'))
            except Exception:
                log.exception('Failed to parse command JSON')
                header = {}
            if self.dispatcher:
                try:
                    self.dispatcher(header)
                except Exception:
                    log.exception('Dispatcher failed')
        except Exception:
            log.exception('Client handler error')
        finally:
            try:
                conn.close()
            except Exception:
                pass
