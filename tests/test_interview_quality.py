"""면접 품질 개선 3가지 기능 E2E 테스트

1. 질문 수 LLM 위임 — min/max 범위 계산, 프롬프트 변수 일관성
2. 꼬리질문 재시도 — _filter_follow_up, skip_count 격리
3. 인성면접 카테고리 확대 — BEHAVIORAL_DIMENSIONS, validate_node
"""

from typing import get_args
from unittest.mock import MagicMock, patch

import pytest

from app.domain.interview.schemas import BEHAVIORAL_DIMENSIONS, InterviewQuestion
from app.domain.interview.store import InterviewContextStore, QuestionContext

# ─────────────────────────────────────────────────
# 1. 질문 수 LLM 위임
# ─────────────────────────────────────────────────


def _calc_min_max(project_count: int) -> tuple[int, int]:
    """interview.py의 min/max 계산 로직 재현"""
    min_count = max(project_count, 3)
    max_count = max(min(project_count * 3, 10), min_count + 1)
    return min_count, max_count


class TestQuestionCountRange:
    """프로젝트 수에 따른 min/max 질문 수 범위 계산 검증"""

    @pytest.mark.parametrize(
        "project_count, expected_min, expected_max",
        [
            (1, 3, 4),
            (2, 3, 6),
            (3, 3, 9),
            (4, 4, 10),
            (5, 5, 10),
            (7, 7, 10),
        ],
    )
    def test_min_max_by_project_count(self, project_count, expected_min, expected_max):
        min_c, max_c = _calc_min_max(project_count)
        assert min_c == expected_min
        assert max_c == expected_max

    @pytest.mark.parametrize("project_count", range(1, 8))
    def test_max_always_greater_than_min(self, project_count):
        min_c, max_c = _calc_min_max(project_count)
        assert max_c > min_c

    def test_max_count_upper_bound(self):
        """project_count * 3은 10으로 클램핑, 단 min_count+1 보장"""
        _, max_c = _calc_min_max(5)
        assert max_c == 10

        min_c, max_c = _calc_min_max(7)
        assert min_c == 7
        assert max_c == 10


class TestPromptVariableConsistency:
    """프롬프트에 min/max 질문 수 변수가 존재하는지 검증"""

    @pytest.fixture(autouse=True)
    def _load_templates(self):
        from app.domain.interview.prompts.templates import (
            INTERVIEW_BEHAVIORAL_HUMAN,
            INTERVIEW_BEHAVIORAL_RETRY_HUMAN,
            INTERVIEW_BEHAVIORAL_SYSTEM,
            INTERVIEW_TECHNICAL_HUMAN,
            INTERVIEW_TECHNICAL_RETRY_HUMAN,
            INTERVIEW_TECHNICAL_SYSTEM,
        )

        self.templates = {
            "technical_system": INTERVIEW_TECHNICAL_SYSTEM,
            "technical_human": INTERVIEW_TECHNICAL_HUMAN,
            "technical_retry": INTERVIEW_TECHNICAL_RETRY_HUMAN,
            "behavioral_system": INTERVIEW_BEHAVIORAL_SYSTEM,
            "behavioral_human": INTERVIEW_BEHAVIORAL_HUMAN,
            "behavioral_retry": INTERVIEW_BEHAVIORAL_RETRY_HUMAN,
        }

    @pytest.mark.parametrize(
        "template_key",
        [
            "technical_system",
            "technical_human",
            "behavioral_system",
            "behavioral_human",
        ],
    )
    def test_has_min_max_placeholders(self, template_key):
        template = self.templates[template_key]
        assert "{{min_question_count}}" in template
        assert "{{max_question_count}}" in template

    def test_no_fixed_question_count_directive(self):
        """프롬프트에 고정 질문 수 지시가 없어야 함"""
        for key, template in self.templates.items():
            assert "exactly 2 questions" not in template.lower(), f"{key}에 고정 수 지시 발견"
            assert "정확히 2개" not in template, f"{key}에 고정 수 지시 발견"


# ─────────────────────────────────────────────────
# 2. 꼬리질문 재시도
# ─────────────────────────────────────────────────


