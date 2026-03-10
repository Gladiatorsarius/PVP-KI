from __future__ import annotations

from typing import Any

import mss
import numpy as np

try:
    import pygetwindow as gw
except Exception:
    gw = None


class ScreenCapturer:
    def __init__(self, preferred_title_contains: str = "VirtualBox"):
        self.preferred_title_contains = preferred_title_contains.lower().strip()
        self._sct = mss.mss()
        # Cache window region to avoid expensive gw.getActiveWindow() calls every frame
        self._cached_region = None
        self._cache_time = 0
        self._cache_duration_ms = 500  # Update cache every 500ms

    def _find_focus_region(self) -> dict[str, int] | None:
        """Find the active window region, with caching to reduce overhead."""
        import time
        current_time = int(time.time() * 1000)
        
        # Return cached region if still valid
        if self._cached_region is not None and (current_time - self._cache_time) < self._cache_duration_ms:
            return self._cached_region
        
        if gw is None:
            return None
        try:
            active = gw.getActiveWindow()
            if active is None or active.width <= 0 or active.height <= 0:
                return None
            title = (active.title or "").lower()
            if self.preferred_title_contains and self.preferred_title_contains not in title:
                return None
            self._cached_region = {
                "left": int(active.left),
                "top": int(active.top),
                "width": int(active.width),
                "height": int(active.height),
            }
            self._cache_time = current_time
            return self._cached_region
        except Exception:
            return None

    def grab_bgr(self) -> np.ndarray:
        region = self._find_focus_region()
        if region is None:
            mon = self._sct.monitors[1]
            region = {
                "left": int(mon["left"]),
                "top": int(mon["top"]),
                "width": int(mon["width"]),
                "height": int(mon["height"]),
            }
        shot = self._sct.grab(region)
        bgra = np.asarray(shot)
        return bgra[:, :, :3]

    def close(self) -> None:
        self._sct.close()
