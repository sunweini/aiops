# host-access/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    zabbix_url: str = ""
    zabbix_user: str = "Admin"
    zabbix_password: str = ""
    rag_api_url: str = "http://localhost:8001/api/v1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
