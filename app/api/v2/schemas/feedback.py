from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "ProfileTechStack",
    "ProfileExperience",
    "ProfileEducation",
    "ProfileActivity",
    "ProfileCertificate",
    "CandidateProfile",
    "InterviewEndMessage",
    "InterviewEndRequest",
    "InterviewEndFeedbackItem",
    "InterviewEndOverallFeedback",
    "InterviewEndErrorResponse",
    "InterviewEndResponse",
]


class ProfileTechStack(BaseModel):
    """프로필 - 기술 스택"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str


class ProfileExperience(BaseModel):
    """프로필 - 경력"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    company_name: str = Field(alias="companyName")
    position: str
    department: str | None = None
    start_at: str = Field(alias="startAt")
    end_at: str | None = Field(default=None, alias="endAt")
    is_currently_working: bool = Field(default=False, alias="isCurrentlyWorking")
    employment_type: str = Field(alias="employmentType")
    responsibilities: str | None = None


class ProfileEducation(BaseModel):
    """프로필 - 학력"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    education_type: str = Field(alias="educationType")
    institution: str
    major: str | None = None
    status: str
    start_at: str = Field(alias="startAt")
    end_at: str | None = Field(default=None, alias="endAt")


class ProfileActivity(BaseModel):
    """프로필 - 활동"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: str
    organization: str | None = None
    year: int | None = None
    description: str | None = None


class ProfileCertificate(BaseModel):
    """프로필 - 자격증"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    score: str | None = None
    issuer: str | None = None
    issued_at: str | None = Field(default=None, alias="issuedAt")


class CandidateProfile(BaseModel):
    """지원자 프로필 - PII 제외, 피드백에 필요한 정보만 사용"""

    model_config = ConfigDict(populate_by_name=True)

    introduction: str | None = None
    tech_stacks: list[ProfileTechStack] = Field(default_factory=list, alias="techStacks")
    experiences: list[ProfileExperience] = Field(default_factory=list, alias="experiences")
    educations: list[ProfileEducation] = Field(default_factory=list, alias="educations")
    activities: list[ProfileActivity] = Field(default_factory=list, alias="activities")
    certificates: list[ProfileCertificate] = Field(default_factory=list, alias="certificates")


class InterviewEndMessage(BaseModel):
    """면접 종료 요청 - 개별 메시지"""

    model_config = ConfigDict(populate_by_name=True)

    turn_no: int = Field(alias="turnNo", gt=0)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=5000)
    answer_input_type: Literal["text", "stt"] = Field(alias="answerInputType")
    asked_at: str = Field(alias="askedAt")
    answered_at: str = Field(alias="answeredAt")

    @field_validator("answer_input_type", mode="before")
    @classmethod
    def normalize_answer_input_type(cls, v: str) -> str:
        return v.lower() if isinstance(v, str) else v


class InterviewEndRequest(BaseModel):
    """면접 종료 최상위 요청 - 백엔드 팀 형식"""

    model_config = ConfigDict(populate_by_name=True)

    ai_session_id: str = Field(alias="aiSessionId", min_length=1)
    interview_type: Literal["technical", "behavioral"] = Field(alias="interviewType")
    position: str = Field(min_length=1, max_length=100)
    company: str = Field(min_length=1, max_length=100)
    profile: CandidateProfile | None = None
    messages: list[InterviewEndMessage] = Field(min_length=1, max_length=20)

    @field_validator("interview_type", mode="before")
    @classmethod
    def normalize_interview_type(cls, v: str) -> str:
        return v.lower() if isinstance(v, str) else v


class InterviewEndFeedbackItem(BaseModel):
    """개별 피드백 결과"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    turn_no: int = Field(alias="turnNo")
    score: int = Field(ge=1, le=10)
    strengths: list[str]
    improvements: list[str]
    model_answer: str = Field(alias="modelAnswer")


class InterviewEndOverallFeedback(BaseModel):
    """종합 피드백 결과"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    overall_score: int = Field(alias="overallScore", ge=1, le=10)
    summary: str
    key_strengths: list[str] = Field(alias="keyStrengths")
    key_improvements: list[str] = Field(alias="keyImprovements")


class InterviewEndErrorResponse(BaseModel):
    """에러 정보"""

    code: str
    message: str


class InterviewEndResponse(BaseModel):
    """면접 종료 응답 - 개별 + 종합 피드백 통합"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    status: Literal["success", "failed"]
    feedbacks: list[InterviewEndFeedbackItem] | None = None
    overall_feedback: InterviewEndOverallFeedback | None = Field(
        default=None, alias="overallFeedback"
    )
    error: InterviewEndErrorResponse | None = None
