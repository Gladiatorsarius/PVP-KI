from __future__ import annotations

from dataclasses import dataclass

import pydirectinput


@dataclass
class InputAction:
    movement: dict
    look: dict
    mouse: dict


class InputDriver:
    _movement_map = {
        "forward": "w",
        "back": "s",
        "left": "a",
        "right": "d",
        "jump": "space",
        "sprint": "shift",
        "sneak": "ctrl",
    }

    def __init__(self) -> None:
        pydirectinput.PAUSE = 0
        pydirectinput.FAILSAFE = False
        self._pressed: set[str] = set()

    def apply(self, action: InputAction) -> None:
        movement = action.movement or {}
        for key_name, scan_key in self._movement_map.items():
            should_press = bool(movement.get(key_name, False))
            if should_press and scan_key not in self._pressed:
                pydirectinput.keyDown(scan_key)
                self._pressed.add(scan_key)
            elif not should_press and scan_key in self._pressed:
                pydirectinput.keyUp(scan_key)
                self._pressed.remove(scan_key)

        look = action.look or {}
        # Add bounds checking to prevent extreme input values
        try:
            dx = float(look.get("dx", 0.0))
            dy = float(look.get("dy", 0.0))
            # Clamp look deltas to [-180, 180] degrees range
            dx = max(-180.0, min(180.0, dx))
            dy = max(-180.0, min(180.0, dy))
            dx = int(dx)
            dy = int(dy)
        except (ValueError, TypeError):
            # If conversion fails, use zero movement
            dx, dy = 0, 0
        if dx or dy:
            pydirectinput.moveRel(dx, dy)

        mouse = action.mouse or {}
        left_click = bool(mouse.get("left_click", False))
        right_click = bool(mouse.get("right_click", False))
        if left_click:
            pydirectinput.click(button="left")
        if right_click:
            pydirectinput.click(button="right")

        if bool(movement.get("attack", False)):
            pydirectinput.click(button="left")
        if bool(movement.get("use", False)):
            pydirectinput.click(button="right")

    def release_all(self) -> None:
        for scan_key in list(self._pressed):
            pydirectinput.keyUp(scan_key)
            self._pressed.remove(scan_key)
        pydirectinput.mouseUp(button="left")
        pydirectinput.mouseUp(button="right")
