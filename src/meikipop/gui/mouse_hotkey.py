# meikipop/gui/mouse_hotkey.py
"""Lets a mouse button (middle or a side button) work as the popup hotkey, in addition to the keyboard hotkey."""
import logging
import threading

from pynput import mouse

from meikipop.config.config import config, IS_WINDOWS

logger = logging.getLogger(__name__)

# config value -> label shown in settings
MOUSE_HOTKEY_OPTIONS = {
    'none': 'None',
    'middle': 'Middle Button (Wheel Click)',
    'x1': 'Side Button (Back)',
    'x2': 'Side Button (Forward)',
}

# Windows low-level mouse hook messages
_WM_MBUTTONDOWN, _WM_MBUTTONUP = 0x0207, 0x0208
_WM_XBUTTONDOWN, _WM_XBUTTONUP = 0x020B, 0x020C


class MouseHotkey:
    def __init__(self):
        self._pressed = False
        self._lock = threading.Lock()
        self._listener = None
        self._button = 'none'
        self._block = False
        self.apply_settings()

    def is_pressed(self) -> bool:
        return self._pressed

    def apply_settings(self):
        button = (config.mouse_hotkey or 'none').lower()
        block = bool(config.mouse_hotkey_block) and IS_WINDOWS
        with self._lock:
            if button == self._button and block == self._block and (self._listener or button == 'none'):
                return
            self._stop()
            self._button, self._block = button, block
            self._pressed = False
            if button not in MOUSE_HOTKEY_OPTIONS or button == 'none':
                return
            try:
                if IS_WINDOWS:
                    self._listener = mouse.Listener(win32_event_filter=self._win32_filter)
                else:
                    self._listener = mouse.Listener(on_click=self._on_click)
                self._listener.daemon = True
                self._listener.start()
                logger.info(f"Mouse hotkey '{button}' enabled (block normal action: {block}).")
            except Exception as e:
                self._listener = None
                logger.error(f"Could not start mouse hotkey listener: {e}")

    def _stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    # --- Windows: raw hook messages, so the button's normal action (e.g. browser back) can be blocked ---
    def _win32_filter(self, msg, data):
        is_down = is_up = False
        if self._button == 'middle':
            is_down, is_up = msg == _WM_MBUTTONDOWN, msg == _WM_MBUTTONUP
        elif self._button in ('x1', 'x2') and msg in (_WM_XBUTTONDOWN, _WM_XBUTTONUP):
            which = (data.mouseData >> 16) & 0xFFFF  # 1 = XBUTTON1 (back), 2 = XBUTTON2 (forward)
            if which == (1 if self._button == 'x1' else 2):
                is_down, is_up = msg == _WM_XBUTTONDOWN, msg == _WM_XBUTTONUP
        if not (is_down or is_up):
            return True
        self._pressed = is_down
        if self._block and self._listener:
            self._listener.suppress_event()
        return True

    # --- macOS / Linux ---
    def _on_click(self, x, y, button, pressed):
        names = {'middle': ['middle'], 'x1': ['x1', 'button8'], 'x2': ['x2', 'button9']}
        if getattr(button, 'name', '') in names.get(self._button, []):
            self._pressed = pressed