class TestFollowUpRetrySystem:
    """_filter_follow_up의 스킵 감지 및 카운팅 검증"""

    @pytest.fixture
    def fresh_store(self):
        return InterviewContextStore()

    @pytest.fixture
    def question_ctx(self):
        return QuestionContext(
            question_id="q-001",
            question_text="FastAPI 비동기 처리 경험을 설명해주세요",
            intent="비동기 이해도",
            related_project="test-project",
        )

    def test_first_skip_preserves_follow_up(self, fresh_store, question_ctx):
        """첫 번째 스킵 답변 시 follow_up 유지"""
        body = MagicMock()
        body.answer = "모르겠습니다"
        body.ai_session_id = "session-1"
        body.question_id = "q-001"
        follow_up = "그럼 이런 경우는요?"

        with patch("app.api.v2.chat.interview_context_store", fresh_store):
            from app.api.v2.chat import _filter_follow_up

            result = _filter_follow_up(follow_up, body, question_ctx, turn_count=0)

        assert result is not None

    def test_second_skip_removes_follow_up(self, fresh_store, question_ctx):
        """두 번째 스킵 답변 시 follow_up이 None"""
        body = MagicMock()
        body.answer = "잘 모르겠어요"
        body.ai_session_id = "session-1"
        body.question_id = "q-001"
        follow_up = "그럼 이런 경우는요?"

        with patch("app.api.v2.chat.interview_context_store", fresh_store):
            from app.api.v2.chat import _filter_follow_up

            _filter_follow_up(follow_up, body, question_ctx, turn_count=0)
            result = _filter_follow_up(follow_up, body, question_ctx, turn_count=1)

        assert result is None

    @pytest.mark.parametrize(
        "pattern",
        ["모르겠", "잘 모르", "패스", "모릅니다", "생각이 안", "기억이 안"],
    )
    def test_all_skip_patterns_trigger_counter(self, fresh_store, question_ctx, pattern):
        """모든 SKIP_PATTERNS가 카운터를 증가시키는지 확인"""
        body = MagicMock()
        body.answer = f"음... {pattern}네요"
        body.ai_session_id = "session-1"
        body.question_id = "q-001"

        with patch("app.api.v2.chat.interview_context_store", fresh_store):
            from app.api.v2.chat import _filter_follow_up

            _filter_follow_up("follow-up", body, question_ctx, turn_count=0)

        assert fresh_store.get_skip_count("session-1", "q-001") == 1

    def test_skip_count_isolation_per_question(self, fresh_store, question_ctx):
        """다른 questionId의 skip_count는 독립적"""
        body1 = MagicMock()
        body1.answer = "모르겠습니다"
        body1.ai_session_id = "session-1"
        body1.question_id = "q-001"

        body2 = MagicMock()
        body2.answer = "패스할게요"
        body2.ai_session_id = "session-1"
        body2.question_id = "q-002"

        ctx2 = QuestionContext(
            question_id="q-002",
            question_text="Redis 캐시 전략",
            intent="캐싱 이해도",
            related_project=None,
        )

        with patch("app.api.v2.chat.interview_context_store", fresh_store):
            from app.api.v2.chat import _filter_follow_up

            _filter_follow_up("follow-up", body1, question_ctx, turn_count=0)
            _filter_follow_up("follow-up", body2, ctx2, turn_count=0)

        assert fresh_store.get_skip_count("session-1", "q-001") == 1
        assert fresh_store.get_skip_count("session-1", "q-002") == 1

    def test_normal_answer_does_not_increment(self, fresh_store, question_ctx):
        """정상 답변은 skip_count를 증가시키지 않음"""
        body = MagicMock()
        body.answer = "FastAPI에서 async/await를 사용해 비동기 엔드포인트를 구현했습니다"
        body.ai_session_id = "session-1"
        body.question_id = "q-001"

        with patch("app.api.v2.chat.interview_context_store", fresh_store):
            from app.api.v2.chat import _filter_follow_up

            _filter_follow_up("follow-up", body, question_ctx, turn_count=0)

        assert fresh_store.get_skip_count("session-1", "q-001") == 0


# ─────────────────────────────────────────────────
# 3. 인성면접 카테고리 확대
# ─────────────────────────────────────────────────


