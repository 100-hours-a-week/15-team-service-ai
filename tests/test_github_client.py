"""GitHub 클라이언트 테스트"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infra.github.client import (
    _get_headers,
    _sanitize_file_path,
    get_commits,
    get_file_content,
    get_files_content,
    get_project_info,
    get_pulls,
    get_repo_context,
    get_repo_tree,
    get_user_stats,
    parse_repo_url,
)


class TestParseRepoUrl:
    """parse_repo_url 함수 테스트"""

    @pytest.mark.parametrize(
        "url,expected_owner,expected_repo",
        [
            ("https://github.com/user/my-repo", "user", "my-repo"),
            ("https://github.com/user/my-repo.git", "user", "my-repo"),
            ("https://github.com/user/my-repo/", "user", "my-repo"),
            ("https://github.com/org-name/repo_name", "org-name", "repo_name"),
            ("https://github.com/User123/Repo.Name", "User123", "Repo.Name"),
        ],
    )
    def test_valid_urls(self, url, expected_owner, expected_repo):
        """유효한 GitHub URL 파싱"""
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
        """유효하지 않은 URL은 ValueError 발생"""
        with pytest.raises(ValueError, match="유효하지 않은 GitHub URL"):
            parse_repo_url(invalid_url)


class TestSanitizeFilePath:
    """_sanitize_file_path 함수 테스트"""

    @pytest.mark.parametrize(
        "path",
        [
            "src/main.py",
            "package.json",
            "src/utils/helper.ts",
            "my-app/utils_helper.py",
            "README.md",
        ],
    )
    def test_valid_paths(self, path):
        """유효한 파일 경로는 그대로 반환"""
        assert _sanitize_file_path(path) == path

    @pytest.mark.parametrize(
        "invalid_path,error_msg",
        [
            ("../secret.txt", "경로 순회"),
            ("/etc/passwd", "절대 경로"),
            ("src/.git/config", "민감한 경로"),
            ("src/.env", "민감한 경로"),
            ("src/file;rm.py", "유효하지 않은"),
        ],
    )
    def test_invalid_paths(self, invalid_path, error_msg):
        """위험한 경로는 ValueError 발생"""
        with pytest.raises(ValueError, match=error_msg):
            _sanitize_file_path(invalid_path)


class TestGetHeaders:
    """_get_headers 함수 테스트"""

    def test_without_token(self):
        """토큰 없이 헤더 생성"""
        headers = _get_headers()
        assert "Accept" in headers
        assert "Authorization" not in headers

    def test_with_token(self):
        """토큰 포함 헤더 생성"""
        headers = _get_headers("test-token")
        assert "Accept" in headers
        assert headers["Authorization"] == "Bearer test-token"


class TestGetCommits:
    """get_commits 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """커밋 조회 성공"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "sha": "abc123",
                "commit": {"message": "feat: init", "author": {"name": "user"}},
                "parents": [{"sha": "parent1"}],
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await get_commits("https://github.com/user/repo", "token")

        assert len(result) == 1
        assert result[0].sha == "abc123"

    @pytest.mark.asyncio
    async def test_filters_merge_commits(self):
        """merge 커밋 제외"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "sha": "abc123",
                "commit": {"message": "normal", "author": {"name": "user"}},
                "parents": [{"sha": "p1"}],
            },
            {
                "sha": "merge123",
                "commit": {"message": "Merge branch", "author": {"name": "user"}},
                "parents": [{"sha": "p1"}, {"sha": "p2"}],
            },
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await get_commits("https://github.com/user/repo")

        assert len(result) == 1
        assert result[0].sha == "abc123"


class TestGetPulls:
    """get_pulls 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """PR 조회 성공"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "number": 1,
                "title": "Add feature",
                "body": "Description",
                "user": {"login": "user"},
                "merged_at": "2024-01-01T00:00:00Z",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await get_pulls("https://github.com/user/repo", "token")

        assert len(result) == 1
        assert result[0].number == 1


class TestGetRepoTree:
    """get_repo_tree 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """파일 트리 조회 성공"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tree": [
                {"path": "src/main.py", "type": "blob"},
                {"path": "src", "type": "tree"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await get_repo_tree("https://github.com/user/repo", "token")

        assert "src/main.py" in result
        assert "src" not in result


class TestGetFileContent:
    """get_file_content 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """파일 내용 조회 성공"""
        import base64

        content = base64.b64encode(b"print('hello')").decode()
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": content, "encoding": "base64"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await get_file_content(
                "https://github.com/user/repo", "src/main.py", "token"
            )

        assert result == "print('hello')"


class TestGetFilesContent:
    """get_files_content 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """여러 파일 내용 조회"""
        import base64

        content = base64.b64encode(b"fastapi==0.100.0").decode()
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": content}
        mock_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await get_files_content(
                "https://github.com/user/repo",
                ["requirements.txt"],
                "token",
            )

        assert "requirements.txt" in result


class TestGetProjectInfo:
    """get_project_info 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """프로젝트 정보 조회 성공"""
        mock_tree_response = MagicMock()
        mock_tree_response.json.return_value = {
            "tree": [{"path": "src/main.py", "type": "blob"}]
        }
        mock_tree_response.raise_for_status = MagicMock()

        mock_commits_response = MagicMock()
        mock_commits_response.json.return_value = []
        mock_commits_response.raise_for_status = MagicMock()

        mock_pulls_response = MagicMock()
        mock_pulls_response.json.return_value = []
        mock_pulls_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.get = AsyncMock(
                side_effect=[
                    mock_tree_response,
                    mock_commits_response,
                    mock_pulls_response,
                ]
            )
            result = await get_project_info("https://github.com/user/repo", "token")

        assert "file_tree" in result
        assert "commits" in result
        assert "pulls" in result


class TestGetRepoContext:
    """get_repo_context 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success_with_graphql(self):
        """GraphQL로 레포지토리 컨텍스트 조회 성공"""
        mock_graphql_result = {
            "languages": {"Python": 10000},
            "description": "Test repo",
            "topics": ["python"],
            "readme": "# README",
        }

        with patch(
            "app.infra.github.client.get_repo_context_graphql",
            new_callable=AsyncMock,
            return_value=mock_graphql_result,
        ):
            result = await get_repo_context("https://github.com/user/repo", "token")

        assert result["description"] == "Test repo"
        assert result["languages"] == {"Python": 10000}

    @pytest.mark.asyncio
    async def test_fallback_to_rest_without_token(self):
        """토큰 없이 REST API로 조회"""
        with (
            patch(
                "app.infra.github.client.get_repo_languages",
                new_callable=AsyncMock,
                return_value={"Python": 10000},
            ),
            patch(
                "app.infra.github.client.get_repo_info",
                new_callable=AsyncMock,
                return_value={"description": "Test repo", "topics": ["python"]},
            ),
            patch(
                "app.infra.github.client.get_repo_readme",
                new_callable=AsyncMock,
                return_value="# README",
            ),
        ):
            result = await get_repo_context("https://github.com/user/repo")

        assert result["description"] == "Test repo"
        assert result["languages"] == {"Python": 10000}
        assert result["readme"] == "# README"


class TestGetUserStats:
    """get_user_stats 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self):
        """사용자 통계 조회 성공"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "user": {
                    "contributionsCollection": {
                        "totalCommitContributions": 100,
                        "totalPullRequestContributions": 20,
                        "totalIssueContributions": 10,
                    }
                }
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.infra.github.client._client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            result = await get_user_stats("testuser", "token")

        assert result.total_commits == 100
        assert result.total_prs == 20
        assert result.total_issues == 10
