import httpx


class EmbeddingClient:
    def __init__(self, endpoint: str, model: str = "Marqo/marqo-fashionSigLIP", timeout: int = 30):
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._timeout = timeout

    def _embed(self, input_value: str, modality: str) -> list[float]:
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

    def embed_image(self, image_url: str) -> list[float]:
        """Embed an image via its HTTPS URL. Returns 768-dim float list."""
        return self._embed(image_url, "image")

    def embed_text(self, text: str) -> list[float]:
        """Embed a text query. Returns 768-dim float list."""
        return self._embed(text, "text")


def get_embedding_client() -> EmbeddingClient:
    from app.config import settings
    return EmbeddingClient(
        endpoint=settings.embed_endpoint,
        model=getattr(settings, "embed_model", "Marqo/marqo-fashionSigLIP"),
    )
