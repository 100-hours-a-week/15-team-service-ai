"""프롬프트 내용 검증 테스트

Planner-Executor 패턴 적용 후 프롬프트 구조 검증
- System: Executor 역할 정의, FORMAT RULES, OUTPUT FORMAT
- Human: generation_plans 기반 생성 지시
- Retry: 피드백 반영 + 동일 plans 참조
"""

import pytest

from app.domain.resume.prompts.generation import (
    RESUME_GENERATOR_HUMAN,
    RESUME_GENERATOR_RETRY_HUMAN,
    RESUME_GENERATOR_SYSTEM,
)
from app.domain.resume.validators import FORBIDDEN_ENDINGS


class TestResumeGeneratorSystem:
    """system 프롬프트 검증"""

    def test_executor_role_defined(self):
        """Executor 역할이 정의되었는지 확인"""
        assert "YOUR ROLE" in RESUME_GENERATOR_SYSTEM
        assert "executor" in RESUME_GENERATOR_SYSTEM.lower()

    def test_format_rules_section_exists(self):
        """FORMAT RULES 섹션이 존재하는지 확인"""
        assert "FORMAT RULES" in RESUME_GENERATOR_SYSTEM
        assert "tech_stack" in RESUME_GENERATOR_SYSTEM
        assert "description" in RESUME_GENERATOR_SYSTEM

    def test_output_format_section_exists(self):
        """OUTPUT FORMAT 섹션이 존재하는지 확인"""
        assert "OUTPUT FORMAT" in RESUME_GENERATOR_SYSTEM

    def test_plan_following_instruction_exists(self):
        """Plan을 따르라는 지시가 존재하는지 확인"""
        assert "plan" in RESUME_GENERATOR_SYSTEM.lower()
        assert "REMINDER" in RESUME_GENERATOR_SYSTEM

    def test_korean_output_instruction(self):
        """한국어 출력 지시가 포함되었는지 확인"""
        assert "Korean" in RESUME_GENERATOR_SYSTEM

    def test_placeholders_preserved(self):
        """{position}, {position_rules} 플레이스홀더가 보존되었는지 확인"""
        assert "{position}" in RESUME_GENERATOR_SYSTEM
        assert "{position_rules}" in RESUME_GENERATOR_SYSTEM


class TestResumeGeneratorHuman:
    """human 프롬프트 검증"""

    def test_generation_plans_placeholder(self):
        """{generation_plans} 플레이스홀더가 포함되었는지 확인"""
        assert "{generation_plans}" in RESUME_GENERATOR_HUMAN

    def test_project_count_placeholder(self):
        """{project_count} 플레이스홀더가 포함되었는지 확인"""
        assert "{project_count}" in RESUME_GENERATOR_HUMAN

    def test_steps_section_exists(self):
        """STEPS 섹션이 존재하는지 확인"""
        assert "STEPS" in RESUME_GENERATOR_HUMAN
        assert "Step 1" in RESUME_GENERATOR_HUMAN

    def test_reminder_exists(self):
        """REMINDER가 존재하는지 확인"""
        assert "REMINDER" in RESUME_GENERATOR_HUMAN


class TestResumeGeneratorRetryHuman:
    """retry 프롬프트 검증"""

    def test_feedback_placeholder(self):
        """{feedback} 플레이스홀더가 보존되었는지 확인"""
        assert "{feedback}" in RESUME_GENERATOR_RETRY_HUMAN

    def test_previous_resume_placeholder(self):
        """{previous_resume_json} 플레이스홀더가 보존되었는지 확인"""
        assert "{previous_resume_json}" in RESUME_GENERATOR_RETRY_HUMAN

    def test_generation_plans_placeholder(self):
        """{generation_plans} 플레이스홀더가 포함되었는지 확인"""
        assert "{generation_plans}" in RESUME_GENERATOR_RETRY_HUMAN

    def test_retry_specific_placeholders_preserved(self):
        """{feedback}, {previous_resume_json} 플레이스홀더가 보존되었는지 확인"""
        assert "{feedback}" in RESUME_GENERATOR_RETRY_HUMAN
        assert "{previous_resume_json}" in RESUME_GENERATOR_RETRY_HUMAN

    def test_reminder_exists(self):
        """REMINDER가 존재하는지 확인"""
        assert "REMINDER" in RESUME_GENERATOR_RETRY_HUMAN


class TestPromptConsistency:
    """프롬프트 간 일관성 검증"""

    def test_both_human_prompts_have_generation_plans(self):
        """human과 retry 모두 generation_plans를 참조하는지 확인"""
        assert "{generation_plans}" in RESUME_GENERATOR_HUMAN
        assert "{generation_plans}" in RESUME_GENERATOR_RETRY_HUMAN

    def test_both_human_prompts_have_project_count(self):
        """human과 retry 모두 project_count를 참조하는지 확인"""
        assert "{project_count}" in RESUME_GENERATOR_HUMAN
        assert "{project_count}" in RESUME_GENERATOR_RETRY_HUMAN

    def test_system_and_human_plan_consistency(self):
        """system의 plan 지시와 human의 plans 참조가 일관되는지 확인"""
        has_plan_in_system = "plan" in RESUME_GENERATOR_SYSTEM.lower()
        has_plans_in_human = "{generation_plans}" in RESUME_GENERATOR_HUMAN
        assert has_plan_in_system and has_plans_in_human, (
            "system에 plan 지시가 있으면 human에도 generation_plans가 있어야 함"
        )

    @pytest.mark.parametrize("ending", FORBIDDEN_ENDINGS)
    def test_forbidden_endings_in_system_prompt(self, ending):
        """validators.py의 FORBIDDEN_ENDINGS가 system 프롬프트에 존재하는지 확인"""
        assert f"~{ending}" in RESUME_GENERATOR_SYSTEM, (
            f"금지 어미 '~{ending}'이 system 프롬프트의 FORBIDDEN endings에 누락됨"
        )
