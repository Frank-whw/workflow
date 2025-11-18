import requests
import base64


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def summarize(self, info: dict, collage_b64: str = "", system_prompt: str = "") -> dict:
        content = []
        text_parts = []
        titles = info.get("window_titles") or []
        if titles:
            text_parts.append("Windows/pages: " + "; ".join(titles[-5:]))
        ocr_text = (info.get("ocr_text") or "").strip()
        if ocr_text:
            text_parts.append("OCR keywords: " + ocr_text[:600])
        prompt = "\n\n".join(text_parts) or "Summarize recent activity based on the collage image and window titles."
        content.append({"type": "text", "text": prompt})
        if collage_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64," + collage_b64}
            })
        sys_text = system_prompt.strip() if system_prompt else (
            "You are an objective activity synthesizer. Produce concise, English-only outputs. "
            "Return a title (5–10 words) and a factual summary (≤2 sentences). Optionally return a timeline array with per-card entries "
            "containing startTime, endTime, category, subcategory, title, summary, detailedSummary, appSites. No distraction lists or subjective judgments."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_text},
                {"role": "user", "content": content}
            ],
            "stream": False,
            "max_tokens": 512,
            "temperature": 0.6
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json"
        }
        url = self.base_url + "/chat/completions"
        fallback_used = "none"
        raw_data = None
        # primary style
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            raw_data = data
        except Exception:
            # fallback: text-only
            fallback_used = "text_only"
            payload_fallback = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": sys_text},
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.6
            }
            try:
                r = requests.post(url, json=payload_fallback, headers=headers, timeout=30)
                r.raise_for_status()
                data = r.json()
                raw_data = data
            except Exception:
                # fallback 2: some implementations use images sidecar
                fallback_used = "images_sidecar" if collage_b64 else fallback_used
                if collage_b64:
                    payload_images = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": sys_text},
                            {"role": "user", "content": prompt}
                        ],
                        "images": [{"mime_type": "image/jpeg", "data": collage_b64}],
                        "max_tokens": 512,
                        "temperature": 0.6
                    }
                    r = requests.post(url, json=payload_images, headers=headers, timeout=30)
                    r.raise_for_status()
                    data = r.json()
                    raw_data = data
                else:
                    data = {"choices": [{"message": {"content": ""}}]}
        msg = (data.get("choices") or [{}])[0].get("message", {})
        txt = ""
        if isinstance(msg.get("content"), list):
            parts = [p.get("text", "") for p in msg["content"] if p.get("type") == "text"]
            txt = " ".join([t for t in parts if t])
        else:
            txt = msg.get("content") or ""
        # try parsing as JSON array
        import json as _json
        parsed = None
        try:
            s = txt.strip()
            if s.startswith("```"):
                s = s.strip("`\n ")
            parsed = _json.loads(s)
        except Exception:
            parsed = None
        if isinstance(parsed, list) and parsed:
            first = parsed[0]
            title = first.get("title") or "Recent Activity"
            summary = first.get("summary") or txt or "No model output"
            return {
                "title": title,
                "summary": summary,
                "apps": [],
                "domains": [],
                "timeline": parsed,
                "provider_fallback": fallback_used,
                "raw_response": raw_data,
                "source": "model",
            }
        return {
            "title": "Recent Activity",
            "summary": txt or "No model output",
            "apps": [],
            "domains": [],
            "provider_fallback": fallback_used,
            "raw_response": raw_data,
            "source": "model",
        }