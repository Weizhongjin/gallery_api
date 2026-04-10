import os
from typing import Any, Optional

import httpx


class EmbeddingClient:
    def __init__(
        self,
        endpoint: str,
        model: str = "Marqo/marqo-fashionSigLIP",
        timeout: int = 30,
        provider: str = "infinity",
        api_key: str = "",
        dimension: int = 0,
    ):
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._provider = (provider or "infinity").strip().lower()
        self._api_key = api_key
        self._dimension = int(dimension or 0)

    # ---------- Infinity-compatible HTTP mode ----------
    def _embed_infinity(self, input_value: str, modality: str) -> list[float]:
        payload = {
            "input": input_value,
            "modality": modality,
            "model": self._model,
            "encoding_format": "float",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                f"{self._endpoint}/v1/embeddings",
                json=payload,
            )
            resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    # ---------- DashScope SDK mode ----------
    @staticmethod
    def _extract_dashscope_embedding(output: Any) -> list[float]:
        if isinstance(output, dict):
            embeddings = output.get("embeddings") or output.get("embedding")
            if isinstance(embeddings, list) and embeddings:
                first = embeddings[0]
                if isinstance(first, dict) and isinstance(first.get("embedding"), list):
                    return first["embedding"]
                if isinstance(first, list):
                    return first
            if isinstance(embeddings, dict) and isinstance(embeddings.get("embedding"), list):
                return embeddings["embedding"]
        raise ValueError(f"Unexpected DashScope embedding output format: {output!r}")

    def _embed_dashscope(self, text: Optional[str] = None, image_url: Optional[str] = None) -> list[float]:
        try:
            import dashscope
        except Exception as exc:
            raise RuntimeError("dashscope package is required for EMBED_PROVIDER=dashscope") from exc

        key = self._api_key or os.getenv("DASHSCOPE_API_KEY", "")
        if not key:
            raise RuntimeError("Missing DashScope API key. Set EMBED_API_KEY or DASHSCOPE_API_KEY.")

        input_data: list[dict[str, str]] = []
        if text is not None:
            input_data.append({"text": text})
        if image_url is not None:
            input_data.append({"image": image_url})
        if not input_data:
            raise ValueError("Either text or image_url is required")

        # Single-modality by default for current API usage.
        resp = dashscope.MultiModalEmbedding.call(
            api_key=key,
            model=self._model,
            input=input_data,
            enable_fusion=False,
            **({"dimension": self._dimension} if self._dimension > 0 else {}),
        )
        status_code = getattr(resp, "status_code", None)
        code = getattr(resp, "code", None)
        message = getattr(resp, "message", None)
        # SDK objects usually expose .output; fallback to dict access for compatibility.
        output = getattr(resp, "output", None)
        if output is None and isinstance(resp, dict):
            output = resp.get("output")
        if output is None:
            raise RuntimeError(
                f"DashScope embedding failed: status={status_code} code={code} message={message}"
            )
        return self._extract_dashscope_embedding(output)

    def embed_image(self, image_url: str) -> list[float]:
        """Embed an image via HTTPS URL."""
        if self._provider == "dashscope":
            return self._embed_dashscope(image_url=image_url)
        return self._embed_infinity(image_url, "image")

    def embed_text(self, text: str) -> list[float]:
        """Embed a text query."""
        if self._provider == "dashscope":
            return self._embed_dashscope(text=text)
        return self._embed_infinity(text, "text")


def get_embedding_client() -> EmbeddingClient:
    from app.config import settings

    provider = getattr(settings, "embed_provider", "infinity")
    api_key = (
        getattr(settings, "embed_api_key", "")
        or getattr(settings, "dashscope_api_key", "")
        or os.getenv("DASHSCOPE_API_KEY", "")
    )
    return EmbeddingClient(
        endpoint=settings.embed_endpoint,
        model=getattr(settings, "embed_model", "Marqo/marqo-fashionSigLIP"),
        provider=provider,
        api_key=api_key,
        dimension=getattr(settings, "embed_dimension", 0),
    )
