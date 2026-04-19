import logging
import tempfile
from pathlib import Path

import requests
from volcenginesdkarkruntime import Ark

logger = logging.getLogger(__name__)


class SeedreamArkProvider:
    provider_key = "seedream_ark"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        timeout_seconds: int,
    ) -> None:
        self._client = Ark(base_url=base_url, api_key=api_key, timeout=timeout_seconds)
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds

    def build_request_payload(
        self,
        *,
        prompt: str,
        image_data_urls: list[str],
        resolution: str = "2K",
    ) -> dict:
        return {
            "model": self._model_name,
            "prompt": prompt,
            "image": image_data_urls,
            "response_format": "url",
            "size": resolution,
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": True,
        }

    def generate(
        self,
        *,
        prompt: str,
        image_data_urls: list[str],
        resolution: str = "2K",
    ) -> list[bytes]:
        resp = self._client.images.generate(
            model=self._model_name,
            prompt=prompt,
            image=image_data_urls,
            response_format="url",
            size=resolution,
            sequential_image_generation="disabled",
            stream=False,
            watermark=True,
        )
        urls = [item.url for item in resp.data]
        return self._download_images(urls)

    @staticmethod
    def _download_images(urls: list[str]) -> list[bytes]:
        results: list[bytes] = []
        for url in urls:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            results.append(r.content)
        return results
