"""기술-포지션 매핑 상수

레포의 의존성을 분석하여 포지션별 기술 필터링을 수행하기 위한 기술 목록
"""

BACKEND_TECHS = frozenset(
    [
        "python",
        "java",
        "kotlin",
        "go",
        "rust",
        "node.js",
        "fastapi",
        "django",
        "flask",
        "spring boot",
        "spring",
        "express",
        "nestjs",
        "jpa",
        "sqlalchemy",
        "prisma",
        "typeorm",
        "hibernate",
        "querydsl",
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "kafka",
        "rabbitmq",
        "celery",
        "graphql",
        "grpc",
    ]
)

FRONTEND_TECHS = frozenset(
    [
        "javascript",
        "typescript",
        "react",
        "vue",
        "angular",
        "next.js",
        "nuxt",
        "svelte",
        "redux",
        "zustand",
        "recoil",
        "mobx",
        "tailwind css",
        "styled-components",
        "emotion",
        "mui",
        "chakra ui",
        "webpack",
        "vite",
    ]
)

MOBILE_TECHS = frozenset(
    [
        "swift",
        "kotlin",
        "dart",
        "swiftui",
        "jetpack compose",
        "react native",
        "flutter",
    ]
)

DATA_TECHS = frozenset(
    [
        "python",
        "sql",
        "r",
        "spark",
        "pandas",
        "numpy",
        "hadoop",
        "airflow",
        "tableau",
        "powerbi",
        "jupyter",
        "snowflake",
        "bigquery",
        "redshift",
        "dbt",
    ]
)

DEVOPS_TECHS = frozenset(
    [
        "docker",
        "kubernetes",
        "terraform",
        "ansible",
        "aws",
        "gcp",
        "azure",
        "jenkins",
        "github actions",
        "gitlab ci",
        "argocd",
        "prometheus",
        "grafana",
        "nginx",
        "helm",
    ]
)

SECURITY_TECHS = frozenset(
    [
        "python",
        "java",
        "c",
        "burp suite",
        "nmap",
        "wireshark",
        "metasploit",
        "splunk",
        "siem",
        "hashicorp vault",
        "keycloak",
    ]
)

AI_TECHS = frozenset(
    [
        "python",
        "tensorflow",
        "pytorch",
        "keras",
        "scikit-learn",
        "pandas",
        "numpy",
        "huggingface",
        "transformers",
        "langchain",
        "opencv",
        "cuda",
        "mlflow",
        "openai",
        "whisper",
        "gpt",
        "claude",
        "gemini",
    ]
)

POSITION_TECH_MAP: dict[str, frozenset[str]] = {
    "백엔드": BACKEND_TECHS,
    "backend": BACKEND_TECHS,
    "프론트엔드": FRONTEND_TECHS,
    "frontend": FRONTEND_TECHS,
    "풀스택": FRONTEND_TECHS | BACKEND_TECHS,
    "fullstack": FRONTEND_TECHS | BACKEND_TECHS,
    "모바일": MOBILE_TECHS,
    "mobile": MOBILE_TECHS,
    "앱": MOBILE_TECHS,
    "데이터": DATA_TECHS,
    "data": DATA_TECHS,
    "devops": DEVOPS_TECHS,
    "데브옵스": DEVOPS_TECHS,
    "보안": SECURITY_TECHS,
    "security": SECURITY_TECHS,
    "ai": AI_TECHS,
    "인공지능": AI_TECHS,
    "머신러닝": AI_TECHS,
    "ml": AI_TECHS,
}

EXCLUDED_TECHS = frozenset(
    [
        "lombok",
        "pydantic",
        "dotenv",
        "python-dotenv",
        "uvicorn",
        "gunicorn",
        "jackson",
        "gson",
        "mapstruct",
        "validation",
        "swagger",
        "springdoc",
        "postman",
        "notion",
        "ffmpeg",
        "imagemagick",
        "yt-dlp",
        "logback",
        "slf4j",
        "log4j",
        "commons-lang",
        "commons-io",
        "guava",
        "jjwt",
        "java-jwt",
        "aws sdk",
    ]
)
