import chromadb
import numpy as np
from app.utils.openai import oa_client
from chromadb import EmbeddingFunction, Embeddings

chromadb_client = chromadb.PersistentClient(path="chroma_db")


class CustomEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model: str = "perplexity/pplx-embed-v1-4b"):
        self.client = oa_client
        self.model = model

    def __call__(self, input: list[str]) -> Embeddings:
        response = self.client.embeddings.create(
            model=self.model,
            input=input,
        )

        # Return embeddings in the same order as input
        return [np.array(item.embedding, dtype=np.float32) for item in response.data]


def get_pdf_collection():
    return chromadb_client.get_or_create_collection(
        name="pdf_rag", embedding_function=CustomEmbeddingFunction()
    )
