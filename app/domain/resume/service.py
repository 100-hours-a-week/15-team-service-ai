from app.domain.resume.schemas import ResumeData, ResumeRequest
from app.infra.github.client import get_commit_detail, get_commits, parse_repo_url
from app.infra.llm.client import analyze_diff, generate_resume


async def create_resume(request: ResumeRequest) -> ResumeData:
    """이력서 생성 서비스.

    Args:
        request: 이력서 생성 요청 (repo_urls, position, github_token 등)

    Returns:
        생성된 이력서 데이터
    """
    all_experiences = []

    for repo_url in request.repo_urls:
        _, repo_name = parse_repo_url(repo_url)

        # 1. 커밋 목록 조회
        commits = await get_commits(repo_url, request.github_token)

        # 2. 각 커밋의 diff 수집 및 분석
        for commit in commits:
            commit_detail = await get_commit_detail(
                repo_url, commit.sha, request.github_token
            )

            # diff 내용 추출
            diff_content = "\n".join(
                f"파일: {f.get('filename', '')}\n{f.get('patch', '')}"
                for f in commit_detail.files
                if f.get("patch")
            )

            if diff_content:
                # 3. LLM으로 diff 분석
                experience = await analyze_diff(diff_content, repo_name)
                all_experiences.append(experience)

    # 4. 추출된 경험으로 이력서 생성
    resume = await generate_resume(
        experiences=all_experiences,
        position=request.position,
        repo_urls=request.repo_urls,
    )

    return resume
