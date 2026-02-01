"""LLM 클라이언트 테스트"""

from unittest.mock import AsyncMock

import pytest

from app.domain.resume.schemas import (
    EvaluationOutput,
    ProjectInfo,
    RepoContext,
    ResumeData,
    UserStats,
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
    def base_project_info(self) -> list[dict]:
        """테스트용 기본 프로젝트 정보"""
        return [
            {
                "repo_name": "test-repo",
                "repo_url": "https://github.com/user/test-repo",
                "dependencies": ["fastapi"],
                "messages": ["feat: init"],
            }
        ]

    @pytest.fixture
    def expected_resume(self) -> ResumeData:
        """기대하는 이력서 결과"""
        return ResumeData(
            projects=[
                ProjectInfo(
                    name="Test Project",
                    repo_url="https://github.com/user/test-repo",
                    description="테스트 프로젝트",
                    tech_stack=["Python", "FastAPI"],
                )
            ]
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "feedback,repo_contexts,user_stats,test_id",
        [
            (None, None, None, "기본 생성"),
            ("기술 스택을 더 추가해주세요", None, None, "피드백 포함"),
            (
                None,
                {
                    "test-repo": RepoContext(
                        name="test-repo",
                        languages={"Python": 10000},
                        description="테스트",
                        topics=["python"],
                        readme_summary="README",
                    )
                },
                None,
                "컨텍스트 포함",
            ),
            (
                None,
                None,
                UserStats(total_commits=100, total_prs=20, total_issues=10),
                "통계 포함",
            ),
        ],
        ids=["basic", "with_feedback", "with_contexts", "with_stats"],
    )
    async def test_generate_resume(
        self,
        mock_vllm_client,
        base_project_info,
        expected_resume,
        feedback,
        repo_contexts,
        user_stats,
        test_id,
    ):
        """이력서 생성 테스트 - 다양한 옵션 조합"""
        mock_vllm_client.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=expected_resume
        )

        result = await generate_resume(
            project_info=base_project_info,
            position="백엔드 개발자",
            repo_urls=["https://github.com/user/test-repo"],
            feedback=feedback,
            repo_contexts=repo_contexts,
            user_stats=user_stats,
        )

        assert result == expected_resume
        assert len(result.projects) == 1


class TestEvaluateResume:
    """evaluate_resume 함수 테스트"""

    @pytest.fixture
    def base_resume_data(self) -> ResumeData:
        """테스트용 이력서 데이터"""
        return ResumeData(
            projects=[
                ProjectInfo(
                    name="Test Project",
                    repo_url="https://github.com/user/test-repo",
                    description="테스트 프로젝트입니다",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "eval_result,violated_rule,violated_item,feedback,session_id",
        [
            ("pass", None, None, "모든 기준을 충족합니다", None),
            ("fail", 2, "description", "설명이 너무 짧습니다", None),
            ("pass", None, None, "좋습니다", "test-session-123"),
        ],
        ids=["pass", "fail", "with_session"],
    )
    async def test_evaluate_resume(
        self,
        mock_gemini_client,
        base_resume_data,
        eval_result,
        violated_rule,
        violated_item,
        feedback,
        session_id,
    ):
        """이력서 평가 테스트 - 다양한 결과"""
        expected = EvaluationOutput(
            result=eval_result,
            violated_rule=violated_rule,
            violated_item=violated_item,
            feedback=feedback,
        )

        mock_gemini_client.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=expected
        )

        result = await evaluate_resume(
            resume_data=base_resume_data,
            position="백엔드 개발자",
            session_id=session_id,
        )

        assert result.result == eval_result
        assert result.violated_rule == violated_rule
        assert result.feedback == feedback
