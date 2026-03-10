import hashlib
import hmac
import json
import logging
import os
import socket
import struct
import threading

log = logging.getLogger(__name__)

MAX_HDR = int(os.environ.get('PVP_MAX_HDR', 64 * 1024))
MAX_BODY = int(os.environ.get('PVP_MAX_BODY', 10 * 1024 * 1024))
SOCK_TIMEOUT = float(os.environ.get('PVP_SOCK_TIMEOUT', 10.0))
CMD_SECRET = os.environ.get('PVP_CMD_SECRET')


def _verify_command_token(token: str | None, secret: str) -> bool:
    """Verify HMAC-SHA256 token using constant-time comparison to prevent timing attacks."""
    if not token or not secret:
        return False
    expected = hmac.new(secret.encode(), b'command', hashlib.sha256).hexdigest()
    # Use hmac.compare_digest for constant-time comparison
    return hmac.compare_digest(token, expected)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError('Socket closed while receiving data')
        buf.extend(chunk)
    return bytes(buf)


class CommandConnector:
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
        log.info('CommandConnector started on %s:%s', self.host, self.port)

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
                thread = threading.Thread(target=self._handle_client_conn, args=(conn, addr), daemon=True)
                thread.start()
            except Exception:
                if self._running:
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

            if not isinstance(header, dict):
                log.warning('Command header not a dict from %s', addr)
                return

            if CMD_SECRET:
                token = header.get('token')
                if not _verify_command_token(token, CMD_SECRET):
                    log.warning('Rejected command with invalid HMAC token from %s', addr)
                    return

            body_len = int(header.get('bodyLength', 0)) if header.get('bodyLength') is not None else 0
            if body_len < 0 or body_len > MAX_BODY:
                log.warning('Rejecting command: bodyLength out of bounds %s from %s', body_len, addr)
                return

            # Ensure message body is fully consumed from socket even on errors
            body_bytes = b''
            if body_len:
                try:
                    body_bytes = recv_exact(conn, body_len)
                except ConnectionError as e:
                    log.warning('Failed to read command body from %s: %s', addr, e)
                    return

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
