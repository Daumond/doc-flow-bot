from pydantic_settings import BaseSettings
from pydantic import Field

class YandexDiskSettings(BaseSettings):
    """Yandex.Disk API settings"""
    access_token: str = Field(..., env="YANDEX_DISK_TOKEN")
    base_url: str = "https://cloud-api.yandex.net/v1/disk"
    upload_timeout: int = 30  # seconds
    max_retries: int = 3

    class Config:
        env_prefix = "YANDEX_DISK_"

def get_yandex_disk_settings() -> YandexDiskSettings:
    """Get Yandex.Disk settings"""
    return YandexDiskSettings()
