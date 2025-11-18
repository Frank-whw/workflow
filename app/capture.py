from typing import Optional
import os


class ScreenCapture:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir

    def capture_to_file(self, filename: Optional[str] = None) -> Optional[str]:
        return None