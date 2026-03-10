from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from typing import Any

from websockets.exceptions import ConnectionClosed

from .capture import ScreenCapturer
from .config import RuntimeConfig
from .input_driver import InputAction, InputDriver
from .preprocess import grayscale_to_jpeg_b64, to_grayscale
from .ws_client import WSClient

PROTOCOL_VERSION = "v1"


def _now_ms() -> int:
    return int(time.time() * 1000)


class RuntimeState:
    def __init__(self, agent_id: int):
        self.session_id = f"s-{uuid.uuid4().hex[:8]}"
        self.episode_id = "ep-0"
        self.agent_id = agent_id
        self.running = False
        self.ready_sent = False
        self.frame_id = 0
        self.latest_action_id = -1
        self.latest_action: InputAction | None = None


async def _send_hello_and_ready(ws: WSClient, state: RuntimeState) -> None:
    await ws.send(
        {
            "type": "hello",
            "protocol_version": PROTOCOL_VERSION,
            "agent_id": state.agent_id,
            "client_role": "vm-runtime",
            "capabilities": {"grayscale": True, "input_driver": "pydirectinput"},
        }
    )
    await ws.send(
        {
            "type": "ready",
            "protocol_version": PROTOCOL_VERSION,
            "agent_id": state.agent_id,
            "timestamp_ms": _now_ms(),
        }
    )
    state.ready_sent = True


def _as_action(msg: dict[str, Any]) -> InputAction:
    return InputAction(
        movement=(msg.get("movement") or {}),
        look=(msg.get("look") or {}),
        mouse=(msg.get("mouse") or {}),
    )


async def _receiver_loop(ws: WSClient, state: RuntimeState, input_driver: InputDriver) -> None:
    while True:
        msg = await ws.recv_json()
        msg_type = str(msg.get("type", "")).lower()

        if msg_type == "start":
            if isinstance(msg.get("session_id"), str):
                state.session_id = msg["session_id"]
            if isinstance(msg.get("episode_id"), str):
                state.episode_id = msg["episode_id"]
            state.running = True
            continue

        if msg_type in {"stop", "disconnect"}:
            state.running = False
            input_driver.release_all()
            continue

        if msg_type == "reset":
            if isinstance(msg.get("next_episode_id"), str):
                state.episode_id = msg["next_episode_id"]
            state.frame_id = 0
            continue

        if msg_type == "heartbeat":
            await ws.send(
                {
                    "type": "heartbeat",
                    "protocol_version": PROTOCOL_VERSION,
                    "session_id": state.session_id,
                    "agent_id": state.agent_id,
                    "episode_id": state.episode_id,
                    "timestamp_ms": _now_ms(),
                }
            )
            continue

        if msg_type == "action":
            action_id = int(msg.get("action_id", -1))
            if action_id >= state.latest_action_id:
                if isinstance(msg.get("session_id"), str):
                    state.session_id = msg["session_id"]
                if isinstance(msg.get("episode_id"), str):
                    state.episode_id = msg["episode_id"]
                state.latest_action_id = action_id
                state.latest_action = _as_action(msg)


async def _frame_loop(config: RuntimeConfig, ws: WSClient, state: RuntimeState, input_driver: InputDriver) -> None:
    capturer = ScreenCapturer(preferred_title_contains=config.window_title_contains)
    interval = 1.0 / float(config.fps)
    dropped_frame_count = 0

    try:
        while True:
            tick_start = time.perf_counter()

            if state.running:
                capture_ts = _now_ms()
                bgr = capturer.grab_bgr()
                gray = to_grayscale(bgr, config.width, config.height)
                payload_b64 = grayscale_to_jpeg_b64(gray, config.jpeg_quality)

                state.frame_id += 1
                msg = {
                    "type": "frame",
                    "protocol_version": PROTOCOL_VERSION,
                    "session_id": state.session_id,
                    "agent_id": state.agent_id,
                    "episode_id": state.episode_id,
                    "frame_id": state.frame_id,
                    "timestamp_ms": _now_ms(),
                    "capture_ts_ms": capture_ts,
                    "width": int(gray.shape[1]),
                    "height": int(gray.shape[0]),
                    "channels": 1,
                    "dtype": "uint8",
                    "encoding": "jpeg",
                    "payload_b64": payload_b64,
                    "dropped_frame_count": dropped_frame_count,
                }
                # Send frame with retry logic and error handling
                try:
                    await ws.send(msg)
                except Exception as e:
                    import logging
                    logging.warning(f"Frame send failed (frame {state.frame_id}): {e}, reconnecting...")
                    # Attempt reconnection on send failure
                    try:
                        await ws.close()
                        await ws.connect()
                    except Exception as reconnect_err:
                        logging.error(f"Reconnection failed: {reconnect_err}")
                        raise
                dropped_frame_count = 0

                if state.latest_action is not None:
                    input_driver.apply(state.latest_action)

            elapsed = time.perf_counter() - tick_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                dropped_frame_count += 1
                await asyncio.sleep(0)
    finally:
        capturer.close()


async def run(config: RuntimeConfig) -> None:
    state = RuntimeState(agent_id=config.agent_id)
    ws = WSClient(config.server_url)
    input_driver = InputDriver()

    try:
        await ws.connect()
        await _send_hello_and_ready(ws, state)

        recv_task = asyncio.create_task(_receiver_loop(ws, state, input_driver))
        frame_task = asyncio.create_task(_frame_loop(config, ws, state, input_driver))

        done, pending = await asyncio.wait(
            {recv_task, frame_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )

        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc

        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    except (ConnectionClosed, OSError):
        pass
    finally:
        input_driver.release_all()
        await ws.close()
