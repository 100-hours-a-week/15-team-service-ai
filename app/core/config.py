from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    environment: str = "development"

    # LLM 설정
    llm_generator_model: str = "gpt-5.2-codex"
    llm_evaluator_model: str = "gpt-4o"

    # OpenAI
    openai_api_key: str = ""

    # GitHub
    github_token: str = ""

    # Callback
    backend_callback_url: str = ""

    # Timeout 설정
    github_timeout: float = 60.0
    openai_timeout: float = 120.0
    callback_timeout: float = 120.0

    # 동시 요청 제한
    github_max_concurrent_requests: int = 5

    # Callback 재시도 설정
    callback_max_retries: int = 3
    callback_retry_base_delay: float = 1.0

    # 로깅 설정
    log_level: str = "INFO"

    # Langfuse 설정
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("openai_api_key", "github_token")
    @classmethod
    def validate_required_in_production(cls, v: str, info) -> str:
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_for_production(self) -> list[str]:
        """프로덕션 환경에서 필수 설정 검증"""
        errors = []
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
        if not self.github_token:
            errors.append("GITHUB_TOKEN is required")
        return errors


settings = Settings()
