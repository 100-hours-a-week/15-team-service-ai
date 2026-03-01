from app.core.config import settings
from app.domain.resume.prompts import get_position_rules
from app.domain.resume.schemas import ProjectInfoDict, RepoContext


def format_project_info(project_info: list[ProjectInfoDict]) -> str:
    """프로젝트 정보를 프롬프트용 텍스트로 포맷"""
    lines = []
    total_projects = len(project_info)

    for idx, project in enumerate(project_info, start=1):
        if idx > 1:
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append(f"### 프로젝트 {idx}/{total_projects}: {project['repo_name']}")
        lines.append(f"- 레포지토리: {project['repo_url']}")

        if project.get("file_tree"):
            tree_summary = ", ".join(project["file_tree"][: settings.prompt_file_tree_max_count])
            lines.append(f"- 파일 구조: {tree_summary}")

        if project.get("dependencies"):
            lines.append("<dependencies_for_techstack>")
            for dep in project["dependencies"][: settings.prompt_dependencies_max_count]:
                lines.append(f"  * {dep}")
            lines.append("</dependencies_for_techstack>")

        if project.get("messages"):
            lines.append("<user_commits>")
            lines.append("아래 커밋만이 description 작성의 유일한 근거입니다")
            for msg in project["messages"][: settings.prompt_messages_max_count]:
                lines.append(f"  - {msg}")
            lines.append("</user_commits>")

    return "\n".join(lines)


def format_repo_contexts(repo_contexts: dict[str, RepoContext]) -> str:
    """레포지토리 컨텍스트를 프롬프트용 텍스트로 포맷"""
    if not repo_contexts:
        return "없음"

    lines = []
    total = len(repo_contexts)

    for idx, (name, ctx) in enumerate(repo_contexts.items(), start=1):
        if idx > 1:
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append(f"### 레포지토리 {idx}/{total}: {name}")
        lines.append(f"- 언어: {', '.join(ctx.languages.keys()) or '없음'}")
        lines.append(f"- 설명: {ctx.description or '없음'}")
        lines.append(f"- 토픽: {', '.join(ctx.topics) if ctx.topics else '없음'}")

        if ctx.readme_summary:
            readme_content = ctx.readme_summary[: settings.readme_max_length_prompt]
            lines.append(
                f"<readme_reference_only>\n"
                f"이 README는 프로젝트 전체 설명이며 사용자 개인의 기여가 아닙니다\n"
                f"tech_stack 참고용으로만 사용하고 description 작성에 사용하지 마세요\n"
                f"{readme_content}\n"
                f"</readme_reference_only>"
            )

    return "\n".join(lines)


def build_generator_system_prompt(position: str) -> str:
    """포지션별 규칙을 주입한 시스템 프롬프트 생성"""
    from app.domain.resume.prompts.generation import RESUME_GENERATOR_SYSTEM

    position_rules = get_position_rules(position)
    return RESUME_GENERATOR_SYSTEM.format(
        position=position,
        position_rules=position_rules,
    )


def build_evaluator_system_prompt(position: str) -> str:
    """포지션별 규칙을 주입한 Evaluator 시스템 프롬프트 생성 - 로컬 상수 직접 사용"""
    from app.domain.resume.prompts.evaluation import RESUME_EVALUATOR_SYSTEM

    position_rules = get_position_rules(position)
    return RESUME_EVALUATOR_SYSTEM.format(
        position=position,
        position_rules=position_rules,
    )
