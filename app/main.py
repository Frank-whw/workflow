import os
import sys
import time
import threading
from dataclasses import dataclass
import json
from app.capture import ScreenCapture
from app.activity import ActivityTracker


@dataclass
class Settings:
    capture_fps: int = 1
    analysis_interval_minutes: int = 15


def load_settings() -> Settings:
    path = os.path.join(os.getcwd(), "config", "settings.json")
    data = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    debug = os.environ.get("APP_DEBUG_SHORT_INTERVALS")
    if debug:
        return Settings(capture_fps=int(data.get("capture_fps", 1)) if data else 1,
                        analysis_interval_minutes=1)
    if data:
        return Settings(capture_fps=int(data.get("capture_fps", 1)),
                        analysis_interval_minutes=int(data.get("analysis_interval_minutes", 15)))
    return Settings()


class Scheduler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop = threading.Event()
        self._threads = []
        self._cap = ScreenCapture(out_dir=os.path.join(os.getcwd(), "data", "tmp_frames"))
        self._tracker = ActivityTracker()

    def start(self):
        t1 = threading.Thread(target=self._capture_loop, daemon=True)
        t2 = threading.Thread(target=self._analysis_loop, daemon=True)
        self._threads.extend([t1, t2])
        for t in self._threads:
            t.start()

    def stop(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)

    def _capture_loop(self):
        interval = 1.0 / max(1, self.settings.capture_fps)
        while not self._stop.is_set():
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            path = self._cap.capture_to_file()
            title, pid = self._tracker.get_foreground_activity()
            info = f"title={title or ''} pid={pid or ''}"
            print(f"[capture] {ts} saved={bool(path)} {info}")
            time.sleep(interval)

    def _analysis_loop(self):
        interval = max(1, self.settings.analysis_interval_minutes) * 60
        while not self._stop.is_set():
            time.sleep(interval)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[analysis] run {ts}")


def main():
    settings = load_settings()
    scheduler = Scheduler(settings)
    scheduler.start()
    try:
        run_seconds = os.environ.get("RUN_SECONDS")
        if run_seconds:
            end = time.time() + max(1, int(run_seconds))
            while time.time() < end:
                time.sleep(0.5)
        else:
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        scheduler.stop()
        print("stopped")


if __name__ == "__main__":
    sys.exit(main())