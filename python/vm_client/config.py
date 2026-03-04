from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class RuntimeConfig:
    server_url: str
    agent_id: int
    fps: int
    jpeg_quality: int
    width: int
    height: int
    window_title_contains: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VM runtime stream client (Protocol v1)")
    parser.add_argument("--server-url", default="ws://127.0.0.1:8765/ws", help="Coordinator websocket URL")
    parser.add_argument("--agent-id", type=int, default=1, help="Agent id (>=1)")
    parser.add_argument("--fps", type=int, default=30, help="Target capture fps")
    parser.add_argument("--jpeg-quality", type=int, default=70, help="JPEG quality [1-100]")
    parser.add_argument("--width", type=int, default=320, help="Resize width")
    parser.add_argument("--height", type=int, default=180, help="Resize height")
    parser.add_argument(
        "--window-title-contains",
        default="VirtualBox",
        help="Preferred active window title substring for focused capture",
    )
    return parser


def parse_config(argv: list[str] | None = None) -> RuntimeConfig:
    parser = build_parser()
    args = parser.parse_args(argv)
    return RuntimeConfig(
        server_url=args.server_url,
        agent_id=max(1, int(args.agent_id)),
        fps=max(1, int(args.fps)),
        jpeg_quality=max(1, min(100, int(args.jpeg_quality))),
        width=max(32, int(args.width)),
        height=max(32, int(args.height)),
        window_title_contains=args.window_title_contains,
    )
