from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "cloth-gallery"
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True

    embed_endpoint: str = "http://localhost:8001"
    vlm_endpoint: str = "http://localhost:8002"

    class Config:
        env_file = ".env"


settings = Settings()
