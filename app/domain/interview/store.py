import time
from dataclasses import dataclass


@dataclass
class QuestionContext:
    """질문별 백엔드 전용 메타데이터"""

    question_id: str
    question_text: str
    intent: str
    related_project: str | None
    dimension: str | None = None
    category: str | None = None


@dataclass
class SessionMeta:
    """면접 세션 메타데이터 - 피드백 생성 시 필요"""

    resume_json: str
    position: str
    interview_type: str


CLEANUP_INTERVAL = 60  # TTL의 일부 주기로 만료 항목 정리


class InterviewContextStore:
    """면접 질문 컨텍스트 인메모리 저장소 - aiSessionId 기반"""

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[str, dict[str, QuestionContext]] = {}
        self._meta_store: dict[str, SessionMeta] = {}
        self._skip_counts: dict[str, int] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl = ttl_seconds
        self._last_cleanup: float = 0.0

    def save(self, session_id: str, contexts: list[QuestionContext]) -> None:
        """질문 컨텍스트 저장"""
        self._cleanup()
        self._store[session_id] = {ctx.question_id: ctx for ctx in contexts}
        self._timestamps[session_id] = time.time()

    def save_single(self, session_id: str, context: QuestionContext) -> None:
        """개별 질문 컨텍스트 추가 저장 - 꼬리질문용"""
        self._cleanup()
        if session_id not in self._store:
            self._store[session_id] = {}
        self._store[session_id][context.question_id] = context
        self._timestamps[session_id] = time.time()

    def get(self, session_id: str) -> dict[str, QuestionContext] | None:
        """session_id로 질문 컨텍스트 조회"""
        self._cleanup()
        ts = self._timestamps.get(session_id)
        if ts is not None and time.time() - ts > self._ttl:
            return None
        result = self._store.get(session_id)
        if result is not None:
            self._timestamps[session_id] = time.time()
        return result

    def save_session_meta(self, session_id: str, meta: SessionMeta) -> None:
        """면접 세션 메타데이터 저장"""
        self._meta_store[session_id] = meta
        if session_id not in self._timestamps:
            self._timestamps[session_id] = time.time()

    def get_session_meta(self, session_id: str) -> SessionMeta | None:
        """면접 세션 메타데이터 조회"""
        self._cleanup()
        ts = self._timestamps.get(session_id)
        if ts is not None and time.time() - ts > self._ttl:
            return None
        result = self._meta_store.get(session_id)
        if result is not None:
            self._timestamps[session_id] = time.time()
        return result

    def increment_skip_count(self, session_id: str, question_id: str) -> int:
        """질문별 성의없는 답변 횟수 증가 후 현재값 반환"""
        key = f"{session_id}:{question_id}"
        self._skip_counts[key] = self._skip_counts.get(key, 0) + 1
        if session_id in self._timestamps:
            self._timestamps[session_id] = time.time()
        return self._skip_counts[key]

    def get_skip_count(self, session_id: str, question_id: str) -> int:
        """질문별 성의없는 답변 횟수 조회"""
        key = f"{session_id}:{question_id}"
        return self._skip_counts.get(key, 0)

    def _cleanup(self) -> None:
        """만료된 항목 제거 - 60초 간격으로만 실행"""
        now = time.time()
        if now - self._last_cleanup < CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        expired = [sid for sid, ts in self._timestamps.items() if now - ts > self._ttl]
        for sid in expired:
            self._store.pop(sid, None)
            self._meta_store.pop(sid, None)
            self._timestamps.pop(sid, None)
            skip_keys = [k for k in self._skip_counts if k.startswith(f"{sid}:")]
            for k in skip_keys:
                self._skip_counts.pop(k, None)


interview_context_store = InterviewContextStore()
