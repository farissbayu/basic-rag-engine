from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from starlette.status import HTTP_200_OK

from app.core.engine import get_db
from app.tools.documents import list_all_documents, get_document_by_id

document_router = APIRouter(prefix="/documents", tags=["documents"])


@document_router.get("/", status_code=HTTP_200_OK)
def list_documents(db: Session = Depends(get_db)):
    """List all uploaded documents."""
    documents = list_all_documents(db)
    return {"documents": documents}


@document_router.get("/{document_id}", status_code=HTTP_200_OK)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get a specific document by ID."""
    document = get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": document}
