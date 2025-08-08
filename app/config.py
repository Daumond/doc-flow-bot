from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    bot_token: str = os.getenv("BOT_TOKEN", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./dealflow.sqlite3")
    yandex_disk_token: str = os.getenv("YANDEX_DISK_TOKEN", "")
    env: str = os.getenv("ENV", "dev")

settings = Settings()