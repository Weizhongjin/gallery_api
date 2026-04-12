import json
import os
import base64

from openai import OpenAI

_CLASSIFY_PROMPT = """你是一个专业服装分类专家。请分析这张服装图片，按以下5个维度输出JSON。
只输出JSON，不要解释。所有字段必须存在，无对应内容用空数组或null。

- category: 品类（单值字符串，从以下选项中选择最匹配的一个）：
  T恤、衬衫、飘带衬衫、针织衫、毛衣、开衫、背心、卫衣、
  西装马甲、针织马甲、
  单件西装、套装、夹克、
  长大衣、短大衣、风衣、
  羽绒服、棉服、
  西装裤、阔腿裤、直筒裤、休闲裤、
  铅笔裙、A字裙、百褶裙、鱼尾裙、
  西装式连衣裙、礼服裙、日常连衣裙、针织连衣裙

- style: 风格（字符串数组，选取2-4个最匹配的）：
  静奢、知性、干练、职业、东方美学、优雅、女性力量、气场、精致、华丽、
  松弛感、温润、舒适、休闲、层次感、简约、极简、百搭、经典、大气、灵动、
  设计感、文化底蕴、匠心、联名限定

- color: 颜色（字符串数组，描述主要颜色，如：米白、黑色、藏青、驼色、深绿、灰色、卡其、焦糖、酒红、象牙白）

- scene: 场景（字符串数组，选取1-3个最匹配的）：
  职场通勤、日常出行、日常办公、周末休闲、差旅出行、
  商务社交、商务谈判、约会聚会、正式会议、重要场合、
  文化沙龙、艺术展、节庆聚会、品牌活动、晚宴、社交酒会、下午茶、户外休闲

- detail: 款式细节（字符串数组，描述版型、领型、袖型、工艺等视觉细节，如：宽松版型、西装领、修身、长袖、盘扣、刺绣、镂空、系带）

严格输出JSON格式：{"category": "...", "style": [...], "color": [...], "scene": [...], "detail": [...]}"""


class VLMClient:
    def __init__(self, endpoint: str, api_key: str = "", model: str = "qwen-vl-plus", timeout: int = 30):
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = OpenAI(
            api_key=self._api_key or "EMPTY",
            base_url=self._endpoint,
            timeout=self._timeout,
        )

    def classify(self, image_url: str = "", image_bytes: bytes | None = None, content_type: str = "image/jpeg") -> dict:
        """Call VLM with image URL or raw image bytes, return parsed classification dict.

        Returns dict with keys: category, style, color, scene, detail.
        Raises ValueError if VLM response is not valid JSON.
        Raises httpx.HTTPError on network/HTTP failures.
        """
        if image_bytes is not None:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            img_ref = f"data:{content_type};base64,{b64}"
        elif image_url:
            img_ref = image_url
        else:
            raise ValueError("Either image_url or image_bytes must be provided")

        payload = {
            "model": self._model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": img_ref}},
                    {"type": "text", "text": _CLASSIFY_PROMPT},
                ],
            }],
            "response_format": {"type": "json_object"},
            "max_tokens": 512,
        }
        completion = self._client.chat.completions.create(**payload)
        content = completion.choices[0].message.content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"VLM returned non-JSON content: {content[:200]}")


def get_vlm_client() -> VLMClient:
    from app.config import settings
    resolved_key = (
        getattr(settings, "vlm_api_key", "")
        or getattr(settings, "dashscope_api_key", "")
        or os.getenv("DASHSCOPE_API_KEY", "")
    )
    return VLMClient(
        endpoint=settings.vlm_endpoint,
        api_key=resolved_key,
        model=getattr(settings, "vlm_model", "qwen-vl-plus"),
    )
