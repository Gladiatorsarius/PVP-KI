from __future__ import annotations

import asyncio
import sys

from vm_client.config import parse_config
from vm_client.runtime import run


def main(argv: list[str] | None = None) -> int:
    config = parse_config(argv)
    try:
        asyncio.run(run(config))
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
