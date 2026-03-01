from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.resume.schemas import (
    ProjectInfo,
    RepoContext,
    ResumeData,
)
from app.infra.llm.client import (
    evaluate_resume,
    format_project_info,
    format_repo_contexts,
    generate_resume,
)


class TestFormatProjectInfo:
    """format_project_info 함수 테스트"""

    def test_format_single_project(self):
        """단일 프로젝트 포맷팅"""
        project_info = [
            {
                "repo_name": "test-repo",
                "repo_url": "https://github.com/user/test-repo",
                "file_tree": ["src/main.py", "requirements.txt"],
                "dependencies": ["fastapi", "uvicorn"],
                "messages": ["feat: initial commit", "fix: bug fix"],
            }
        ]

        result = format_project_info(project_info)

        assert "### 프로젝트 1/1: test-repo" in result
        assert "https://github.com/user/test-repo" in result
        assert "fastapi" in result
        assert "uvicorn" in result
        assert "feat: initial commit" in result

    def test_format_multiple_projects(self):
        """다중 프로젝트 포맷팅"""
        project_info = [
            {
                "repo_name": "repo1",
                "repo_url": "https://github.com/user/repo1",
                "file_tree": [],
                "dependencies": ["django"],
                "messages": ["init"],
            },
            {
                "repo_name": "repo2",
                "repo_url": "https://github.com/user/repo2",
                "file_tree": [],
                "dependencies": ["express"],
                "messages": ["init"],
            },
        ]

        result = format_project_info(project_info)

        assert "### 프로젝트 1/2: repo1" in result
        assert "### 프로젝트 2/2: repo2" in result
        assert "---" in result

    def test_format_project_without_optional_fields(self):
        """선택 필드 없는 프로젝트 포맷팅"""
        project_info = [
            {
                "repo_name": "minimal-repo",
                "repo_url": "https://github.com/user/minimal-repo",
            }
        ]

        result = format_project_info(project_info)

        assert "### 프로젝트 1/1: minimal-repo" in result
        assert "https://github.com/user/minimal-repo" in result

    def test_format_project_limits_dependencies(self):
        """의존성 30개 제한"""
        many_deps = [f"dep-{i}" for i in range(50)]
        project_info = [
            {
                "repo_name": "many-deps",
                "repo_url": "https://github.com/user/many-deps",
                "dependencies": many_deps,
            }
        ]

        result = format_project_info(project_info)

        assert "dep-0" in result
        assert "dep-29" in result
        assert "dep-30" not in result


class TestFormatRepoContexts:
    """format_repo_contexts 함수 테스트"""

    def test_format_empty_contexts(self):
        """빈 컨텍스트 처리"""
        result = format_repo_contexts({})

        assert result == "없음"

    def test_format_single_context(self):
        """단일 컨텍스트 포맷팅"""
        contexts = {
            "test-repo": RepoContext(
                name="test-repo",
                languages={"Python": 10000, "JavaScript": 2000},
                description="테스트 프로젝트",
                topics=["python", "fastapi"],
                readme_summary="이 프로젝트는 테스트용입니다",
            )
        }

        result = format_repo_contexts(contexts)

        assert "### 레포지토리 1/1: test-repo" in result
        assert "Python" in result
        assert "JavaScript" in result
        assert "테스트 프로젝트" in result
        assert "python" in result
        assert "fastapi" in result

    def test_format_context_without_description(self):
        """설명 없는 컨텍스트 처리"""
        contexts = {
            "no-desc-repo": RepoContext(
                name="no-desc-repo",
                languages={"Python": 5000},
                description=None,
                topics=[],
                readme_summary=None,
            )
        }

        result = format_repo_contexts(contexts)

        assert "설명: 없음" in result
        assert "토픽: 없음" in result

    def test_format_multiple_contexts(self):
        """다중 컨텍스트 포맷팅"""
        contexts = {
            "repo1": RepoContext(
                name="repo1",
                languages={"Python": 10000},
                description="Repo 1",
                topics=["python"],
                readme_summary="Readme 1",
            ),
            "repo2": RepoContext(
                name="repo2",
                languages={"TypeScript": 8000},
                description="Repo 2",
                topics=["typescript"],
                readme_summary="Readme 2",
            ),
        }

        result = format_repo_contexts(contexts)

        assert "### 레포지토리 1/2:" in result
        assert "### 레포지토리 2/2:" in result
        assert "---" in result


