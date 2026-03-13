import concurrent.futures
from pathlib import Path

from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.prompts.positions import normalize_position

logger = get_logger(__name__)

EMBEDDING_MODEL = "gemini-embedding-2-preview"
VECTOR_DIM = 3072

POSITION_CATEGORIES: dict[str, list[str]] = {
    "backend": ["backend", "database", "cs", "security"],
    "frontend": ["frontend", "cs"],
    "fullstack": ["frontend", "backend", "database", "cs", "security"],
    "mobile": ["mobile", "frontend", "cs"],
    "devops": ["devops", "cs", "security"],
    "ai": ["ai_ml", "backend", "database", "cs"],
    "data": ["database", "cs", "ai_ml"],
    "security": ["security", "cs", "backend"],
}

POSITION_TECH_EXCLUDE: dict[str, list[str]] = {
    "frontend": [
        "Jetpack Compose", "React Native", "Android", "Flutter",
        "Kotlin", "Swift", "SwiftUI", "Firebase Cloud Messaging",
        "Mobile Security", "Mobile Testing",
        "LangGraph", "LangChain", "LangChain Summarization",
    ],
    "backend": [
        "Jetpack Compose", "React Native", "Android", "Flutter",
        "Kotlin", "Swift", "SwiftUI",
        "Mobile Security", "Mobile Testing",
    ],
    "mobile": [
        "LangGraph", "LangChain", "LangChain Summarization",
    ],
}

_qdrant_client: QdrantClient | None = None
_genai_client: genai.Client | None = None


def _get_qdrant_client() -> QdrantClient:
    """Qdrant 클라이언트 지연 초기화 싱글턴"""
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client

    if settings.qdrant_url:
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        logger.info("Qdrant 서버 모드 연결", url=settings.qdrant_url)
    else:
        data_path = str(
            Path(__file__).parent.parent.parent.parent / "vector-db-scripts" / "qdrant_data"
        )
        _qdrant_client = QdrantClient(path=data_path)
        logger.info("Qdrant 임베디드 모드 연결", path=data_path)

    return _qdrant_client


def _get_genai_client() -> genai.Client:
    """Google GenAI 클라이언트 지연 초기화 싱글턴"""
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("Google GenAI 클라이언트 초기화 완료", model=EMBEDDING_MODEL)
    return _genai_client


def search_knowledge(
    query: str,
    top_k: int | None = None,
    position: str | None = None,
    score_threshold: float | None = None,
) -> list[dict]:
    """Qdrant Dense Search — Gemini 임베딩 기반 코사인 유사도 검색

    Args:
        query: 검색 쿼리 - 질문 + 질문 의도 조합
        top_k: 반환할 최대 결과 수
        position: 포지션명 - 해당 카테고리만 필터링
        score_threshold: 최소 유사도 점수 - 호환성 유지용
    """
    try:
        qdrant = _get_qdrant_client()
        genai_client = _get_genai_client()
        k = top_k or settings.qdrant_top_k

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                genai_client.models.embed_content,
                model=EMBEDDING_MODEL,
                contents=query,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=VECTOR_DIM,
                ),
            )
            try:
                result = future.result(timeout=30)
            except concurrent.futures.TimeoutError as e:
                raise TimeoutError("Google GenAI 임베딩 호출 타임아웃 — 30초 초과") from e
        query_vector = result.embeddings[0].values

        query_filter = None
        if position:
            pos_lower = normalize_position(position)
            categories = POSITION_CATEGORIES.get(pos_lower)
            must_conditions = []
            must_not_conditions = []
            if categories:
                must_conditions.append(
                    FieldCondition(key="category", match=MatchAny(any=categories))
                )
            exclude_techs = POSITION_TECH_EXCLUDE.get(pos_lower)
            if exclude_techs:
                must_not_conditions.append(
                    FieldCondition(key="tech", match=MatchAny(any=exclude_techs))
                )
            if must_conditions or must_not_conditions:
                query_filter = Filter(
                    must=must_conditions or None,
                    must_not=must_not_conditions or None,
                )

        response = qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            using="dense",
            query_filter=query_filter,
            limit=k,
        )

        chunks = []
        for hit in response.points:
            chunks.append(
                {
                    "document": hit.payload.get("document", ""),
                    "score": hit.score,
                    "tech": hit.payload.get("tech", ""),
                    "topic": hit.payload.get("topic", ""),
                }
            )

        logger.debug(
            "Qdrant Dense 검색 완료",
            query_length=len(query),
            results_count=len(chunks),
            position_filter=position,
        )
        return chunks

    except Exception as e:
        logger.warning("Qdrant 검색 실패 - 검색 없이 진행", error=str(e))
        return []


def close_client() -> None:
    """Qdrant 클라이언트 종료 - lifespan에서 호출"""
    global _qdrant_client, _genai_client
    if _qdrant_client is not None:
        _qdrant_client.close()
        _qdrant_client = None
    _genai_client = None
