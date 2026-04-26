from app.core.settings import settings
import os
from datetime import datetime, timezone

from chonkie import SemanticChunker
from pypdf import PdfReader
from sqlmodel import Session
from chromadb import Collection

from app.core.schema import Document


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_pdf(content_type: str, file_size: int) -> tuple[bool, str]:
    if content_type != "application/pdf":
        return (False, "Only PDF files are allowed.")
    if file_size > MAX_FILE_SIZE:
        return (False, "File size exceeds the 10MB limit.")
    return (True, "")


def save_pdf(file_content: bytes, filename: str) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_filename = filename or "uploaded_file"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    return file_path


def extract_pdf_text(file_path: str) -> str:
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
    chunker = SemanticChunker(chunk_size=chunk_size, threshold=threshold)
    return [chunk.text for chunk in chunker.chunk(text)]


def store_chunks(collection: Collection, chunks: list[str]) -> None:
    collection.add(
        documents=chunks,
        ids=[f"chunk_{i}" for i in range(len(chunks))],
    )


def save_document_metadata(
    db: Session,
    filename: str,
    file_size: int,
) -> Document:
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
    # Validasi
    is_valid, error_message = validate_pdf(content_type, file_size)
    if not is_valid:
        raise ValueError(error_message)

    # Save file pdf
    file_path = save_pdf(file_content, filename)

    # Ekstrak text
    extracted_text = extract_pdf_text(file_path)

    # Chunking
    chunks = chunk_text(extracted_text)

    # Simpan chunks ke chromadb
    store_chunks(collection, chunks)

    # Simpan metadata ke database
    safe_filename = filename or "uploaded_file"
    document = save_document_metadata(db, safe_filename, file_size)

    return document
