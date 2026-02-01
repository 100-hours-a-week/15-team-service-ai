from unittest.mock import AsyncMock, patch

import pytest

from app.domain.resume.schemas import PRInfoExtended, RepoContext, ResumeRequest, UserStats
from app.domain.resume.service import (
    _filter_and_sort_dependencies,
    _format_messages,
    _parse_dependencies,
    _summarize_file_tree,
    collect_project_info,
    collect_repo_contexts,
    collect_user_stats,
)


class TestFilterAndSortDependencies:
    """_filter_and_sort_dependencies 함수 테스트."""

    @pytest.mark.parametrize(
        "excluded_dep",
        [
            "pytest",
            "jest",
            "mocha",
            "eslint",
            "prettier",
            "ruff",
            "black",
            "@types/node",
            "types-requests",
            "pre-commit",
            "husky",
        ],
    )
    def test_excludes_dev_tools(self, excluded_dep):
        """테스트/린트/타입 도구는 제외."""
        deps = ["fastapi", excluded_dep]
        result = _filter_and_sort_dependencies(deps)

        assert excluded_dep not in result
        assert "fastapi" in result

    @pytest.mark.parametrize(
        "deps, expected_order",
        [
            (["redis", "fastapi", "some-lib"], ["fastapi", "redis", "some-lib"]),
            (["express", "react", "prisma"], ["react", "express", "prisma"]),
            (["kafka", "django", "celery"], ["django", "celery", "kafka"]),
        ],
    )
    def test_priority_sorting(self, deps, expected_order):
        """우선순위에 따라 정렬."""
        result = _filter_and_sort_dependencies(deps)
        assert result == expected_order

    @pytest.mark.parametrize(
        "deps, expected",
        [
            ([], []),
            (["pytest", "jest", "eslint"], []),
        ],
    )
    def test_edge_cases(self, deps, expected):
        """빈 리스트와 모두 제외되는 경우."""
        result = _filter_and_sort_dependencies(deps)
        assert result == expected


class TestSummarizeFileTree:
    """_summarize_file_tree 함수 테스트."""

    def test_extracts_top_directories(self):
        """최상위 디렉토리 추출."""
        file_tree = [
            "src/main.py",
            "src/utils/helper.py",
            "tests/test_main.py",
            "README.md",
        ]
        result = _summarize_file_tree(file_tree)

        assert "src" in result
        assert "tests" in result

    def test_extracts_nested_directories(self):
        """중첩 디렉토리 추출."""
        file_tree = [
            "app/api/v1/routes.py",
            "app/domain/user/service.py",
        ]
        result = _summarize_file_tree(file_tree)

        assert "app" in result
        assert "app/api" in result
        assert "app/domain" in result

    @pytest.mark.parametrize(
        "extensions",
        [
            ["py", "ts", "css", "json"],
            ["java", "xml", "kt"],
            ["go", "mod", "sum"],
        ],
    )
    def test_extracts_extensions(self, extensions):
        """파일 확장자 추출."""
        file_tree = [f"file.{ext}" for ext in extensions]
        result = _summarize_file_tree(file_tree)

        extensions_line = [r for r in result if r.startswith("extensions:")][0]
        for ext in extensions:
            assert ext in extensions_line

    def test_limits_directories_to_20(self):
        """디렉토리는 최대 20개."""
        file_tree = [f"dir{i}/file.py" for i in range(30)]
        result = _summarize_file_tree(file_tree)

        dir_count = len([r for r in result if not r.startswith("extensions:")])
        assert dir_count <= 20

    def test_empty_file_tree(self):
        """빈 파일 트리 처리."""
        result = _summarize_file_tree([])

        assert len(result) == 1
        assert result[0].startswith("extensions:")


class TestFormatMessages:
    """_format_messages 함수 테스트."""

    def test_formats_pull_requests(self, sample_pr):
        """PR 정보 포맷팅."""
        result = _format_messages([], [sample_pr])

        assert len(result) == 1
        assert "PR #1: Add feature" in result[0]
        assert "커밋 3개" in result[0]
        assert "+100/-20" in result[0]

    def test_formats_commits(self, sample_commits):
        """커밋 정보 포맷팅."""
        result = _format_messages(sample_commits, [])

        assert len(result) == 2
        assert "commit: Fix bug" in result[0]
        assert "commit: Add test" in result[1]

    def test_truncates_pr_body(self):
        """PR 본문은 200자로 제한."""
        long_body = "A" * 300
        pr = PRInfoExtended(
            number=1,
            title="Test",
            body=long_body,
            author="user",
            merged_at="2024-01-01",
            repo_url="https://github.com/user/repo",
            commits_count=1,
            additions=10,
            deletions=5,
        )

        result = _format_messages([], [pr])
        assert len(result[0]) < 400

    def test_empty_inputs(self):
        """빈 입력 처리."""
        result = _format_messages([], [])
        assert result == []

    def test_pr_without_body(self):
        """본문 없는 PR 처리."""
        pr = PRInfoExtended(
            number=1,
            title="Quick fix",
            body=None,
            author="user",
            merged_at="2024-01-01",
            repo_url="https://github.com/user/repo",
            commits_count=1,
            additions=5,
            deletions=2,
        )

        result = _format_messages([], [pr])

        assert len(result) == 1
        assert "PR #1: Quick fix" in result[0]


