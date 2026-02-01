"""도구 함수 테스트"""

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.resume.schemas import EvaluationOutput, RepoContext, ResumeData, ProjectInfo
from app.domain.resume.tools import (
    collect_project_info,
    collect_repo_context,
    evaluate_resume,
    generate_resume,
    get_resume_tools,
)


class TestCollectProjectInfo:
    """collect_project_info 도구 테스트"""

    @pytest.mark.asyncio
    async def test_collect_project_info_success(self):
        """프로젝트 정보 수집 성공"""
        mock_project_info = [
            {
                "repo_name": "test-repo",
                "repo_url": "https://github.com/user/test-repo",
                "dependencies": ["fastapi"],
            }
        ]

        with patch(
            "app.domain.resume.tools.collect_project_info_service",
            new_callable=AsyncMock,
            return_value=mock_project_info,
        ):
            result = await collect_project_info.ainvoke(
                {"repo_urls": ["https://github.com/user/test-repo"], "github_token": "token"}
            )

        assert result["project_info"] == mock_project_info
        assert result["total_projects"] == 1


class TestCollectRepoContext:
    """collect_repo_context 도구 테스트"""

    @pytest.mark.asyncio
    async def test_collect_repo_context_success(self):
        """레포지토리 컨텍스트 수집 성공"""
        mock_contexts = {
            "test-repo": RepoContext(
                name="test-repo",
                languages={"Python": 10000},
                description="Test",
                topics=["python"],
                readme_summary="README",
            )
        }

        with patch(
            "app.domain.resume.tools.collect_repo_contexts_service",
            new_callable=AsyncMock,
            return_value=mock_contexts,
        ):
            result = await collect_repo_context.ainvoke(
                {"repo_urls": ["https://github.com/user/test-repo"], "github_token": "token"}
            )

        assert "test-repo" in result
        assert result["test-repo"]["name"] == "test-repo"


class TestGenerateResume:
    """generate_resume 도구 테스트"""

    @pytest.mark.asyncio
    async def test_generate_resume_success(self):
        """이력서 생성 성공"""
        mock_resume = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/user/test",
                    description="Test project",
                    tech_stack=["Python"],
                )
            ]
        )

        with patch(
            "app.domain.resume.tools.generate_resume_llm",
            new_callable=AsyncMock,
            return_value=mock_resume,
        ):
            result = await generate_resume.ainvoke(
                {
                    "project_info": [{"repo_name": "test"}],
                    "position": "백엔드",
                    "repo_urls": ["https://github.com/user/test"],
                }
            )

        assert "projects" in result
        assert len(result["projects"]) == 1

    @pytest.mark.asyncio
    async def test_generate_resume_with_contexts(self):
        """컨텍스트 포함 이력서 생성"""
        mock_resume = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/user/test",
                    description="Test",
                    tech_stack=["Python"],
                )
            ]
        )

        with patch(
            "app.domain.resume.tools.generate_resume_llm",
            new_callable=AsyncMock,
            return_value=mock_resume,
        ):
            result = await generate_resume.ainvoke(
                {
                    "project_info": [{"repo_name": "test"}],
                    "position": "백엔드",
                    "repo_urls": ["https://github.com/user/test"],
                    "repo_contexts": {
                        "test": {
                            "name": "test",
                            "languages": {"Python": 100},
                            "description": "desc",
                            "topics": [],
                            "readme_summary": None,
                        }
                    },
                }
            )

        assert "projects" in result


class TestEvaluateResume:
    """evaluate_resume 도구 테스트"""

    @pytest.mark.asyncio
    async def test_evaluate_resume_success(self):
        """이력서 평가 성공"""
        mock_evaluation = EvaluationOutput(
            result="pass",
            violated_rule=None,
            violated_item=None,
            feedback="Good",
        )

        with patch(
            "app.domain.resume.tools.evaluate_resume_llm",
            new_callable=AsyncMock,
            return_value=mock_evaluation,
        ):
            result = await evaluate_resume.ainvoke(
                {
                    "resume_data": {
                        "projects": [
                            {
                                "name": "Test",
                                "repo_url": "https://github.com/user/test",
                                "description": "Test",
                                "tech_stack": ["Python"],
                            }
                        ]
                    },
                    "position": "백엔드",
                }
            )

        assert result["result"] == "pass"


class TestGetResumeTools:
    """get_resume_tools 함수 테스트"""

    def test_returns_all_tools(self):
        """모든 도구 반환"""
        tools = get_resume_tools()

        assert len(tools) == 4
        tool_names = [t.name for t in tools]
        assert "collect_project_info" in tool_names
        assert "collect_repo_context" in tool_names
        assert "generate_resume" in tool_names
        assert "evaluate_resume" in tool_names
