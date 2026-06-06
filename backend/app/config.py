from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    listen_host: str = "127.0.0.1"
    listen_port: int = 8756

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
