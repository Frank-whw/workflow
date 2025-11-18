from typing import Optional, Tuple
import ctypes


class ActivityTracker:
    def get_foreground_activity(self) -> Tuple[Optional[str], Optional[int]]:
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None, None
            length = user32.GetWindowTextLengthW(hwnd) + 1
            buf = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(hwnd, buf, length)
            pid = ctypes.c_uint32()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return buf.value, int(pid.value)
        except Exception:
            return None, None