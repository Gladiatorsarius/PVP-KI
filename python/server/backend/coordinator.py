import asyncio
import json
import logging
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from .session_registry import SessionRegistry
from .ws_protocol_v1 import PROTOCOL_VERSION, default_action_payload, validate_incoming_message

log = logging.getLogger(__name__)


class WebSocketCoordinator:
    def __init__(self, 
                 host: str = '0.0.0.0', 
                 port: int = 8765, 
                 path: str = '/ws', 
                 status_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
                 inference_engine = None,
                 inference_executor: Optional[ThreadPoolExecutor] = None,
                 model_lock: Optional[threading.RLock] = None):
        self.host = host
        self.port = port
        self.path = path
        self.status_hook = status_hook
        self.registry = SessionRegistry()

        # Inference dependencies
        self.inference_engine = inference_engine
        self.inference_executor = inference_executor
        self.model_lock = model_lock

        # Fallback mechanism for inference failures
        self._inference_failure_count = 0
        self._fallback_mode = False
        self._fallback_timer = None

        self._thread = None
        self._loop = None
        self._server = None
        self._running = False
        self._clients: Dict[int, Any] = {}
        self._clients_lock = threading.Lock()

    def start(self) -> bool:
        if self._running:
            return True
        self._thread = threading.Thread(target=self._run_loop_thread, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if not self._running:
            return
        loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(lambda: asyncio.create_task(self._shutdown()))
        if self._thread:
            self._thread.join(timeout=3.0)
        self._thread = None

    def start_all(self):
        ready_agents = self.registry.ready_agent_ids()
        if not ready_agents:
            self._emit_status('start_all_skipped', reason='no_ready_agents')
            return

        loop = self._loop
        if not loop or not loop.is_running():
            self._emit_status('start_all_skipped', reason='coordinator_not_running')
            return

        for agent_id in ready_agents:
            self.registry.mark_started(agent_id)
            loop.call_soon_threadsafe(lambda aid=agent_id: asyncio.create_task(self._send_start(aid)))
        self._emit_status('start_all', agent_ids=ready_agents)

    def status_snapshot(self) -> Dict[int, Dict[str, Any]]:
        return self.registry.snapshot()

    def _run_loop_thread(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._start_server())
            self._running = True
            self._emit_status('coordinator_started', host=self.host, port=self.port, path=self.path)
            self._loop.run_forever()
        except Exception as exc:
            self._emit_status('coordinator_error', error=str(exc))
            log.exception('Coordinator failed to start')
        finally:
            self._running = False
            if self._loop and not self._loop.is_closed():
                self._loop.close()
            self._emit_status('coordinator_stopped')

    async def _start_server(self):
        try:
            import importlib
            websockets = importlib.import_module('websockets')
        except Exception as exc:
            raise RuntimeError("'websockets' package is required for coordinator service") from exc

        self._server = await websockets.serve(self._handle_connection, self.host, self.port)

    async def _shutdown(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._loop and self._loop.is_running():
            self._loop.stop()

    async def _handle_connection(self, websocket):
        agent_id = None
        try:
            async for raw in websocket:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_error(websocket, 'invalid_json')
                    continue

                is_valid, error = validate_incoming_message(message)
                if not is_valid:
                    await self._send_error(websocket, error)
                    continue

                message_type = message.get('type')
                # Validate and extract agent_id before processing any message
                try:
                    agent_id = int(message['agent_id'])
                    if agent_id <= 0:
                        await self._send_error(websocket, 'invalid_agent_id')
                        continue
                except (ValueError, KeyError) as e:
                    await self._send_error(websocket, 'invalid_agent_id')
                    continue

                if message_type == 'hello':
                    await self._handle_hello(websocket, message)
                elif message_type == 'ready':
                    await self._handle_ready(websocket, message)
                elif message_type == 'frame':
                    await self._handle_frame(websocket, message)
                elif message_type == 'heartbeat':
                    self._emit_status('heartbeat', agent_id=agent_id)
                elif message_type == 'stop':
                    self.registry.disconnect(agent_id)
                    await self._send_stop(websocket, agent_id=agent_id)
                elif message_type == 'disconnect':
                    self.registry.disconnect(agent_id)
                    break
        except Exception as exc:
            if agent_id is not None:
                self.registry.disconnect(agent_id)
            self._emit_status('connection_error', agent_id=agent_id, error=str(exc))
        finally:
            if agent_id is not None:
                self.registry.disconnect(agent_id)
                with self._clients_lock:
                    self._clients.pop(agent_id, None)
                self._emit_status('agent_disconnected', agent_id=agent_id)

    async def _handle_hello(self, websocket, message: Dict[str, Any]):
        agent_id = int(message['agent_id'])
        session_id = message.get('session_id') or f"s-{uuid.uuid4().hex[:8]}"
        episode_id = message.get('episode_id') or 'ep-0'
        client_role = message.get('client_role', 'vm-runtime')

        self.registry.register_hello(
            agent_id=agent_id,
            session_id=session_id,
            episode_id=episode_id,
            client_role=client_role,
            capabilities=message.get('capabilities') if isinstance(message.get('capabilities'), dict) else {},
        )

        with self._clients_lock:
            self._clients[agent_id] = websocket

        ack = {
            'type': 'hello',
            'protocol_version': PROTOCOL_VERSION,
            'agent_id': agent_id,
            'session_id': session_id,
            'episode_id': episode_id,
            'accepted': True,
            'timestamp_ms': int(time.time() * 1000),
        }
        await websocket.send(json.dumps(ack))
        self._emit_status('agent_registered', agent_id=agent_id, session_id=session_id, episode_id=episode_id)

    async def _handle_ready(self, websocket, message: Dict[str, Any]):
        agent_id = int(message['agent_id'])
        state = self.registry.mark_ready(agent_id)
        if not state:
            await self._send_error(websocket, 'ready before hello', agent_id=agent_id)
            return

        # Validate state attributes before use
        if not hasattr(state, 'session_id') or not hasattr(state, 'episode_id'):
            await self._send_error(websocket, 'invalid_state', agent_id=agent_id)
            return

        ack = {
            'type': 'ready',
            'protocol_version': PROTOCOL_VERSION,
            'agent_id': agent_id,
            'session_id': state.session_id,
            'episode_id': state.episode_id,
            'accepted': True,
            'timestamp_ms': int(time.time() * 1000),
        }
        try:
            await websocket.send(json.dumps(ack))
        except Exception as e:
            log.warning(f"Failed to send ready ack to agent {agent_id}: {e}")
            return
        self._emit_status('agent_ready', agent_id=agent_id)

    def _run_inference_locked(self, payload_b64: str, agent_id: int):
        """
        Run inference in a thread-safe manner.
        This function is executed in the inference executor thread.
        """
        with self.model_lock:
            return self.inference_engine.predict(payload_b64)

    def _reset_fallback(self):
        """Reset the fallback mode after 60 seconds."""
        log.info("Resetting inference fallback mode.")
        self._fallback_mode = False
        self._inference_failure_count = 0

    async def _handle_frame(self, websocket, message: Dict[str, Any]):
        agent_id = int(message['agent_id'])
        frame_id = int(message['frame_id'])
        timestamp_ms = int(message['timestamp_ms'])
        session_id = str(message['session_id'])
        episode_id = str(message['episode_id'])
        payload_b64 = message.get('payload_b64', '')

        state = self.registry.mark_frame(
            agent_id=agent_id,
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            session_id=session_id,
            episode_id=episode_id,
        )
        if not state:
            await self._send_error(websocket, 'frame before hello', agent_id=agent_id)
            return

        # Validate state object has required attributes before accessing
        if state.state is None:
            await self._send_error(websocket, 'invalid_state', agent_id=agent_id)
            return

        if state.state == 'started':
            self.registry.mark_running(agent_id)

        action_id = self.registry.next_action_id(agent_id)

        # --- INFERENCE INTEGRATION ---
        # If fallback mode is active, skip inference and use default actions
        if self._fallback_mode:
            action = default_action_payload(
                session_id=state.session_id,
                agent_id=agent_id,
                episode_id=state.episode_id,
                action_id=action_id,
                timestamp_ms=int(time.time() * 1000),
            )
        elif self.inference_engine and self.inference_executor:
            # Validate payload size to prevent DoS
            MAX_PAYLOAD_LENGTH = 1_000_000  # 1MB base64 encoded
            if len(payload_b64) > MAX_PAYLOAD_LENGTH:
                await self._send_error(websocket, 'payload_too_large', agent_id=agent_id)
                return

            try:
                # Offload GPU inference to a dedicated thread to avoid blocking asyncio
                loop = asyncio.get_event_loop()
                action = await loop.run_in_executor(
                    self.inference_executor,
                    self._run_inference_locked,
                    payload_b64,
                    agent_id
                )
                # Add protocol fields to the action
                action['session_id'] = state.session_id
                action['agent_id'] = agent_id
                action['episode_id'] = state.episode_id
                action['action_id'] = action_id
                action['timestamp_ms'] = int(time.time() * 1000)
                
                # Reset failure counter on successful inference
                self._inference_failure_count = 0

            except Exception as e:
                log.error(f"Inference failed for agent {agent_id}: {e}", exc_info=True)
                self._inference_failure_count += 1
                
                # Activate fallback mode after 3 consecutive failures
                if self._inference_failure_count >= 3:
                    log.error("Entering fallback mode after 3 consecutive inference failures.")
                    self._fallback_mode = True
                    if self._fallback_timer:
                        self._fallback_timer.cancel()
                    self._fallback_timer = threading.Timer(60, self._reset_fallback)
                    self._fallback_timer.start()

                # Return default action on inference failure
                action = default_action_payload(
                    session_id=state.session_id,
                    agent_id=agent_id,
                    episode_id=state.episode_id,
                    action_id=action_id,
                    timestamp_ms=int(time.time() * 1000),
                )
        else:
            # No inference engine available, use default actions
            action = default_action_payload(
                session_id=state.session_id,
                agent_id=agent_id,
                episode_id=state.episode_id,
                action_id=action_id,
                timestamp_ms=int(time.time() * 1000),
            )

        await websocket.send(json.dumps(action))
        self._emit_status('frame_processed', agent_id=agent_id, frame_id=frame_id, action_id=action_id)

    async def _send_start(self, agent_id: int):
        with self._clients_lock:
            websocket = self._clients.get(agent_id)

        state = self.registry.get(agent_id)
        if not websocket or not state:
            return

        payload = {
            'type': 'start',
            'protocol_version': PROTOCOL_VERSION,
            'session_id': state.session_id,
            'agent_id': agent_id,
            'episode_id': state.episode_id,
            'timestamp_ms': int(time.time() * 1000),
        }
        try:
            await websocket.send(json.dumps(payload))
            self._emit_status('start_sent', agent_id=agent_id)
        except Exception as exc:
            self._emit_status('start_send_error', agent_id=agent_id, error=str(exc))

    async def _send_stop(self, websocket, agent_id: int):
        state = self.registry.get(agent_id)
        payload = {
            'type': 'stop',
            'protocol_version': PROTOCOL_VERSION,
            'session_id': state.session_id if state else '',
            'agent_id': agent_id,
            'episode_id': state.episode_id if state else '',
            'timestamp_ms': int(time.time() * 1000),
        }
        await websocket.send(json.dumps(payload))

    async def _send_error(self, websocket, reason: str, agent_id: Optional[int] = None):
        payload = {
            'type': 'error',
            'protocol_version': PROTOCOL_VERSION,
            'reason': reason,
            'agent_id': agent_id,
            'timestamp_ms': int(time.time() * 1000),
        }
        try:
            await websocket.send(json.dumps(payload))
        except Exception:
            pass
        self._emit_status('protocol_error', agent_id=agent_id, reason=reason)

    def _emit_status(self, event_type: str, **fields):
        data = {
            'type': event_type,
            'timestamp_ms': int(time.time() * 1000),
            **fields,
        }
        log.debug('coordinator_status=%s', data)
        if self.status_hook:
            try:
                self.status_hook(data)
            except Exception:
                pass
