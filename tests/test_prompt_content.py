"""프롬프트 내용 검증 테스트

프롬프트 개선사항이 정확히 반영되었는지, 기존 구조가 보존되었는지 검증
- Rule 1-A PR body 활용
- HOW TO TRANSFORM 5단계 변환 규칙
- TRANSFORMATION EXAMPLES 2개
"""

import pytest

from app.domain.resume.prompts.generation import (
    RESUME_GENERATOR_HUMAN,
    RESUME_GENERATOR_RETRY_HUMAN,
    RESUME_GENERATOR_SYSTEM,
)
from app.domain.resume.validators import ALLOWED_ENDINGS


class TestResumeGeneratorSystem:
    """system 프롬프트 검증"""

    def test_rule_1a_exists(self):
        """Rule 1-A PR body 활용 가이드가 존재하는지 확인"""
        assert "Rule 1-A" in RESUME_GENERATOR_SYSTEM
        assert "PR body" in RESUME_GENERATOR_SYSTEM or "PR descriptions" in RESUME_GENERATOR_SYSTEM

    def test_how_to_transform_section_exists(self):
        """HOW TO TRANSFORM 섹션과 Step A~E가 존재하는지 확인"""
        assert "HOW TO TRANSFORM" in RESUME_GENERATOR_SYSTEM
        assert "Step A" in RESUME_GENERATOR_SYSTEM
        assert "Step B" in RESUME_GENERATOR_SYSTEM
        assert "Step C" in RESUME_GENERATOR_SYSTEM
        assert "Step D" in RESUME_GENERATOR_SYSTEM
        assert "Step E" in RESUME_GENERATOR_SYSTEM

    def test_transformation_examples_exist(self):
        """TRANSFORMATION EXAMPLES와 Example 1, 2가 존재하는지 확인"""
        assert "TRANSFORMATION EXAMPLES" in RESUME_GENERATOR_SYSTEM
        assert "Example 1" in RESUME_GENERATOR_SYSTEM
        assert "Example 2" in RESUME_GENERATOR_SYSTEM

    def test_existing_sections_preserved(self):
        """기존 핵심 섹션들이 보존되었는지 확인"""
        assert "BAD EXAMPLE" in RESUME_GENERATOR_SYSTEM
        assert "MOST IMPORTANT RULE" in RESUME_GENERATOR_SYSTEM
        assert "OUTPUT FORMAT" in RESUME_GENERATOR_SYSTEM

    def test_placeholders_preserved(self):
        """{position}, {position_rules} 플레이스홀더가 보존되었는지 확인"""
        assert "{position}" in RESUME_GENERATOR_SYSTEM
        assert "{position_rules}" in RESUME_GENERATOR_SYSTEM


class TestResumeGeneratorHuman:
    """human 프롬프트 검증"""

    def test_step1_includes_pr_descriptions(self):
        """Step 1에 PR descriptions가 포함되었는지 확인"""
        assert "PR descriptions" in RESUME_GENERATOR_HUMAN

    def test_reminder_includes_pr_descriptions(self):
        """REMINDER에 PR descriptions가 포함되었는지 확인"""
        assert "REMINDER" in RESUME_GENERATOR_HUMAN
        reminder_section = RESUME_GENERATOR_HUMAN.split("REMINDER")[-1]
        assert "PR descriptions" in reminder_section

    def test_all_placeholders_preserved(self):
        """기존 플레이스홀더 6개가 보존되었는지 확인"""
        expected_placeholders = [
            "{position}",
            "{project_count}",
            "{user_stats}",
            "{repo_contexts}",
            "{project_info}",
            "{repo_urls}",
        ]
        for placeholder in expected_placeholders:
            assert placeholder in RESUME_GENERATOR_HUMAN, f"플레이스홀더 {placeholder}가 누락됨"


class TestResumeGeneratorRetryHuman:
    """retry 프롬프트 검증"""

    def test_step2_includes_pr_descriptions(self):
        """Step 2에 PR descriptions가 포함되었는지 확인"""
        assert "PR descriptions" in RESUME_GENERATOR_RETRY_HUMAN

    def test_reminder_includes_pr_descriptions(self):
        """REMINDER에 PR descriptions가 포함되었는지 확인"""
        assert "REMINDER" in RESUME_GENERATOR_RETRY_HUMAN
        reminder_section = RESUME_GENERATOR_RETRY_HUMAN.split("REMINDER")[-1]
        assert "PR descriptions" in reminder_section

    def test_retry_specific_placeholders_preserved(self):
        """{feedback}, {previous_resume_json} 플레이스홀더가 보존되었는지 확인"""
        assert "{feedback}" in RESUME_GENERATOR_RETRY_HUMAN
        assert "{previous_resume_json}" in RESUME_GENERATOR_RETRY_HUMAN


class TestPromptConsistency:
    """프롬프트 간 일관성 검증"""

    def test_both_human_prompts_mention_pr_descriptions(self):
        """human과 retry 모두 PR descriptions를 언급하는지 확인"""
        assert "PR descriptions" in RESUME_GENERATOR_HUMAN
        assert "PR descriptions" in RESUME_GENERATOR_RETRY_HUMAN

    def test_system_rule1a_and_human_pr_mention_consistent(self):
        """system의 Rule 1-A와 human의 PR 언급이 일관되는지 확인"""
        has_rule_1a = "Rule 1-A" in RESUME_GENERATOR_SYSTEM
        has_pr_in_human = "PR descriptions" in RESUME_GENERATOR_HUMAN
        assert has_rule_1a and has_pr_in_human, (
            "system에 Rule 1-A가 있으면 human에도 PR 관련 안내가 있어야 함"
        )

    @pytest.mark.parametrize("ending", ALLOWED_ENDINGS)
    def test_allowed_endings_in_system_prompt(self, ending):
        """validators.py의 ALLOWED_ENDINGS가 system 프롬프트에 존재하는지 확인"""
        assert f"~{ending}" in RESUME_GENERATOR_SYSTEM, (
            f"허용 어미 '~{ending}'이 system 프롬프트의 ALLOWED endings에 누락됨"
        )
