from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정."""

    environment: str = "development"

    # LLM 설정
    llm_model: str = "gpt-5.2"

    # OpenAI
    openai_api_key: str = ""

    # GitHub
    github_token: str = ""

    # Callback
    backend_callback_url: str = ""

    # RunPod
    runpod_api_url: str = ""
    runpod_api_key: str = ""

    # Timeout 설정
    github_timeout: float = 60.0
    openai_timeout: float = 120.0
    callback_timeout: float = 30.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
