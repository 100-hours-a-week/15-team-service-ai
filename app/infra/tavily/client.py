from tavily import AsyncTavilyClient

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TALENT_SEARCH_EXCLUDE_DOMAINS = [
    # 개인 블로그
    "tistory.com",
    "velog.io",
    "brunch.co.kr",
    "blog.naver.com",
    "medium.com",
    "notion.site",
    # 커뮤니티/비공식
    "namu.wiki",
    "namuwiki.mirror",
    "reddit.com",
    "quora.com",
    # 학습/강의 사이트
    "inflearn.com",
    "udemy.com",
    "youtube.com",
]

_client: AsyncTavilyClient | None = None


def _get_client() -> AsyncTavilyClient | None:
    global _client
    if _client is not None:
        return _client
    if not settings.tavily_api_key:
        return None
    _client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    return _client


async def search_company_talent(company: str) -> str:
    """기업 인재상을 Tavily로 검색하여 요약 텍스트 반환

    검색 실패 시 빈 문자열 반환 - 피드백 생성에 영향을 주지 않음
    """
    if not company or not company.strip():
        return ""

    client = _get_client()
    if client is None:
        logger.warning("Tavily API 키 미설정 - 기업 인재상 검색 스킵")
        return ""

    query = f"{company} 인재상 핵심가치 채용 기준 원하는 인재"
    try:
        response = await client.search(
            query=query,
            max_results=5,
            search_depth="advanced",
            include_answer="advanced",
            time_range="year",
            exclude_domains=TALENT_SEARCH_EXCLUDE_DOMAINS,
        )

        answer = response.get("answer", "")
        if answer:
            logger.info("기업 인재상 검색 완료", company=company, answer_length=len(answer))
            return answer

        results = response.get("results", [])
        if not results:
            logger.info("기업 인재상 검색 결과 없음", company=company)
            return ""

        snippets = []
        for r in results[:3]:
            content = r.get("content", "")
            if content:
                snippets.append(content[:500])

        combined = "\n".join(snippets)
        logger.info("기업 인재상 검색 완료", company=company, snippets_count=len(snippets))
        return combined

    except Exception as e:
        logger.warning("기업 인재상 검색 실패 - 스킵", company=company, error=str(e))
        return ""
