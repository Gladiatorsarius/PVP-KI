import logging
import socket
import struct
import threading
import json
import os
from .ipc_connector import recv_exact

log = logging.getLogger(__name__)

# configurable limits (env overrides)
MAX_HDR = int(os.environ.get('PVP_MAX_HDR', 64 * 1024))
MAX_BODY = int(os.environ.get('PVP_MAX_BODY', 10 * 1024 * 1024))
SOCK_TIMEOUT = float(os.environ.get('PVP_SOCK_TIMEOUT', 10.0))
# Simple token-based auth for commands (set PVP_CMD_SECRET to enable)
CMD_SECRET = os.environ.get('PVP_CMD_SECRET')


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
                conn.settimeout(SOCK_TIMEOUT)
                t = threading.Thread(target=self._handle_client_conn, args=(conn, addr), daemon=True)
                t.start()
            except Exception:
                log.exception('Accept loop error')

    def _handle_client_conn(self, conn: socket.socket, addr):
        try:
            hdr_len_b = recv_exact(conn, 4)
            hdr_len = struct.unpack('>I', hdr_len_b)[0]
            if hdr_len <= 0 or hdr_len > MAX_HDR:
                log.warning('Rejecting command: header length out of bounds %s from %s', hdr_len, addr)
                return
            hdr_bytes = recv_exact(conn, hdr_len)
            try:
                header = json.loads(hdr_bytes.decode('utf-8'))
            except json.JSONDecodeError:
                log.warning('Failed to parse command JSON from %s', addr)
                return

            # validate header shape
            if not isinstance(header, dict):
                log.warning('Command header not a dict from %s', addr)
                return

            # optional token auth
            if CMD_SECRET:
                token = header.get('token')
                if token != CMD_SECRET:
                    log.warning('Rejected command without valid token from %s', addr)
                    return

            # optional body handling validated by length field
            body_len = int(header.get('bodyLength', 0)) if header.get('bodyLength') is not None else 0
            if body_len < 0 or body_len > MAX_BODY:
                log.warning('Rejecting command: bodyLength out of bounds %s from %s', body_len, addr)
                return
            if body_len:
                _ = recv_exact(conn, body_len)

            if self.dispatcher:
                try:
                    self.dispatcher(header)
                except Exception:
                    log.exception('Dispatcher failed')
        except ConnectionError:
            log.debug('Client disconnected during command handling %s', addr)
        except socket.timeout:
            log.debug('Client socket timeout %s', addr)
        except Exception:
            log.exception('Client handler error')
        finally:
            try:
                conn.close()
            except Exception:
                pass
