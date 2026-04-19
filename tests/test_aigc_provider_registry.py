from app.aigc.provider_registry import get_provider, list_available_providers
from app.aigc.providers.seedream_ark import SeedreamArkProvider
from app.config import settings


def test_get_provider_seedream_ark():
    provider = get_provider("seedream_ark", settings)
    assert isinstance(provider, SeedreamArkProvider)
    assert provider.provider_key == "seedream_ark"


def test_get_provider_unknown_raises():
    try:
        get_provider("nonexistent_provider", settings)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "nonexistent_provider" in str(e)


def test_list_available_providers():
    providers = list_available_providers()
    assert len(providers) >= 1
    seedream = next(p for p in providers if p["provider_key"] == "seedream_ark")
    assert seedream["default_model"] == "doubao-seedream-4-5-251128"
