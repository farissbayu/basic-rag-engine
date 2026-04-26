from app.router.documents import document_router
from app.router.search import search_router
from app.router.uploads import upload_router
from app.core.settings import settings
from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference
import os


app = FastAPI()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app.include_router(upload_router)
app.include_router(search_router)
app.include_router(document_router)


@app.get("/")
def root():
    return {"message": "Hello, World!"}


@app.get("/scalar")
def scalar():
    return get_scalar_api_reference(openapi_url=app.openapi_url)
