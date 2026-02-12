import pytest

from app.domain.resume.schemas import CommitInfo, PRInfoExtended
from app.domain.resume.service import (
    _filter_and_sort_dependencies,
    _format_messages,
    _is_empty_repository,
    _summarize_file_tree,
    filter_tech_stack_by_position,
    validate_position_match,
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

    @pytest.fixture
    def sample_pr(self):
        """테스트용 PR 데이터."""
        return PRInfoExtended(
            number=1,
            title="Add feature",
            body="This PR adds a new feature",
            author="user1",
            merged_at="2024-01-01",
            repo_url="https://github.com/user/repo",
            commits_count=3,
            additions=100,
            deletions=20,
        )

    @pytest.fixture
    def sample_commits(self):
        """테스트용 커밋 데이터."""
        return [
            CommitInfo(sha="abc123", message="Fix bug\n\nDetailed description", author="user1"),
            CommitInfo(sha="def456", message="Add test", author="user2"),
        ]

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


class TestIsEmptyRepository:
    """_is_empty_repository 함수 테스트"""

    def test_empty_file_tree(self):
        """빈 파일 트리는 빈 레포지토리"""
        assert _is_empty_repository([]) is True

    def test_only_config_files(self):
        """설정 파일만 있으면 빈 레포지토리"""
        file_tree = ["README.md", ".gitignore", "LICENSE"]
        assert _is_empty_repository(file_tree) is True

    def test_with_python_files(self):
        """파이썬 파일이 있으면 빈 레포지토리가 아님"""
        file_tree = ["README.md", "src/main.py"]
        assert _is_empty_repository(file_tree) is False

    def test_with_java_files(self):
        """자바 파일이 있으면 빈 레포지토리가 아님"""
        file_tree = ["src/Main.java"]
        assert _is_empty_repository(file_tree) is False

    def test_with_javascript_files(self):
        """자바스크립트 파일이 있으면 빈 레포지토리가 아님"""
        file_tree = ["index.js"]
        assert _is_empty_repository(file_tree) is False

    def test_with_typescript_files(self):
        """타입스크립트 파일이 있으면 빈 레포지토리가 아님"""
        file_tree = ["src/app.ts", "src/app.tsx"]
        assert _is_empty_repository(file_tree) is False


class TestValidatePositionMatch:
    """validate_position_match 함수 테스트"""

    def test_backend_with_backend_deps(self):
        """백엔드 포지션 + 백엔드 의존성 = 성공"""
        is_valid, error_msg = validate_position_match(
            "백엔드 개발자",
            ["spring-boot", "mysql"],
        )
        assert is_valid is True
        assert error_msg == ""

    def test_backend_with_frontend_only_deps(self):
        """백엔드 포지션 + 프론트엔드 의존성만 = 실패"""
        is_valid, error_msg = validate_position_match(
            "백엔드 개발자",
            ["react", "next"],
        )
        assert is_valid is False
        assert "포지션에 맞는 기술 스택이 없습니다" in error_msg

    def test_frontend_with_frontend_deps(self):
        """프론트엔드 포지션 + 프론트엔드 의존성 = 성공"""
        is_valid, error_msg = validate_position_match(
            "프론트엔드 개발자",
            ["react", "typescript"],
        )
        assert is_valid is True
        assert error_msg == ""

    def test_frontend_with_backend_only_deps(self):
        """프론트엔드 포지션 + 백엔드 의존성만 = 실패"""
        is_valid, error_msg = validate_position_match(
            "프론트엔드 개발자",
            ["spring-boot", "mysql"],
        )
        assert is_valid is False

    def test_unknown_position_always_valid(self):
        """알 수 없는 포지션은 항상 성공"""
        is_valid, error_msg = validate_position_match(
            "데이터 엔지니어",
            ["airflow", "spark"],
        )
        assert is_valid is True

    def test_empty_dependencies(self):
        """빈 의존성 리스트"""
        is_valid, error_msg = validate_position_match(
            "백엔드 개발자",
            [],
        )
        assert is_valid is False


class TestFilterTechStackByPosition:
    """filter_tech_stack_by_position 함수 테스트"""

    def test_backend_filters_frontend_techs(self):
        """백엔드 포지션에서 프론트엔드 기술 제외"""
        tech_stack = ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "Redis"]
        result = filter_tech_stack_by_position(tech_stack, "백엔드 개발자")

        assert "Python" in result
        assert "FastAPI" in result

    def test_max_count_limit(self):
        """max_count 제한 적용"""
        tech_stack = [f"Tech{i}" for i in range(15)]
        result = filter_tech_stack_by_position(tech_stack, "백엔드 개발자", max_count=5)

        assert len(result) <= 5

    def test_empty_tech_stack(self):
        """빈 기술 스택"""
        result = filter_tech_stack_by_position([], "백엔드 개발자")
        assert result == []

    def test_excluded_techs_removed(self):
        """제외 대상 기술은 제거"""
        tech_stack = ["Python", "lombok", "FastAPI", "Spring Boot", "Docker", "Redis"]
        result = filter_tech_stack_by_position(tech_stack, "백엔드 개발자")

        assert "lombok" not in result
