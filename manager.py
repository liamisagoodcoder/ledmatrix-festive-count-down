"""
Festive Countdown plugin for LEDMatrix.

Counts down the days to Christmas over an animated winter scene: falling
snow, a snowman, a twinkling tree, and Santa's sleigh flying past. On
Christmas Day it shows MERRY XMAS!; from the 26th it counts to next year.

The drawing itself lives in festive_scene.py. This file connects it to
LEDMatrix: it reads the settings, works out how many days are left, and
hands a fresh frame to the display many times a second.
"""

import time
from datetime import date, datetime
from typing import Any, Dict, Optional

from src.plugin_system.base_plugin import BasePlugin

from festive_scene import DEFAULT_OPTIONS, draw_scene


def _colour(value, default):
    """Turn a [r, g, b] setting into a colour, or use the default if it's bad."""
    try:
        r, g, b = (max(0, min(255, int(c))) for c in value)
        return (r, g, b)
    except (TypeError, ValueError):
        return default


class FestiveCountdownPlugin(BasePlugin):
    """Animated Christmas countdown."""

    def __init__(self, plugin_id: str, config: Dict[str, Any],
                 display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        # Ask the display loop to call display() many times a second instead
        # of once a second, so the snow falls smoothly.
        self.needs_high_fps = True
        self._clock_start = time.monotonic()
        self._last_frame = 0.0
        self._apply_config()

    def _apply_config(self) -> None:
        cfg = self.config
        self.scene_options = {
            "number_color": _colour(cfg.get("number_color"), DEFAULT_OPTIONS["number_color"]),
            "label_color": _colour(cfg.get("label_color"), DEFAULT_OPTIONS["label_color"]),
            "show_sleigh": bool(cfg.get("show_sleigh", True)),
            "sleigh_every_seconds": max(10.0, float(cfg.get("sleigh_every_seconds", 30))),
            "snowflakes": max(0, min(100, int(cfg.get("snowflakes", 34)))),
            "show_snowman": bool(cfg.get("show_snowman", True)),
            "show_tree": bool(cfg.get("show_tree", True)),
        }
        fps = max(5, min(60, int(cfg.get("animation_fps", 30))))
        self._frame_interval = 1.0 / fps

    def on_config_change(self, new_config: Dict[str, Any]) -> None:
        """Settings saved in the web UI take effect straight away."""
        super().on_config_change(new_config)
        self._apply_config()

    def _get_global_timezone(self) -> Optional[str]:
        """The LEDMatrix timezone setting, or None when it cannot be read."""
        try:
            for source in (self.plugin_manager, self.cache_manager):
                config_manager = getattr(source, "config_manager", None)
                if config_manager:
                    return config_manager.get_timezone()
        except Exception as e:
            self.logger.warning(f"Error getting global timezone: {e}")
        return None

    def _today(self) -> date:
        """Today's date in the LEDMatrix timezone, falling back to system time."""
        tz_name = self._get_global_timezone()
        if tz_name:
            try:
                from zoneinfo import ZoneInfo
                return datetime.now(ZoneInfo(tz_name)).date()
            except Exception:
                pass
        return date.today()

    def days_until_christmas(self) -> int:
        """0 on Christmas Day; after the 25th, counts to next year's."""
        today = self._today()
        christmas = date(today.year, 12, 25)
        if today > christmas:
            christmas = date(today.year + 1, 12, 25)
        return (christmas - today).days

    def update(self) -> None:
        # Nothing to download: the countdown is worked out from the date
        # every frame in display().
        pass

    def display(self, force_clear: bool = False) -> None:
        now = time.monotonic()
        # The display loop calls us up to ~100 times a second. Drawing about
        # 30 frames a second looks just as smooth and leaves the Pi time to
        # do everything else.
        if not force_clear and now - self._last_frame < self._frame_interval:
            return
        self._last_frame = now

        width = self.display_manager.width
        height = self.display_manager.height
        frame = draw_scene(now - self._clock_start, self.days_until_christmas(),
                           width, height, self.scene_options)
        self.display_manager.image.paste(frame, (0, 0))
        self.display_manager.update_display()
