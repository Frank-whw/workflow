import os
import sys
import re
import json
from typing import List, Dict, Optional
from flask import Flask, jsonify, render_template, send_from_directory, request, abort


def create_app() -> Flask:
    base_dir = getattr(sys, "_MEIPASS", os.getcwd())
    data_dir = os.path.join(base_dir, "data")
    analysis_dir = os.path.join(data_dir, "analysis")
    collages_dir = os.path.join(data_dir, "tmp_collages")
    settings_path = os.path.join(base_dir, "config", "settings.json")

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "app", "templates"),
        static_folder=os.path.join(base_dir, "app", "static")
    )
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    def _list_main_files() -> List[str]:
        if not os.path.isdir(analysis_dir):
            return []
        files = []
        for f in os.listdir(analysis_dir):
            m = re.fullmatch(r"analysis_(\d+)\.json", f)
            if m:
                files.append(f)
        files.sort(key=lambda n: int(re.findall(r"\d+", n)[0]), reverse=True)
        return files

    def _load_json(path: str) -> Optional[Dict]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _file_for_ts(ts: str) -> str:
        return os.path.join(analysis_dir, f"analysis_{ts}.json")

    def _index_for_ts(ts: str) -> str:
        return os.path.join(analysis_dir, f"analysis_{ts}_index.json")

    def _load_settings() -> Dict:
        obj = _load_json(settings_path) or {}
        mp = obj.get("model_provider") or {}
        ak_env = os.environ.get("MODEL_API_KEY") or ""
        ak_file = mp.get("api_key") or ""
        if "model_provider" not in obj:
            obj["model_provider"] = mp
        obj["model_provider"]["api_key_set"] = bool(ak_env or ak_file)
        if "api_key" in obj["model_provider"]:
            obj["model_provider"].pop("api_key", None)
        return obj

    def _save_settings(payload: Dict) -> bool:
        current = _load_json(settings_path) or {}
        current["capture_fps"] = int(payload.get("capture_fps", current.get("capture_fps", 1)))
        current["analysis_interval_minutes"] = int(payload.get("analysis_interval_minutes", current.get("analysis_interval_minutes", 15)))
        mp_in = payload.get("model_provider") or {}
        mp_cur = current.get("model_provider") or {}
        mp_cur["type"] = str(mp_in.get("type", mp_cur.get("type", "none")))
        mp_cur["base_url"] = str(mp_in.get("base_url", mp_cur.get("base_url", "")))
        mp_cur["model"] = str(mp_in.get("model", mp_cur.get("model", "")))
        api_key_new = mp_in.get("api_key")
        if isinstance(api_key_new, str) and api_key_new.strip():
            mp_cur["api_key"] = api_key_new.strip()
        current["model_provider"] = mp_cur
        an_in = payload.get("analysis") or {}
        an_cur = current.get("analysis") or {}
        an_cur["use_image"] = bool(an_in.get("use_image", an_cur.get("use_image", True)))
        an_cur["use_ocr"] = bool(an_in.get("use_ocr", an_cur.get("use_ocr", False)))
        an_cur["log_capture"] = bool(an_in.get("log_capture", an_cur.get("log_capture", False)))
        an_cur["persist_raw_response"] = bool(an_in.get("persist_raw_response", an_cur.get("persist_raw_response", False)))
        current["analysis"] = an_cur
        cl_in = payload.get("cleanup") or {}
        cl_cur = current.get("cleanup") or {}
        cl_cur["tmp_frames_minutes"] = int(cl_in.get("tmp_frames_minutes", cl_cur.get("tmp_frames_minutes", 25)))
        cl_cur["collages_days"] = int(cl_in.get("collages_days", cl_cur.get("collages_days", 3)))
        cl_cur["cards_days"] = int(cl_in.get("cards_days", cl_cur.get("cards_days", 30)))
        cl_cur["max_data_size_mb"] = int(cl_in.get("max_data_size_mb", cl_cur.get("max_data_size_mb", 500)))
        current["cleanup"] = cl_cur
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @app.get("/")
    def home():
        query = (request.args.get("query") or "").strip().lower()
        if len(query) > 200:
            query = query[:200]
        try:
            limit = int(request.args.get("limit") or 50)
        except Exception:
            limit = 50
        try:
            offset = int(request.args.get("offset") or 0)
        except Exception:
            offset = 0
        limit = max(1, min(200, limit))
        offset = max(0, min(10000, offset))
        files = _list_main_files()
        items = []
        for f in files[offset: offset + limit]:
            obj = _load_json(os.path.join(analysis_dir, f)) or {}
            title = obj.get("title") or ""
            summary = obj.get("summary") or ""
            meta = {
                "ts": re.findall(r"\d+", f)[0],
                "time": obj.get("time") or "",
                "title": title,
                "summary": summary,
                "provider": obj.get("provider") or "",
                "model": obj.get("model") or "",
                "source": obj.get("source") or "",
                "provider_fallback": obj.get("provider_fallback") or "",
            }
            txt = (title + " " + summary).lower()
            if query and query not in txt:
                continue
            items.append(meta)
        return render_template("index.html", items=items)

    @app.get("/analysis/<ts>")
    def detail(ts: str):
        if not _safe_ts(ts):
            abort(400)
        p = _file_for_ts(ts)
        obj = _load_json(p)
        if not obj:
            abort(404)
        idx = _load_json(_index_for_ts(ts))
        parts = []
        if idx and isinstance(idx.get("parts"), list):
            for part_path in idx["parts"]:
                try:
                    name = os.path.basename(part_path)
                    part_obj = _load_json(os.path.join(analysis_dir, name))
                    if part_obj:
                        parts.append(part_obj.get("card") or {})
                except Exception:
                    continue
        timeline = obj.get("timeline") if isinstance(obj.get("timeline"), list) else []
        if not timeline and parts:
            timeline = parts
        collage_name = ""
        try:
            collage_name = os.path.basename(obj.get("collage") or "")
        except Exception:
            collage_name = ""
        return render_template("detail.html", ts=ts, obj=obj, timeline=timeline, collage_name=collage_name)

    @app.get("/api/analyses")
    def api_list():
        query = (request.args.get("query") or "").strip().lower()
        if len(query) > 200:
            query = query[:200]
        try:
            offset = int(request.args.get("offset") or 0)
        except Exception:
            offset = 0
        try:
            limit = int(request.args.get("limit") or 50)
        except Exception:
            limit = 50
        offset = max(0, min(10000, offset))
        limit = max(1, min(200, limit))
        files = _list_main_files()[offset: offset + limit]
        out = []
        for f in files:
            obj = _load_json(os.path.join(analysis_dir, f)) or {}
            meta = {
                "ts": re.findall(r"\d+", f)[0],
                "time": obj.get("time") or "",
                "title": obj.get("title") or "",
                "summary": obj.get("summary") or "",
                "provider": obj.get("provider") or "",
                "model": obj.get("model") or "",
                "source": obj.get("source") or "",
                "provider_fallback": obj.get("provider_fallback") or "",
            }
            txt = (meta["title"] + " " + meta["summary"]).lower()
            if query and query not in txt:
                continue
            out.append(meta)
        return jsonify({"items": out, "offset": offset, "limit": limit})

    @app.get("/api/analysis/<ts>")
    def api_analysis(ts: str):
        if not _safe_ts(ts):
            abort(400)
        p = _file_for_ts(ts)
        obj = _load_json(p)
        if not obj:
            abort(404)
        return jsonify(obj)

    @app.get("/api/index/<ts>")
    def api_index(ts: str):
        if not _safe_ts(ts):
            abort(400)
        idx = _load_json(_index_for_ts(ts))
        if not idx:
            abort(404)
        return jsonify(idx)

    @app.get("/api/raw/<ts>")
    def api_raw(ts: str):
        if not _safe_ts(ts):
            abort(400)
        raw_path = os.path.join(analysis_dir, f"raw_{ts}.json")
        if not os.path.isfile(raw_path):
            abort(404)
        obj = _load_json(raw_path)
        if obj is None:
            abort(404)
        return jsonify(obj)

    @app.get("/settings")
    def settings_page():
        return render_template("settings.html")

    @app.get("/api/settings")
    def api_settings_get():
        return jsonify(_load_settings())

    @app.post("/api/settings")
    def api_settings_post():
        data = request.get_json(silent=True) or {}
        try:
            cfps = int(data.get("capture_fps", 1))
            cfps = max(1, min(30, cfps))
            aim = int(data.get("analysis_interval_minutes", 15))
            aim = max(1, min(1440, aim))
        except Exception:
            abort(400)
        mp_in = data.get("model_provider") or {}
        mp_type = str(mp_in.get("type", "none")).strip()
        if mp_type not in {"none", "openai_compatible"}:
            mp_type = "none"
        mp_base = str(mp_in.get("base_url", "")).strip()
        if len(mp_base) > 300:
            mp_base = mp_base[:300]
        mp_model = str(mp_in.get("model", "")).strip()
        if len(mp_model) > 120:
            mp_model = mp_model[:120]
        mp_key = mp_in.get("api_key")
        an_in = data.get("analysis") or {}
        cl_in = data.get("cleanup") or {}
        try:
            tmp_min = int(cl_in.get("tmp_frames_minutes", 25))
            coll_days = int(cl_in.get("collages_days", 3))
            cards_days = int(cl_in.get("cards_days", 30))
            max_mb = int(cl_in.get("max_data_size_mb", 500))
        except Exception:
            abort(400)
        tmp_min = max(1, min(1440, tmp_min))
        coll_days = max(0, min(365, coll_days))
        cards_days = max(0, min(365, cards_days))
        max_mb = max(50, min(10000, max_mb))
        payload = {
            "capture_fps": cfps,
            "analysis_interval_minutes": aim,
            "model_provider": {
                "type": mp_type,
                "base_url": mp_base,
                "model": mp_model,
            },
            "analysis": {
                "use_image": bool(an_in.get("use_image", True)),
                "use_ocr": bool(an_in.get("use_ocr", False)),
                "log_capture": bool(an_in.get("log_capture", False)),
                "persist_raw_response": bool(an_in.get("persist_raw_response", False)),
            },
            "cleanup": {
                "tmp_frames_minutes": tmp_min,
                "collages_days": coll_days,
                "cards_days": cards_days,
                "max_data_size_mb": max_mb,
            }
        }
        if isinstance(mp_key, str) and mp_key.strip():
            payload["model_provider"]["api_key"] = mp_key.strip()
        ok = _save_settings(payload)
        if not ok:
            abort(400)
        return jsonify({"ok": True})

    @app.get("/collages/<path:name>")
    def collages(name: str):
        n = (name or "").lower()
        if not (n.endswith(".jpg") or n.endswith(".jpeg")):
            abort(400)
        return send_from_directory(collages_dir, name, cache_timeout=86400)

    @app.get("/analysis_files/<path:name>")
    def analysis_files(name: str):
        n = (name or "").lower()
        if not n.endswith(".json"):
            abort(400)
        return send_from_directory(analysis_dir, name, cache_timeout=86400)

    return app


def main():
    app = create_app()
    port = int(os.environ.get("WEB_PORT") or 8080)
    cert = os.environ.get("WEB_SSL_CERT") or ""
    key = os.environ.get("WEB_SSL_KEY") or ""
    use_ssl = bool(cert and key)
    app.config["USE_SSL"] = use_ssl
    if use_ssl:
        print(f"[web] Serving on https://localhost:{port}/")
        app.run(host="127.0.0.1", port=port, debug=False, ssl_context=(cert, key))
    else:
        print(f"[web] Serving on http://localhost:{port}/")
        app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
    def _safe_ts(ts: str) -> Optional[str]:
        if re.fullmatch(r"\d+", ts or ""):
            return ts
        return None

    @app.after_request
    def _secure_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'"
        if app.config.get("USE_SSL"):
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp