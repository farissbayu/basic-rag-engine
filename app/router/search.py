from fastapi import APIRouter
from starlette.status import HTTP_200_OK

from app.core.dependencies import get_collection, get_llm_client
from app.core.schema import SearchResponse
from app.tools.rag import search_documents

search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.get("/", status_code=HTTP_200_OK)
def search(q: str) -> SearchResponse:
    """
    Search documents using RAG (Retrieval-Augmented Generation).

    Retrieves relevant chunks and generates an AI answer.
    """
    collection = get_collection()
    client = get_llm_client()

    return search_documents(
        collection=collection,
        client=client,
        query=q,
    )