class TestCollectProjectInfo:
    """collect_project_info 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self, sample_resume_request):
        """정상 수집"""
        mock_project_info = {
            "file_tree": ["src/main.py"],
            "commits": [],
            "pulls": [],
        }

        with (
            patch(
                "app.domain.resume.service.get_project_info",
                new_callable=AsyncMock,
                return_value=mock_project_info,
            ),
            patch(
                "app.domain.resume.service._parse_dependencies",
                new_callable=AsyncMock,
                return_value=["fastapi"],
            ),
        ):
            result = await collect_project_info(sample_resume_request)

        assert len(result) == 1
        assert result[0]["repo_name"] == "testrepo"
        assert "fastapi" in result[0]["dependencies"]

    @pytest.mark.asyncio
    async def test_handles_exception(self, sample_resume_request):
        """예외 발생 시 빈 정보 반환"""
        with patch(
            "app.domain.resume.service.get_project_info",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            result = await collect_project_info(sample_resume_request)

        assert len(result) == 1
        assert result[0]["repo_name"] == "testrepo"
        assert result[0]["dependencies"] == []

    @pytest.mark.asyncio
    async def test_removes_duplicate_urls(self):
        """중복 URL 제거"""
        request = ResumeRequest(
            repo_urls=[
                "https://github.com/user/repo",
                "https://github.com/user/repo",
            ],
            position="백엔드",
            github_token="token",
        )

        mock_project_info = {
            "file_tree": [],
            "commits": [],
            "pulls": [],
        }

        with (
            patch(
                "app.domain.resume.service.get_project_info",
                new_callable=AsyncMock,
                return_value=mock_project_info,
            ),
            patch(
                "app.domain.resume.service._parse_dependencies",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await collect_project_info(request)

        assert len(result) == 1


class TestCollectRepoContexts:
    """collect_repo_contexts 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self, sample_resume_request):
        """정상 수집"""
        mock_context = {
            "languages": {"Python": 10000},
            "description": "Test repo",
            "topics": ["python"],
            "readme": "README content",
        }

        with patch(
            "app.domain.resume.service.get_repo_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ):
            result = await collect_repo_contexts(sample_resume_request)

        assert "testrepo" in result
        assert result["testrepo"].languages == {"Python": 10000}

    @pytest.mark.asyncio
    async def test_handles_exception(self, sample_resume_request):
        """예외 발생 시 빈 컨텍스트 반환"""
        with patch(
            "app.domain.resume.service.get_repo_context",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            result = await collect_repo_contexts(sample_resume_request)

        assert "testrepo" in result
        assert result["testrepo"].languages == {}


class TestCollectUserStats:
    """collect_user_stats 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """정상 수집"""
        mock_stats = UserStats(total_commits=100, total_prs=20, total_issues=10)

        with patch(
            "app.domain.resume.service.get_user_stats",
            new_callable=AsyncMock,
            return_value=mock_stats,
        ):
            result = await collect_user_stats("testuser", "token")

        assert result is not None
        assert result.total_commits == 100
        assert result.total_prs == 20

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """예외 발생 시 None 반환"""
        with patch(
            "app.domain.resume.service.get_user_stats",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            result = await collect_user_stats("testuser", "token")

        assert result is None


class TestParseDependencies:
    """_parse_dependencies 함수 테스트"""

    @pytest.mark.asyncio
    async def test_parses_dependency_files(self):
        """의존성 파일 파싱"""
        file_tree = ["requirements.txt", "src/main.py"]

        with patch(
            "app.domain.resume.service.get_files_content",
            new_callable=AsyncMock,
            return_value={"requirements.txt": "fastapi==0.100.0\nuvicorn>=0.20.0"},
        ):
            result = await _parse_dependencies(
                "https://github.com/user/repo", file_tree, "token"
            )

        assert "fastapi" in result
        assert "uvicorn" in result

    @pytest.mark.asyncio
    async def test_no_dependency_files(self):
        """의존성 파일 없음"""
        file_tree = ["src/main.py", "README.md"]

        result = await _parse_dependencies(
            "https://github.com/user/repo", file_tree, "token"
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """빈 콘텐츠 처리"""
        file_tree = ["requirements.txt"]

        with patch(
            "app.domain.resume.service.get_files_content",
            new_callable=AsyncMock,
            return_value={"requirements.txt": ""},
        ):
            result = await _parse_dependencies(
                "https://github.com/user/repo", file_tree, "token"
            )
