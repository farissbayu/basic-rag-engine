from starlette.status import HTTP_201_CREATED, HTTP_415_UNSUPPORTED_MEDIA_TYPE
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException
from scalar_fastapi import get_scalar_api_reference
import os

app = FastAPI()

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
def root():
    return {"message": "Hello, World!"}


@app.post("/upload", status_code=HTTP_201_CREATED)
def upload_document(file: UploadFile = File(...)):
    # Cek apakah file yang diupload adalah PDF
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are allowed.",
        )

    safe_filename = file.filename or "uploaded_file"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "message": "File berhasil disimpan!",
        "filename": safe_filename,
        "saved_location": file_path,
        "file_info": file,
    }


@app.get("/scalar")
def scalar():
    return get_scalar_api_reference(openapi_url=app.openapi_url)
