# 1. Base Stage: 런타임 및 시스템 의존성 설치
FROM python:3.12-slim-bookworm AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# [중요] 깃 로그 분석을 위해 실제 git 바이너리가 필요합니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 의존성 설치 (캐시 활용)
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# 의존성 파일 복사
COPY pyproject.toml uv.lock ./

# 프로덕션 의존성 설치 (dev 제외)
# --frozen: 락파일 기준 설치
# --no-dev: 개발 의존성 제외
# --no-install-project: 프로젝트 자체는 설치하지 않음 (나중에 COPY)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# PATH 설정 (.venv/bin 우선)
ENV PATH="/app/.venv/bin:$PATH"

# 2. Test Stage: CI 과정에서의 코드 검증
FROM base AS test

# 테스트 의존성 추가 설치 (dev 포함)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Mypy 수동 설치 (lock 파일에 없는 경우 대비)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install mypy


COPY . .
# CI 워크플로우에서 여기서 린트와 유닛 테스트를 수행
CMD ["pytest"]



# 3. Prod Stage: 실제 운영 환경
FROM base AS prod

# 소스 코드 복사
COPY . .

# [환경 변수] 
# 깃허브 API 호출을 위한 Token이나 환경 설정
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# 헬스체크
# 분석 서버가 API 요청을 받을 준비가 되었는지 확인
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# --timeout-graceful-shutdown: 대량의 코드를 분석 중일 때 배포가 시작되어도 
# 작업을 끝까지 완료할 수 있도록 시간을 벌어준다
ENTRYPOINT ["uvicorn", "app.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "120"]