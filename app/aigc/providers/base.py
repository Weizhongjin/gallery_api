from typing import Protocol, runtime_checkable


@runtime_checkable
class AigcProvider(Protocol):
    provider_key: str

    def generate(
        self,
        *,
        prompt: str,
        image_data_urls: list[str],
        resolution: str,
    ) -> list[bytes]: ...

    def build_request_payload(
        self,
        *,
        prompt: str,
        image_data_urls: list[str],
        resolution: str,
    ) -> dict: ...
