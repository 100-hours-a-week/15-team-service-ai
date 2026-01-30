import pytest

from app.infra.github.client import _sanitize_file_path, parse_repo_url


class TestParseRepoUrl:
    """parse_repo_url 함수 테스트."""

    @pytest.mark.parametrize(
        "url, expected_owner, expected_repo",
        [
            ("https://github.com/user/my-repo", "user", "my-repo"),
            ("https://github.com/user/my-repo.git", "user", "my-repo"),
            ("https://github.com/user/my-repo/", "user", "my-repo"),
            ("https://github.com/org-name/repo_name", "org-name", "repo_name"),
            ("https://github.com/User123/Repo.Name", "User123", "Repo.Name"),
        ],
    )
    def test_valid_urls(self, url, expected_owner, expected_repo):
        """유효한 GitHub URL 파싱."""
        owner, repo = parse_repo_url(url)
        assert owner == expected_owner
        assert repo == expected_repo

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "invalid-url",
            "https://gitlab.com/user/repo",
            "https://github.com/user",
            "https://github.com/",
            "not-a-url",
            "",
        ],
    )
    def test_invalid_urls(self, invalid_url):
        """유효하지 않은 URL은 ValueError 발생."""
        with pytest.raises(ValueError, match="유효하지 않은 GitHub URL"):
            parse_repo_url(invalid_url)


class TestSanitizeFilePath:
    """_sanitize_file_path 함수 테스트."""

    @pytest.mark.parametrize(
        "path",
        [
            "src/main.py",
            "package.json",
            "src/utils/helper.ts",
            "my-app/utils_helper.py",
            "src/my_module/test-file.js",
            "README.md",
            "app/api/v1/routes.py",
        ],
    )
    def test_valid_paths(self, path):
        """유효한 파일 경로는 그대로 반환."""
        assert _sanitize_file_path(path) == path

    @pytest.mark.parametrize(
        "invalid_path",
        [
            "src/main.py; rm -rf /",
            'src/"malicious".py',
            "src/`whoami`.py",
            "src/$(cat /etc/passwd).py",
            "src/file|cat.py",
            "src/file>output.py",
            "src/file<input.py",
            "src/file&background.py",
        ],
    )
    def test_invalid_paths(self, invalid_path):
        """특수문자가 포함된 경로는 ValueError 발생."""
        with pytest.raises(ValueError, match="유효하지 않은 파일 경로"):
            _sanitize_file_path(invalid_path)
