"""콜백 페이로드 스키마 테스트"""

from app.api.v1.schemas.callback import (
    CallbackErrorData,
    CallbackFailurePayload,
    CallbackProjectData,
    CallbackResumeData,
    CallbackSuccessPayload,
)


class TestCallbackProjectData:
    def test_alias_serialization(self):
        project = CallbackProjectData(
            name="test-project",
            repo_url="https://github.com/user/repo",
            description="테스트 프로젝트",
            tech_stack=["Python", "FastAPI"],
        )
        dumped = project.model_dump(by_alias=True)

        assert dumped["repoUrl"] == "https://github.com/user/repo"
        assert dumped["techStack"] == ["Python", "FastAPI"]
        assert "repo_url" not in dumped
        assert "tech_stack" not in dumped


class TestCallbackSuccessPayload:
    def test_success_payload_serialization(self):
        payload = CallbackSuccessPayload(
            job_id="test-job-123",
            resume=CallbackResumeData(
                projects=[
                    CallbackProjectData(
                        name="my-app",
                        repo_url="https://github.com/user/my-app",
                        description="앱 설명",
                        tech_stack=["React", "TypeScript"],
                    )
                ]
            ),
        )
        dumped = payload.model_dump(by_alias=True)

        assert dumped["jobId"] == "test-job-123"
        assert dumped["status"] == "success"
        assert len(dumped["resume"]["projects"]) == 1
        assert dumped["resume"]["projects"][0]["repoUrl"] == "https://github.com/user/my-app"
        assert dumped["resume"]["projects"][0]["techStack"] == ["React", "TypeScript"]


class TestCallbackFailurePayload:
    def test_failure_payload_serialization(self):
        payload = CallbackFailurePayload(
            job_id="test-job-456",
            error=CallbackErrorData(
                code="GENERATION_FAILED",
                message="이력서 생성에 실패했습니다",
            ),
        )
        dumped = payload.model_dump(by_alias=True)

        assert dumped["jobId"] == "test-job-456"
        assert dumped["status"] == "failed"
        assert dumped["error"]["code"] == "GENERATION_FAILED"
        assert dumped["error"]["message"] == "이력서 생성에 실패했습니다"
