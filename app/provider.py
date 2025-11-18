import requests
import base64


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def summarize(self, info: dict, collage_b64: str = "") -> dict:
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
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": "你是一个时间线助手，请用一句话总结过去时间段的活动，并给出可能的分心来源。"}]},
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
        return {
            "title": "最近活动摘要",
            "summary": txt or "无模型返回",
            "apps": [],
            "domains": []
        }