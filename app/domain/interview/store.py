import time
from dataclasses import dataclass


@dataclass
class QuestionContext:
    """질문별 백엔드 전용 메타데이터"""

    question_id: str
    question_text: str
    intent: str
    related_project: str | None


class InterviewContextStore:
    """면접 질문 컨텍스트 인메모리 저장소"""

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[int, dict[str, QuestionContext]] = {}
        self._timestamps: dict[int, float] = {}
        self._ttl = ttl_seconds

    def save(self, resume_id: int, contexts: list[QuestionContext]) -> None:
        """질문 컨텍스트 저장"""
        self._cleanup()
        self._store[resume_id] = {ctx.question_id: ctx for ctx in contexts}
        self._timestamps[resume_id] = time.time()

    def get(self, resume_id: int) -> dict[str, QuestionContext] | None:
        """resume_id로 질문 컨텍스트 조회"""
        self._cleanup()
        return self._store.get(resume_id)

    def _cleanup(self) -> None:
        """만료된 항목 제거"""
        now = time.time()
        expired = [rid for rid, ts in self._timestamps.items() if now - ts > self._ttl]
        for rid in expired:
            self._store.pop(rid, None)
            self._timestamps.pop(rid, None)


interview_context_store = InterviewContextStore()
