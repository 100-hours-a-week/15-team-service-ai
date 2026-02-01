"""스키마 모델 테스트"""

import pytest

from app.domain.resume.schemas import (
    CommitDetail,
    CommitInfo,
    ProjectInfo,
    ResumeData,
    ResumeRequest,
)


class TestSchemaModels:
    """스키마 모델 생성 테스트"""

    @pytest.mark.parametrize(
        "model_class,kwargs,assertions",
        [
            (
                CommitInfo,
                {"sha": "abc123", "message": "feat: add feature", "author": "user"},
                [("sha", "abc123"), ("message", "feat: add feature"), ("author", "user")],
            ),
            (
                CommitDetail,
                {
                    "sha": "abc123",
                    "message": "feat: add feature",
                    "author": "user",
                    "files": [{"filename": "test.py", "patch": "+print('hello')"}],
                },
                [("sha", "abc123"), ("files", lambda v: len(v) == 1)],
            ),
            (
                ProjectInfo,
                {
                    "name": "my-project",
                    "repo_url": "https://github.com/user/my-project",
                    "description": "프로젝트 설명",
                    "tech_stack": ["Python", "FastAPI"],
                },
                [("name", "my-project"), ("tech_stack", ["Python", "FastAPI"])],
            ),
            (
                ResumeRequest,
                {
                    "repo_urls": ["https://github.com/user/repo"],
                    "position": "backend",
                    "github_token": "token",
                    "callback_url": "https://example.com/callback",
                },
                [("position", "backend"), ("company", None)],
            ),
        ],
        ids=["commit_info", "commit_detail", "project_info", "resume_request"],
    )
    def test_model_creation(self, model_class, kwargs, assertions):
        """모델 생성 및 필드 검증"""
        instance = model_class(**kwargs)

        for attr, expected in assertions:
            value = getattr(instance, attr)
            if callable(expected):
                assert expected(value), f"{attr} assertion failed"
            else:
                assert value == expected, f"{attr} mismatch"

    def test_resume_data_with_projects(self):
        """ResumeData 모델 생성"""
        resume = ResumeData(
            projects=[
                ProjectInfo(
                    name="my-project",
                    repo_url="https://github.com/user/my-project",
                    description="프로젝트 설명",
                    tech_stack=["Python", "FastAPI"],
                )
            ],
        )

        assert len(resume.projects) == 1
        assert resume.projects[0].tech_stack == ["Python", "FastAPI"]
