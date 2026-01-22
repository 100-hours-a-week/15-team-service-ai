import httpx
from langgraph.graph import END, StateGraph

from app.domain.resume.schemas import ResumeState
from app.domain.resume.service import create_resume


async def collect_data(state: ResumeState) -> ResumeState:
    """GitHub에서 커밋/diff 수집."""
    state["retry_count"] = state.get("retry_count", 0)
    return state


async def generate_resume_node(state: ResumeState) -> ResumeState:
    """이력서 초안 생성."""
    try:
        request = state["request"]
        resume_data = await create_resume(request)
        state["resume_data"] = resume_data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            state["error_code"] = "GITHUB_UNAUTHORIZED"
            state["error_message"] = "GitHub 토큰이 유효하지 않습니다."
        elif e.response.status_code == 404:
            state["error_code"] = "GITHUB_NOT_FOUND"
            state["error_message"] = "레포지토리를 찾을 수 없습니다."
        else:
            state["error_code"] = "GITHUB_ERROR"
            state["error_message"] = f"GitHub API 오류: {e.response.status_code}"
        state["evaluation"] = "error"
    except Exception as e:
        state["error_code"] = "INTERNAL_ERROR"
        state["error_message"] = str(e)
        state["evaluation"] = "error"
    return state


async def evaluate(state: ResumeState) -> ResumeState:
    """품질 평가."""
    resume_data = state.get("resume_data")

    if resume_data and resume_data.projects:
        state["evaluation"] = "pass"
    else:
        state["evaluation"] = "fail"
        state["retry_count"] = state.get("retry_count", 0) + 1

    return state


def should_retry(state: ResumeState) -> str:
    """재시도 여부 결정."""
    if state.get("evaluation") == "error":
        return "send_callback"
    if state.get("evaluation") == "pass":
        return "send_callback"
    if state.get("retry_count", 0) >= 1:
        return "send_callback"
    return "generate_resume"


async def send_callback(state: ResumeState) -> ResumeState:
    """결과 전송."""
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
                "code": state.get("error_code", "GENERATION_FAILED"),
                "message": state.get("error_message", "이력서 생성에 실패했습니다."),
            },
        }

    async with httpx.AsyncClient() as client:
        await client.post(request.callback_url, json=payload)

    return state


def create_workflow() -> StateGraph:
    """LangGraph 워크플로우 생성."""
    workflow = StateGraph(ResumeState)

    # 노드 추가
    workflow.add_node("collect_data", collect_data)
    workflow.add_node("generate_resume", generate_resume_node)
    workflow.add_node("evaluate", evaluate)
    workflow.add_node("send_callback", send_callback)

    # 엣지 연결
    workflow.set_entry_point("collect_data")
    workflow.add_edge("collect_data", "generate_resume")
    workflow.add_edge("generate_resume", "evaluate")
    workflow.add_conditional_edges("evaluate", should_retry)
    workflow.add_edge("send_callback", END)

    return workflow.compile()
