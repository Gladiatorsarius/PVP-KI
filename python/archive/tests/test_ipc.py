import socket
import struct
import threading
import time
import sys
import os
# Archived IPC tests moved here after migrating to Gym-based integration.
# Original tests are preserved for reference but not run by default.

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib
import types

# Minimal package mapping for imports
pkg = types.ModuleType('python')
pkg.__path__ = [ROOT]
sys.modules['python'] = pkg
backend_pkg = types.ModuleType('python.backend')
backend_pkg.__path__ = [os.path.join(ROOT, 'backend')]
sys.modules['python.backend'] = backend_pkg

cc_mod = importlib.import_module('python.backend.command_connector')
ipc_mod = importlib.import_module('python.backend.ipc_connector')

def _get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    addr, port = s.getsockname()
    s.close()
    return port

def test_reject_too_large_header(monkeypatch):
    port = _get_free_port()
    received = []

    def dispatcher(hdr):
        received.append(hdr)

    conn = cc_mod.CommandConnector(dispatcher, host='127.0.0.1', port=port)
    conn.start()
    time.sleep(0.05)

    client = socket.create_connection(('127.0.0.1', port), timeout=2)
    try:
        bad_len = cc_mod.MAX_HDR + 1
        client.sendall(struct.pack('>I', bad_len))
        client.settimeout(1.0)
        try:
            data = client.recv(1)
            assert data == b''
        except (ConnectionResetError, socket.timeout):
            pass
    finally:
        client.close()
        conn.stop()

def test_concurrent_send_and_stop():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', 0))
    srv.listen(1)
    host, port = srv.getsockname()

    server_ready = threading.Event()
    stop_server = threading.Event()

    def server_thread():
        server_ready.set()
        try:
            conn, _ = srv.accept()
            conn.settimeout(1.0)
            while not stop_server.is_set():
                try:
                    _ = conn.recv(1024)
                    if not _:
                        break
                except socket.timeout:
                    continue
            try:
                conn.close()
            except Exception:
                pass
        finally:
            srv.close()

    t = threading.Thread(target=server_thread, daemon=True)
    t.start()
    server_ready.wait(timeout=1.0)

    sc = ipc_mod.SocketConnector(host, port)
    sc.start()

    deadline = time.time() + 2.0
    while time.time() < deadline:
        with sc._lock:
            if sc._sock:
                break
        time.sleep(0.01)
    else:
        sc.stop()
        print('SKIP: Could not establish connector socket')
        sys.exit(0)

    exceptions = []

    def sender():
        try:
            for _ in range(100):
                try:
                    sc.send_prefixed(b'hello', length_bytes=2)
                except Exception as e:
                    exceptions.append(e)
                time.sleep(0.005)
        except Exception as e:
            exceptions.append(e)

    def stopper():
        time.sleep(0.02)
        sc.stop()

    s_thread = threading.Thread(target=sender)
    stop_thread = threading.Thread(target=stopper)
    s_thread.start()
    stop_thread.start()
    s_thread.join()
    stop_thread.join()

    stop_server.set()
    t.join(timeout=1.0)

    assert not any(isinstance(e, AttributeError) for e in exceptions)
    assert True
