import os
import time


def _dir_size_mb(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
    return total // (1024 * 1024)


def _remove_older_than(path: str, seconds: int) -> int:
    now = time.time()
    count = 0
    if not os.path.isdir(path):
        return 0
    for f in os.listdir(path):
        fp = os.path.join(path, f)
        try:
            if os.path.isfile(fp):
                age = now - os.path.getmtime(fp)
                if age > seconds:
                    os.remove(fp)
                    count += 1
        except Exception:
            pass
    return count


class CleanupService:
    def __init__(self, base_dir: str, tmp_minutes: int, collages_days: int, cards_days: int, max_mb: int):
        self.base_dir = base_dir
        self.tmp_minutes = tmp_minutes
        self.collages_days = collages_days
        self.cards_days = cards_days
        self.max_mb = max_mb
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        while not self._stop:
            frames_dir = os.path.join(self.base_dir, "tmp_frames")
            collages_dir = os.path.join(self.base_dir, "tmp_collages")
            cards_dir = os.path.join(self.base_dir, "cards")
            c1 = _remove_older_than(frames_dir, self.tmp_minutes * 60)
            c2 = _remove_older_than(collages_dir, self.collages_days * 86400)
            c3 = _remove_older_than(cards_dir, self.cards_days * 86400) if self.cards_days > 0 else 0
            total_mb = _dir_size_mb(self.base_dir)
            if total_mb > self.max_mb:
                _remove_older_than(frames_dir, 0)
                _remove_older_than(collages_dir, 0)
            print(f"[cleanup] frames={c1} collages={c2} cards={c3} total_mb={total_mb}")
            time.sleep(600)