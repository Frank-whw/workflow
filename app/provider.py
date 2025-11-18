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
            text_parts.append("窗口/页面：" + "; ".join(titles[-5:]))
        ocr_text = (info.get("ocr_text") or "").strip()
        if ocr_text:
            text_parts.append("文本关键词：" + ocr_text[:600])
        prompt = "\n\n".join(text_parts) or "请根据图像与窗口标题总结最近活动。"
        content.append({"type": "text", "text": prompt})
        if collage_b64:
            content.append({
                "type": "input_image",
                "image_url": {"url": "data:image/jpeg;base64," + collage_b64}
            })
        sys_text = system_prompt.strip() if system_prompt else "你是时间线助手。任务：依据最近的窗口标题与代表拼贴图，简洁总结过去一段时间的主要活动（不超过60字），并指出2-3个可能的分心来源（应用或网站）。以中文输出。"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": sys_text}]},
                {"role": "user", "content": content}
            ]
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json"
        }
        url = self.base_url + "/chat/completions"
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        msg = (data.get("choices") or [{}])[0].get("message", {})
        txt = ""
        if isinstance(msg.get("content"), list):
            parts = [p.get("text", "") for p in msg["content"] if p.get("type") == "text"]
            txt = " ".join([t for t in parts if t])
        else:
            txt = msg.get("content") or ""
        # 尝试解析为 JSON 数组（若提示要求返回结构化结果）
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
            title = first.get("title") or "最近活动摘要"
            summary = first.get("summary") or txt or "无模型返回"
            return {"title": title, "summary": summary, "apps": [], "domains": [], "timeline": parsed}
        return {"title": "最近活动摘要", "summary": txt or "无模型返回", "apps": [], "domains": []}