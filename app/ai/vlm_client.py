import json
import httpx

_CLASSIFY_PROMPT = """你是一个服装分类专家。请分析这张服装图片，按以下5个维度输出JSON。
只输出JSON，不要解释。

维度（所有字段必须存在，无对应标签用空数组或null）：
- category: 品类（单值字符串）：上衣/裤子/裙子/外套/套装
- style: 风格（字符串数组）：商务风/休闲/运动/高端/简约/...
- color: 颜色（字符串数组）：藏青色/米白/黑色/...
- scene: 场景（字符串数组）：通勤/日常/晚宴/户外/...
- detail: 款式细节（字符串数组）：西装领/长袖/宽松版型/...

严格输出JSON格式：{"category": "...", "style": [...], "color": [...], "scene": [...], "detail": [...]}"""


class VLMClient:
    def __init__(self, endpoint: str, api_key: str = "", model: str = "qwen-vl-plus", timeout: int = 30):
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def classify(self, image_url: str) -> dict:
        """Call VLM with image URL, return parsed classification dict.

        Returns dict with keys: category, style, color, scene, detail.
        Raises ValueError if VLM response is not valid JSON.
        Raises httpx.HTTPError on network/HTTP failures.
        """
        payload = {
            "model": self._model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": _CLASSIFY_PROMPT},
                ],
            }],
            "response_format": {"type": "json_object"},
            "max_tokens": 512,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._endpoint}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

        content = resp.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"VLM returned non-JSON content: {content[:200]}")


def get_vlm_client() -> VLMClient:
    from app.config import settings
    return VLMClient(
        endpoint=settings.vlm_endpoint,
        api_key=getattr(settings, "vlm_api_key", ""),
        model=getattr(settings, "vlm_model", "qwen-vl-plus"),
    )
