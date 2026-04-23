from __future__ import annotations

from app.config import Settings


def get_provider(provider_key: str, settings: Settings):
    if provider_key == "seedream_ark":
        from app.aigc.providers.seedream_ark import SeedreamArkProvider

        return SeedreamArkProvider(
            api_key=settings.volc_ark_api_key,
            base_url=settings.volc_ark_base_url,
            model_name=settings.aigc_model_name,
            timeout_seconds=settings.aigc_provider_timeout_seconds,
        )
    raise ValueError(f"unsupported AIGC provider: {provider_key}")


def list_available_providers() -> list[dict]:
    return [
        {
            "provider_key": "seedream_ark",
            "display_name": "Seedream (Volcengine Ark)",
            "default_model": "doubao-seedream-4-5-251128",
        },
    ]