class TestGenerateResume:
    """generate_resume 함수 테스트"""

    @pytest.fixture
    def sample_project_info(self) -> list[dict]:
        """테스트용 프로젝트 정보"""
        return [
            {
                "repo_name": "test-repo",
                "repo_url": "https://github.com/user/test-repo",
                "dependencies": ["fastapi"],
                "messages": ["feat: init"],
            }
        ]

    async def test_generate_resume_success(self, sample_project_info):
        """정상 이력서 생성"""
        expected_result = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test Project",
                    repo_url="https://github.com/user/test-repo",
                    description="테스트 프로젝트",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=expected_result
        )

        with patch("app.infra.llm.resume.get_generator_llm", return_value=mock_llm):
            result = await generate_resume(
                project_info=sample_project_info,
                position="백엔드 개발자",
            )

        assert result == expected_result
        assert len(result.projects) == 1
        assert result.projects[0].name == "Test Project"

    async def test_generate_resume_with_feedback(self, sample_project_info):
        """피드백 포함 재시도 생성"""
        expected_result = ResumeData(
            projects=[
                ProjectInfo(
                    name="Improved Project",
                    repo_url="https://github.com/user/test-repo",
                    description="개선된 설명",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=expected_result
        )

        with patch("app.infra.llm.resume.get_generator_llm", return_value=mock_llm):
            result = await generate_resume(
                project_info=sample_project_info,
                position="백엔드 개발자",
            )

        assert result == expected_result

    async def test_generate_resume_with_repo_contexts(self, sample_project_info):
        """레포지토리 컨텍스트 포함 생성"""
        expected_result = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/user/test-repo",
                    description="Test",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=expected_result
        )

        with patch("app.infra.llm.resume.get_generator_llm", return_value=mock_llm):
            result = await generate_resume(
                project_info=sample_project_info,
                position="백엔드 개발자",
            )

        assert result == expected_result

    async def test_generate_resume_with_user_stats(self, sample_project_info):
        """사용자 통계 포함 생성"""
        expected_result = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/user/test-repo",
                    description="Test",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=expected_result
        )

        with patch("app.infra.llm.resume.get_generator_llm", return_value=mock_llm):
            result = await generate_resume(
                project_info=sample_project_info,
                position="백엔드 개발자",
            )

        assert result == expected_result


class TestEvaluateResume:
    """evaluate_resume 함수 테스트"""

    @pytest.fixture
    def sample_resume_data(self) -> ResumeData:
        """테스트용 이력서 데이터"""
        return ResumeData(
            projects=[
                ProjectInfo(
                    name="Test Project",
                    repo_url="https://github.com/user/test-repo",
                    description="- FastAPI 기반 인증 API 구현",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

    async def test_evaluate_resume_pass(self, sample_resume_data):
        """평가 통과 시 EvaluationOutput 반환"""
        from app.domain.resume.schemas import EvaluationOutput

        expected = EvaluationOutput(
            result="pass",
            violated_rule=None,
            violated_item=None,
            feedback="모든 규칙 준수",
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=expected)

        with patch("app.infra.llm.resume.get_evaluator_llm", return_value=mock_llm):
            result = await evaluate_resume(
                resume_data=sample_resume_data,
                position="백엔드 개발자",
                commit_messages=["feat: 인증 API 구현"],
            )

        assert result.result == "pass"
        assert result.feedback == "모든 규칙 준수"

    async def test_evaluate_resume_fail(self, sample_resume_data):
        """평가 실패 시 EvaluationOutput에 피드백 포함"""
        from app.domain.resume.schemas import EvaluationOutput

        expected = EvaluationOutput(
            result="fail",
            violated_rule=1,
            violated_item="Redis 캐싱",
            feedback="불릿 2 ('Redis 캐싱'): 커밋에서 Redis 사용 확인 불가. 해당 불릿 제거 필요",
        )

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=expected)

        with patch("app.infra.llm.resume.get_evaluator_llm", return_value=mock_llm):
            result = await evaluate_resume(
                resume_data=sample_resume_data,
                position="백엔드 개발자",
                commit_messages=["feat: 인증 API 구현"],
                session_id="test-session-123",
            )

        assert result.result == "fail"
        assert "Redis" in result.feedback
