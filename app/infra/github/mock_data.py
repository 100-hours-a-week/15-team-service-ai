from app.domain.resume.schemas import RepoContext, UserStats

MOCK_DELAY = 2.0

MOCK_USER_STATS = UserStats(total_commits=120, total_prs=18, total_issues=7)


def make_mock_project_info(repo_url: str, repo_name: str) -> dict:
    """요청 URL 기반으로 모의 프로젝트 정보 생성"""
    return {
        "repo_name": repo_name,
        "repo_url": repo_url,
        "file_tree": ["app/", "tests/", "pyproject.toml", "README.md"],
        "dependencies": ["fastapi", "langgraph", "langchain", "httpx", "postgresql", "redis"],
        "messages": [
            "PR #3: feat: GitHub 레포지토리 분석 워크플로우 구현 [커밋 7개, +580/-40] | LangGraph를 활용한 비동기 파이프라인 설계, GraphQL 기반 데이터 수집, LLM 이력서 생성 자동화",
            "PR #2: feat: 이력서 생성 API 및 콜백 구조 설계 [커밋 5개, +320/-20] | FastAPI 비동기 엔드포인트 구현, 백그라운드 태스크 처리, Spring 서버 콜백 전송 로직 추가",
            "PR #1: feat: 사용자 인증 기능 추가 [커밋 4개, +230/-15] | JWT 기반 인증 시스템 구현, 로그인/로그아웃 API 및 토큰 갱신 로직 포함",
            "commit: feat: 초기 프로젝트 설정 및 FastAPI 라우터 구성",
            "commit: refactor: 서비스 레이어 분리 및 의존성 주입 개선",
            "commit: fix: 인증 미들웨어 응답 오류 수정",
            "commit: chore: GitHub Actions CI 파이프라인 구성",
        ],
    }


def make_mock_repo_context(repo_name: str) -> RepoContext:
    """레포 이름 기반으로 모의 컨텍스트 생성"""
    return RepoContext(
        name=repo_name,
        languages={"Python": 85000, "Dockerfile": 2000},
        description="GitHub 레포지토리 데이터를 LLM으로 분석해 이력서를 자동 생성하고 모의 면접을 제공하는 FastAPI 백엔드 서비스",
        topics=["fastapi", "langgraph", "langchain", "python", "llm", "resume"],
        readme_summary=(
            "LangGraph 워크플로우로 GitHub 커밋, PR, 파일 구조를 분석해 이력서를 자동 생성합니다. "
            "GraphQL 기반 GitHub 데이터 수집, LLM 이력서 생성, 모의 면접 질문 생성 기능을 제공합니다"
        ),
    )
