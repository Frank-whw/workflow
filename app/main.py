import os
import sys
import time
import threading
from dataclasses import dataclass
import json
from app.capture import ScreenCapture
from app.activity import ActivityTracker
from app.sampler import list_recent_frames, sample_even, make_collage
from app.ocr import extract_text
from app.model import summarize_card
import json as _json
from collections import deque
import base64
from app.cleanup import CleanupService

def _normalize_title(title: str) -> str:
    t = (title or "").strip()
    parts = [p for p in t.split() if p]
    parts = parts[:10]
    return " ".join(parts) or "Recent Activity"

def _normalize_summary(summary: str) -> str:
    s = (summary or "").strip()
    if not s:
        return "No model output"
    seps = ".!?"
    out = []
    buf = ""
    for ch in s:
        buf += ch
        if ch in seps:
            out.append(buf.strip())
            buf = ""
            if len(out) >= 2:
                break
    if len(out) < 2 and buf.strip():
        out.append(buf.strip())
    return " ".join(out)

def _to_12h(t: str) -> str:
    s = (t or "").strip()
    if not s:
        return s
    if "AM" in s or "PM" in s:
        return s
    try:
        hh, mm = s.split(":")[:2]
        h = int(hh)
        m = int(mm)
        ap = "AM" if h < 12 else "PM"
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{m:02d} {ap}"
    except Exception:
        return s

def _infer_category(titles: list) -> tuple:
    joined = " ".join(titles or []).lower()
    if any(k in joined for k in ["visual studio", "cursor", "code", "github", "gitlab", "terminal"]):
        return "Work", "Coding"
    if any(k in joined for k in ["figma", "sketch", "photoshop"]):
        return "Work", "Design"
    if any(k in joined for k in ["youtube", "netflix", "twitch"]):
        return "Leisure", "Video"
    if any(k in joined for k in ["chrome", "edge", "safari", "firefox"]):
        return "Browsing", "Research"
    return "General", "Activity"


@dataclass
class Settings:
    capture_fps: int = 1
    analysis_interval_minutes: int = 15
    model_type: str = "none"
    model_base_url: str = ""
    model_api_key: str = ""
    model_name: str = ""
    analysis_use_image: bool = True
    analysis_use_ocr: bool = False
    analysis_log_capture: bool = False
    analysis_persist_raw_response: bool = False
    cleanup_tmp_frames_minutes: int = 25
    cleanup_collages_days: int = 3
    cleanup_cards_days: int = 30
    cleanup_max_data_size_mb: int = 500


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
    base = Settings()
    if data:
        base.capture_fps = int(data.get("capture_fps", base.capture_fps))
        base.analysis_interval_minutes = int(data.get("analysis_interval_minutes", base.analysis_interval_minutes))
        mp = data.get("model_provider", {})
        base.model_type = str(mp.get("type", base.model_type))
        base.model_base_url = str(mp.get("base_url", base.model_base_url))
        base.model_api_key = str(mp.get("api_key", base.model_api_key))
        base.model_name = str(mp.get("model", base.model_name))
        an = data.get("analysis", {})
        base.analysis_use_image = bool(an.get("use_image", base.analysis_use_image))
        base.analysis_use_ocr = bool(an.get("use_ocr", base.analysis_use_ocr))
        base.analysis_log_capture = bool(an.get("log_capture", base.analysis_log_capture))
        base.analysis_persist_raw_response = bool(an.get("persist_raw_response", base.analysis_persist_raw_response))
        cl = data.get("cleanup", {})
        base.cleanup_tmp_frames_minutes = int(cl.get("tmp_frames_minutes", base.cleanup_tmp_frames_minutes))
        base.cleanup_collages_days = int(cl.get("collages_days", base.cleanup_collages_days))
        base.cleanup_cards_days = int(cl.get("cards_days", base.cleanup_cards_days))
        base.cleanup_max_data_size_mb = int(cl.get("max_data_size_mb", base.cleanup_max_data_size_mb))
    if debug:
        base.analysis_interval_minutes = 1
    env_base = os.environ.get("MODEL_BASE_URL")
    env_key = os.environ.get("MODEL_API_KEY")
    if env_base:
        base.model_base_url = env_base
        base.model_type = "openai_compatible"
    if env_key:
        base.model_api_key = env_key
    return base


