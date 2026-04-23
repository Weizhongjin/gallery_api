from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    budan_database_url: str = "postgresql://postgres:postgres@192.168.0.103:5432/budan"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    storage_provider: str = "s3"  # "s3" | "tos"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "cloth-gallery"
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True
    # TOS-specific config (storage_provider=tos). Credentials can be read from file.
    tos_endpoint: str = "https://tos-cn-beijing.volces.com"
    tos_region: str = "cn-beijing"
    tos_bucket: str = "joeffe"
    tos_credentials_file: str = "/Users/weizhongjin/develop_program/shared/third-party/toc/AccessKey.txt"

    embed_endpoint: str = "http://localhost:8001"
    embed_provider: str = "infinity"  # "infinity" | "dashscope"
    embed_model: str = "Marqo/marqo-fashionSigLIP"
    embed_dimension: int = 0  # 0 means provider default
    embed_api_key: str = ""
    vlm_endpoint: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: str = ""
    vlm_api_key: str = ""
    vlm_model: str = "qwen-vl-plus"

    async_mode: str = "background"        # "background" | "celery"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_default_queue: str = "celery"
    celery_aigc_queue: str = "aigc"

    # AIGC provider settings
    volc_ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    # Support both VOLC_ARK_API_KEY and ARK_API_KEY for compatibility.
    volc_ark_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("VOLC_ARK_API_KEY", "ARK_API_KEY"),
    )
    aigc_default_provider: str = "seedream_ark"
    aigc_model_name: str = "doubao-seedream-4-5-251128"
    aigc_default_candidate_count: int = 2
    aigc_provider_timeout_seconds: int = 700
    aigc_soft_timeout_seconds: int = 900
    aigc_hard_timeout_seconds: int = 1200

    class Config:
        env_file = ".env"


settings = Settings()
