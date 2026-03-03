from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    environment: str = "development"

    # vLLM 설정
    vllm_api_key: str = ""
    vllm_base_url: str = ""
    vllm_model: str = ""
    vllm_timeout: float = 600.0

    # Gemini 평가용 설정
    gemini_api_key: str = ""
    gemini_evaluator_model: str = ""
    gemini_timeout: float = 60.0

    # Callback
    generate_callback_url: str = ""
    edit_callback_url: str = ""
    chat_callback_url: str = ""
    ai_callback_secret: str = ""
    

    # Timeout 설정
    github_timeout: float = 60.0
    callback_timeout: float = 120.0
    workflow_timeout: float = 600.0

    # 동시 요청 제한
    github_max_concurrent_requests: int = 5

    # Callback 재시도 설정
    callback_max_retries: int = 3
    callback_retry_base_delay: float = 1.0

    # 워크플로우 설정
    workflow_max_retries: int = 2
    workflow_batch_size: int = 1

    # README 설정
    readme_max_length_github: int = 8000
    readme_max_length_prompt: int = 6000

    # 프롬프트 포맷 설정
    prompt_messages_max_count: int = 50
    prompt_file_tree_max_count: int = 15
    prompt_dependencies_max_count: int = 30

    # 로깅 설정
    log_level: str = "INFO"

    # Langfuse 설정
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # ElevenLabs STT 설정
    elevenlabs_api_key: str = ""
    elevenlabs_stt_model: str = "scribe_v2"
    stt_timeout: float = 30.0

    # AWS S3 설정
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-northeast-2"
    s3_bucket_name: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_for_production(self) -> list[str]:
        """프로덕션 환경에서 필수 설정 검증 후 누락된 항목 반환"""
        errors = []
        if not self.vllm_api_key:
            errors.append("VLLM_API_KEY")
        if not self.vllm_base_url:
            errors.append("VLLM_BASE_URL")
        if not self.gemini_api_key:
            errors.append("GEMINI_API_KEY")
        if not self.generate_callback_url:
            errors.append("GENERATE_CALLBACK_URL")
        if not self.edit_callback_url:
            errors.append("EDIT_CALLBACK_URL")
        if not self.chat_callback_url:
            errors.append("CHAT_CALLBACK_URL")
        if not self.ai_callback_secret:
            errors.append("AI_CALLBACK_SECRET")
        return errors

    @model_validator(mode="after")
    def validate_production_settings(self):
        """프로덕션 환경에서 필수 설정 검증"""
        if self.is_production:
            missing = self.validate_for_production()
            if missing:
                raise ValueError(f"프로덕션 환경에서 필수 설정 누락: {', '.join(missing)}")
        return self


settings = Settings()