class Scheduler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop = threading.Event()
        self._threads = []
        self._cap = ScreenCapture(out_dir=os.path.join(os.getcwd(), "data", "tmp_frames"))
        self._tracker = ActivityTracker()
        self._title_buffer = deque(maxlen=max(120, self.settings.analysis_interval_minutes * 60))

    def start(self):
        t1 = threading.Thread(target=self._capture_loop, daemon=True)
        t2 = threading.Thread(target=self._analysis_loop, daemon=True)
        t3 = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._threads.extend([t1, t2, t3])
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
            if self.settings.analysis_log_capture:
                info = f"title={title or ''} pid={pid or ''}"
                print(f"[capture] {ts} saved={bool(path)} {info}")
            if title:
                self._title_buffer.append((time.time(), title))
            time.sleep(interval)

    def _analysis_loop(self):
        interval = max(1, self.settings.analysis_interval_minutes) * 60
        while not self._stop.is_set():
            time.sleep(interval)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            self._do_analysis(ts)

    def _do_analysis(self, ts: str):
        frames = list_recent_frames(os.path.join(os.getcwd(), "data", "tmp_frames"), 120)
        picked = sample_even(frames, 12)
        collage_dir = os.path.join(os.getcwd(), "data", "tmp_collages")
        collage_path = os.path.join(collage_dir, f"collage_{int(time.time())}.jpg")
        out = make_collage(picked, (3, 4), collage_path)
        text = extract_text(picked) if self.settings.analysis_use_ocr else ""
        card_info = {
            "window_titles": [t for ts2, t in self._title_buffer if time.time() - ts2 <= self.settings.analysis_interval_minutes * 60][-10:],
            "ocr_text": text,
            "apps": [],
            "domains": [],
        }
        card = None
        provider_used = "local"
        model_used = ""
        collage_b64 = ""
        if self.settings.analysis_use_image and out and os.path.exists(out):
            with open(out, "rb") as f:
                collage_b64 = base64.b64encode(f.read()).decode("ascii")
        if self.settings.model_type == "openai_compatible" and self.settings.model_base_url:
            try:
                from app.provider import OpenAICompatibleProvider
                prov = OpenAICompatibleProvider(
                    base_url=self.settings.model_base_url,
                    api_key=self.settings.model_api_key,
                    model=self.settings.model_name or "gpt-4o-mini"
                )
                sys_prompt = ""
                ppath = os.path.join(os.getcwd(), "prompt.txt")
                if os.path.exists(ppath):
                    try:
                        with open(ppath, "r", encoding="utf-8") as pf:
                            sys_prompt = pf.read()
                    except Exception:
                        sys_prompt = ""
                card = prov.summarize(card_info, collage_b64 if self.settings.analysis_use_image else "", sys_prompt)
                provider_used = "openai_compatible"
                model_used = prov.model
            except Exception:
                card = None
        if not card:
            card = summarize_card(card_info)
        title = _normalize_title(card.get("title"))
        summary = _normalize_summary(card.get("summary"))
        timeline = card.get("timeline") if isinstance(card.get("timeline"), list) else None
        if timeline and len(timeline) > 0:
            for it in timeline:
                if isinstance(it, dict):
                    it["startTime"] = _to_12h(str(it.get("startTime", "")))
                    it["endTime"] = _to_12h(str(it.get("endTime", "")))
        else:
            cat, sub = _infer_category(card_info.get("window_titles") or [])
            timeline = [{
                "startTime": "",
                "endTime": "",
                "category": cat,
                "subcategory": sub,
                "title": title,
                "summary": summary,
                "detailedSummary": summary,
                "appSites": {"primary": (card_info.get("window_titles") or [""])[-1] or ""}
            }]
            card["source"] = card.get("source") or "heuristic"
        cards_dir = os.path.join(os.getcwd(), "data", "analysis")
        os.makedirs(cards_dir, exist_ok=True)
        base_ts = int(time.time())
        primary_path = os.path.join(cards_dir, f"analysis_{base_ts}.json")
        provider_fallback = card.get("provider_fallback") or "none"
        obj = {
            "time": ts,
            "title": title,
            "summary": summary,
            "timeline": timeline,
            "collage": out,
            "provider": provider_used,
            "model": model_used,
            "provider_fallback": provider_fallback,
            "source": card.get("source") or ("model" if provider_used != "local" else "heuristic")
        }
        with open(primary_path, "w", encoding="utf-8") as f:
            f.write(_json.dumps(obj, ensure_ascii=False))
        split_paths = []
        if timeline and len(timeline) > 1:
            for i, it in enumerate(timeline):
                p = os.path.join(cards_dir, f"analysis_{base_ts}_{i}.json")
                with open(p, "w", encoding="utf-8") as f:
                    f.write(_json.dumps({
                        "time": ts,
                        "card": it,
                        "collage": out,
                        "provider": provider_used,
                        "model": model_used,
                        "source": obj["source"],
                    }, ensure_ascii=False))
                split_paths.append(p)
            index_path = os.path.join(cards_dir, f"analysis_{base_ts}_index.json")
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(_json.dumps({
                    "primary": primary_path,
                    "parts": split_paths
                }, ensure_ascii=False))
        raw = card.get("raw_response")
        persist_raw = False
        try:
            persist_raw = bool(getattr(self.settings, "analysis_persist_raw_response", False))
        except Exception:
            persist_raw = False
        if persist_raw and raw is not None:
            raw_path = os.path.join(cards_dir, f"raw_{base_ts}.json")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(_json.dumps(raw, ensure_ascii=False))
        print(f"[analysis] {ts} provider={provider_used} model={model_used} title={title} saved={os.path.basename(primary_path)}")

    def _cleanup_loop(self):
        base_dir = os.path.join(os.getcwd(), "data")
        svc = CleanupService(
            base_dir=base_dir,
            tmp_minutes=self.settings.cleanup_tmp_frames_minutes,
            collages_days=self.settings.cleanup_collages_days,
            cards_days=self.settings.cleanup_cards_days,
            max_mb=self.settings.cleanup_max_data_size_mb,
        )
        while not self._stop.is_set():
            svc.run()


def main():
    settings = load_settings()
    scheduler = Scheduler(settings)
    scheduler.start()
    try:
        run_seconds = os.environ.get("RUN_SECONDS")
        if os.environ.get("RUN_SINGLE_ANALYSIS_AFTER_SECONDS"):
            wait_s = int(os.environ.get("RUN_SINGLE_ANALYSIS_AFTER_SECONDS"))
            end = time.time() + max(1, wait_s)
            while time.time() < end:
                time.sleep(0.5)
            scheduler._do_analysis(time.strftime("%Y-%m-%d %H:%M:%S"))
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