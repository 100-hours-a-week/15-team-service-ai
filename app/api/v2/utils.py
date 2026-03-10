import json
from typing import Protocol


class ProjectProtocol(Protocol):
    """프로젝트 필드를 가진 객체"""

    name: str
    repo_url: str
    tech_stack: list[str]
    description: str


class ContentProtocol(Protocol):
    """projects 리스트를 가진 객체"""

    projects: list[ProjectProtocol]


def build_resume_json(content: ContentProtocol) -> str:
    """이력서 내용을 LLM 입력용 JSON 문자열로 변환"""
    projects = []
    for p in content.projects:
        projects.append(
            {
                "name": p.name,
                "repo_url": p.repo_url,
                "tech_stack": p.tech_stack,
                "description": p.description,
            }
        )
    return json.dumps({"projects": projects}, ensure_ascii=False, indent=2)
