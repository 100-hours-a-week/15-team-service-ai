"""이력서 형식 규칙 코드 검증

LLM 평가 전에 실행하여 형식적 문제를 사전 검출
12B 모델의 규칙 준수 부담을 줄이기 위한 코드 기반 검증
"""

from app.core.logging import get_logger
from app.domain.resume.schemas import ProjectInfo, ResumeData

logger = get_logger(__name__)

ALLOWED_ENDINGS = [
    "구현",
    "구축",
    "설계",
    "처리",
    "연동",
    "도입",
    "최적화",
    "개선",
    "적용",
    "개발",
    "분석",
    "관리",
    "배포",
    "자동화",
    "통합",
    "활용",
    "해결",
    "수행",
    "제공",
    "변경",
]

FORBIDDEN_ENDINGS = ["했습니다", "하였습니다", "입니다", "했음", "함"]

TRIVIAL_CONTENT = ["CSS 수정", "오타 수정", "README 수정", "패키지 설치"]

EXCLUDED_TECH_ITEMS = {
    "Pydantic",
    "Lombok",
    "uvicorn",
    "gunicorn",
    "nodemon",
    "dotenv",
    "cors",
    "ESLint",
    "Prettier",
    "Jest",
    "pytest",
    "Swagger",
    "JUnit",
    "OpenAI",
    "Whisper",
    "GPT",
    "Claude",
    "Gemini",
    "Anthropic",
    "ChatGPT",
    "FFmpeg",
    "yt-dlp",
    "Pillow",
    "ImageMagick",
    "npm",
    "pip",
    "yarn",
    "uv",
    "Git",
    "GitHub",
    "GitLab",
}

_EXCLUDED_LOWER = {item.lower() for item in EXCLUDED_TECH_ITEMS}


def _validate_tech_stack(project: ProjectInfo) -> list[dict]:
    """tech_stack 개수 및 금지 항목 검증"""
    violations = []

    tech_count = len(project.tech_stack)
    if tech_count < 3 or tech_count > 8:
        violations.append(
            {
                "rule": "tech_stack_count",
                "project": project.name,
                "detail": f"tech_stack {tech_count}개, 3-8개 필요",
            }
        )

    forbidden_found = [tech for tech in project.tech_stack if tech.lower() in _EXCLUDED_LOWER]
    if forbidden_found:
        violations.append(
            {
                "rule": "forbidden_tech",
                "project": project.name,
                "detail": f"금지 항목: {', '.join(forbidden_found)}",
            }
        )

    return violations


def _validate_bullets(project: ProjectInfo) -> list[dict]:
    """description 불릿 형식, 어미, 내용 검증"""
    violations = []
    bullets = [line for line in project.description.split("\n") if line.strip()]

    bullet_count = len(bullets)
    if bullet_count < 5 or bullet_count > 8:
        violations.append(
            {
                "rule": "bullet_count",
                "project": project.name,
                "detail": f"불릿 {bullet_count}개, 5-8개 필요",
            }
        )

    for i, bullet in enumerate(bullets):
        if not bullet.strip().startswith("- "):
            violations.append(
                {
                    "rule": "bullet_format",
                    "project": project.name,
                    "detail": f"불릿 {i + 1}이 '- '로 시작하지 않음",
                }
            )
            break

    for bullet in bullets:
        text = bullet.strip().rstrip(".")
        for ending in FORBIDDEN_ENDINGS:
            if text.endswith(ending):
                violations.append(
                    {
                        "rule": "forbidden_ending",
                        "project": project.name,
                        "detail": f"금지 어미 '~{ending}' 사용: {bullet.strip()[:50]}",
                    }
                )
                break

    for bullet in bullets:
        for trivial in TRIVIAL_CONTENT:
            if trivial in bullet:
                violations.append(
                    {
                        "rule": "trivial_content",
                        "project": project.name,
                        "detail": f"사소한 내용: {trivial}",
                    }
                )
                break

    return violations


def validate_resume_format(resume_data: ResumeData, position: str) -> list[dict]:
    """이력서 형식 규칙 검증, 위반 사항 목록 반환

    반환 형식: [{"rule": "...", "project": "...", "detail": "..."}, ...]
    빈 리스트면 모든 형식 규칙 통과
    """
    violations = []

    for project in resume_data.projects:
        violations.extend(_validate_tech_stack(project))
        violations.extend(_validate_bullets(project))

    if violations:
        logger.info("형식 검증 위반 발견", count=len(violations))
    else:
        logger.debug("형식 검증 통과")

    return violations


def format_violations_as_feedback(violations: list[dict]) -> str:
    """위반 사항을 LLM 피드백 문자열로 변환"""
    if not violations:
        return ""

    lines = []
    for v in violations:
        lines.append(f"- [{v['project']}] {v['rule']}: {v['detail']}")

    return "\n".join(lines)
