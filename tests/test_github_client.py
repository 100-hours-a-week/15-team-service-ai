from app.infra.github.client import parse_repo_url


def test_parse_repo_url():
    """기본 GitHub URL 파싱."""
    owner, repo = parse_repo_url("https://github.com/user/my-repo")
    assert owner == "user"
    assert repo == "my-repo"


def test_parse_repo_url_with_git_suffix():
    """.git 접미사가 있는 URL 파싱."""
    owner, repo = parse_repo_url("https://github.com/user/my-repo.git")
    assert owner == "user"
    assert repo == "my-repo"


def test_parse_repo_url_with_trailing_slash():
    """끝에 슬래시가 있는 URL 파싱."""
    owner, repo = parse_repo_url("https://github.com/user/my-repo/")
    assert owner == "user"
    assert repo == "my-repo"
