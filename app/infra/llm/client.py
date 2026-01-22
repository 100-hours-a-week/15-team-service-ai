import json

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.domain.resume.schemas import ProjectInfo, ResumeData


def get_llm():
    """OpenAI LLM 클라이언트 반환."""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout,
    )


async def analyze_diff(diff_content: str, repo_name: str) -> dict:
    """diff에서 경험 추출.

    Args:
        diff_content: 커밋 diff 내용
        repo_name: 레포지토리 이름

    Returns:
        추출된 경험 정보 (기술스택, 구현 내용 등)
    """
    prompt = f"""다음은 GitHub 커밋의 diff 내용입니다. 이 diff를 분석하여 개발자의 경험을 추출해주세요.

레포지토리: {repo_name}

diff 내용:
{diff_content}

다음 형식으로 JSON만 응답해주세요 (다른 텍스트 없이):
{{
    "tech_stack": ["사용된 기술/라이브러리 목록"],
    "description": "이 커밋에서 구현한 내용을 이력서에 쓸 수 있는 문장으로 작성"
}}
"""

    llm = get_llm()
    response = await llm.ainvoke([HumanMessage(content=prompt)])

    return json.loads(response.content)


async def generate_resume(
    experiences: list[dict], position: str, repo_urls: list[str]
) -> ResumeData:
    """경험 기반 이력서 생성.

    Args:
        experiences: analyze_diff로 추출된 경험 목록
        position: 희망 포지션
        repo_urls: 레포지토리 URL 목록

    Returns:
        생성된 이력서 데이터
    """
    experiences_text = "\n".join(
        f"- 기술: {exp.get('tech_stack', [])}, 내용: {exp.get('description', '')}"
        for exp in experiences
    )

    prompt = f"""다음은 개발자의 GitHub 커밋에서 추출한 경험 목록입니다.
이 정보를 바탕으로 {position} 포지션에 맞는 이력서를 작성해주세요.

경험 목록:
{experiences_text}

레포지토리 URL:
{chr(10).join(repo_urls)}

다음 형식으로 JSON만 응답해주세요 (다른 텍스트 없이):
{{
    "tech_stack": ["핵심 기술 스택 목록"],
    "projects": [
        {{
            "name": "프로젝트명",
            "repo_url": "레포지토리 URL",
            "description": "프로젝트 설명 (이력서에 적합한 문장)"
        }}
    ]
}}
"""

    llm = get_llm()
    response = await llm.ainvoke([HumanMessage(content=prompt)])

    data = json.loads(response.content)

    return ResumeData(
        tech_stack=data.get("tech_stack", []),
        projects=[
            ProjectInfo(
                name=p.get("name", ""),
                repo_url=p.get("repo_url", ""),
                description=p.get("description", ""),
            )
            for p in data.get("projects", [])
        ],
    )