class TestBehavioralDimensionExpansion:
    """BEHAVIORAL_DIMENSIONS Literal 타입 확장 검증"""

    def test_includes_new_dimensions(self):
        dims = set(get_args(BEHAVIORAL_DIMENSIONS))
        assert "우선순위" in dims
        assert "사용자관점" in dims

    def test_total_count_is_nine(self):
        dims = get_args(BEHAVIORAL_DIMENSIONS)
        assert len(dims) == 9

    def test_includes_all_original_dimensions(self):
        dims = set(get_args(BEHAVIORAL_DIMENSIONS))
        expected = {"협업", "갈등해결", "성장마인드", "실패경험", "자기소개", "장단점", "기타"}
        assert expected.issubset(dims)

    def test_question_accepts_new_dimensions(self):
        q1 = InterviewQuestion(
            question="우선순위 질문",
            intent="우선순위 판단력",
            dimension="우선순위",
        )
        assert q1.dimension == "우선순위"

        q2 = InterviewQuestion(
            question="사용자 관점 질문",
            intent="사용자 중심 사고",
            dimension="사용자관점",
        )
        assert q2.dimension == "사용자관점"

    def test_rejects_invalid_dimension(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InterviewQuestion(
                question="질문",
                intent="의도",
                dimension="리더십",
            )


class TestBehavioralValidation:
    """워크플로우 validate_node의 dimension 검증 로직"""

    @pytest.fixture
    def _import_validate(self):
        from app.domain.interview.workflow import (
            REQUIRED_BEHAVIORAL_DIMENSIONS,
            _validate_behavioral,
        )

        self.validate_fn = _validate_behavioral
        self.required = REQUIRED_BEHAVIORAL_DIMENSIONS

    def test_required_dimensions_is_correct_set(self, _import_validate):
        assert self.required == {"협업", "갈등해결", "성장마인드", "실패경험"}

    def test_passes_with_all_required(self, _import_validate):
        questions = MagicMock()
        questions.questions = [
            InterviewQuestion(question="q1", intent="i1", dimension="협업"),
            InterviewQuestion(question="q2", intent="i2", dimension="갈등해결"),
            InterviewQuestion(question="q3", intent="i3", dimension="성장마인드"),
            InterviewQuestion(question="q4", intent="i4", dimension="실패경험"),
        ]
        state = {"interview_type": "behavioral", "questions": questions}
        result = self.validate_fn(state, questions)
        assert result["validation_passed"] is True

    def test_passes_with_required_plus_new(self, _import_validate):
        questions = MagicMock()
        questions.questions = [
            InterviewQuestion(question="q1", intent="i1", dimension="협업"),
            InterviewQuestion(question="q2", intent="i2", dimension="갈등해결"),
            InterviewQuestion(question="q3", intent="i3", dimension="성장마인드"),
            InterviewQuestion(question="q4", intent="i4", dimension="실패경험"),
            InterviewQuestion(question="q5", intent="i5", dimension="우선순위"),
            InterviewQuestion(question="q6", intent="i6", dimension="사용자관점"),
        ]
        state = {"interview_type": "behavioral", "questions": questions}
        result = self.validate_fn(state, questions)
        assert result["validation_passed"] is True

    def test_fails_with_missing_required(self, _import_validate):
        questions = MagicMock()
        questions.questions = [
            InterviewQuestion(question="q1", intent="i1", dimension="협업"),
            InterviewQuestion(question="q2", intent="i2", dimension="갈등해결"),
            InterviewQuestion(question="q3", intent="i3", dimension="우선순위"),
        ]
        state = {"interview_type": "behavioral", "questions": questions}
        result = self.validate_fn(state, questions)
        assert result["validation_passed"] is False
        assert "성장마인드" in result["missing_dimensions"]
        assert "실패경험" in result["missing_dimensions"]

    def test_fails_with_only_new_dimensions(self, _import_validate):
        questions = MagicMock()
        questions.questions = [
            InterviewQuestion(question="q1", intent="i1", dimension="우선순위"),
            InterviewQuestion(question="q2", intent="i2", dimension="사용자관점"),
        ]
        state = {"interview_type": "behavioral", "questions": questions}
        result = self.validate_fn(state, questions)
        assert result["validation_passed"] is False


class TestBehavioralPromptDimensions:
    """프롬프트에 6개 면접 dimension이 정의되어 있는지 검증"""

    @pytest.fixture(autouse=True)
    def _load_prompts(self):
        from app.domain.interview.prompts.templates import (
            INTERVIEW_BEHAVIORAL_HUMAN,
            INTERVIEW_BEHAVIORAL_SYSTEM,
        )

        self.system = INTERVIEW_BEHAVIORAL_SYSTEM
        self.human = INTERVIEW_BEHAVIORAL_HUMAN

    @pytest.mark.parametrize(
        "dimension",
        ["협업", "갈등해결", "성장마인드", "실패경험", "우선순위", "사용자관점"],
    )
    def test_system_prompt_lists_dimension(self, dimension):
        assert dimension in self.system

    @pytest.mark.parametrize(
        "dimension",
        ["협업", "갈등해결", "성장마인드", "실패경험", "우선순위", "사용자관점"],
    )
    def test_human_prompt_lists_dimension(self, dimension):
        assert dimension in self.human
