# Refactoring Guide: RAG Engine → MCP-Ready + FastAPI

This guide covers the step-by-step process of refactoring the current RAG Engine codebase into a clean, modular architecture that supports both **FastAPI** and **MCP (Model Context Protocol)**.

---

## Table of Contents

1. [Current Architecture](#1-current-architecture)
2. [Target Architecture](#2-target-architecture)
3. [Problems with Current Code](#3-problems-with-current-code)
4. [Refactoring Strategy](#4-refactoring-strategy)
5. [Step-by-Step Implementation](#5-step-by-step-implementation)
6. [Dependency Injection Patterns](#6-dependency-injection-patterns)
7. [MCP Server Setup](#7-mcp-server-setup)
8. [Refactored FastAPI Routes](#8-refactored-fastapi-routes)
9. [Testing Strategy](#9-testing-strategy)
10. [Running the Application](#10-running-the-application)

---

## 1. Current Architecture

```
app/
├── main.py                  # All routes + business logic mixed together
├── core/
│   ├── engine.py            # SQLAlchemy engine + get_db
│   ├── schema.py            # SQLModel & Pydantic models
│   ├── settings.py          # App settings (env vars)
│   └── __init__.py
├── utils/
│   ├── chromadb_client.py   # ChromaDB client + custom embedding
│   ├── openai.py            # OpenAI client
│   └── __init__.py
└── __init__.py
```

### Current `main.py` Responsibilities

The `main.py` file handles **everything**:

| Responsibility | Lines | Should Be In |
|---------------|-------|-------------|
| PDF upload route | 32-92 | `routers/upload.py` |
| PDF validation (type, size) | 33-47 | `tools/pdf_processor.py` |
| PDF text extraction | 57-63 | `tools/pdf_processor.py` |
| Text chunking | 66-69 | `tools/pdf_processor.py` |
| ChromaDB storage | 71-76 | `tools/pdf_processor.py` |
| DB metadata save | 78-87 | `tools/pdf_processor.py` |
| RAG prompt builder | 95-117 | `tools/rag.py` |
| RAG search route | 120-147 | `routers/search.py` + `tools/rag.py` |
| LLM call | 123-141 | `tools/rag.py` |
| Document list route | 150-153 | `routers/documents.py` + `tools/documents.py` |
| Document get route | 156-161 | `routers/documents.py` + `tools/documents.py` |

---

## 2. Target Architecture

```
app/
├── main.py                     # FastAPI app setup + router includes
├── mcp_server.py               # MCP server exposing tools
├── core/
│   ├── engine.py               # SQLAlchemy engine + session factory
│   ├── schema.py               # SQLModel & Pydantic models
│   ├── settings.py              # App settings
│   ├── dependencies.py         # NEW: Dependency injection providers
│   └── __init__.py
├── routers/                    # NEW: FastAPI route definitions
│   ├── __init__.py
│   ├── upload.py               # POST /upload
│   ├── search.py               # GET /search
│   └── documents.py            # GET /documents, GET /documents/{id}
├── tools/                      # NEW: Reusable business logic
│   ├── __init__.py
│   ├── rag.py                  # RAG search + prompt building
│   ├── documents.py            # Document CRUD operations
│   └── pdf_processor.py        # PDF validation, extraction, chunking
└── utils/
    ├── chromadb_client.py      # ChromaDB client + custom embedding
    ├── openai.py               # OpenAI client
    └── __init__.py
```

### Data Flow Comparison

**Before (all in main.py):**
```
HTTP Request → FastAPI Route → Business Logic (inline) → Response
```

**After (separated concerns):**
```
HTTP Request → FastAPI Route → Tool Function → Database/ChromaDB/LLM → Response

MCP Request → MCP Tool → Same Tool Function → Database/ChromaDB/LLM → Response
```

---

## 3. Problems with Current Code

### Problem 1: Business Logic Mixed with HTTP Concerns

```python
# Current: Route handler does everything
@app.post("/upload", status_code=HTTP_201_CREATED)
def upload_document(file: UploadFile = File(...), db=Depends(get_db)):
    if file.content_type != "application/pdf":        # ← Business logic
        raise HTTPException(...)                        # ← HTTP concern
    if len(file_content) > MAX_FILE_SIZE:               # ← Business logic
        raise HTTPException(...)                        # ← HTTP concern
    reader = PdfReader(file_path)                       # ← Business logic
    for page in reader.pages: ...                       # ← Business logic
    collection = get_pdf_collection()                   # ← Business logic
    db.add(new_document)                                # ← Business logic
```

**Why it's a problem:** You can't reuse this logic from MCP, CLI, or tests without HTTP.

### Problem 2: Hard-to-Test Functions

```python
# Current: Can't test without starting FastAPI + real HTTP requests
def test_upload():
    client = TestClient(app)
    response = client.post("/upload", files={"file": ...})  # Slow, coupled
```

### Problem 3: No Reusability

The search, upload, and document operations are locked inside route handlers. MCP, CLI, or any other interface can't reuse them.

---

## 4. Refactoring Strategy

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│              INTERFACE LAYER                      │
│  (FastAPI Routers / MCP Server / CLI / Tests)    │
│                                                   │
│  - Handles input/output formatting                │
│  - Translates domain errors → HTTP/MCP errors     │
│  - Resolves dependencies                          │
└──────────────────┬──────────────────────────────┘
                   │ calls
┌──────────────────▼──────────────────────────────┐
│              TOOL LAYER                           │
│  (tools/rag.py, tools/documents.py, etc.)        │
│                                                   │
│  - Pure business logic                            │
│  - Accepts dependencies as parameters             │
│  - Framework/framework-independent                │
│  - Returns domain objects (not HTTP responses)    │
└──────────────────┬──────────────────────────────┘
                   │ uses
┌──────────────────▼──────────────────────────────┐
│           INFRASTRUCTURE LAYER                    │
│  (utils/, core/engine.py, core/settings.py)       │
│                                                   │
│  - Database connections                           │
│  - LLM clients                                    │
│  - Vector DB clients                              │
│  - Configuration                                   │
└─────────────────────────────────────────────────┘
```

### Design Principles

1. **Tools don't know about FastAPI** — No `Depends`, `HTTPException`, `UploadFile`
2. **Tools don't know about MCP** — No `@mcp.tool()`
3. **Tools accept dependencies as parameters** — Explicit, testable, flexible
4. **Routers are thin** — Only handle HTTP concerns and call tools
5. **MCP tools are thin** — Only handle MCP formatting and call tools
6. **Prefer functions over classes** — Pure functions with explicit parameters, no classes for business logic

### Functional Approach

This codebase uses a **functional programming style** throughout the tool layer:

- **Pure functions** — Each tool function takes all inputs as parameters and returns outputs, no hidden state or side effects buried in methods
- **Explicit dependencies** — All dependencies (DB session, collection, client) are passed as function arguments, not injected via `self` or class constructors
- **No service/repository classes** — Business logic lives in plain functions, not behind class methods that require instantiation
- **Data as tuples/dicts** — Validation results use tuples `(is_valid, error_message)` instead of exception classes with custom attributes
- **Composition over inheritance** — Complex operations like `process_pdf_upload` compose small functions together, rather than extending base classes

**Why functional over OOP?**
- Easier to test: pass mocks directly as arguments, no need to patch `self` or set up class instances
- Easier to reuse: call `search_documents(collection, client, query)` from anywhere, no need to construct a service object first
- Easier to understand: every dependency is visible in the function signature, no hidden `self.db` or `self.client`
- Works naturally with both FastAPI (passes resolved deps to functions) and MCP (creates deps and passes them to same functions)

> **Note:** The only class in this codebase is `CustomEmbeddingFunction` in `utils/chromadb_client.py`, which **must** be a class because ChromaDB's API requires inheriting from `EmbeddingFunction`. This is an infrastructure adapter, not business logic.

---

## 5. Step-by-Step Implementation

### Step 5.1: Create `app/core/dependencies.py`

This module provides **factory functions** that create dependencies. Both FastAPI and MCP use these.

```python
# app/core/dependencies.py
from sqlmodel import Session
from app.core.engine import engine
from app.utils.chromadb_client import get_pdf_collection
from chromadb import Collection
from openai import OpenAI
from app.utils.openai import oa_client


def get_db_session() -> Session:
    """Create a new database session."""
    return Session(engine)


def get_collection() -> Collection:
    """Get the ChromaDB PDF collection."""
    return get_pdf_collection()


def get_llm_client() -> OpenAI:
    """Get the OpenAI-compatible LLM client."""
    return oa_client
```

### Step 5.2: Create `app/tools/pdf_processor.py`

Extract all PDF-related business logic.

```python
# app/tools/pdf_processor.py
import os
from datetime import datetime, timezone

from chonkie import SemanticChunker
from pypdf import PdfReader
from sqlmodel import Session
from chromadb import Collection

from app.core.schema import Document


UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_pdf(content_type: str, file_size: int) -> tuple[bool, str]:
    """
    Validate PDF file type and size.

    Uses a tuple return instead of raising a custom exception class.
    The caller decides how to handle the error (HTTP exception, error message, etc.).

    Args:
        content_type: MIME type of the file
        file_size: Size of the file in bytes

    Returns:
        Tuple of (is_valid, error_message). error_message is empty string if valid.
    """
    if content_type != "application/pdf":
        return (False, "Only PDF files are allowed.")
    if file_size > MAX_FILE_SIZE:
        return (False, "File size exceeds the 10MB limit.")
    return (True, "")


def save_upload(file_content: bytes, filename: str) -> str:
    """
    Save uploaded file content to disk.

    Args:
        file_content: Raw bytes of the file
        filename: Name for the saved file

    Returns:
        Path to the saved file
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_filename = filename or "uploaded_file"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    return file_path


def extract_pdf_text(file_path: str) -> str:
    """
    Extract text content from a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text as a single string
    """
    extracted_text = ""
    reader = PdfReader(file_path)
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text += text
    return extracted_text


def chunk_text(
    text: str,
    chunk_size: int = 1024,
    threshold: float = 0.6,
) -> list[str]:
    """
    Split text into semantic chunks.

    Args:
        text: The text to chunk
        chunk_size: Maximum chunk size in tokens
        threshold: Semantic similarity threshold for chunking

    Returns:
        List of chunk strings
    """
    chunker = SemanticChunker(chunk_size=chunk_size, threshold=threshold)
    return [chunk.text for chunk in chunker.chunk(text)]


def store_chunks(collection: Collection, chunks: list[str]) -> None:
    """
    Store text chunks in ChromaDB.

    Args:
        collection: ChromaDB collection
        chunks: List of text chunks to store
    """
    collection.add(
        documents=chunks,
        ids=[f"chunk_{i}" for i in range(len(chunks))],
    )


def save_document_metadata(
    db: Session,
    filename: str,
    file_size: int,
) -> Document:
    """
    Save document metadata to the database.

    Args:
        db: Database session
        filename: Name of the uploaded file
        file_size: Size of the file in bytes

    Returns:
        The saved Document object
    """
    new_document = Document(
        filename=filename,
        size=file_size,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    return new_document


def process_pdf_upload(
    file_content: bytes,
    filename: str,
    content_type: str,
    file_size: int,
    db: Session,
    collection: Collection,
) -> Document:
    """
    Process a PDF upload end-to-end.

    Orchestrates: validate → save → extract → chunk → embed → store metadata

    Args:
        file_content: Raw bytes of the PDF
        filename: Original filename
        content_type: MIME type (must be 'application/pdf')
        file_size: File size in bytes
        db: Database session
        collection: ChromaDB collection

    Returns:
        The saved Document object

    Raises:
        ValueError: If PDF validation fails
    """
    # Validate — returns tuple instead of throwing custom exception
    is_valid, error_message = validate_pdf(content_type, file_size)
    if not is_valid:
        raise ValueError(error_message)

    # Save file to disk
    file_path = save_upload(file_content, filename)

    # Extract text
    extracted_text = extract_pdf_text(file_path)

    # Chunk text
    chunks = chunk_text(extracted_text)

    # Store chunks in ChromaDB
    store_chunks(collection, chunks)

    # Save metadata to database
    safe_filename = filename or "uploaded_file"
    document = save_document_metadata(db, safe_filename, file_size)

    return document
```

### Step 5.3: Create `app/tools/rag.py`

Extract all RAG-related logic.

```python
# app/tools/rag.py
from openai import OpenAI
from chromadb import Collection

from app.core.schema import SearchResponse


def build_rag_prompt(query: str, context: list[str]) -> str:
    """
    Build a RAG prompt by combining context with the user query.

    Args:
        query: The user's question
        context: List of retrieved document chunks

    Returns:
        Formatted prompt string
    """
    context_str = "\n\n".join(context)

    prompt = f"""Use the following context to answer the question.
If the context doesn't contain enough information, say "I don't have enough information to answer that."

Context:
{context_str}

Question:
{query}

Formatting Instructions:
- Use markdown format with clear structure
- Use ### for main section headings
- Use **bold text** for key terms and important concepts
- Use bullet points with • (bullet character) for lists, not dashes
- Keep each bullet point concise (1-2 lines max)
- Add a blank line between sections for readability
- End with a brief summary paragraph

Answer:"""
    return prompt


def retrieve_context(
    collection: Collection,
    query: str,
    n_results: int = 3,
) -> list[str]:
    """
    Retrieve relevant document chunks from ChromaDB.

    Args:
        collection: ChromaDB collection to search
        query: The search query
        n_results: Number of results to return

    Returns:
        List of document chunk strings
    """
    results = collection.query(query_texts=[query], n_results=n_results)

    docs = results.get("documents", [[]])
    if not docs or len(docs) == 0:
        return []

    return docs[0]


def generate_answer(
    client: OpenAI,
    prompt: str,
    model: str = "minimax/minimax-m2.5",
) -> str:
    """
    Generate an answer using the LLM.

    Args:
        client: OpenAI-compatible client
        prompt: The full prompt to send
        model: Model identifier to use

    Returns:
        Generated answer string
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that answers questions based on the provided context.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


def search_documents(
    collection: Collection,
    client: OpenAI,
    query: str,
    n_results: int = 3,
    model: str = "minimax/minimax-m2.5",
) -> SearchResponse:
    """
    Full RAG search: retrieve context → build prompt → generate answer.

    Args:
        collection: ChromaDB collection to search
        client: OpenAI-compatible LLM client
        query: The search query / question
        n_results: Number of chunks to retrieve
        model: LLM model to use for generation

    Returns:
        SearchResponse with query, answer, and context
    """
    # Retrieve relevant chunks
    context = retrieve_context(collection, query, n_results)

    if not context:
        return SearchResponse(
            query=query,
            answer="No relevant documents found.",
            context=[],
        )

    # Build prompt
    prompt = build_rag_prompt(query, context)

    # Generate answer
    answer = generate_answer(client, prompt, model)

    return SearchResponse(
        query=query,
        answer=answer or "Sorry, I don't know the answer to that question.",
        context=context,
    )
```

### Step 5.4: Create `app/tools/documents.py`

Extract document CRUD operations.

```python
# app/tools/documents.py
from sqlmodel import Session

from app.core.schema import Document


def list_all_documents(db: Session) -> list[Document]:
    """
    List all uploaded documents.

    Args:
        db: Database session

    Returns:
        List of all Document objects
    """
    return db.query(Document).all()


def get_document_by_id(db: Session, document_id: str) -> Document | None:
    """
    Get a specific document by its ID.

    Args:
        db: Database session
        document_id: The document's unique ID

    Returns:
        Document object if found, None otherwise
    """
    return db.query(Document).filter(Document.id == document_id).first()
```

### Step 5.5: Create `app/tools/__init__.py`

```python
# app/tools/__init__.py
```

### Step 5.6: Create `app/routers/upload.py`

```python
# app/routers/upload.py
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlmodel import Session
from starlette.status import HTTP_201_CREATED, HTTP_415_UNSUPPORTED_MEDIA_TYPE, HTTP_413_CONTENT_TOO_LARGE

from app.core.engine import get_db
from app.core.dependencies import get_collection
from app.tools.pdf_processor import process_pdf_upload

router = APIRouter()


@router.post("/upload", status_code=HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload and process a PDF document.

    Validates, extracts text, chunks, embeds, and stores metadata.
    """
    # Read file content
    file_content = file.file.read()
    file.file.seek(0)

    # Get ChromaDB collection
    collection = get_collection()

    try:
        document = process_pdf_upload(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type or "",
            file_size=file.size or 0,
            db=db,
            collection=collection,
        )
    except ValueError as e:
        # Map validation errors to HTTP status codes
        error_msg = str(e)
        if "Only PDF" in error_msg:
            raise HTTPException(
                status_code=HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=error_msg,
            )
        elif "File size" in error_msg:
            raise HTTPException(
                status_code=HTTP_413_CONTENT_TOO_LARGE,
                detail=error_msg,
            )
        raise HTTPException(status_code=400, detail=error_msg)

    return {
        "message": "File berhasil disimpan!",
        "filename": document.filename,
    }
```

### Step 5.7: Create `app/routers/search.py`

```python
# app/routers/search.py
from fastapi import APIRouter
from starlette.status import HTTP_200_OK

from app.core.dependencies import get_collection, get_llm_client
from app.core.schema import SearchResponse
from app.tools.rag import search_documents

router = APIRouter()


@router.get("/search", status_code=HTTP_200_OK)
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
```

### Step 5.8: Create `app/routers/documents.py`

```python
# app/routers/documents.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from starlette.status import HTTP_200_OK

from app.core.engine import get_db
from app.tools.documents import list_all_documents, get_document_by_id

router = APIRouter()


@router.get("/documents", status_code=HTTP_200_OK)
def list_documents(db: Session = Depends(get_db)):
    """List all uploaded documents."""
    documents = list_all_documents(db)
    return {"documents": documents}


@router.get("/documents/{document_id}", status_code=HTTP_200_OK)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get a specific document by ID."""
    document = get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": document}
```

### Step 5.9: Create `app/routers/__init__.py`

```python
# app/routers/__init__.py
```

### Step 5.10: Update `app/main.py`

Replace everything with a thin app setup.

```python
# app/main.py
from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference

from app.routers.upload import router as upload_router
from app.routers.search import router as search_router
from app.routers.documents import router as documents_router

app = FastAPI()

# Register routers
app.include_router(upload_router)
app.include_router(search_router)
app.include_router(documents_router)


@app.get("/")
def root():
    return {"message": "Hello, World!"}


@app.get("/scalar")
def scalar():
    return get_scalar_api_reference(openapi_url=app.openapi_url)
```

### Step 5.11: Create `app/mcp_server.py`

```python
# app/mcp_server.py
from mcp.server.fastmcp import FastMCP
from sqlmodel import Session

from app.core.dependencies import get_db_session, get_collection, get_llm_client
from app.tools.rag import search_documents
from app.tools.documents import list_all_documents, get_document_by_id

mcp = FastMCP("RAG Engine")


@mcp.tool()
def search_documents_tool(query: str, n_results: int = 3) -> str:
    """
    Search documents and get an AI-generated answer using RAG.

    Args:
        query: The search query or question
        n_results: Number of document chunks to retrieve (default: 3)

    Returns:
        Formatted answer with sources
    """
    collection = get_collection()
    client = get_llm_client()

    result = search_documents(
        collection=collection,
        client=client,
        query=query,
        n_results=n_results,
    )

    # Format for MCP output (plain text, not JSON)
    sources_list = "\n".join(
        [f"  [{i + 1}] {ctx[:200]}..." for i, ctx in enumerate(result.context)]
    )

    return f"""Query: {result.query}

Answer:
{result.answer}

Sources:
{sources_list}"""


@mcp.tool()
def list_documents_tool() -> str:
    """
    List all uploaded documents.

    Returns:
        Formatted list of documents
    """
    db = get_db_session()
    try:
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
    finally:
        db.close()


@mcp.tool()
def get_document_tool(document_id: str) -> str:
    """
    Get details of a specific document by ID.

    Args:
        document_id: The unique document identifier

    Returns:
        Document details or not found message
    """
    db = get_db_session()
    try:
        document = get_document_by_id(db, document_id)

        if not document:
            return f"Document with ID '{document_id}' not found."

        return f"""Document Details:
  ID: {document.id}
  Filename: {document.filename}
  Size: {document.size} bytes
  Uploaded: {document.uploaded_at}"""
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
```

---

## 6. Dependency Injection Patterns

### Functional Approach: Explicit Parameters

This codebase uses **explicit parameter injection** — all dependencies are passed as function arguments. No classes, no `self`, no constructor injection.

**Why?**
- Function signatures are self-documenting: `search_documents(collection, client, query)` clearly shows what it needs
- Mocking is trivial: just pass a mock object as the argument
- Same function works from FastAPI, MCP, CLI, or tests without modification

```
┌──────────────────────────────────────────────────────────────────┐
│                        FASTAPI ROUTE                              │
│                                                                   │
│  @router.get("/search")                                          │
│  def search(q: str):                                             │
│      collection = get_collection()  ← factory function             │
│      client = get_llm_client()      ← factory function             │
│      return search_documents(          ← pure function            │
│          collection=collection,                                   │
│          client=client,                                           │
│          query=q,                                                 │
│      )                                                            │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                          MCP TOOL                                 │
│                                                                   │
│  @mcp.tool()                                                     │
│  def search_documents_tool(query: str):                           │
│      collection = get_collection()  ← same factory function       │
│      client = get_llm_client()      ← same factory function       │
│      result = search_documents(      ← same pure function         │
│          collection=collection,                                   │
│          client=client,                                           │
│          query=query,                                             │
│      )                                                            │
│      return format_for_mcp(result)                               │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                        TOOL FUNCTION                              │
│                                                                   │
│  def search_documents(collection, client, query, ...):           │
│      context = retrieve_context(collection, query)               │
│      prompt = build_rag_prompt(query, context)                   │
│      answer = generate_answer(client, prompt)                    │
│      return SearchResponse(...)                                   │
│                                                                   │
│  No class, no self, no hidden state                              │
│  All dependencies visible in signature                            │
│  Returns plain data objects, not HTTP responses                   │
└──────────────────────────────────────────────────────────────────┘
```

### Dependency Factory Functions

Instead of classes or dependency injection containers, we use **simple factory functions**:

```python
# app/core/dependencies.py
# These are just functions that return the needed objects.
# No DI framework, no container, no class hierarchy.

from sqlmodel import Session
from app.core.engine import engine
from app.utils.chromadb_client import get_pdf_collection
from openai import OpenAI
from app.utils.openai import oa_client


def get_db_session() -> Session:
    """Create a new database session. Caller is responsible for closing."""
    return Session(engine)


def get_collection() -> Collection:
    """Get the ChromaDB PDF collection."""
    return get_pdf_collection()


def get_llm_client() -> OpenAI:
    """Get the OpenAI-compatible LLM client."""
    return oa_client
```

### Dependency Resolution Summary

| Dependency | FastAPI Route | MCP Tool | Unit Test |
|-----------|--------------|---------|-----------|
| **Database Session** | `Depends(get_db)` (generator) | `get_db_session()` (function call) | `Session(mock_engine)` (direct) |
| **ChromaDB Collection** | `get_collection()` | `get_collection()` | `MockCollection()` (direct) |
| **LLM Client** | `get_llm_client()` | `get_llm_client()` | `MockOpenAI()` (direct) |

### How Each Layer Resolves Dependencies

**FastAPI routes** — use `Depends()` for DB sessions (lifecycle managed by FastAPI), factory functions for singletons:

```python
@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),     # FastAPI manages session lifecycle
):
    collection = get_collection()       # Singleton, factory function
    client = get_llm_client()          # Singleton, factory function
    document = process_pdf_upload(
        file_content=file_content,
        db=db,                         # Passed explicitly to tool function
        collection=collection,         # Passed explicitly to tool function
        ...
    )
```

**MCP tools** — manually create and close sessions, same factory functions:

```python
@mcp.tool()
def list_documents_tool() -> str:
    db = get_db_session()              # Create session
    try:
        documents = list_all_documents(db)  # Pass to tool function
        # ... format output
    finally:
        db.close()                     # Manual cleanup
```

**Unit tests** — pass mocks directly, no DI framework needed:

```python
def test_search_documents():
    result = search_documents(
        collection=mock_collection,     # Mock passed directly
        client=mock_client,             # Mock passed directly
        query="What is RAG?",
    )
    assert result.answer == "..."
```

---

## 7. MCP Server Setup

### Running the MCP Server

Add to your `Makefile`:

```makefile
dev:
	uv run uvicorn app.main:app --reload

mcp:
	uv run python -m app.mcp_server
```

### MCP Configuration for Claude Desktop

Create `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-engine": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/basic-rag-engine",
        "run",
        "python",
        "-m",
        "app.mcp_server"
      ]
    }
  }
}
```

### Available MCP Tools

| Tool Name | Parameters | Description |
|-----------|-----------|-------------|
| `search_documents_tool` | `query: str`, `n_results: int = 3` | Search documents with RAG |
| `list_documents_tool` | *(none)* | List all uploaded documents |
| `get_document_tool` | `document_id: str` | Get document details by ID |

---

## 8. Refactored FastAPI Routes

### Route Summary

| Method | Path | Router File | Tool Function |
|--------|------|-------------|---------------|
| POST | `/upload` | `routers/upload.py` | `process_pdf_upload` |
| GET | `/search` | `routers/search.py` | `search_documents` |
| GET | `/documents` | `routers/documents.py` | `list_all_documents` |
| GET | `/documents/{id}` | `routers/documents.py` | `get_document_by_id` |

### Error Handling Pattern

Tools use **tuple returns for validation** and **plain ValueError for errors**. Routers translate them to HTTP exceptions.

```python
# Tool layer — returns tuple (is_valid, error_message) for validation
def validate_pdf(content_type: str, file_size: int) -> tuple[bool, str]:
    if content_type != "application/pdf":
        return (False, "Only PDF files are allowed.")
    if file_size > MAX_FILE_SIZE:
        return (False, "File size exceeds the 10MB limit.")
    return (True, "")

# Tool layer — raises ValueError with human-readable message
def process_pdf_upload(...):
    is_valid, error_message = validate_pdf(content_type, file_size)
    if not is_valid:
        raise ValueError(error_message)
    ...

# Router layer — catches ValueError and maps to HTTP status codes
@router.post("/upload")
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        document = process_pdf_upload(...)
    except ValueError as e:
        error_msg = str(e)
        if "Only PDF" in error_msg:
            raise HTTPException(status_code=415, detail=error_msg)
        elif "File size" in error_msg:
            raise HTTPException(status_code=413, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
```

**Why tuples + ValueError instead of custom exception classes?**

- **Tuples** make validation results explicit and pattern-matchable: `is_valid, msg = validate_pdf(...)`
- **ValueError** is a built-in Python exception — no need to define and maintain a custom class hierarchy
- **No error_code attribute** — the error message itself is descriptive enough for the router to map to HTTP codes
- **Composable** — `process_pdf_upload` calls `validate_pdf` and decides how to handle the result (raise ValueError), keeping function signatures clean

---

## 9. Testing Strategy

### Testing Tool Functions (Framework-Independent)

Since tool functions accept dependencies as parameters, they're easy to test:

```python
# tests/test_rag.py
from unittest.mock import MagicMock


def test_build_rag_prompt():
    prompt = build_rag_prompt(
        query="What is RAG?",
        context=["RAG stands for Retrieval-Augmented Generation."]
    )
    assert "What is RAG?" in prompt
    assert "Retrieval-Augmented Generation" in prompt


def test_search_documents_empty_context():
    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [[]]}

    mock_client = MagicMock()

    result = search_documents(
        collection=mock_collection,
        client=mock_client,
        query="What is RAG?",
    )

    assert result.answer == "No relevant documents found."
    assert result.context == []
    # LLM should NOT be called when there's no context
    mock_client.chat.completions.create.assert_not_called()


def test_search_documents_with_results():
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["RAG stands for Retrieval-Augmented Generation."]]
    }

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "RAG is..."
    mock_client.chat.completions.create.return_value = mock_response

    result = search_documents(
        collection=mock_collection,
        client=mock_client,
        query="What is RAG?",
    )

    assert result.query == "What is RAG?"
    assert result.answer == "RAG is..."
    assert len(result.context) == 1


def test_validate_pdf_invalid_type():
    """validate_pdf returns (False, error_message) for invalid content type."""
    is_valid, error_message = validate_pdf(content_type="text/plain", file_size=100)
    assert is_valid is False
    assert "Only PDF" in error_message


def test_validate_pdf_too_large():
    """validate_pdf returns (False, error_message) for oversized files."""
    is_valid, error_message = validate_pdf(
        content_type="application/pdf", file_size=20 * 1024 * 1024
    )
    assert is_valid is False
    assert "File size" in error_message


def test_validate_pdf_success():
    """validate_pdf returns (True, '') for valid PDFs."""
    is_valid, error_message = validate_pdf(
        content_type="application/pdf", file_size=100
    )
    assert is_valid is True
    assert error_message == ""


def test_process_pdf_upload_invalid_type():
    """process_pdf_upload raises ValueError for invalid content type."""
    with pytest.raises(ValueError, match="Only PDF"):
        process_pdf_upload(
            file_content=b"...",
            filename="test.txt",
            content_type="text/plain",
            file_size=100,
            db=mock_db,
            collection=mock_collection,
        )


def test_extract_pdf_text():
    # This would need a real PDF file or mock PdfReader
    # Example with mock:
    pass


def test_chunk_text():
    chunks = chunk_text("This is a test sentence about AI.", chunk_size=512)
    assert len(chunks) > 0
    assert all(isinstance(c, str) for c in chunks)
```

> **Functional testing advantage:** Notice how `validate_pdf` is tested by checking the tuple return directly — `is_valid, error_message = validate_pdf(...)`. No need to catch custom exception classes or inspect `.error_code` attributes. The result is a plain tuple that's simple to assert on.

### Testing FastAPI Routes

```python
# tests/test_routes.py
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)


def test_search_endpoint():
    with patch("app.routers.search.get_collection") as mock_coll, \
         patch("app.routers.search.get_llm_client") as mock_llm:

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Test context about RAG."]]
        }
        mock_coll.return_value = mock_collection

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "RAG is..."
        mock_llm.return_value.chat.completions.create.return_value = mock_response

        response = client.get("/search?q=What+is+RAG")

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is RAG"
        assert data["answer"] == "RAG is..."
        assert len(data["context"]) == 1
```

---

## 10. Running the Application

### Start FastAPI Server

```bash
make dev
# or
uv run uvicorn app.main:app --reload
```

### Start MCP Server

```bash
make mcp
# or
uv run python -m app.mcp_server
```

### API Documentation

- **Scalar UI**: http://localhost:8000/scalar
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Complete File Change Summary

| Action | File | Description |
|--------|------|-------------|
| **Create** | `app/core/dependencies.py` | Dependency factory functions |
| **Create** | `app/tools/__init__.py` | Package init |
| **Create** | `app/tools/rag.py` | RAG search + prompt building |
| **Create** | `app/tools/documents.py` | Document CRUD operations |
| **Create** | `app/tools/pdf_processor.py` | PDF processing pipeline |
| **Create** | `app/routers/__init__.py` | Package init |
| **Create** | `app/routers/upload.py` | Upload route |
| **Create** | `app/routers/search.py` | Search route |
| **Create** | `app/routers/documents.py` | Document routes |
| **Create** | `app/mcp_server.py` | MCP server with tools |
| **Modify** | `app/main.py` | Thin app setup + router includes |
| **Keep** | `app/core/engine.py` | No changes needed |
| **Keep** | `app/core/schema.py` | No changes needed |
| **Keep** | `app/core/settings.py` | No changes needed |
| **Keep** | `app/utils/chromadb_client.py` | No changes needed |
| **Keep** | `app/utils/openai.py` | No changes needed |
| **Modify** | `Makefile` | Add `mcp` target |

---

## Migration Checklist

Before you start refactoring, make sure you:

- [ ] Create all `tools/` files first (new files, no breakage)
- [ ] Create all `routers/` files next (new files, no breakage)
- [ ] Create `dependencies.py` (new file, no breakage)
- [ ] Update `main.py` to use routers (this changes existing behavior)
- [ ] Create `mcp_server.py` (new file, no breakage)
- [ ] Test all endpoints via `/scalar`
- [ ] Test MCP server via `make mcp`
- [ ] Add `mcp` target to `Makefile`
- [ ] Remove old business logic from `main.py` (cleanup)