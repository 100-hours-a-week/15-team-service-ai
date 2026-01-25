import httpx
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.resume.schemas import ResumeState
from app.domain.resume.service import analyze_experiences, collect_diffs
from app.infra.llm.client import evaluate_resume, generate_resume

logger = get_logger(__name__)

MAX_RETRY = 1


async def collect_data(state: ResumeState) -> ResumeState:
    """GitHub에서 커밋/diff 수집."""
    logger.info("diff 수집 시작 job_id=%s", state.get("job_id"))
    try:
        diffs = await collect_diffs(state["request"])
        state["collected_data"] = diffs
        state["retry_count"] = 0
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            state["error_code"] = ErrorCode.GITHUB_UNAUTHORIZED
            state["error_message"] = "GitHub 토큰이 유효하지 않습니다."
        elif e.response.status_code == 404:
            state["error_code"] = ErrorCode.GITHUB_NOT_FOUND
            state["error_message"] = "레포지토리를 찾을 수 없습니다."
        else:
            state["error_code"] = ErrorCode.GITHUB_ERROR
            state["error_message"] = f"GitHub API 오류: {e.response.status_code}"
        logger.error(
            "GitHub API 에러 job_id=%s code=%s",
            state.get("job_id"),
            state["error_code"],
        )
        state["evaluation"] = "error"
    except Exception as e:
        state["error_code"] = ErrorCode.INTERNAL_ERROR
        state["error_message"] = str(e)
        logger.error("diff 수집 에러 job_id=%s error=%s", state.get("job_id"), str(e))
        state["evaluation"] = "error"
    return state


async def analyze_diffs_node(state: ResumeState) -> ResumeState:
    """수집된 diff들을 LLM으로 분석하여 경험 추출."""
    logger.info("경험 분석 시작 job_id=%s", state.get("job_id"))
    try:
        experiences = await analyze_experiences(state["collected_data"])
        state["experiences"] = experiences
    except Exception as e:
        state["error_code"] = ErrorCode.LLM_ERROR
        state["error_message"] = f"diff 분석 실패: {e}"
        logger.error("경험 분석 에러 job_id=%s error=%s", state.get("job_id"), str(e))
        state["evaluation"] = "error"
    return state


async def compose_resume_node(state: ResumeState) -> ResumeState:
    """경험 기반 이력서 생성 (생성 에이전트)."""
    logger.info(
        "이력서 생성 시작 job_id=%s retry=%d",
        state.get("job_id"),
        state.get("retry_count", 0),
    )
    try:
        request = state["request"]
        resume_data = await generate_resume(
            experiences=state["experiences"],
            position=request.position,
            repo_urls=request.repo_urls,
            feedback=state.get("evaluation_feedback"),
        )
        state["resume_data"] = resume_data
    except Exception as e:
        state["error_code"] = ErrorCode.LLM_ERROR
        state["error_message"] = f"이력서 생성 실패: {e}"
        logger.error("이력서 생성 에러 job_id=%s error=%s", state.get("job_id"), str(e))
        state["evaluation"] = "error"
    return state


async def evaluate_node(state: ResumeState) -> ResumeState:
    """이력서 품질 평가 (평가 에이전트)."""
    logger.info("이력서 평가 시작 job_id=%s", state.get("job_id"))
    try:
        result = await evaluate_resume(state["resume_data"], state["request"].position)
        state["evaluation"] = result.result.lower()
        state["evaluation_feedback"] = result.feedback
        state["retry_count"] = state.get("retry_count", 0) + 1
    except Exception as e:
        state["error_code"] = ErrorCode.LLM_ERROR
        state["error_message"] = f"이력서 평가 실패: {e}"
        logger.error("이력서 평가 에러 job_id=%s error=%s", state.get("job_id"), str(e))
        state["evaluation"] = "error"

    logger.info(
        "평가 결과 job_id=%s result=%s retry=%d",
        state.get("job_id"),
        state.get("evaluation"),
        state.get("retry_count", 0),
    )
    return state


def should_retry(state: ResumeState) -> str:
    """재시도 여부 결정."""
    if state.get("evaluation") == "error":
        return "send_callback"
    if state.get("evaluation") == "pass":
        return "send_callback"
    if state.get("retry_count", 0) > MAX_RETRY:
        return "send_callback"
    return "compose_resume"


def should_continue_after_collect(state: ResumeState) -> str:
    """collect_data 이후 진행 여부."""
    if state.get("evaluation") == "error":
        return "send_callback"
    return "analyze_diffs"


def should_continue_after_analyze(state: ResumeState) -> str:
    """analyze_diffs 이후 진행 여부."""
    if state.get("evaluation") == "error":
        return "send_callback"
    return "compose_resume"


def should_continue_after_compose(state: ResumeState) -> str:
    """compose_resume 이후 진행 여부."""
    if state.get("evaluation") == "error":
        return "send_callback"
    return "evaluate"


async def send_callback(state: ResumeState) -> ResumeState:
    """결과를 Spring 백엔드로 전송."""
    request = state["request"]
    job_id = state["job_id"]
    resume_data = state.get("resume_data")

    if state.get("evaluation") == "pass" and resume_data:
        payload = {
            "jobId": job_id,
            "status": "success",
            "resume": {
                "techStack": resume_data.tech_stack,
                "projects": [
                    {
                        "name": p.name,
                        "repoUrl": p.repo_url,
                        "description": p.description,
                    }
                    for p in resume_data.projects
                ],
            },
        }
    else:
        payload = {
            "jobId": job_id,
            "status": "failed",
            "error": {
                "code": state.get("error_code", ErrorCode.GENERATION_FAILED),
                "message": state.get("error_message", "이력서 생성에 실패했습니다."),
            },
        }

    async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
        await client.post(request.callback_url, json=payload)

    logger.info("콜백 전송 완료 job_id=%s status=%s", job_id, payload["status"])
    return state


def create_workflow() -> StateGraph:
    """LangGraph 워크플로우 생성."""
    workflow = StateGraph(ResumeState)

    workflow.add_node("collect_data", collect_data)
    workflow.add_node("analyze_diffs", analyze_diffs_node)
    workflow.add_node("compose_resume", compose_resume_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("send_callback", send_callback)

    workflow.set_entry_point("collect_data")
    workflow.add_conditional_edges("collect_data", should_continue_after_collect)
    workflow.add_conditional_edges("analyze_diffs", should_continue_after_analyze)
    workflow.add_conditional_edges("compose_resume", should_continue_after_compose)
    workflow.add_conditional_edges("evaluate", should_retry)
    workflow.add_edge("send_callback", END)

    return workflow.compile()
