from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlmodel import Session
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    HTTP_413_CONTENT_TOO_LARGE,
)

from app.core.engine import get_db
from app.core.dependencies import get_collection
from app.tools.pdf_processor import process_pdf_upload

upload_router = APIRouter(prefix="/upload", tags=["upload"])


@upload_router.post("/", status_code=HTTP_201_CREATED)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_content = file.file.read()
    file.file.seek(0)

    collection = get_collection()

    try:
        document = process_pdf_upload(
            file_content=file_content,
            filename=file.filename or "uploaded_file",
            content_type=file.content_type or "",
            file_size=file.size or 0,
            db=db,
            collection=collection,
        )
    except ValueError as e:
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
