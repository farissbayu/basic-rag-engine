# Basic RAG Engine

A Retrieval-Augmented Generation (RAG) engine that lets you upload PDF documents, store their content in a vector database, and query them using an LLM-powered search.

## Tech Stack

- **FastAPI** - REST API framework
- **ChromaDB** - Vector database for storing and querying document embeddings
- **OpenAI API (via OpenRouter)** - LLM completions and embeddings
- **SQLModel / SQLite** - Document metadata storage
- **pypdf** - PDF text extraction
- **Chonkie** - Semantic text chunking
- **MCP** - Model Context Protocol server for tool integration
- **Alembic** - Database migrations
- **Scalar** - API documentation UI

## Prerequisites

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

1. Clone the repository and install dependencies:

```bash
uv sync
```

2. Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://openrouter.ai/api/v1
DATABASE_URL=sqlite:///database.db
UPLOAD_DIR=uploads
```

3. Run database migrations:

```bash
uv run alembic upgrade head
```

## Running the Server

```bash
make dev
```

Or directly:

```bash
uv run uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`. API docs are available at `/scalar`.

## API Endpoints

### Upload

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload/` | Upload a PDF file (max 10MB) |

### Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search/?q=<query>` | Search documents using RAG |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/documents/` | List all uploaded documents |
| GET | `/documents/{document_id}` | Get a specific document by ID |

## MCP Server

The project includes an MCP server that exposes RAG tools for AI assistants:

```bash
uv run python -m app.mcp_server
```

Available tools:

- **search_documents_tool** - Search documents with a query
- **list_documents_tool** - List all uploaded documents
- **get_document_tool** - Get a document by ID

## Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── mcp_server.py        # MCP server with tool definitions
├── core/
│   ├── settings.py      # Configuration via environment variables
│   ├── schema.py        # SQLModel/Pydantic models
│   ├── engine.py        # Database engine setup
│   └── dependencies.py  # Dependency injection helpers
├── router/
│   ├── uploads.py       # PDF upload endpoint
│   ├── search.py        # RAG search endpoint
│   └── documents.py     # Document listing endpoints
├── tools/
│   ├── pdf_processor.py # PDF validation, extraction, chunking, storage
│   ├── rag.py           # RAG pipeline (retrieve → prompt → generate)
│   └── documents.py     # Document CRUD operations
└── utils/
    ├── openai.py        # OpenAI client configuration
    └── chromadb_client.py # ChromaDB client with custom embedding function
```

## How It Works

1. **Upload** - PDF is validated, saved to disk, text is extracted and semantically chunked, then chunks are embedded and stored in ChromaDB.
2. **Search** - Query is embedded, relevant chunks are retrieved from ChromaDB, a prompt is built with context, and an LLM generates an answer.
3. **Documents** - Metadata (filename, size, upload time) is stored in SQLite via SQLModel.
