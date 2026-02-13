from app.core.config import settings
from app.domain.resume.prompts import get_position_example, get_position_rules
from app.domain.resume.prompts.positions import get_position_config
from app.domain.resume.schemas import ProjectInfoDict, RepoContext
from app.infra.langfuse.prompt_manager import get_prompt


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
            lines.append("- 핵심 의존성 [tech_stack에 반드시 포함]:")
            for dep in project["dependencies"][: settings.prompt_dependencies_max_count]:
                lines.append(f"  * {dep}")

        if project.get("messages"):
            lines.append("- 주요 작업:")
            for msg in project["messages"][: settings.prompt_messages_max_count]:
                lines.append(f"  - {msg}")

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
            lines.append(f'- README:\n"""\n{readme_content}\n"""')

    return "\n".join(lines)


def build_generator_system_prompt(position: str) -> str:
    """포지션별 규칙을 주입한 시스템 프롬프트 생성"""
    position_rules = get_position_rules(position)
    position_example = get_position_example(position)

    return get_prompt(
        "resume-generator-system",
        position=position,
        position_rules=position_rules,
        position_example=position_example,
    )


def build_evaluator_system_prompt(position: str) -> str:
    """포지션별 규칙을 주입한 평가 시스템 프롬프트 생성"""
    position_rules = _get_evaluator_position_rules(position)

    return get_prompt(
        "resume-evaluator-system",
        position=position,
        position_rules=position_rules,
    )


def _get_evaluator_position_rules(position: str) -> str:
    """평가용 포지션별 제외 규칙 반환"""
    config = get_position_config(position)
    name_ko = config["name_ko"]

    if not config["tech_exclude"]:
        return f"- {name_ko}: 모든 기술 허용"

    exclude_list = ", ".join(config["tech_exclude"])
    return f"- {name_ko} FAIL if has: {exclude_list}"
