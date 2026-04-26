from sqlmodel import Session, select

from app.core.schema import Document


def list_all_documents(db: Session) -> list[Document]:
    return list(db.exec(select(Document)).all())


def get_document_by_id(db: Session, document_id: str) -> Document | None:
    return db.exec(select(Document).where(Document.id == document_id)).first()
