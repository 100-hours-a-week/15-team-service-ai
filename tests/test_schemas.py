from app.domain.resume.schemas import (
    CommitDetail,
    CommitInfo,
    ProjectInfo,
    ResumeData,
    ResumeRequest,
)


def test_commit_info():
    """CommitInfo 모델 생성."""
    commit = CommitInfo(sha="abc123", message="feat: add feature", author="user")
    assert commit.sha == "abc123"
    assert commit.message == "feat: add feature"
    assert commit.author == "user"


def test_commit_detail():
    """CommitDetail 모델 생성."""
    commit = CommitDetail(
        sha="abc123",
        message="feat: add feature",
        author="user",
        files=[{"filename": "test.py", "patch": "+print('hello')"}],
    )
    assert commit.sha == "abc123"
    assert len(commit.files) == 1


def test_project_info():
    """ProjectInfo 모델 생성."""
    project = ProjectInfo(
        name="my-project",
        repo_url="https://github.com/user/my-project",
        description="프로젝트 설명",
    )
    assert project.name == "my-project"


def test_resume_data():
    """ResumeData 모델 생성."""
    resume = ResumeData(
        tech_stack=["Python", "FastAPI"],
        projects=[
            ProjectInfo(
                name="my-project",
                repo_url="https://github.com/user/my-project",
                description="프로젝트 설명",
            )
        ],
    )
    assert len(resume.tech_stack) == 2
    assert len(resume.projects) == 1


def test_resume_request():
    """ResumeRequest 모델 생성."""
    request = ResumeRequest(
        repo_urls=["https://github.com/user/repo"],
        position="backend",
        github_token="token",
        callback_url="https://example.com/callback",
    )
    assert request.position == "backend"
    assert request.company is None
