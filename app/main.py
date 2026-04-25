from chonkie import SemanticChunker
from datetime import datetime, timezone
from app.core.schema import Document
from app.core.engine import get_db
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    HTTP_413_CONTENT_TOO_LARGE,
)
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from scalar_fastapi import get_scalar_api_reference
import os
from pypdf import PdfReader
from app.utils.chromadb_client import get_pdf_collection

app = FastAPI()

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
def root():
    return {"message": "Hello, World!"}


@app.post("/upload", status_code=HTTP_201_CREATED)
def upload_document(file: UploadFile = File(...), db=Depends(get_db)):
    # Cek apakah file yang diupload adalah PDF
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are allowed.",
        )

    # Cek apakah ukuran file melebihi 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024
    file_content = file.file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=HTTP_413_CONTENT_TOO_LARGE,
            detail="File size exceeds the 10MB limit.",
        )
    file.file.seek(0)

    safe_filename = file.filename or "uploaded_file"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    # Simpan uploaded file ke folder uploads
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Ekstrak text dari file
    extracted_text = ""
    reader = PdfReader(file_path)
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text += text

    # Chunking
    chunker = SemanticChunker(chunk_size=1024, threshold=0.6)
    chunks = []
    for i, chunk in enumerate(chunker.chunk(extracted_text)):
        chunks.append(chunk.text)

    # Embedding dan tambahkan chunks ke ChromaDB
    collection = get_pdf_collection()
    collection.add(
        documents=chunks,
        ids=[f"chunk_{i}" for i in range(len(chunks))],
    )

    # Simpan metadata ke database
    new_document = Document(
        filename=safe_filename,
        size=file.size or 0,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
    )

    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    return {
        "message": "File berhasil disimpan!",
        "filename": safe_filename,
    }


@app.get("/scalar")
def scalar():
    return get_scalar_api_reference(openapi_url=app.openapi_url)
