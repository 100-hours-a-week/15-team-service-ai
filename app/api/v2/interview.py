import uuid

from fastapi import APIRouter, Request

from app.api.v2.schemas.interview import (
    InterviewErrorResponse,
    InterviewQuestionResponse,
    InterviewRequest,
    InterviewResponse,
)
from app.api.v2.utils import build_resume_json
from app.core.exceptions import ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.interview.agent import run_interview_agent
from app.domain.interview.schemas import InterviewQuestion
from app.domain.interview.store import QuestionContext, SessionMeta, interview_context_store

router = APIRouter(prefix="/interview", tags=["v2"])
logger = get_logger(__name__)

BEHAVIORAL_FIXED_QUESTIONS = [
    InterviewQuestion(
        question="1분 자기소개 부탁드립니다",
        intent="지원자의 배경, 경험, 지원 동기를 간결하게 파악",
        dimension="자기소개",
    ),
    InterviewQuestion(
        question="본인의 장단점을 말씀해주세요",
        intent="자기인식 수준과 성장 의지 파악",
        dimension="장단점",
    ),
]

_BEHAVIORAL_FIXED_COUNT = len(BEHAVIORAL_FIXED_QUESTIONS)


@router.post("", response_model=InterviewResponse, summary="면접 질문 생성")
@limiter.limit("10/minute")
async def generate_interview(
    request: Request,
    body: InterviewRequest,
) -> InterviewResponse:
    """면접 질문 생성 요청

    분당 10회 요청 제한이 적용됩니다
    """
    session_id = str(uuid.uuid4())

    is_behavioral = body.type == "behavioral"
    base_count = max(min(len(body.content.projects) * 2, 10), 4)
    llm_question_count = base_count

    logger.info(
        "면접 질문 생성 요청",
        resume_id=body.resume_id,
        interview_type=body.type,
        position=body.position,
        question_count=llm_question_count,
        session_id=session_id,
    )

    resume_json = build_resume_json(body.content)

    questions, error_message = await run_interview_agent(
        resume_json=resume_json,
        interview_type=body.type,
        position=body.position,
        question_count=llm_question_count,
        session_id=session_id,
    )

    if error_message or not questions:
        logger.error("면접 질문 생성 실패", error=error_message)
        return InterviewResponse(
            status="failed",
            error=InterviewErrorResponse(
                code=ErrorCode.INTERVIEW_GENERATE_ERROR,
                message=error_message or "면접 질문 생성에 실패했습니다",
            ),
        )

    all_questions = (
        BEHAVIORAL_FIXED_QUESTIONS + questions.questions if is_behavioral else questions.questions
    )

    question_responses = []
    question_contexts = []

    for idx, q in enumerate(all_questions, start=1):
        qid = f"q-{idx:03d}"
        question_responses.append(InterviewQuestionResponse(question_id=qid, text=q.question))
        question_contexts.append(
            QuestionContext(
                question_id=qid,
                question_text=q.question,
                intent=q.intent,
                related_project=q.related_project,
            )
        )

    interview_context_store.save(session_id, question_contexts)
    interview_context_store.save_session_meta(
        session_id,
        SessionMeta(
            resume_json=resume_json,
            position=body.position,
            interview_type=body.type,
        ),
    )

    logger.info("면접 질문 생성 성공", questions=len(all_questions))
    return InterviewResponse(
        status="success",
        ai_session_id=session_id,
        questions=question_responses,
    )
