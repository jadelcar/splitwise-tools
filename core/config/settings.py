# config/settings.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    
    CONSUMER_KEY: str
    CONSUMER_SECRET: str

    TEST_USER : str
    TEST_PASSWORD : str

    @property
    def BASE_URL(self) -> str:
        if self.ENV == "production":
            return "https://splitwise-tools.onrender.com"
        return f"http://{self.APP_HOST}:{self.APP_PORT}"
    
    @property
    def OAUTH_REDIRECT_URI(self) -> str:
        return f"{self.BASE_URL}/auth/callback"
    
    model_config = ConfigDict(env_file=".env")

@lru_cache()
def get_settings() -> Settings:
    return Settings()