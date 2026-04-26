from app.tools.documents import list_all_documents, get_document_by_id
from app.tools.rag import search_documents
from app.core.dependencies import get_collection, get_llm_client, get_db_session
from mcp.server import FastMCP

mcp = FastMCP("Basic Rag Engine")


@mcp.tool()
def search_documents_tool(query: str, n_results: int = 3) -> str:
    collection = get_collection()
    client = get_llm_client()

    result = search_documents(
        collection=collection, client=client, query=query, n_results=n_results
    )

    sources_list = "\n".join(
        [f"  [{i + 1}] {ctx[:200]}..." for i, ctx in enumerate(result.context)]
    )

    return f"""
      Query: 
      {result.query}

      Answer:
      {result.answer}

      Sources:
      {sources_list}
"""


@mcp.tool()
def list_documents_tool() -> str:
    db = get_db_session()
    documents = list_all_documents(db)

    if not documents:
        return "No documents found."

    lines = ["Uploaded Documents:"]
    for doc in documents:
        lines.append(f"  - ID: {doc.id}")
        lines.append(f"    Filename: {doc.filename}")
        lines.append(f"    Size: {doc.size} bytes")
        lines.append(f"    Uploaded: {doc.uploaded_at}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def get_document_tool(document_id: str) -> str:
    db = get_db_session()

    document = get_document_by_id(db, document_id)

    if not document:
        return f"Document with ID '{document_id}' not found."

    return f"""Document Details:
          ID: {document.id}
          Filename: {document.filename}
          Size: {document.size} bytes
          Uploaded: {document.uploaded_at}"""


if __name__ == "__main__":
    mcp.run()
