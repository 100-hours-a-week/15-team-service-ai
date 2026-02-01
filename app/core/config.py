from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    environment: str = "development"

    # LLM 프로바이더 선택: "openai" 또는 "vllm"
    llm_provider: str = "vllm"

    # OpenAI 설정 - 개발/테스트용
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout: float = 120.0

    # vLLM/RunPod 설정 - 운영용
    vllm_api_url: str = ""
    vllm_api_key: str = ""
    vllm_model: str = ""
    vllm_timeout: float = 180.0

    # Gemini 설정 - 이력서 평가용
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-pro-preview"
    gemini_timeout: float = 120.0

    # GitHub
    github_token: str = ""

    # Callback
    backend_callback_url: str = ""
    ai_callback_secret: str = ""

    # Timeout 설정
    github_timeout: float = 60.0
    callback_timeout: float = 120.0
    workflow_timeout: float = 300.0

    # 동시 요청 제한
    github_max_concurrent_requests: int = 5

    # Callback 재시도 설정
    callback_max_retries: int = 3
    callback_retry_base_delay: float = 1.0

    # 워크플로우 설정
    workflow_max_retries: int = 2
    workflow_batch_size: int = 3

    # README 설정
    readme_max_length_github: int = 2000
    readme_max_length_prompt: int = 1500

    # 로깅 설정
    log_level: str = "INFO"

    # CORS 설정
    cors_allowed_origins: str = ""

    # Langfuse 설정
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_for_production(self) -> list[str]:
        """프로덕션 환경에서 필수 설정 검증 후 누락된 항목 반환"""
        errors = []
        if not self.vllm_api_url:
            errors.append("VLLM_API_URL")
        if not self.gemini_api_key:
            errors.append("GEMINI_API_KEY")
        if not self.backend_callback_url:
            errors.append("BACKEND_CALLBACK_URL")
        return errors

    @model_validator(mode="after")
    def validate_production_settings(self):
        """프로덕션 환경에서 필수 설정 검증"""
        if self.is_production:
            missing = []
            if not self.vllm_api_url:
                missing.append("VLLM_API_URL")
            if not self.gemini_api_key:
                missing.append("GEMINI_API_KEY")
            if not self.backend_callback_url:
                missing.append("BACKEND_CALLBACK_URL")

            if missing:
                raise ValueError(f"프로덕션 환경에서 필수 설정 누락: {', '.join(missing)}")
        return self


settings = Settings()
